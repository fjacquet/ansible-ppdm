import json

from ansible_collections.fjacquet.ppdm.plugins.modules import restore_plan
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    http_error,
    listing,
    methods,
    run_module,
)

GROUP = {"name": "web", "assetType": "VMWARE_VIRTUAL_MACHINE"}
SCHEDULE = {"startTime": "2026-12-01T00:00:00Z"}
PLAN = {
    "id": "rp1",
    "name": "dr-web",
    "description": "d",
    "fallbackStrategy": "CONTINUE_ON_FAILURE",
    "restoreGroups": [dict(GROUP, id="g1", state="IDLE", stateReason="none")],
    "schedule": SCHEDULE,
    "createdAt": "2026-01-01T00:00:00Z",
    "updatedAt": "2026-01-01T00:00:00Z",
    "lastRun": {"id": "x"},
    "state": "IDLE",
    "stateReason": "ok",
}
ARGS = dict(
    description="d",
    fallback_strategy="CONTINUE_ON_FAILURE",
    restore_groups=[GROUP],
    schedule=SCHEDULE,
)


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    kw.setdefault("name", "dr-web")
    return run_module(monkeypatch, restore_plan, op, check_mode=check, **kw)


def body(op, i):
    return json.loads(op.calls[i][1]["data"])


def test_create_posts_exact_body(monkeypatch):
    op = FakeOpener(listing(), Resp({"id": "rp1"}, 201))
    out = run(monkeypatch, op, **ARGS)
    assert out["changed"] and out["restore_plan"]["id"] == "rp1" and methods(op) == ["GET", "POST"]
    assert op.calls[1][0].endswith("/api/v2/restore-plans")
    assert body(op, 1) == {
        "name": "dr-web",
        "description": "d",
        "fallbackStrategy": "CONTINUE_ON_FAILURE",
        "restoreGroups": [GROUP],
        "schedule": SCHEDULE,
    }


def test_noop_when_server_echoes_readonly_and_group_fields(monkeypatch):
    op = FakeOpener(listing(PLAN))
    out = run(monkeypatch, op, **ARGS)
    assert out["changed"] is False and methods(op) == ["GET"]


def test_update_patches_on_difference(monkeypatch):
    op = FakeOpener(listing(PLAN), Resp(dict(PLAN, description="new")))
    args = {**ARGS, "description": "new"}
    out = run(monkeypatch, op, **args)
    assert out["changed"] and methods(op) == ["GET", "PATCH"]
    assert op.calls[1][0].endswith("/api/v2/restore-plans/rp1")
    assert body(op, 1)["description"] == "new" and "id" not in body(op, 1) and "state" not in body(op, 1)


def test_update_patches_when_group_differs(monkeypatch):
    op = FakeOpener(listing(PLAN), Resp(PLAN))
    args = {**ARGS, "restore_groups": [{**GROUP, "name": "db"}]}
    out = run(monkeypatch, op, **args)
    assert out["changed"] and methods(op) == ["GET", "PATCH"]


def test_absent_deletes(monkeypatch):
    op = FakeOpener(listing(PLAN), Resp(None, 204))
    out = run(monkeypatch, op, state="absent")
    assert out["changed"] and methods(op) == ["GET", "DELETE"]


def test_delete_409_fails_with_message(monkeypatch):
    op = FakeOpener(listing(PLAN), http_error(409, {"message": "plan is running"}))
    out = run(monkeypatch, op, state="absent")
    assert out["failed"] and "plan is running" in out["msg"]


def test_check_mode_create_sends_no_write(monkeypatch):
    op = FakeOpener(listing())
    assert run(monkeypatch, op, check_mode=True, **ARGS)["changed"] and methods(op) == ["GET"]


def test_check_mode_delete_sends_no_write(monkeypatch):
    op = FakeOpener(listing(PLAN))
    assert run(monkeypatch, op, check_mode=True, state="absent")["changed"] and methods(op) == ["GET"]


def test_ambiguous_name_fails(monkeypatch):
    op = FakeOpener(listing(PLAN, dict(PLAN, id="rp2")))
    out = run(monkeypatch, op, **ARGS)
    assert out["failed"] and "rp1" in out["msg"] and "rp2" in out["msg"] and methods(op) == ["GET"]


def test_config_collision_fails_before_any_request(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, config={"schedule": {}}, **ARGS)
    assert out["failed"] and op.calls == []
