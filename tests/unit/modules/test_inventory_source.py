import json

from ansible_collections.fjacquet.ppdm.plugins.modules import inventory_source
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import FakeOpener, Resp, listing, methods, run_module

ARGS = dict(name="vc1", type="VCENTER", address="vc.example.com", source_port=443, credential_id="c1")
EXISTING = {"id": "1", "name": "vc1", "type": "VCENTER", "address": "vc.example.com", "port": 443,
            "credentials": {"id": "c1"}, "version": "8", "lastDiscovered": "t", "_links": {}}


def run(monkeypatch, op, **kw):
    return run_module(monkeypatch, inventory_source, op, **dict(ARGS, **kw))


def test_inventory_source_create(monkeypatch):
    op = FakeOpener(listing(), Resp({"id": "9"}, 201))
    out = run(monkeypatch, op, config={"details": {"vCenter": {"x": 1}}})
    assert out["changed"] and methods(op) == ["GET", "POST"]
    assert json.loads(op.calls[1][1]["data"]) == {
        "name": "vc1", "type": "VCENTER", "address": "vc.example.com", "port": 443,
        "credentials": {"id": "c1"}, "details": {"vCenter": {"x": 1}}}


def test_inventory_source_idempotent(monkeypatch):
    op = FakeOpener(listing(EXISTING))
    out = run(monkeypatch, op)
    assert not out["changed"] and methods(op) == ["GET"]


def test_inventory_source_update_on_diff(monkeypatch):
    op = FakeOpener(listing(EXISTING), Resp({"id": "1"}))
    out = run(monkeypatch, op, address="vc2.example.com")
    assert out["changed"] and methods(op) == ["GET", "PUT"]
    sent = json.loads(op.calls[1][1]["data"])
    assert sent["address"] == "vc2.example.com" and "version" not in sent


def test_inventory_source_check_mode(monkeypatch):
    op = FakeOpener(listing(EXISTING))
    out = run_module(monkeypatch, inventory_source, op, check_mode=True, **dict(ARGS, address="x"))
    assert out["changed"] and methods(op) == ["GET"]


def test_inventory_source_absent_missing_is_noop(monkeypatch):
    op = FakeOpener(listing())
    out = run_module(monkeypatch, inventory_source, op, name="vc1", state="absent")
    assert not out["changed"] and methods(op) == ["GET"]


def test_inventory_source_absent_deletes(monkeypatch):
    op = FakeOpener(listing(EXISTING), Resp(None, 204))
    out = run_module(monkeypatch, inventory_source, op, name="vc1", state="absent")
    assert out["changed"] and methods(op) == ["GET", "DELETE"]


def test_inventory_source_duplicate_key_fails(monkeypatch):
    op = FakeOpener(listing(EXISTING, dict(EXISTING, id="2")))
    out = run(monkeypatch, op)
    assert out["failed"] and "1" in out["msg"] and "2" in out["msg"] and methods(op) == ["GET"]
