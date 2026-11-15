import json
from urllib.parse import urlsplit

from ansible_collections.fjacquet.ppdm.plugins.modules import protection_rule_run
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    listing,
    methods,
    run_module,
)

RULE = {"id": "r1", "name": "gold-vms"}
R2 = {"id": "r2", "name": "x"}
NEW = {"name": "gold-vms", "inventorySourceType": "VMWARE_VIRTUAL_MACHINE"}


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    return run_module(monkeypatch, protection_rule_run, op, check_mode=check, **kw)


def test_execution_body_and_name_resolution(monkeypatch):
    op = FakeOpener(listing(RULE), listing(), listing(R2), Resp(None))
    out = run(monkeypatch, op, rules=["gold-vms", "r2"], inventory_source_type="VMWARE_VIRTUAL_MACHINE")
    assert out["changed"] and methods(op) == ["GET", "GET", "GET", "POST"]
    assert urlsplit(op.calls[3][0]).path == "/api/v2/protection-rules-execution"
    assert json.loads(op.calls[3][1]["data"]) == {
        "assetRuleIds": ["r1", R2["id"]],
        "inventorySourceType": "VMWARE_VIRTUAL_MACHINE",
    }


def test_no_target_fails_before_any_request(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op)
    assert out["failed"] and "rules" in out["msg"] and op.calls == []


def test_unknown_rule_fails(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(), listing()), rules=["nope"])
    assert out["failed"] and "not found" in out["msg"]


def test_check_mode_sends_nothing(monkeypatch):
    op = FakeOpener(listing(RULE))
    out = run(monkeypatch, op, rules=["gold-vms"], check_mode=True)
    assert out["changed"] and methods(op) == ["GET"]


def test_invalid_inventory_source_type(monkeypatch):
    op = FakeOpener()
    assert run(monkeypatch, op, inventory_source_type="NOPE")["failed"] and op.calls == []


def test_preview_is_read_only_even_in_check_mode(monkeypatch):
    conflicts = {"content": [{"name": "gold-vms"}]}
    op = FakeOpener(Resp(conflicts))
    out = run(monkeypatch, op, preview=True, rule=NEW, check_mode=True)
    assert out["changed"] is False and out["preview"] == conflicts and methods(op) == ["POST"]
    assert urlsplit(op.calls[0][0]).path == "/api/v2/protection-rules-conflicts-preview"
    assert json.loads(op.calls[0][1]["data"]) == {"previewAction": "CREATE", "protectionRule": NEW}


def test_preview_edit_and_validation(monkeypatch):
    op = FakeOpener(Resp({"content": []}))
    run(monkeypatch, op, preview=True, rule=NEW, preview_action="EDIT")
    assert json.loads(op.calls[0][1]["data"])["previewAction"] == "EDIT"
    op = FakeOpener()
    assert run(monkeypatch, op, preview=True)["failed"] and op.calls == []
    assert run(monkeypatch, op, preview=True, rule={"action": "NOPE"})["failed"] and op.calls == []


def test_preview_and_run_options_are_exclusive(monkeypatch):
    op = FakeOpener()
    assert run(monkeypatch, op, preview=True, rule=NEW, rules=["x"])["failed"]
    assert run(monkeypatch, op, preview=True, rule=NEW, inventory_source_type="KUBERNETES")["failed"]
    assert run(monkeypatch, op, rules=["x"], rule=NEW)["failed"]
    assert run(monkeypatch, op, rules=["x"], preview_action="EDIT")["failed"]
    assert op.calls == []


def test_preview_conditions_must_be_a_list(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, preview=True, rule={"name": "x", "conditions": {"a": 1}})
    assert out["failed"] and "conditions must be a list" in out["msg"] and op.calls == []
