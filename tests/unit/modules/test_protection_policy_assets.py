import json
from urllib.parse import urlsplit

from ansible_collections.fjacquet.ppdm.plugins.modules import protection_policy_assets
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    listing,
    methods,
    run_module,
)

POLICY = {"id": "p1", "name": "gold"}


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    kw.setdefault("policy", "gold")
    return run_module(monkeypatch, protection_policy_assets, op, check_mode=check, **kw)


def assigned(*ids):
    return listing(*[{"id": i} for i in ids])


def test_assign_sends_only_missing(monkeypatch):
    op = FakeOpener(listing(POLICY), assigned("a1", "other"), Resp(None, 204))
    out = run(monkeypatch, op, asset_ids=["a1", "a2"])
    assert out["changed"] and out["assigned"] == ["a1", "a2"] and methods(op) == ["GET", "GET", "POST"]
    assert urlsplit(op.calls[1][0]).path == "/api/v2/protection-policies/p1/asset-assignments"
    assert urlsplit(op.calls[2][0]).path == "/api/v2/protection-policies/p1/asset-assignments"
    assert json.loads(op.calls[2][1]["data"]) == ["a2"]


def test_already_assigned_sends_nothing(monkeypatch):
    op = FakeOpener(listing(POLICY), assigned("a1", "a2"))
    out = run(monkeypatch, op, asset_ids=["a1", "a2"])
    assert not out["changed"] and set(methods(op)) == {"GET"}


def test_unassign_sends_only_present(monkeypatch):
    op = FakeOpener(listing(POLICY), assigned("a1"), Resp(None, 204))
    out = run(monkeypatch, op, state="absent", asset_ids=["a1", "a2"])
    assert out["changed"] and out["assigned"] == [] and methods(op) == ["GET", "GET", "POST"]
    assert urlsplit(op.calls[2][0]).path == "/api/v2/protection-policies/p1/asset-unassignments"
    assert json.loads(op.calls[2][1]["data"]) == ["a1"]


def test_unassign_absent_sends_nothing(monkeypatch):
    op = FakeOpener(listing(POLICY), assigned("other"))
    out = run(monkeypatch, op, state="absent", asset_ids=["a1"])
    assert not out["changed"] and set(methods(op)) == {"GET"}


def test_policy_found_by_id(monkeypatch):
    op = FakeOpener(listing(), listing(POLICY), assigned(), Resp(None, 204))
    assert run(monkeypatch, op, policy="p1", asset_ids=["a1"])["changed"]


def test_unknown_policy_fails(monkeypatch):
    op = FakeOpener(listing(), listing())
    out = run(monkeypatch, op, asset_ids=["a1"])
    assert out["failed"] and "not found" in out["msg"] and set(methods(op)) == {"GET"}


def test_check_mode_sends_nothing(monkeypatch):
    op = FakeOpener(listing(POLICY), assigned())
    out = run(monkeypatch, op, asset_ids=["a1"], check_mode=True)
    assert out["changed"] and set(methods(op)) == {"GET"}
