# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""PowerProtect Data Manager REST client (HTTP only via ansible open_url).

Bounds: PAGE_SIZE is the pageSize requested and the most items accepted in one page; MAX_BODY_BYTES
(32 MiB) is the most bytes read from any response body (success or error); MAX_ITEMS is the most items
collected across all the pages of one listing. Beyond any of them, PpdmError.
"""

from __future__ import annotations

import heapq
import ipaddress
import json
import re
import time
from http.client import HTTPException
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode

from ansible.module_utils.basic import AnsibleModule, env_fallback
from ansible.module_utils.urls import open_url
from ansible_collections.fjacquet.ppdm.plugins.module_utils._routes import ROUTES

PAGE_SIZE = 100
# Total items one get_all/list_all may collect (PAGE_SIZE * MAX_PAGES = 1_000_000 is the API ceiling, kept
# explicit so a server that keeps returning full pages cannot grow the module memory without bound).
MAX_ITEMS = 1_000_000
MAX_BODY_BYTES = 32 * 1024 * 1024
MAX_ERROR_TEXT = 64 * 1024  # an error body kept in PpdmError.body is cut to this AFTER it is scrubbed
MAX_SCRUB_TEXT = 1024 * 1024  # a server text longer than this is never scrubbed nor kept (marker with its length)
MAX_PAGES = 10000  # the OpenAPI maximum of the `page` query parameter
REDIRECT_CODES = frozenset([301, 302, 303, 307, 308])
MASK = "VALUE_SPECIFIED_IN_NO_LOG_PARAMETER"
# OpenAPI 20.3.0 Activity.state: QUEUED/RUNNING/PENDING_CANCELLATION|CANCELING/RETRYING/COMPLETED.
# COMPLETED is the only terminal state; success/failure is in result.status (OK, FAILED, CANCELED, ...).
ACTIVITY_TERMINAL_STATES = frozenset(["COMPLETED"])


# Write-only fields PPDM does not return in clear: a GET value is never sent back in a PUT unless the caller set it.
WRITE_ONLY_KEYS = frozenset(
    {"password", "secretKey", "userKey", "credentialPassword", "applicationUserPassword", "token", "privateKey"}
)


def strip_readonly(resource: str, obj: dict) -> dict:
    """Copy of obj without the readOnly properties of the resource (from ROUTES) and without _links."""
    drop = set(ROUTES[resource]["readonly"]) | {"_links"}
    return {k: v for k, v in obj.items() if k not in drop}


def filter_eq(key: str, value: Any) -> str:
    """PPDM filter expression `key eq "value"` (backslash and double quote escaped)."""
    # shortcut: the OpenAPI does not document filter escaping; backslash-escaping \ and " is best effort.
    return '%s eq "%s"' % (key, str(value).replace("\\", "\\\\").replace('"', '\\"'))


def merge_config(named: dict, config: dict | None) -> dict:
    """Body from the named options (None values dropped) over config; no named option's key, no id/_links."""
    config = config or {}
    forbidden = sorted(set(config) & {"id", "_links"})  # the body id must stay the path id
    if forbidden:
        raise PpdmError("config must not set %s: the server owns it" % ", ".join(forbidden))
    clash = sorted(set(config) & set(named))
    if clash:
        raise PpdmError("config must not set %s: use the matching module option instead" % ", ".join(clash))
    return dict(config, **{k: v for k, v in named.items() if v is not None})


def quote_id(value: Any) -> str:
    """Percent-encode an id for one path segment; a bare "." or ".." is encoded too (quote leaves it as is)."""
    text = str(value)
    if text == "":
        raise PpdmError("id must not be empty")
    quoted = quote(text, safe="")
    return quoted.replace(".", "%2E") if quoted in (".", "..") else quoted


DNS_NAME = re.compile(r"[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*\.?")


def _host_netloc(hostname: Any) -> str:
    """Allowlist: a DNS name or an IPv4/IPv6 literal -> URL host part (IPv6 bracketed); PpdmError otherwise."""
    host = hostname if isinstance(hostname, str) else ""
    if 0 < len(host) <= 253 and DNS_NAME.fullmatch(host):
        return host
    inner = host[1:-1] if host.startswith("[") and host.endswith("]") and ":" in host else host
    if inner and "%" not in inner:
        try:
            return "[%s]" % ipaddress.IPv6Address(inner) if ":" in inner else str(ipaddress.IPv4Address(inner))
        except ValueError:
            pass
    raise PpdmError(
        "hostname must be a DNS name or an IP address, without scheme, user, port, path or spaces "
        "(use the port option for the port)"
    )


