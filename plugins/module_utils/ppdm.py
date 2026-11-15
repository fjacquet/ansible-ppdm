# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""PowerProtect Data Manager REST client (HTTP only via ansible open_url)."""

from __future__ import annotations

import json
import time
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode

from ansible.module_utils.basic import AnsibleModule, env_fallback
from ansible.module_utils.urls import open_url
from ansible_collections.fjacquet.ppdm.plugins.module_utils._routes import ROUTES

PAGE_SIZE = 100
MAX_PAGES = 10000  # the OpenAPI maximum of the `page` query parameter
REDIRECT_CODES = frozenset([301, 302, 303, 307, 308])
MASK = "VALUE_SPECIFIED_IN_NO_LOG_PARAMETER"
# OpenAPI 20.3.0 Activity.state: QUEUED/RUNNING/PENDING_CANCELLATION|CANCELING/RETRYING/COMPLETED.
# COMPLETED is the only terminal state; success/failure is in result.status (OK, FAILED, CANCELED, ...).
ACTIVITY_TERMINAL_STATES = frozenset(["COMPLETED"])


def strip_readonly(resource, obj):
    drop = set(ROUTES[resource]["readonly"]) | {"_links"}
    return {k: v for k, v in obj.items() if k not in drop}


def filter_eq(key, value):
    # shortcut: the OpenAPI does not document filter escaping; backslash-escaping \ and " is best effort.
    return '%s eq "%s"' % (key, str(value).replace("\\", "\\\\").replace('"', '\\"'))


def merge_config(named, config):
    """Body from the named options (None values dropped) over config; config may not use a named option's key."""
    config = config or {}
    clash = sorted(set(config) & set(named))
    if clash:
        raise PpdmError("config must not set %s: use the matching module option instead" % ", ".join(clash))
    return dict(config, **{k: v for k, v in named.items() if v is not None})


def _mask(obj, secret_keys):
    return {k: (MASK if k in secret_keys else v) for k, v in obj.items()}


class PpdmError(Exception):
    def __init__(self, msg, status=None, body=None):
        super().__init__(msg)
        self.msg = msg
        self.status = status
        self.body = body


