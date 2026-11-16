import json
from urllib.parse import urlsplit

from ansible_collections.fjacquet.ppdm.plugins.modules import activity_action
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    http_error,
    methods,
    run_module,
)


def activity(state="RUNNING", supported=("CANCEL", "RETRY"), **extra):
    return Resp(dict({"id": "a1", "state": state, "supportedActions": list(supported)}, **extra))


ACCEPTED = Resp({"activityId": "a2"}, 202)


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    kw.setdefault("id", "a1")
    kw.setdefault("action", "cancel")
    kw.setdefault("confirm", True)
    return run_module(monkeypatch, activity_action, op, check_mode=check, **kw)


def test_cancel_without_confirm_sends_nothing(monkeypatch):
    for check in (False, True):
        op = FakeOpener()
        out = run(monkeypatch, op, confirm=False, check_mode=check)
        assert out["failed"] and "confirm" in out["msg"] and op.calls == []


def test_cancel_path_and_body(monkeypatch):
    op = FakeOpener(activity(), ACCEPTED)
    out = run(monkeypatch, op)
    assert out["changed"] and out["response"] == {"activityId": "a2"} and out["activity"]["id"] == "a1"
    assert methods(op) == ["GET", "POST"]
    assert urlsplit(op.calls[1][0]).path == "/api/v3/activities/a1/cancel"
    assert json.loads(op.calls[1][1]["data"]) == {}


def test_cancel_completed_is_noop(monkeypatch):
    op = FakeOpener(activity("COMPLETED", supported=()))
    out = run(monkeypatch, op)
    assert not out["failed"] and not out["changed"] and methods(op) == ["GET"]


def test_unsupported_action_fails_without_post(monkeypatch):
    op = FakeOpener(activity(supported=("RETRY",)))
    out = run(monkeypatch, op)
    assert out["failed"] and "RUNNING" in out["msg"] and methods(op) == ["GET"]


def test_unknown_activity_fails(monkeypatch):
    op = FakeOpener(http_error(404, {"message": "nope"}))
    out = run(monkeypatch, op)
    assert out["failed"] and methods(op) == ["GET"]


def test_retry_with_options_body(monkeypatch):
    op = FakeOpener(activity("COMPLETED"), ACCEPTED)
    out = run(monkeypatch, op, action="retry", confirm=False, retry_options=["FROM_FAILED_STEP", "NO_AUDIT_LOG"])
    assert out["changed"]
    assert urlsplit(op.calls[1][0]).path == "/api/v3/activities/a1/retry"
    assert json.loads(op.calls[1][1]["data"]) == {"retryOptions": ["FROM_FAILED_STEP", "NO_AUDIT_LOG"]}


def test_retry_without_options_sends_empty_body(monkeypatch):
    op = FakeOpener(activity("COMPLETED"), ACCEPTED)
    run(monkeypatch, op, action="retry")
    assert json.loads(op.calls[1][1]["data"]) == {}


def test_retry_wait_polls_new_activity(monkeypatch):
    done = Resp({"id": "a2", "state": "COMPLETED", "result": {"status": "OK"}})
    op = FakeOpener(activity("COMPLETED"), ACCEPTED, done)
    out = run(monkeypatch, op, action="retry", wait=True)
    assert out["activity"]["id"] == "a2" and urlsplit(op.calls[2][0]).path == "/api/v3/activities/a2"


def test_retry_wait_without_activity_id_fails(monkeypatch):
    op = FakeOpener(activity("COMPLETED"), Resp({}, 202))
    out = run(monkeypatch, op, action="retry", wait=True)
    assert out["failed"] and "activityId" in out["msg"]


def test_cancel_wait_canceled_is_success(monkeypatch):
    done = Resp({"id": "a1", "state": "COMPLETED", "result": {"status": "CANCELED"}})
    op = FakeOpener(activity(), ACCEPTED, done)
    out = run(monkeypatch, op, wait=True)
    assert not out["failed"] and out["changed"] and out["activity"]["result"]["status"] == "CANCELED"
    assert urlsplit(op.calls[2][0]).path == "/api/v3/activities/a1"


def test_check_mode_sends_no_post(monkeypatch):
    op = FakeOpener(activity())
    out = run(monkeypatch, op, check_mode=True, wait=True)
    assert out["changed"] and methods(op) == ["GET"]
