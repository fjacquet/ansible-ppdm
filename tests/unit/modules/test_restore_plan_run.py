import json
from urllib.parse import urlsplit

from ansible_collections.fjacquet.ppdm.plugins.modules import restore_plan_run
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    http_error,
    listing,
    methods,
    run_module,
)

PLAN = {"id": "r1", "name": "dr-web"}
STARTED = Resp({"executionType": "IMMEDIATELY", "activities": [{"activityId": "a1", "restoreGroupId": "g1"}]}, 201)
TWO = Resp(
    {
        "executionType": "IMMEDIATELY",
        "activities": [{"activityId": "a1", "restoreGroupId": "g1"}, {"activityId": "a2", "restoreGroupId": "g2"}],
    },
    201,
)


def act(i, status):
    return Resp({"id": i, "state": "COMPLETED", "result": {"status": status}})


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    kw.setdefault("plan", "dr-web")
    kw.setdefault("confirm", True)
    return run_module(monkeypatch, restore_plan_run, op, check_mode=check, **kw)


def test_without_confirm_never_connects(monkeypatch):
    def boom(module):
        raise AssertionError("client_from_module called")

    monkeypatch.setattr(restore_plan_run, "client_from_module", boom)
    for check in (False, True):
        op = FakeOpener()
        out = run(monkeypatch, op, confirm=False, check_mode=check)
        assert out["failed"] and "confirm" in out["msg"] and op.calls == []


def test_run_by_name(monkeypatch):
    op = FakeOpener(listing(PLAN), STARTED)
    out = run(monkeypatch, op)
    assert out["changed"] and out["result"]["activities"][0]["activityId"] == "a1" and "activities" not in out
    assert methods(op) == ["GET", "POST"]
    assert urlsplit(op.calls[1][0]).path == "/api/v2/restore-plans/r1/execute"
    assert json.loads(op.calls[1][1]["data"]) == {"executionType": "IMMEDIATELY"}


def test_run_by_id_scheduled(monkeypatch):
    sched = Resp({"executionType": "SCHEDULE", "activities": [{"activityId": "a1"}]}, 202)
    op = FakeOpener(listing(), listing(PLAN), sched)
    out = run(monkeypatch, op, plan="r1", execution_type="SCHEDULE", schedule_time="2026-12-01T22:00:00Z")
    assert out["changed"]
    assert json.loads(op.calls[2][1]["data"]) == {"executionType": "SCHEDULE", "scheduleTime": "2026-12-01T22:00:00Z"}


def test_schedule_without_time_fails(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, execution_type="SCHEDULE")
    assert out["failed"] and "schedule_time" in out["msg"] and op.calls == []


def test_immediately_with_time_fails(monkeypatch):
    out = run(monkeypatch, FakeOpener(), schedule_time="2026-12-01T22:00:00Z")
    assert out["failed"] and "schedule_time" in out["msg"]


def test_wait_with_schedule_fails(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, execution_type="SCHEDULE", schedule_time="2026-12-01T22:00:00Z", wait=True)
    assert out["failed"] and "wait" in out["msg"] and op.calls == []


def test_wait_ok(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(PLAN), STARTED, act("a1", "OK")), wait=True)
    assert out["changed"] and [a["id"] for a in out["activities"]] == ["a1"]


def test_wait_two_one_failed_reports_both(monkeypatch):
    op = FakeOpener(listing(PLAN), TWO, act("a1", "FAILED"), act("a2", "OK"))
    out = run(monkeypatch, op, wait=True)
    assert out["failed"] and "a1" in out["msg"] and "FAILED" in out["msg"]
    assert [a["id"] for a in out["activities"]] == ["a1", "a2"] and len(out["result"]["activities"]) == 2


def test_wait_two_second_failed(monkeypatch):
    op = FakeOpener(listing(PLAN), TWO, act("a1", "OK"), act("a2", "FAILED"))
    out = run(monkeypatch, op, wait=True)
    assert out["failed"] and "a2" in out["msg"] and [a["id"] for a in out["activities"]] == ["a1", "a2"]


def test_wait_warn_status(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(PLAN), STARTED, act("a1", "OK_WITH_ERRORS")), wait=True)
    assert not out["failed"] and out["warnings"]


def test_wait_empty_activities_fails(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(PLAN), Resp({"activities": []}, 201)), wait=True)
    assert out["failed"] and "no activit" in out["msg"]


def test_entry_without_activity_id(monkeypatch):
    r = Resp({"activities": [{"restoreGroupId": "g1"}]}, 201)
    out = run(monkeypatch, FakeOpener(listing(PLAN), r), wait=True)
    assert out["failed"] and "g1" in out["msg"]
    out = run(monkeypatch, FakeOpener(listing(PLAN), r))
    assert not out["failed"] and "g1" in out["warnings"][0]


def test_empty_activities_warns_without_wait(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(PLAN), Resp({"activities": []}, 201)))
    assert not out["failed"] and out["warnings"]


def test_already_running_409(monkeypatch):
    op = FakeOpener(listing(PLAN), http_error(409, {"message": "plan is running"}))
    out = run(monkeypatch, op)
    assert out["failed"] and "plan is running" in out["msg"]


def test_check_mode_sends_no_post(monkeypatch):
    op = FakeOpener(listing(PLAN))
    out = run(monkeypatch, op, check_mode=True, wait=True)
    assert out["changed"] and methods(op) == ["GET"]


def test_unknown_plan_fails(monkeypatch):
    op = FakeOpener(listing(), listing())
    out = run(monkeypatch, op)
    assert out["failed"] and "not found" in out["msg"] and methods(op) == ["GET", "GET"]
