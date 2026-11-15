import json
from urllib.parse import urlsplit

from ansible_collections.fjacquet.ppdm.plugins.modules import discovery
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    http_error,
    listing,
    methods,
    run_module,
)

SRC = {"id": "s1", "name": "vc"}
STARTED = Resp({"id": "d1", "start": "/inventory-sources/s1", "taskId": "a1"}, 202)


def act(status):
    return Resp({"id": "a1", "state": "COMPLETED", "result": {"status": status}})


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    kw.setdefault("inventory_source", "vc")
    return run_module(monkeypatch, discovery, op, check_mode=check, **kw)


def test_body_and_name_resolution(monkeypatch):
    op = FakeOpener(listing(SRC), STARTED)
    out = run(monkeypatch, op, level="HOST", name="n", description="d", config={"schedule": {"x": 1}})
    assert out["changed"] and out["discovery"]["taskId"] == "a1" and methods(op) == ["GET", "POST"]
    assert urlsplit(op.calls[1][0]).path == "/api/v2/discoveries"
    assert json.loads(op.calls[1][1]["data"]) == {
        "start": "/inventory-sources/s1",
        "level": "HOST",
        "name": "n",
        "description": "d",
        "schedule": {"x": 1},
    }


def test_minimal_body_and_id_lookup(monkeypatch):
    op = FakeOpener(listing(), listing(SRC), STARTED)
    run(monkeypatch, op, inventory_source="s1")
    assert json.loads(op.calls[2][1]["data"]) == {"start": "/inventory-sources/s1"}


def test_unknown_source_fails(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(), listing()))
    assert out["failed"] and "not found" in out["msg"]


def test_bad_level_rejected(monkeypatch):
    op = FakeOpener()
    assert run(monkeypatch, op, level="Nope")["failed"] and op.calls == []


def test_config_collision_fails_before_post(monkeypatch):
    op = FakeOpener(listing(SRC))
    out = run(monkeypatch, op, config={"start": "/x"})
    assert out["failed"] and "start" in out["msg"] and methods(op) == ["GET"]


def test_check_mode_sends_nothing(monkeypatch):
    op = FakeOpener(listing(SRC))
    out = run(monkeypatch, op, check_mode=True)
    assert out["changed"] and methods(op) == ["GET"]


def test_wait_uses_task_id(monkeypatch):
    op = FakeOpener(listing(SRC), STARTED, act("OK"))
    out = run(monkeypatch, op, wait=True)
    assert out["activity"]["id"] == "a1" and urlsplit(op.calls[2][0]).path == "/api/v3/activities/a1"


def test_wait_failed(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(SRC), STARTED, act("FAILED")), wait=True)
    assert out["failed"] and "FAILED" in out["msg"]


def test_wait_ok_with_errors_warns(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(SRC), STARTED, act("OK_WITH_ERRORS")), wait=True)
    assert not out["failed"] and out["warnings"]


def test_wait_without_task_id_fails(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(SRC), Resp({"id": "d1"}, 202)), wait=True)
    assert out["failed"] and "taskId" in out["msg"]


def test_409_fails(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(SRC), http_error(409, {"message": "running"})))
    assert out["failed"] and "already running" in out["msg"]


def test_409_ignored(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(SRC), http_error(409, {"message": "running"})), ignore_running=True)
    assert not out["failed"] and not out["changed"] and "already running" in out["msg"]
