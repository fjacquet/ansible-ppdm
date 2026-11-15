# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""PowerProtect Data Manager REST client (HTTP only via ansible open_url)."""

from __future__ import absolute_import, annotations, division, print_function

__metaclass__ = type

import json
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode

from ansible.module_utils.basic import env_fallback
from ansible.module_utils.urls import open_url

from ansible_collections.fjacquet.ppdm.plugins.module_utils._routes import ROUTES

PAGE_SIZE = 100


class PpdmError(Exception):
    def __init__(self, msg, status=None, body=None):
        super().__init__(msg)
        self.msg = msg
        self.status = status
        self.body = body


class PpdmClient:
    def __init__(self, hostname, username, password, port=8443, validate_certs=True,
                 ca_path=None, timeout=30, opener=open_url):
        self.base_url = "https://%s:%s" % (hostname, port)
        self.username = username
        self.password = password
        self.validate_certs = validate_certs
        self.ca_path = ca_path
        self.timeout = timeout
        self.opener = opener
        self.token = None

    def _scrub(self, value):
        # Never let the password reach error text or body, whatever the server echoes.
        if not self.password:
            return value
        text = json.dumps(value)
        for secret in (self.password, json.dumps(self.password)[1:-1]):
            text = text.replace(secret, "********")
        return json.loads(text)

    def login(self):
        data = {"username": self.username, "password": self.password}
        self.token = None
        resp = self.request("POST", "/api/v2/login", body=data)
        token = resp.get("access_token") if isinstance(resp, dict) else None
        if not token:
            raise PpdmError("POST /api/v2/login failed: response has no access_token")
        self.token = token

    def request(self, method, path, query=None, body=None):
        url = self.base_url + path
        if query:
            url += "?" + urlencode(query, quote_via=quote)
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        try:
            resp = self.opener(
                url, method=method, headers=headers,
                data=None if body is None else json.dumps(body),
                validate_certs=self.validate_certs, ca_path=self.ca_path, timeout=self.timeout,
            )
            raw = resp.read()
            status = getattr(resp, "status", None) or resp.getcode()
        except HTTPError as e:
            raw = e.read()
            try:
                err_body = json.loads(raw) if raw else None
            except ValueError:
                err_body = raw.decode("utf-8", "replace")
            err_body = self._scrub(err_body)
            detail = err_body.get("message") if isinstance(err_body, dict) else err_body
            raise PpdmError("%s %s failed: HTTP %s%s" % (method, path, e.code, ": %s" % detail if detail else ""),
                            status=e.code, body=err_body)
        except (URLError, OSError, HTTPException) as e:
            raise PpdmError(self._scrub("%s %s failed: %s" % (method, path, e)))
        if status == 204 or not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            raise PpdmError("%s %s failed: HTTP %s response is not valid JSON" % (method, path, status), status=status)

    def list_all(self, resource, filter=None, order_by=None):
        path = ROUTES[resource]["base"]
        items = []
        page = 1
        while True:
            query = {"page": page, "pageSize": PAGE_SIZE}
            if filter:
                query["filter"] = filter
            if order_by:
                query["orderby"] = order_by
            data = self.request("GET", path, query=query)
            if not isinstance(data, dict):
                raise PpdmError("GET %s failed: unexpected response" % path)
            content = data.get("content") or []
            items.extend(content)
            if "page" not in data:
                if content:
                    raise PpdmError("GET %s failed: paginated response has no 'page' envelope" % path)
                return items
            if page >= data["page"].get("totalPages", 0):
                return items
            page += 1


def connection_argument_spec():
    return dict(
        hostname=dict(type="str", required=True, fallback=(env_fallback, ["PPDM_HOSTNAME"])),
        username=dict(type="str", required=True, fallback=(env_fallback, ["PPDM_USERNAME"])),
        password=dict(type="str", required=True, no_log=True, fallback=(env_fallback, ["PPDM_PASSWORD"])),
        port=dict(type="int", default=8443, fallback=(env_fallback, ["PPDM_PORT"])),
        validate_certs=dict(type="bool", default=True),
        ca_path=dict(type="path"),
        timeout=dict(type="int", default=30),
    )


def fail_from(module, err):
    module.fail_json(msg=err.msg, status=err.status, body=err.body)


def client_from_module(module):
    p = module.params
    client = PpdmClient(p["hostname"], p["username"], p["password"], port=p["port"],
                        validate_certs=p["validate_certs"], ca_path=p["ca_path"], timeout=p["timeout"])
    try:
        client.login()
    except PpdmError as err:
        fail_from(module, err)
    return client
