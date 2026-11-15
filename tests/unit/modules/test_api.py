import io
import json
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest
from ansible.module_utils.testing import patch_module_args

from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmClient
from ansible_collections.fjacquet.ppdm.plugins.modules import api


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


CONN = dict(hostname="h", username="u", password="s3cret")


class Exit(Exception):
    def __init__(self, kwargs):
        self.kwargs = kwargs


def run(monkeypatch, opener, check_mode=False, **args):
    client = PpdmClient("h", "u", "s3cret", opener=opener, sleep=lambda s: None)
    monkeypatch.setattr(api, "client_from_module", lambda module: client)

    def exit_json(self, **kw):
        raise Exit(dict(kw, failed=False))

    def fail_json(self, **kw):
        raise Exit(dict(kw, failed=True))

    monkeypatch.setattr(api.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(api.AnsibleModule, "fail_json", fail_json)
    warnings = []
    monkeypatch.setattr(api.AnsibleModule, "warn", lambda self, m: warnings.append(m))
    with patch_module_args(dict(CONN, _ansible_check_mode=check_mode, **args)):
        with pytest.raises(Exit) as e:
            api.main()
    return dict(e.value.kwargs, _warnings=warnings)


def test_get_paginates_all_pages(monkeypatch):
    op = FakeOpener(
        Resp({"content": [{"id": 1}], "page": {"totalPages": 2}}),
        Resp({"content": [{"id": 2}], "page": {"totalPages": 2}}),
    )
    out = run(monkeypatch, op, path="/api/v3/alerts")
    assert out["result"] == [{"id": 1}, {"id": 2}]
    assert out["changed"] is False
    assert len(op.calls) == 2
    assert parse_qs(urlsplit(op.calls[1][0]).query)["page"] == ["2"]


def test_get_non_paged_returns_as_is(monkeypatch):
    op = FakeOpener(Resp({"version": "20.3.0"}))
    out = run(monkeypatch, op, path="/api/v3/version")
    assert out["result"] == {"version": "20.3.0"}


def test_post_marks_changed(monkeypatch):
    op = FakeOpener(Resp({"id": "x"}, status=201))
    out = run(monkeypatch, op, method="POST", path="/api/v3/alerts", body={"a": 1})
    assert out["changed"] is True and out["result"] == {"id": "x"} and out["status"] == 201
    assert op.calls[0][1]["method"] == "POST"
    assert json.loads(op.calls[0][1]["data"]) == {"a": 1}


def test_check_mode_does_not_send_post(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, check_mode=True, method="POST", path="/api/v3/alerts", body={"a": 1})
    assert out["changed"] is True and out["skipped_write"] is True
    assert op.calls == []


def test_path_must_start_with_api(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, path="/etc/passwd")
    assert out["failed"] and "/api/" in out["msg"]
    assert op.calls == []


def test_http_error_fails_with_body(monkeypatch):
    op = FakeOpener(http_error(404, {"message": "nope"}))
    out = run(monkeypatch, op, path="/api/v3/alerts/zz")
    assert out["failed"] and out["status"] == 404 and out["body"] == {"message": "nope"}


def _async(activity):
    return FakeOpener(Resp({"activityId": "a1"}, status=202), Resp(activity))


def test_wait_ok_returns_activity(monkeypatch):
    act = {"id": "a1", "state": "COMPLETED", "result": {"status": "OK"}}
    out = run(monkeypatch, _async(act), method="POST", path="/api/v3/x", wait=True)
    assert out["failed"] is False and out["activity"] == act


def test_wait_fails_on_failed_activity(monkeypatch):
    act = {"id": "a1", "state": "COMPLETED", "result": {"status": "FAILED"}}
    out = run(monkeypatch, _async(act), method="POST", path="/api/v3/x", wait=True)
    assert out["failed"] and out["activity"] == act


def test_wait_warns_on_ok_with_errors(monkeypatch):
    act = {"id": "a1", "state": "COMPLETED", "result": {"status": "OK_WITH_ERRORS"}}
    out = run(monkeypatch, _async(act), method="POST", path="/api/v3/x", wait=True)
    assert out["failed"] is False and out["_warnings"]
