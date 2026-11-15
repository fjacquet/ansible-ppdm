import json
from urllib.parse import parse_qs, urlsplit

import pytest
from ansible.module_utils.testing import patch_module_args
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmClient
from ansible_collections.fjacquet.ppdm.plugins.modules import api
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    Exit,
    FakeOpener,
    Resp,
    http_error,
)

CONN = dict(hostname="h", username="u", password="s3cret")


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
    out = run(
        monkeypatch,
        op,
        check_mode=True,
        method="POST",
        path="/api/v3/alerts",
        body={"a": 1},
    )
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


@pytest.mark.parametrize(
    "path",
    [
        "/api/../x",
        "/api/%2e%2e/x",
        "/api/%2E%2E/x",
        "/api/v2/x?y=1",
        "/api/v2/x#f",
        "/api/v2/ x",
        "/api/%252e%252e/x",
        "/api/v2/x%00.json",
        "/api/v2/x\x00",
        "/api/v2/x\x07y",
        "/api/v2/x\\y",
        "/api/v2/x;jsessionid=1",
        "/api/\uff0e\uff0e/x",
        "/api/v2/caf\u00e9",
        "/api/v2/x%0d%0aH:v",
        "/api/v2/x%01",
        "/api/v2/x%7f",
        "/api/v2/x%1F",
        "/api/v2/%2f%2fx",
        "/api/v2/a%5Cb",
        "/api/v2/%c0%ae",
        "/api/v2/%C1%9c",
        "/api/./x",
        "/api/v2/.",
        "/api/v2/./x",
    ],
)
def test_unsafe_paths_rejected_before_request(monkeypatch, path):
    op = FakeOpener()
    out = run(monkeypatch, op, path=path)
    assert out["failed"] and "s3cret" not in json.dumps(out)
    assert op.calls == []


@pytest.mark.parametrize(
    "path", ["/api/v2/activities", "/api/v3/protection-policies/abc-123", "/api/v2/a%2db", "/api/v2/a.b", "/api/v2/.x"]
)
def test_valid_paths_accepted(monkeypatch, path):
    out = run(monkeypatch, FakeOpener(Resp({"content": [], "page": {"totalPages": 0}})), path=path)
    assert out["failed"] is False


def test_warns_when_body_dropped_for_paged_get(monkeypatch):
    op = FakeOpener(Resp({"content": [], "page": {"totalPages": 0}}))
    out = run(monkeypatch, op, path="/api/v3/alerts", body={"a": 1})
    assert out["failed"] is False and any("body" in w for w in out["_warnings"])


def test_no_body_warning_when_all_pages_false(monkeypatch):
    out = run(monkeypatch, FakeOpener(Resp({"x": 1})), path="/api/v3/x", body={"a": 1}, all_pages=False)
    assert out["_warnings"] == []


def test_warns_when_wait_but_no_activity_id(monkeypatch):
    out = run(monkeypatch, FakeOpener(Resp({"ok": 1})), method="POST", path="/api/v3/x", wait=True)
    assert out["failed"] is False and any("activityId" in w for w in out["_warnings"])


def test_wait_failure_message_scrubs_server_status(monkeypatch):
    act = {"id": "a1", "state": "COMPLETED", "result": {"status": "s3cret"}}
    out = run(monkeypatch, _async(act), method="POST", path="/api/v3/x", wait=True)
    assert out["failed"] and "s3cret" not in out["msg"]


def test_wait_ok_with_errors_warning_scrubs_activity_id(monkeypatch):
    act = {"id": "a1", "state": "COMPLETED", "result": {"status": "OK_WITH_ERRORS"}}
    op = FakeOpener(Resp({"activityId": "s3cret"}, status=202), Resp(act))
    out = run(monkeypatch, op, method="POST", path="/api/v3/x", wait=True)
    assert not any("s3cret" in w for w in out["_warnings"])


@pytest.mark.parametrize("result", [["x"], "OK", 5])
def test_non_dict_activity_result_fails_cleanly(monkeypatch, result):
    act = {"id": "a1", "state": "COMPLETED", "result": result}
    out = run(monkeypatch, _async(act), method="POST", path="/api/v3/x", wait=True)
    assert out["failed"] and "status" in out["msg"]
