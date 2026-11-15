import json

from ansible_collections.fjacquet.ppdm.plugins.modules import storage_system
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    listing,
    methods,
    run_module,
)

EXISTING = {
    "id": "1",
    "name": "dd1",
    "type": "DATA_DOMAIN_SYSTEM",
    "description": "old",
    "lastDiscoveryAt": "t",
    "_embedded": {},
    "_links": {},
}


def run(monkeypatch, op, check_mode=False, **kw):
    return run_module(monkeypatch, storage_system, op, check_mode=check_mode, **dict(name="dd1", **kw))


def test_storage_system_update_on_diff(monkeypatch):
    op = FakeOpener(listing(EXISTING), listing(EXISTING), Resp({"id": "1"}))
    out = run(monkeypatch, op, description="new")
    assert out["changed"] and methods(op) == ["GET", "GET", "PUT"]
    sent = json.loads(op.calls[2][1]["data"])
    assert sent["description"] == "new" and sent["type"] == "DATA_DOMAIN_SYSTEM" and "lastDiscoveryAt" not in sent


def test_storage_system_idempotent(monkeypatch):
    op = FakeOpener(listing(EXISTING), listing(EXISTING))
    out = run(monkeypatch, op, description="old")
    assert not out["changed"] and methods(op) == ["GET", "GET"]


def test_storage_system_config_passthrough(monkeypatch):
    op = FakeOpener(listing(EXISTING), listing(EXISTING), Resp({"id": "1"}))
    out = run(monkeypatch, op, config={"local": True})
    assert out["changed"] and json.loads(op.calls[2][1]["data"])["local"] is True


def test_storage_system_check_mode(monkeypatch):
    op = FakeOpener(listing(EXISTING), listing(EXISTING))
    out = run(monkeypatch, op, check_mode=True, description="new")
    assert out["changed"] and methods(op) == ["GET", "GET"]


def test_storage_system_missing_fails(monkeypatch):
    op = FakeOpener(listing())
    out = run(monkeypatch, op, description="new")
    assert out["failed"] and "dd1" in out["msg"] and methods(op) == ["GET"]
