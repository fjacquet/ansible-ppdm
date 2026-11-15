import json
from urllib.parse import urlsplit

from ansible_collections.fjacquet.ppdm.plugins.modules import protection_rule
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    listing,
    methods,
    run_module,
)

COND = {"assetAttributeName": "tag", "operator": "EQUALS", "assetAttributeValues": ["gold"]}
RULE = {
    "id": "r1",
    "name": "gold-vms",
    "action": "MOVE_TO_GROUP",
    "inventorySourceType": "VMWARE_VIRTUAL_MACHINE",
    "actionResult": "p1",
    "priority": 5,
    "conditions": [dict(COND, assetAttributeValue="gold")],
    "assignedAssetsCount": 3,
    "displayDescription": "tag = gold",
    "lastRunAt": "2026-01-01T00:00:00Z",
    "_embedded": {},
}
POLICY = {"id": "p1", "name": "vm-gold"}


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    kw.setdefault("name", "gold-vms")
    return run_module(monkeypatch, protection_rule, op, check_mode=check, **kw)


def body(op, i):
    return json.loads(op.calls[i][1]["data"])


def test_create_resolves_policy_name(monkeypatch):
    op = FakeOpener(listing(POLICY), listing(), Resp({"id": "r1"}, 201))
    out = run(
        monkeypatch,
        op,
        action="MOVE_TO_GROUP",
        inventory_source_type="VMWARE_VIRTUAL_MACHINE",
        priority=5,
        conditions=[COND],
        condition_connector="AND",
        policy="vm-gold",
        tenant="t1",
        config={"logicalOperator": "AND"},
    )
    assert out["changed"] and out["protection_rule"]["id"] == "r1" and methods(op) == ["GET", "GET", "POST"]
    assert urlsplit(op.calls[2][0]).path == "/api/v2/protection-rules"
    assert body(op, 2) == {
        "name": "gold-vms",
        "action": "MOVE_TO_GROUP",
        "inventorySourceType": "VMWARE_VIRTUAL_MACHINE",
        "priority": 5,
        "conditions": [COND],
        "conditionConnector": "AND",
        "actionResult": "p1",
        "tenant": {"id": "t1"},
        "logicalOperator": "AND",
    }


def test_policy_by_id(monkeypatch):
    op = FakeOpener(listing(), listing(POLICY), listing(), Resp({"id": "r1"}, 201))
    run(monkeypatch, op, policy="p1")
    assert body(op, 3)["actionResult"] == "p1"


def test_unknown_policy_fails(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(), listing()), policy="nope")
    assert out["failed"] and "not found" in out["msg"]


def test_idempotent_ignores_server_fields(monkeypatch):
    op = FakeOpener(listing(POLICY), listing(RULE))
    out = run(monkeypatch, op, action="MOVE_TO_GROUP", priority=5, conditions=[COND], policy="vm-gold")
    assert not out["changed"] and methods(op) == ["GET", "GET"]


def test_update_puts_without_readonly(monkeypatch):
    op = FakeOpener(listing(RULE), Resp(dict(RULE, priority=9)))
    out = run(monkeypatch, op, priority=9)
    assert out["changed"] and methods(op) == ["GET", "PUT"]
    assert urlsplit(op.calls[1][0]).path == "/api/v2/protection-rules/r1"
    sent = body(op, 1)
    assert sent["priority"] == 9 and sent["id"] == "r1"
    assert not {"assignedAssetsCount", "displayDescription", "lastRunAt", "_embedded"} & set(sent)
    assert out["diff"]["before"]["priority"] == 5 and out["diff"]["after"]["priority"] == 9


def test_check_mode(monkeypatch):
    op = FakeOpener(listing())
    out = run(monkeypatch, op, action="MOVE_TO_GROUP", check_mode=True)
    assert out["changed"] and methods(op) == ["GET"]


def test_absent(monkeypatch):
    op = FakeOpener(listing(RULE), Resp(None))
    out = run(monkeypatch, op, state="absent")
    assert out["changed"] and methods(op) == ["GET", "DELETE"]
    assert not run(monkeypatch, FakeOpener(listing()), state="absent")["changed"]


def test_invalid_enums_fail_before_any_request(monkeypatch):
    for kw in ({"action": "DELETE"}, {"inventory_source_type": "NOPE"}, {"condition_connector": "XOR"}):
        op = FakeOpener()
        assert run(monkeypatch, op, **kw)["failed"] and op.calls == []
    op = FakeOpener()
    out = run(monkeypatch, op, conditions=[{"assetAttributeName": "tag", "operator": "LIKE"}])
    assert out["failed"] and "operator" in out["msg"] and op.calls == []
    assert run(monkeypatch, op, conditions=["tag"])["failed"] and op.calls == []


def test_config_collision_fails(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, priority=1, config={"priority": 2})
    assert out["failed"] and "priority" in out["msg"] and op.calls == []


def test_bad_config_sends_nothing_even_with_policy(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, policy="vm-gold", priority=1, config={"priority": 2})
    assert out["failed"] and op.calls == []


def test_config_cannot_carry_action_result(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, config={"actionResult": "p9"})
    assert out["failed"] and "actionResult" in out["msg"] and op.calls == []


def test_update_check_mode_sends_no_put(monkeypatch):
    op = FakeOpener(listing(RULE))
    out = run(monkeypatch, op, priority=9, check_mode=True)
    assert out["changed"] and methods(op) == ["GET"]


def test_changed_conditions_put(monkeypatch):
    other = dict(COND, assetAttributeValues=["silver"])
    op = FakeOpener(listing(RULE), Resp(RULE))
    out = run(monkeypatch, op, conditions=[other])
    assert out["changed"] and methods(op) == ["GET", "PUT"] and body(op, 1)["conditions"] == [other]
