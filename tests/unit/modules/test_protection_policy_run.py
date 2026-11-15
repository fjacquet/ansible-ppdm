import json
from urllib.parse import urlsplit

from ansible_collections.fjacquet.ppdm.plugins.modules import protection_policy_run
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    listing,
    methods,
    run_module,
)

POLICY = {"id": "p1", "name": "gold"}
STARTED = Resp({"results": [{"activityId": "a1", "objectiveId": "o1", "status": "SUCCESS"}]}, 202)


def act(status):
    return Resp({"id": "a1", "state": "COMPLETED", "result": {"status": status}})


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    kw.setdefault("policy", "gold")
    return run_module(monkeypatch, protection_policy_run, op, check_mode=check, **kw)


def test_body_and_name_resolution(monkeypatch):
    op = FakeOpener(listing(POLICY), STARTED)
    out = run(monkeypatch, op, asset_ids=["x1"], objective_ids=["o1", "o2"])
    assert out["changed"] and out["results"][0]["activityId"] == "a1" and methods(op) == ["GET", "POST"]
    assert urlsplit(op.calls[1][0]).path == "/api/v3/protections"
    assert json.loads(op.calls[1][1]["data"]) == {
        "policy": {"id": "p1", "objectives": [{"id": "o1"}, {"id": "o2"}]},
        "source": {"assetIds": ["x1"]},
    }


def test_policy_by_id_and_group_only(monkeypatch):
    op = FakeOpener(listing(), listing(POLICY), STARTED)
    run(monkeypatch, op, policy="p1", protection_group_ids=["g1"])
    assert json.loads(op.calls[2][1]["data"]) == {"policy": {"id": "p1"}, "source": {"protectionGroupIds": ["g1"]}}


def test_no_target_fails_before_any_request(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op)
    assert out["failed"] and "asset_ids" in out["msg"] and op.calls == []


def test_unknown_policy_fails(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(), listing()), asset_ids=["x1"])
    assert out["failed"] and "not found" in out["msg"]


def test_check_mode_sends_nothing(monkeypatch):
    op = FakeOpener(listing(POLICY))
    out = run(monkeypatch, op, asset_ids=["x1"], check_mode=True)
    assert out["changed"] and methods(op) == ["GET"]


def test_wait_ok(monkeypatch):
    op = FakeOpener(listing(POLICY), STARTED, act("OK"))
    out = run(monkeypatch, op, asset_ids=["x1"], wait=True)
    assert out["changed"] and out["activities"][0]["id"] == "a1" and "warnings" not in out


def test_wait_failed(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(POLICY), STARTED, act("FAILED")), asset_ids=["x1"], wait=True)
    assert out["failed"] and "FAILED" in out["msg"]


def test_wait_ok_with_errors_warns(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(POLICY), STARTED, act("OK_WITH_ERRORS")), asset_ids=["x1"], wait=True)
    assert not out["failed"] and out["warnings"]


def test_entry_without_activity_fails_with_wait(monkeypatch):
    skipped = Resp({"results": [{"objectiveId": "o1", "status": "FAILED", "reason": "disabled"}]}, 202)
    out = run(monkeypatch, FakeOpener(listing(POLICY), skipped), asset_ids=["x1"], wait=True)
    assert out["failed"] and "disabled" in out["msg"]


def test_entry_without_activity_id_not_failed_status_fails_with_wait(monkeypatch):
    r = Resp({"results": [{"objectiveId": "o1", "status": "SUCCESS"}]}, 202)
    out = run(monkeypatch, FakeOpener(listing(POLICY), r), asset_ids=["x1"], wait=True)
    assert out["failed"] and "o1" in out["msg"]


def test_entry_without_activity_warns_without_wait(monkeypatch):
    skipped = Resp({"results": [{"objectiveId": "o1", "status": "FAILED", "reason": "disabled"}]}, 202)
    out = run(monkeypatch, FakeOpener(listing(POLICY), skipped), asset_ids=["x1"])
    assert not out["failed"] and "disabled" in out["warnings"][0]


def act2(i, status):
    return Resp({"id": i, "state": "COMPLETED", "result": {"status": status}})


TWO = Resp({"results": [{"activityId": "a1", "objectiveId": "o1"}, {"activityId": "a2", "objectiveId": "o2"}]}, 202)


def test_multi_one_failed_keeps_context(monkeypatch):
    op = FakeOpener(listing(POLICY), TWO, act2("a1", "OK"), act2("a2", "FAILED"))
    out = run(monkeypatch, op, asset_ids=["x1"], wait=True)
    assert out["failed"] and "a2" in out["msg"] and "FAILED" in out["msg"]
    assert len(out["results"]) == 2 and [a["id"] for a in out["activities"]] == ["a1", "a2"]


def test_multi_all_polled_even_after_failure(monkeypatch):
    op = FakeOpener(listing(POLICY), TWO, act2("a1", "FAILED"), act2("a2", "OK"))
    out = run(monkeypatch, op, asset_ids=["x1"], wait=True)
    assert out["failed"] and len(out["activities"]) == 2


def test_multi_ok_and_ok_with_errors(monkeypatch):
    op = FakeOpener(listing(POLICY), TWO, act2("a1", "OK"), act2("a2", "OK_WITH_ERRORS"))
    out = run(monkeypatch, op, asset_ids=["x1"], wait=True)
    assert not out["failed"] and len(out["activities"]) == 2 and len(out["warnings"]) == 1


def test_wait_with_empty_results_fails(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(POLICY), Resp({"results": []}, 202)), asset_ids=["x1"], wait=True)
    assert out["failed"] and "no result" in out["msg"]


def test_failed_entry_warns_without_wait(monkeypatch):
    r = Resp({"results": [{"activityId": "a1", "status": "FAILED", "reason": "boom"}]}, 202)
    out = run(monkeypatch, FakeOpener(listing(POLICY), r), asset_ids=["x1"])
    assert not out["failed"] and "boom" in out["warnings"][0]