def _mask(obj, secret_keys):
    return {k: (MASK if k in secret_keys else v) for k, v in obj.items()}


class PpdmError(Exception):
    """Any client failure: msg is safe to show (scrubbed), status the HTTP code if any, body the scrubbed error body."""

    def __init__(self, msg: str, status: int | None = None, body: Any = None):
        super().__init__(msg)
        self.msg = msg
        self.status = status
        self.body = body


class PpdmClient:
    """Session with one PPDM server: login once, then JSON requests, paging and ensure/remove helpers."""

    def __init__(
        self,
        hostname: str,
        username: str,
        password: str,
        port: int = 8443,
        validate_certs: bool = True,
        ca_path: str | None = None,
        timeout: int = 30,
        opener: Callable = open_url,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.base_url = "https://%s:%s" % (_host_netloc(hostname), port)
        self.username = username
        self.password = password
        self.validate_certs = validate_certs
        self.ca_path = ca_path
        self.timeout = timeout
        self.opener = opener
        self.sleep = sleep
        self.token = None
        self.last_status = None

    def _secret_strings(self):
        """The password and the token plus their JSON (lower and upper case \\uXXXX) and repr escaped forms."""
        out = set()
        for x in (self.password, self.token):
            if isinstance(x, str) and x:
                ascii_form = json.dumps(x)[1:-1]
                upper = re.sub(r"\\u([0-9a-f]{4})", lambda m: "\\u" + m.group(1).upper(), ascii_form)  # Jackson
                raw_form = json.dumps(x, ensure_ascii=False)[1:-1]
                # Jackson default: non-ASCII raw, control characters as \\u00XX uppercase, DEL raw
                raw_upper = re.sub(r"\\u([0-9a-f]{4})", lambda m: "\\u" + m.group(1).upper(), raw_form)
                out |= {x, ascii_form, upper, raw_form, raw_upper, repr(x)[1:-1]}
        return sorted(out)

    def scrub(self, value):
        """Mask the password and the token (and their escaped forms) in every string of value (dict keys too).

        Never raises.
        """
        try:
            secrets = self._secret_strings()

            def mask(text):
                # every occurrence of every secret (overlaps included), merged on the fly, then masked once per run
                found = ((m.span(1) for m in re.finditer("(?=(%s))" % re.escape(x), text)) for x in secrets)
                merged = []
                for start, end in heapq.merge(*found):
                    if merged and start <= merged[-1][1]:
                        merged[-1][1] = max(merged[-1][1], end)
                    else:
                        merged.append([start, end])
                out, pos = [], 0
                for start, end in merged:
                    out += [text[pos:start], "********"]
                    pos = end
                return "".join(out) + text[pos:]

            def walk(v):
                if isinstance(v, str):
                    return mask(v)
                if isinstance(v, dict):
                    return {(mask(k) if isinstance(k, str) else k): walk(x) for k, x in v.items()}
                if isinstance(v, list):
                    return [walk(x) for x in v]
                return v

            return walk(value)
        except Exception:  # e.g. RecursionError on a hostile body: hide it rather than risk a leak
            return "********"

    _scrub = scrub

    def scrub_text(self, value, limit=200):
        """Scrub the structure, stringify, scrub the text again, cut to limit: safe for a message.

        The structure goes first because repr escapes (backslash, quotes, control characters) hide a secret
        from a text scrub. Nothing is cut before the scrub: a pre-cut can leave part of a secret that masks
        before it then pull inside limit. A value whose text is longer than MAX_SCRUB_TEXT is not scrubbed
        (cost bound) and gives only "<... of N characters omitted>". The cut to limit comes last: it drops
        characters of masked text only (it may split a mask, never expose a secret).
        """
        try:
            text = value if isinstance(value, str) else str(value)  # unscrubbed: only its length is used
            if len(text) <= MAX_SCRUB_TEXT and not isinstance(value, str):
                text = str(self.scrub(value))
        except Exception:  # e.g. RecursionError on a hostile structure
            return "********"[:limit]
        if len(text) > MAX_SCRUB_TEXT:
            return ("<... of %d characters omitted>" % len(text))[:limit]
        return self.scrub(text)[:limit]

    @staticmethod
    def _read(resp, method, path):
        raw = resp.read(MAX_BODY_BYTES + 1)
        if len(raw) > MAX_BODY_BYTES:
            raise PpdmError(
                "%s %s failed: response body too large (more than %d bytes)" % (method, path, MAX_BODY_BYTES)
            )
        return raw

    def login(self) -> None:
        """POST /api/v2/login and keep the bearer token; PpdmError when the response has no usable token."""
        data = {"username": self.username, "password": self.password}
        self.token = None
        resp = self.request("POST", "/api/v2/login", body=data)
        token = resp.get("access_token") if isinstance(resp, dict) else None
        if not isinstance(token, str) or not token:
            raise PpdmError("POST /api/v2/login failed: response has no access_token")
        if not re.fullmatch(r"[\x21-\x7e]+", token):
            raise PpdmError("POST /api/v2/login failed: invalid access_token (not printable ASCII)")
        self.token = token

    def request(self, method: str, path: str, query: dict | None = None, body: Any = None) -> Any:
        """One JSON call; returns the decoded body (None for 204 or an empty body). Every failure is a PpdmError."""
        try:
            url = self.base_url + path
            if query:
                url += "?" + urlencode(query, quote_via=quote)
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = "Bearer " + self.token
            resp = self.opener(
                url,
                method=method,
                headers=headers,
                data=None if body is None else json.dumps(body),
                validate_certs=self.validate_certs,
                ca_path=self.ca_path,
                timeout=self.timeout,
                follow_redirects="none",  # never forward the Authorization header to a redirect target
            )
            raw = self._read(resp, method, path)
            status = getattr(resp, "status", None) or resp.getcode()
            self.last_status = status
        except HTTPError as e:
            if e.code in REDIRECT_CODES:  # no Location (it may carry a query): it is not echoed
                raise PpdmError(
                    "%s %s failed: HTTP %s: PPDM redirected the request; redirects are not followed"
                    % (method, path, e.code),
                    status=e.code,
                ) from None
            raw = self._read(e, method, path)
            if len(raw) > MAX_SCRUB_TEXT:  # too big to scrub cheaply: keep no raw text at all
                err_body = detail = "<error body of %d bytes omitted>" % len(raw)
            else:
                try:
                    parsed = json.loads(raw) if raw else None
                except (ValueError, RecursionError):
                    parsed = raw.decode("utf-8", "replace")
                detail = parsed.get("message") if isinstance(parsed, dict) else parsed
                detail = self.scrub_text(detail, 1000) if detail else ""
                # scrub first, cut after: a cut before the scrub could split a secret
                err_body = self.scrub(parsed) if len(raw) <= MAX_ERROR_TEXT else self.scrub_text(parsed, MAX_ERROR_TEXT)
            raise PpdmError(
                "%s %s failed: HTTP %s%s" % (method, path, e.code, ": %s" % detail if detail else ""),
                status=e.code,
                body=err_body,
            ) from None
        except (ValueError, TypeError) as e:  # bad headers, urlencode, unicode, non-JSON body: name the class only
            raise PpdmError(
                "%s %s failed: could not build the request (%s)" % (method, path, type(e).__name__)
            ) from None
        except (URLError, OSError, HTTPException) as e:
            raise PpdmError(self._scrub("%s %s failed: %s" % (method, path, e))) from None
        if status == 204 or not raw:
            return None
        try:
            return json.loads(raw)
        except (ValueError, RecursionError):
            raise PpdmError(
                "%s %s failed: HTTP %s response is not valid JSON" % (method, path, status),
                status=status,
            ) from None

    def get_all(self, path: str, query: dict | None = None) -> Any:
        """GET path; a {content, page} envelope is paged to the end and returned as a list, anything else as is."""
        return self._get_pages(path, query)[0]

    def _get_pages(self, path: str, query: dict | None) -> tuple[Any, bool]:
        """Return (data, paged); paged is False when the first response had no content envelope."""
        items = []
        page = 1
        while True:
            data = self.request("GET", path, query=dict(query or {}, page=page, pageSize=PAGE_SIZE))
            if not isinstance(data, dict) or "content" not in data:
                if page > 1:  # never drop or truncate what was already collected
                    raise PpdmError("GET %s failed: unexpected response on page %d" % (path, page))
                return data, False
            content = data["content"] or []
            if not isinstance(content, list):
                raise PpdmError("GET %s failed: 'content' is not a list" % path)
            if len(content) > PAGE_SIZE:
                raise PpdmError(
                    "GET %s failed: page has %d items, more than the %d requested" % (path, len(content), PAGE_SIZE)
                )
            items.extend(content)
            if len(items) > MAX_ITEMS:
                raise PpdmError("GET %s failed: more than %d items in total" % (path, MAX_ITEMS))
            pg = data.get("page")
            total = pg.get("totalPages") if isinstance(pg, dict) else None
            if total is not None and (
                not isinstance(total, int) or isinstance(total, bool) or total < 0 or total > MAX_PAGES
            ):
                raise PpdmError(
                    "GET %s failed: invalid page.totalPages %s (must be an integer 0..%d)"
                    % (path, self.scrub_text(total, 40), MAX_PAGES)
                )
            if total is None:
                if content:
                    raise PpdmError("GET %s failed: paginated response has no 'page.totalPages'" % path)
                return items, True
            if page >= total:
                return items, True
            page += 1

    def list_all(self, resource: str, filter: str | None = None, order_by: str | None = None) -> list:
        """Every item of the resource collection (all pages, at most MAX_ITEMS), optionally filtered/ordered."""
        path = ROUTES[resource]["base"]
        query = {}
        if filter:
            query["filter"] = filter
        if order_by:
            query["orderby"] = order_by
        data, paged = self._get_pages(path, query)
        if paged:
            return data
        if not isinstance(data, dict):
            raise PpdmError("GET %s failed: unexpected response" % path)
        return []  # envelope-less object: no items, as before

    def find_one(self, resource: str, key: str, value: Any) -> dict | None:
        """The single object whose key equals value exactly, None if none; PpdmError when several match."""
        found = self.list_all(resource, filter=filter_eq(key, value))
        # never trust the server-side filter: exact, case-sensitive match only (a loose filter must not
        # make ensure/remove write to or delete another object)
        found = [o for o in found if isinstance(o, dict) and o.get(key) == value]
        if len(found) > 1:
            ids = ", ".join(self.scrub_text(o.get("id"), 64) for o in found[:10])
            raise PpdmError(
                self._scrub("%s: %d objects match %s=%s (ids: %s)" % (resource, len(found), key, value, ids))
            )
        return found[0] if found else None

    def _route(self, resource, verb, obj_id=None):
        route = ROUTES[resource]
        if verb not in route["methods"]:
            raise PpdmError("%s does not support %s" % (resource, verb))
        if obj_id is None:
            if verb in ("PUT", "PATCH", "DELETE"):  # item verbs must never fall back to the collection path
                raise PpdmError("%s %s: id is required" % (resource, verb))
            return route["base"]
        if str(obj_id) == "":
            raise PpdmError("%s %s: id must not be empty" % (resource, verb))
        return route["item"].replace("{id}", quote_id(obj_id))

    def _item_id(self, resource, existing):
        obj_id = existing.get("id")
        if not isinstance(obj_id, str) or not obj_id:
            raise PpdmError("%s: the existing object has no usable id" % resource)
        return obj_id

    def ensure(
        self,
        resource: str,
        desired: dict,
        key: str = "name",
        check_mode: bool = False,
        secret_keys: Any = (),
        update_secrets: str = "on_create",
        create: bool = True,
    ) -> dict:
        """Create or update one object; the merge over the existing object is shallow (top-level keys only).

        With create=False a missing object is a PpdmError instead of a POST.
        """
        if update_secrets not in ("on_create", "always"):
            raise PpdmError("update_secrets must be 'on_create' or 'always', got %r" % (update_secrets,))
        secret_keys = set(secret_keys)
        existing = self.find_one(resource, key, desired[key])
        want = strip_readonly(resource, desired)
        if existing is None:
            if not create:
                raise PpdmError("%s %s=%s not found" % (resource, key, self.scrub_text(desired[key], 200)))
            path = self._route(resource, "POST")
            obj = want if check_mode else (self.request("POST", path, body=want) or want)
            return {
                "changed": True,
                "object": _mask(obj, secret_keys),
                "diff": {"before": {}, "after": _mask(want, secret_keys)},
            }
        before = strip_readonly(resource, existing)
        after = dict(before, **want)

        # Secrets are write-only (GET omits/masks them): never part of the comparison.
        def plain(o):
            return {k: v for k, v in o.items() if k not in secret_keys}

        force = update_secrets == "always" and bool(secret_keys & set(want))
        if plain(after) == plain(before) and not force:
            return {
                "changed": False,
                "object": _mask(existing, secret_keys),
                "diff": {
                    "before": _mask(before, secret_keys),
                    "after": _mask(after, secret_keys),
                },
            }
        path = self._route(resource, "PUT", self._item_id(resource, existing))
        drop = (WRITE_ONLY_KEYS | secret_keys) - set(want)
        body = {k: v for k, v in after.items() if k not in drop}
        obj = after if check_mode else (self.request("PUT", path, body=body) or after)
        return {
            "changed": True,
            "object": _mask(obj, secret_keys),
            "diff": {
                "before": _mask(before, secret_keys),
                "after": _mask(after, secret_keys),
            },
        }

    def remove(self, resource: str, key: str, value: Any, check_mode: bool = False, secret_keys: Any = ()) -> dict:
        """Delete the object whose key equals value; {changed, diff}. Nothing is sent in check mode."""
        existing = self.find_one(resource, key, value)
        if existing is None:
            return {"changed": False, "diff": {"before": {}, "after": {}}}
        path = self._route(resource, "DELETE", self._item_id(resource, existing))
        if not check_mode:
            self.request("DELETE", path)
        return {
            "changed": True,
            "diff": {"before": _mask(strip_readonly(resource, existing), set(secret_keys)), "after": {}},
        }

    def wait_activity(self, activity_id: str, timeout: int, interval: int = 5) -> dict:
        """Poll the activity until it is COMPLETED and return it.

        interval must be greater than 0 (PpdmError otherwise). timeout is counted as the sum of the
        sleeps between polls; PpdmError is raised when it is reached before completion.
        """
        if interval <= 0:
            raise PpdmError("wait_activity: interval must be greater than 0, got %r" % (interval,))
        path = self._route("activities", "GET", activity_id)
        waited = 0
        while True:
            act = self.request("GET", path)
            if isinstance(act, dict) and isinstance(act.get("state"), str) and act["state"] in ACTIVITY_TERMINAL_STATES:
                return act
            if waited >= timeout:
                raise PpdmError(
                    "activity %s timed out after %ss (state %s)"
                    % (
                        self.scrub_text(activity_id, 64),
                        timeout,
                        self.scrub_text(act.get("state") if isinstance(act, dict) else None, 64),
                    )
                )
            self.sleep(interval)
            waited += interval


def connection_argument_spec() -> dict:
    """Argument spec of the connection options shared by every module (kept in sync with the doc fragment)."""
    return dict(
        hostname=dict(type="str", required=True, fallback=(env_fallback, ["PPDM_HOSTNAME"])),
        username=dict(type="str", required=True, fallback=(env_fallback, ["PPDM_USERNAME"])),
        password=dict(
            type="str",
            required=True,
            no_log=True,
            fallback=(env_fallback, ["PPDM_PASSWORD"]),
        ),
        port=dict(type="int", default=8443, fallback=(env_fallback, ["PPDM_PORT"])),
        validate_certs=dict(type="bool", default=True),
        ca_path=dict(type="path"),
        timeout=dict(type="int", default=30),
    )


def fail_from(module: AnsibleModule, err: PpdmError) -> None:
    """fail_json with the message, status and body of err."""
    module.fail_json(msg=err.msg, status=err.status, body=err.body)


def client_from_module(module: AnsibleModule) -> PpdmClient:
    """Logged-in client from the connection options of module; fails the module on a PpdmError."""
    p = module.params
    try:
        client = PpdmClient(
            p["hostname"],
            p["username"],
            p["password"],
            port=p["port"],
            validate_certs=p["validate_certs"],
            ca_path=p["ca_path"],
            timeout=p["timeout"],
        )
        client.login()
    except PpdmError as err:
        fail_from(module, err)
    return client


def info_main(resource: str, result_key: str, argument_spec: dict, secret_fields: Any = ()) -> None:
    """Shared main() of the read-only *_info modules."""
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **argument_spec),
        supports_check_mode=True,
        mutually_exclusive=[("id", "name"), ("id", "filter"), ("name", "filter")],
    )
    p = module.params
    if p["name"] == "":  # an empty name must not silently become "list everything"
        module.fail_json(msg="name must not be empty (omit it to list all)")
    client = client_from_module(module)
    try:
        if p["id"] is not None:  # an empty id must fail in _route, not fall through to a full list
            try:
                body = client.request("GET", client._route(resource, "GET", p["id"]))
            except PpdmError as err:
                if err.status != 404:
                    raise
                found = []
            else:
                if not isinstance(body, dict):
                    raise PpdmError("GET %s/%s failed: unexpected response" % (resource, p["id"]))
                found = [body]
        else:
            flt = filter_eq("name", p["name"]) if p["name"] else p["filter"]
            found = client.list_all(resource, filter=flt)
            if p["name"]:  # the server-side filter is advisory (and I(filter) is passed through unchanged)
                found = [o for o in found if isinstance(o, dict) and o.get("name") == p["name"]]
    except PpdmError as err:
        fail_from(module, err)
    items = [{k: v for k, v in o.items() if k not in secret_fields} for o in found]
    module.exit_json(**{"changed": False, result_key: items})
