import json
from urllib.parse import urlsplit

from ansible_collections.fjacquet.ppdm.plugins.modules import resource_group
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    listing,
    methods,
    run_module,
)

GROUP = {
    "id": "g1",
    "name": "web",
    "description": "d",
    "createdAt": "2026-01-01T00:00:00Z",
    "createdBy": "admin",
    "numberOfResources": 3,
    "updatedAt": "2026-01-01T00:00:00Z",
}


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    kw.setdefault("name", "web")
    return run_module(monkeypatch, resource_group, op, check_mode=check, **kw)


def body(op, i):
    return json.loads(op.calls[i][1]["data"])


def test_create(monkeypatch):
    op = FakeOpener(listing(), Resp({"id": "g1", "name": "web"}, 201))
    out = run(monkeypatch, op, description="d")
    assert out["changed"] and out["resource_group"]["id"] == "g1" and methods(op) == ["GET", "POST"]
    assert urlsplit(op.calls[1][0]).path == "/api/v2/resource-groups"
    assert body(op, 1) == {"name": "web", "description": "d"}


def test_idempotent_ignores_readonly(monkeypatch):
    op = FakeOpener(listing(GROUP))
    out = run(monkeypatch, op, description="d")
    assert not out["changed"] and methods(op) == ["GET"]


def test_update_patches(monkeypatch):
    op = FakeOpener(listing(GROUP), Resp(dict(GROUP, description="new")))
    out = run(monkeypatch, op, description="new")
    assert out["changed"] and methods(op) == ["GET", "PATCH"]
    assert urlsplit(op.calls[1][0]).path == "/api/v2/resource-groups/g1"
    b = body(op, 1)
    assert b["description"] == "new" and not {"createdAt", "createdBy", "numberOfResources", "updatedAt"} & set(b)


def test_check_mode_sends_no_write(monkeypatch):
    op = FakeOpener(listing())
    assert run(monkeypatch, op, check_mode=True)["changed"] and methods(op) == ["GET"]
    op = FakeOpener(listing(GROUP))
    assert run(monkeypatch, op, check_mode=True, description="x")["changed"] and methods(op) == ["GET"]
    op = FakeOpener(listing(GROUP))
    assert run(monkeypatch, op, check_mode=True, state="absent")["changed"] and methods(op) == ["GET"]


def test_absent(monkeypatch):
    op = FakeOpener(listing(GROUP), Resp(None, 204))
    out = run(monkeypatch, op, state="absent")
    assert out["changed"] and methods(op) == ["GET", "DELETE"]
    assert urlsplit(op.calls[1][0]).path == "/api/v2/resource-groups/g1"
    op = FakeOpener(listing())
    assert not run(monkeypatch, op, state="absent")["changed"]


def test_ambiguous_name_fails(monkeypatch):
    op = FakeOpener(listing(GROUP, dict(GROUP, id="g2")))
    out = run(monkeypatch, op)
    assert out["failed"] and "g1" in out["msg"] and "g2" in out["msg"] and methods(op) == ["GET"]


def test_config_collision_fails_before_request(monkeypatch):
    op = FakeOpener()
    assert run(monkeypatch, op, description="a", config={"description": "b"})["failed"]
    assert run(monkeypatch, op, config={"id": "x"})["failed"] and op.calls == []


def test_config_passes_extra_keys(monkeypatch):
    op = FakeOpener(listing(), Resp({"id": "g1"}, 201))
    run(monkeypatch, op, config={"extra": 1})
    assert body(op, 1) == {"name": "web", "extra": 1}