class PpdmClient:
    def __init__(
        self,
        hostname,
        username,
        password,
        port=8443,
        validate_certs=True,
        ca_path=None,
        timeout=30,
        opener=open_url,
        sleep=time.sleep,
    ):
        self.base_url = "https://%s:%s" % (hostname, port)
        self.username = username
        self.password = password
        self.validate_certs = validate_certs
        self.ca_path = ca_path
        self.timeout = timeout
        self.opener = opener
        self.sleep = sleep
        self.token = None
        self.last_status = None

    def _scrub(self, value):
        """Replace the password and the token inside string values only (keys kept); never raises."""
        # longest first: a password that is a substring of the token must not cut it before it is replaced
        secrets = sorted({self.password, self.token} - {None, ""}, key=len, reverse=True)

        def walk(v):
            if isinstance(v, str):
                for secret in secrets:
                    v = v.replace(secret, "********")
                return v
            if isinstance(v, dict):
                return {k: walk(x) for k, x in v.items()}
            if isinstance(v, list):
                return [walk(x) for x in v]
            return v

        try:
            return walk(value)
        except Exception:  # e.g. RecursionError on a hostile body: hide it rather than risk a leak
            return "********"

    def login(self):
        data = {"username": self.username, "password": self.password}
        self.token = None
        resp = self.request("POST", "/api/v2/login", body=data)
        token = resp.get("access_token") if isinstance(resp, dict) else None
        if not token:
            raise PpdmError("POST /api/v2/login failed: response has no access_token")
        self.token = token

    def request(self, method, path, query=None, body=None):
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
            raw = resp.read()
            status = getattr(resp, "status", None) or resp.getcode()
            self.last_status = status
        except HTTPError as e:
            if e.code in REDIRECT_CODES:  # no Location (it may carry a query): it is not echoed
                raise PpdmError(
                    "%s %s failed: HTTP %s: PPDM redirected the request; redirects are not followed"
                    % (method, path, e.code),
                    status=e.code,
                ) from None
            raw = e.read()
            try:
                err_body = json.loads(raw) if raw else None
            except (ValueError, RecursionError):
                err_body = raw.decode("utf-8", "replace")
            err_body = self._scrub(err_body)
            detail = err_body.get("message") if isinstance(err_body, dict) else err_body
            raise PpdmError(
                "%s %s failed: HTTP %s%s" % (method, path, e.code, ": %s" % detail if detail else ""),
                status=e.code,
                body=err_body,
            ) from None
        # ValueError covers UnicodeError, bad headers and urlencode failures
        except (URLError, OSError, HTTPException, ValueError) as e:
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

    def get_all(self, path, query=None):
        """GET path; a {content, page} envelope is paged to the end and returned as a list, anything else as is."""
        return self._get_pages(path, query)[0]

    def _get_pages(self, path, query):
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
            items.extend(content)
            pg = data.get("page")
            total = pg.get("totalPages") if isinstance(pg, dict) else None
            if total is not None and (
                not isinstance(total, int) or isinstance(total, bool) or total < 0 or total > MAX_PAGES
            ):
                raise PpdmError(
                    "GET %s failed: invalid page.totalPages %r (must be an integer 0..%d)" % (path, total, MAX_PAGES)
                )
            if total is None:
                if content:
                    raise PpdmError("GET %s failed: paginated response has no 'page.totalPages'" % path)
                return items, True
            if page >= total:
                return items, True
            page += 1

    def list_all(self, resource, filter=None, order_by=None):
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

    def find_one(self, resource, key, value):
        found = self.list_all(resource, filter=filter_eq(key, value))
        # never trust the server-side filter: exact, case-sensitive match only (a loose filter must not
        # make ensure/remove write to or delete another object)
        found = [o for o in found if isinstance(o, dict) and o.get(key) == value]
        if len(found) > 1:
            ids = ", ".join(str(o.get("id")) for o in found)
            raise PpdmError("%s: %d objects match %s=%s (ids: %s)" % (resource, len(found), key, value, ids))
        return found[0] if found else None

    def _route(self, resource, verb, obj_id=None):
        route = ROUTES[resource]
        if verb not in route["methods"]:
            raise PpdmError("%s does not support %s" % (resource, verb))
        if obj_id is None:
            return route["base"]
        if str(obj_id) == "":
            raise PpdmError("%s %s: id must not be empty" % (resource, verb))
        return route["item"].replace("{id}", quote(str(obj_id), safe=""))

    def ensure(
        self,
        resource,
        desired,
        key="name",
        check_mode=False,
        secret_keys=(),
        update_secrets="on_create",
    ):
        """Create or update one object; the merge over the existing object is shallow (top-level keys only)."""
        if update_secrets not in ("on_create", "always"):
            raise PpdmError("update_secrets must be 'on_create' or 'always', got %r" % (update_secrets,))
        secret_keys = set(secret_keys)
        existing = self.find_one(resource, key, desired[key])
        want = strip_readonly(resource, desired)
        if existing is None:
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
        path = self._route(resource, "PUT", existing["id"])
        obj = after if check_mode else (self.request("PUT", path, body=after) or after)
        return {
            "changed": True,
            "object": _mask(obj, secret_keys),
            "diff": {
                "before": _mask(before, secret_keys),
                "after": _mask(after, secret_keys),
            },
        }

    def remove(self, resource, key, value, check_mode=False, secret_keys=()):
        existing = self.find_one(resource, key, value)
        if existing is None:
            return {"changed": False, "diff": {"before": {}, "after": {}}}
        path = self._route(resource, "DELETE", existing["id"])
        if not check_mode:
            self.request("DELETE", path)
        return {
            "changed": True,
            "diff": {"before": _mask(strip_readonly(resource, existing), set(secret_keys)), "after": {}},
        }

    def wait_activity(self, activity_id, timeout, interval=5):
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
            if isinstance(act, dict) and act.get("state") in ACTIVITY_TERMINAL_STATES:
                return act
            if waited >= timeout:
                raise PpdmError(
                    "activity %s timed out after %ss (state %s)"
                    % (
                        activity_id,
                        timeout,
                        act.get("state") if isinstance(act, dict) else None,
                    )
                )
            self.sleep(interval)
            waited += interval


def connection_argument_spec():
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


def fail_from(module, err):
    module.fail_json(msg=err.msg, status=err.status, body=err.body)


def client_from_module(module):
    p = module.params
    client = PpdmClient(
        p["hostname"],
        p["username"],
        p["password"],
        port=p["port"],
        validate_certs=p["validate_certs"],
        ca_path=p["ca_path"],
        timeout=p["timeout"],
    )
    try:
        client.login()
    except PpdmError as err:
        fail_from(module, err)
    return client


def info_main(resource, result_key, argument_spec, secret_fields=()):
    """Shared main() of the read-only *_info modules."""
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **argument_spec),
        supports_check_mode=True,
        mutually_exclusive=[("id", "name"), ("id", "filter"), ("name", "filter")],
    )
    p = module.params
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
    except PpdmError as err:
        fail_from(module, err)
    items = [{k: v for k, v in o.items() if k not in secret_fields} for o in found]
    module.exit_json(**{"changed": False, result_key: items})
