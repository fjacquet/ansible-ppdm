import http.client
import io
import json
import ssl
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (
    PpdmClient,
    PpdmError,
)


class Resp:
    def __init__(self, payload=None, status=200):
        self.status = status
        self._raw = b"" if payload is None else json.dumps(payload).encode()

    def read(self):
        return self._raw


class FakeOpener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def http_error(status, payload):
    return HTTPError("u", status, "err", {}, io.BytesIO(json.dumps(payload).encode()))


def client(opener, **kw):
    return PpdmClient("ppdm.local", "admin", "S3cret!", opener=opener, **kw)


def page(items, number, total):
    return Resp({"content": items, "page": {"number": number, "totalPages": total}})


def test_login_sets_bearer_header():
    op = FakeOpener(Resp({"access_token": "tok"}), Resp({"ok": 1}))
    c = client(op)
    c.login()
    c.request("GET", "/api/v3/alerts")
    url, kw = op.calls[0]
    assert url == "https://ppdm.local:8443/api/v2/login" and kw["method"] == "POST"
    assert json.loads(kw["data"]) == {"username": "admin", "password": "S3cret!"}
    assert op.calls[1][1]["headers"]["Authorization"] == "Bearer tok"


def test_list_all_paginates_250_items_in_three_requests():
    items = [{"id": i} for i in range(250)]
    op = FakeOpener(
        Resp({"access_token": "t"}),
        page(items[:100], 1, 3),
        page(items[100:200], 2, 3),
        page(items[200:], 3, 3),
    )
    c = client(op)
    c.login()
    assert c.list_all("alerts") == items
    qs = [parse_qs(urlsplit(u).query) for u, _ in op.calls[1:]]
    assert [q["page"] for q in qs] == [["1"], ["2"], ["3"]]
    assert all(q["pageSize"] == ["100"] for q in qs)


def test_list_all_empty_returns_empty_list_and_one_request():
    op = FakeOpener(Resp({"access_token": "t"}), page([], 1, 0))
    c = client(op)
    c.login()
    assert c.list_all("alerts") == []
    assert len(op.calls) == 2


def test_filter_is_url_encoded():
    op = FakeOpener(Resp({"access_token": "t"}), page([], 1, 1))
    c = client(op)
    c.login()
    c.list_all("alerts", filter='name eq "a b"')
    url = op.calls[1][0]
    assert "filter=name%20eq%20%22a%20b%22" in url or "filter=name+eq+%22a+b%22" in url
    assert parse_qs(urlsplit(url).query)["filter"] == ['name eq "a b"']


def test_non_2xx_raises_ppdm_error_with_status_and_body():
    body = {"code": 404, "message": "nope"}
    op = FakeOpener(Resp({"access_token": "t"}), http_error(404, body))
    c = client(op)
    c.login()
    with pytest.raises(PpdmError) as e:
        c.request("GET", "/api/v3/alerts/1")
    assert e.value.status == 404 and e.value.body == body and "404" in e.value.msg


def test_204_returns_none():
    op = FakeOpener(Resp({"access_token": "t"}), Resp(None, 204))
    c = client(op)
    c.login()
    assert c.request("DELETE", "/api/v3/alerts/1") is None


def test_login_failure_never_leaks_password():
    op = FakeOpener(http_error(401, {"message": "bad password S3cret!"}))
    with pytest.raises(PpdmError) as e:
        client(op).login()
    assert "S3cret!" not in e.value.msg and "S3cret!" not in repr(e.value.body)
    assert e.value.status == 401


def test_ca_path_and_validate_certs_passed_to_opener():
    op = FakeOpener(Resp({"access_token": "t"}))
    client(op, validate_certs=False, ca_path="/ca.pem", timeout=7).login()
    kw = op.calls[0][1]
    assert kw["validate_certs"] is False and kw["ca_path"] == "/ca.pem" and kw["timeout"] == 7


class RawResp(Resp):
    def __init__(self, raw, status=200):
        self.status = status
        self._raw = raw


@pytest.mark.parametrize(
    "exc",
    [
        TimeoutError("timed out S3cret!"),
        ConnectionResetError("reset"),
        http.client.RemoteDisconnected("closed"),
        ssl.SSLError("tls S3cret!"),
    ],
)
def test_transport_errors_become_ppdm_error(exc):
    op = FakeOpener(exc)
    with pytest.raises(PpdmError) as e:
        client(op).login()
    assert "S3cret!" not in e.value.msg


def test_read_timeout_becomes_ppdm_error():
    class Bad:
        status = 200

        def read(self):
            raise TimeoutError("read timed out")

    with pytest.raises(PpdmError):
        client(FakeOpener(Bad())).login()


def test_non_json_2xx_body_raises_ppdm_error():
    op = FakeOpener(Resp({"access_token": "t"}), RawResp(b"<html>proxy</html>"))
    c = client(op)
    c.login()
    with pytest.raises(PpdmError) as e:
        c.request("GET", "/api/v3/alerts")
    assert "S3cret!" not in e.value.msg


@pytest.mark.parametrize("resp", [Resp({"foo": 1}), Resp(None, 204)])
def test_login_without_access_token_raises_ppdm_error(resp):
    with pytest.raises(PpdmError) as e:
        client(FakeOpener(resp)).login()
    assert "S3cret!" not in e.value.msg


def test_list_all_missing_page_with_content_raises():
    op = FakeOpener(Resp({"access_token": "t"}), Resp({"content": [{"id": 1}]}))
    c = client(op)
    c.login()
    with pytest.raises(PpdmError) as e:
        c.list_all("alerts")
    assert "S3cret!" not in e.value.msg


def test_list_all_bare_list_response_raises():
    c = PpdmClient("h", "u", "p", opener=FakeOpener(Resp([{"id": 1}])))
    with pytest.raises(PpdmError):
        c.list_all("alerts")
