"""Security regressions of the client: redirects, find_one post-filter, scrubbing, pagination bounds."""

import io
import json
import urllib.error

import pytest
from ansible_collections.fjacquet.ppdm.plugins.module_utils import ppdm
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmClient, PpdmError
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import FakeOpener, Resp, http_error


def mk(*responses, password="S3cret!"):
    op = FakeOpener(*responses)
    return PpdmClient("ppdm.local", "admin", password, opener=op, sleep=lambda s: None), op


def page(items, total):
    return Resp({"content": items, "page": {"totalPages": total}})


# S1: redirects are never followed


def test_request_disables_redirects():
    c, op = mk(Resp({"a": 1}))
    c.request("GET", "/api/v2/x")
    assert op.calls[0][1]["follow_redirects"] == "none"


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_redirect_response_is_ppdm_error_without_location(code):
    loc = "http://evil.example/steal?token=SECRET-QUERY"
    err = urllib.error.HTTPError(loc, code, "Found", {"Location": loc}, io.BytesIO(b""))
    c, _ = mk(err)
    with pytest.raises(PpdmError) as e:
        c.request("GET", "/api/v2/x")
    assert "redirects are not followed" in e.value.msg
    assert e.value.status == code
    assert "evil" not in e.value.msg and "SECRET-QUERY" not in e.value.msg
    assert "evil" not in str(e.value.body) and "SECRET-QUERY" not in str(e.value.body)


# S2: find_one keeps exact matches only


def test_find_one_ignores_unrelated_object():
    c, _ = mk(page([{"id": "other", "name": "vcenter-prod"}], 1))
    assert c.find_one("credentials", "name", "dd-lab") is None


def test_find_one_is_case_sensitive():
    c, _ = mk(page([{"id": "1", "name": "DD-LAB"}], 1))
    assert c.find_one("credentials", "name", "dd-lab") is None


def test_find_one_duplicate_rule_applies_after_filtering():
    c, _ = mk(page([{"id": "1", "name": "a"}, {"id": "2", "name": "other"}], 1))
    assert c.find_one("credentials", "name", "a")["id"] == "1"
    c, _ = mk(page([{"id": "1", "name": "a"}, {"id": "2", "name": "a"}], 1))
    with pytest.raises(PpdmError, match="2 objects match"):
        c.find_one("credentials", "name", "a")


def test_ensure_creates_instead_of_putting_on_unrelated_object():
    c, op = mk(page([{"id": "other", "name": "vcenter-prod"}], 1), Resp({"id": "n"}, 201))
    c.ensure("credentials", {"name": "dd-lab", "type": "DATADOMAIN"})
    assert [kw["method"] for _, kw in op.calls] == ["GET", "POST"]


def test_remove_sends_no_delete_for_unrelated_object():
    c, op = mk(page([{"id": "other", "name": "vcenter-prod"}], 1))
    assert c.remove("credentials", "name", "dd-lab")["changed"] is False
    assert [kw["method"] for _, kw in op.calls] == ["GET"]


# S4: scrubbing never corrupts JSON, never raises, covers the token


@pytest.mark.parametrize("pw", ["a", "e", '"', ":", "401", "\\", "null", "s3cret", "péss", "message"])
def test_scrub_http_error_json_body(pw):
    body = {"status": 401, "message": "bad login for admin: %s" % pw, "detail": {"x": [pw, 1, None]}}
    c, _ = mk(http_error(401, body), password=pw)
    with pytest.raises(PpdmError) as e:
        c.request("POST", "/api/v2/login", body={"password": pw})
    assert e.value.status == 401
    assert isinstance(e.value.body, dict) and e.value.body["status"] == 401
    assert e.value.body["message"] == ("bad login for admin: %s" % pw).replace(pw, "********")
    assert e.value.body["detail"] == {"x": ["********", 1, None]}
    assert "********" in e.value.msg


@pytest.mark.parametrize("pw", ["a", '"', "\\", "401", "hunter22"])
def test_scrub_non_json_body_and_urlerror(pw):
    err = urllib.error.HTTPError("u", 500, "x", {}, io.BytesIO(("oops %s oops" % pw).encode()))
    c, _ = mk(err, urllib.error.URLError("refused %s" % pw), password=pw)
    with pytest.raises(PpdmError) as e:
        c.request("GET", "/x")
    assert "********" in e.value.body
    with pytest.raises(PpdmError) as e:
        c.request("GET", "/x")
    assert "********" in e.value.msg
    if len(pw) > 3:
        assert pw not in e.value.msg


@pytest.mark.parametrize("pw", ["a", '"', "401"])
def test_scrub_login_failure(pw):
    c, _ = mk(http_error(401, {"message": "no %s" % pw}), password=pw)
    with pytest.raises(PpdmError):
        c.login()


def test_scrub_hides_access_token():
    tok = "eyJhbGciOiJIUzI1NiJ9.FAKE.FAKE"
    c, _ = mk(Resp({"access_token": tok}), http_error(400, {"message": "echo Authorization=Bearer " + tok}))
    c.login()
    with pytest.raises(PpdmError) as e:
        c.request("GET", "/api/v2/x")
    assert tok not in e.value.msg and tok not in json.dumps(e.value.body)


def test_scrub_non_container_values_untouched():
    c, _ = mk(http_error(400, [1, "pw", None]), password="pw")
    with pytest.raises(PpdmError) as e:
        c.request("GET", "/x")
    assert e.value.body == [1, "********", None]


# S5: pagination bounds and hostile bodies


@pytest.mark.parametrize("literal", ["NaN", "1.5", "1e9", '"5"', "-1", "true", "[]"])
def test_bad_total_pages_rejected(literal):
    resp = Resp()
    resp._raw = ('{"content": [], "page": {"totalPages": %s}}' % literal).encode()
    c, _ = mk(resp)
    with pytest.raises(PpdmError, match="totalPages"):
        c.list_all("credentials")


def test_huge_int_total_pages_capped():
    c, op = mk(page([{"id": 1}], 10**9))
    with pytest.raises(PpdmError, match="totalPages"):
        c.list_all("credentials")
    assert len(op.calls) == 1


def test_max_pages_boundary_ok_and_over_rejected(monkeypatch):
    monkeypatch.setattr(ppdm, "MAX_PAGES", 2)
    c, _ = mk(page([1], 2), page([2], 2))
    assert c.get_all("/x") == [1, 2]
    c, _ = mk(page([1], 3))
    with pytest.raises(PpdmError, match="totalPages"):
        c.get_all("/x")


def test_zero_total_pages_ok():
    c, _ = mk(page([], 0))
    assert c.list_all("credentials") == []


def test_non_list_content_rejected():
    c, _ = mk(page("abc", 1))
    with pytest.raises(PpdmError, match="content"):
        c.list_all("credentials")


@pytest.mark.parametrize("opener_resp", ["success", "error"])
def test_deeply_nested_json_is_ppdm_error(opener_resp):
    deep = b"[" * 100000 + b"]" * 100000
    resp = Resp()
    resp._raw = deep
    if opener_resp == "error":
        resp = urllib.error.HTTPError("u", 500, "x", {}, io.BytesIO(deep))
    c, _ = mk(resp)
    with pytest.raises(PpdmError):
        c.request("GET", "/x")
