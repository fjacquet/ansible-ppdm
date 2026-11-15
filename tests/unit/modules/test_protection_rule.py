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

FILTER = {
    "objectType": "ASSET",
    "objectSubtype": "VMWARE_VIRTUAL_MACHINE",
    "type": "INCLUDE",
    "operator": "AND",
    "conditions": [
        {
            "operator": "AND",
            "conditions": [
                {"fieldName": "tags", "operator": "EQUALS", "fieldData": {"type": "STRING", "values": ["gold"]}}
            ],
        }
    ],
}
ARGS = [{"name": "PROTECTION_POLICY_ID", "values": ["p1"]}]
RULE = {
    "id": "r1",
    "name": "gold-vms",
    "priority": 5,
    "action": {"name": "ASSIGN_PROTECTION_POLICY", "args": ARGS},
    "filters": [FILTER],
    "uniqueHash": "abc",
    "status": "ACTIVE",
    "createdAt": "2026-01-01T00:00:00Z",
    "updatedAt": "2026-01-01T00:00:00Z",
    "lastRunAt": "2026-01-01T00:00:00Z",
    "lastMigratedAt": "2026-01-01T00:00:00Z",
}
POLICY = {"id": "p1", "name": "vm-gold"}
GROUP = {"id": "g1", "name": "web"}


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
        description="d",
        priority=5,
        action="ASSIGN_PROTECTION_POLICY",
        protection_policy="vm-gold",
        variant="SIMPLE",
        scopes=["ASSET"],
        categories=["LIST_VIEW"],
        filters=[FILTER],
    )
    assert out["changed"] and out["protection_rule"]["id"] == "r1" and methods(op) == ["GET", "GET", "POST"]
    assert urlsplit(op.calls[0][0]).path == "/api/v3/protection-policies"
    assert urlsplit(op.calls[2][0]).path == "/api/v3/rules"
    assert body(op, 2) == {
        "name": "gold-vms",
        "description": "d",
        "priority": 5,
        "action": {"name": "ASSIGN_PROTECTION_POLICY", "args": ARGS},
        "variant": "SIMPLE",
        "scopes": ["ASSET"],
        "categories": ["LIST_VIEW"],
        "filters": [FILTER],
    }


def test_create_with_policy_id_skips_lookup(monkeypatch):
    op = FakeOpener(listing(), Resp({"id": "r1"}, 201))
    run(monkeypatch, op, action="ASSIGN_PROTECTION_POLICY", protection_policy_id="p1")
    assert methods(op) == ["GET", "POST"] and body(op, 1)["action"] == {
        "name": "ASSIGN_PROTECTION_POLICY",
        "args": ARGS,
    }


def test_create_with_resource_group(monkeypatch):
    op = FakeOpener(listing(GROUP), listing(), Resp({"id": "r2"}, 201))
    run(monkeypatch, op, action="ASSIGN_RESOURCE_GROUP", resource_group="web")
    assert urlsplit(op.calls[0][0]).path == "/api/v2/resource-groups"
    assert body(op, 2)["action"] == {
        "name": "ASSIGN_RESOURCE_GROUP",
        "args": [{"name": "RESOURCE_GROUP_ID", "values": ["g1"]}],
    }


def test_idempotent_ignores_server_fields(monkeypatch):
    server = dict(RULE, action={"name": "ASSIGN_PROTECTION_POLICY", "args": [dict(ARGS[0], extra="x")]})
    op = FakeOpener(listing(POLICY), listing(server))
    out = run(
        monkeypatch, op, priority=5, action="ASSIGN_PROTECTION_POLICY", protection_policy="vm-gold", filters=[FILTER]
    )
    assert not out["changed"] and methods(op) == ["GET", "GET"]


def test_idempotent_when_server_adds_filter_fields(monkeypatch):
    echoed = dict(FILTER, displayOrder=1)
    op = FakeOpener(listing(dict(RULE, filters=[echoed])))
    assert not run(monkeypatch, op, filters=[FILTER])["changed"]


def test_update_patches_only_on_difference(monkeypatch):
    op = FakeOpener(listing(RULE), Resp(dict(RULE, priority=9)))
    out = run(monkeypatch, op, priority=9)
    assert out["changed"] and methods(op) == ["GET", "PATCH"]
    assert urlsplit(op.calls[1][0]).path == "/api/v3/rules/r1"
    sent = body(op, 1)
    assert sent["priority"] == 9
    assert not {"uniqueHash", "status", "createdAt", "updatedAt", "lastRunAt", "lastMigratedAt"} & set(sent)
    assert out["diff"]["before"]["priority"] == 5 and out["diff"]["after"]["priority"] == 9


def test_changed_filters_patch(monkeypatch):
    other = dict(FILTER, type="EXCLUDE")
    op = FakeOpener(listing(RULE), Resp(RULE))
    out = run(monkeypatch, op, filters=[other])
    assert out["changed"] and methods(op) == ["GET", "PATCH"] and body(op, 1)["filters"] == [other]


def test_changed_policy_patch(monkeypatch):
    op = FakeOpener(listing(RULE), Resp(RULE))
    out = run(monkeypatch, op, action="ASSIGN_PROTECTION_POLICY", protection_policy_id="p2")
    assert out["changed"] and body(op, 1)["action"]["args"] == [{"name": "PROTECTION_POLICY_ID", "values": ["p2"]}]


def test_check_mode_sends_no_write(monkeypatch):
    op = FakeOpener(listing())
    assert run(monkeypatch, op, priority=1, check_mode=True)["changed"] and methods(op) == ["GET"]
    op = FakeOpener(listing(RULE))
    assert run(monkeypatch, op, priority=9, check_mode=True)["changed"] and methods(op) == ["GET"]
    op = FakeOpener(listing(RULE))
    assert run(monkeypatch, op, state="absent", check_mode=True)["changed"] and methods(op) == ["GET"]


def test_absent(monkeypatch):
    op = FakeOpener(listing(RULE), Resp(None))
    out = run(monkeypatch, op, state="absent")
    assert out["changed"] and methods(op) == ["GET", "DELETE"]
    assert urlsplit(op.calls[1][0]).path == "/api/v3/rules/r1"
    assert not run(monkeypatch, FakeOpener(listing()), state="absent")["changed"]


def test_unknown_policy_fails_without_write(monkeypatch):
    op = FakeOpener(listing())
    out = run(monkeypatch, op, action="ASSIGN_PROTECTION_POLICY", protection_policy="nope")
    assert out["failed"] and "protection policy nope not found" in out["msg"] and methods(op) == ["GET"]


def test_unknown_resource_group_fails_without_write(monkeypatch):
    op = FakeOpener(listing())
    out = run(monkeypatch, op, action="ASSIGN_RESOURCE_GROUP", resource_group="nope")
    assert out["failed"] and "not found" in out["msg"] and methods(op) == ["GET"]


def test_ambiguous_rule_name_fails_listing_ids(monkeypatch):
    op = FakeOpener(listing(RULE, dict(RULE, id="r2")))
    out = run(monkeypatch, op, priority=1)
    assert out["failed"] and "r1" in out["msg"] and "r2" in out["msg"] and methods(op) == ["GET"]


def test_ambiguous_policy_name_fails(monkeypatch):
    op = FakeOpener(listing(POLICY, dict(POLICY, id="p9")))
    out = run(monkeypatch, op, action="ASSIGN_PROTECTION_POLICY", protection_policy="vm-gold")
    assert out["failed"] and "p9" in out["msg"] and methods(op) == ["GET"]


def test_policy_with_wrong_action_fails_before_request(monkeypatch):
    for kw in (
        {"action": "ASSIGN_RESOURCE_GROUP", "protection_policy": "vm-gold"},
        {"action": "ASSIGN_RESOURCE_GROUP", "protection_policy_id": "p1"},
        {"action": "ASSIGN_PROTECTION_POLICY", "resource_group": "web"},
        {"action": "ASSIGN_PROTECTION_POLICY", "resource_group_id": "g1"},
        {"protection_policy_id": "p1"},
    ):
        op = FakeOpener()
        assert run(monkeypatch, op, **kw)["failed"] and op.calls == []


def test_name_and_id_forms_are_exclusive(monkeypatch):
    for kw in (
        {"protection_policy": "a", "protection_policy_id": "b"},
        {"resource_group": "a", "resource_group_id": "b"},
    ):
        op = FakeOpener()
        assert run(monkeypatch, op, action="ASSIGN_PROTECTION_POLICY", **kw)["failed"] and op.calls == []


def test_invalid_input_fails_before_any_request(monkeypatch):
    bad_filters = (
        "x",
        ["x"],
        [dict(FILTER, objectType="NOPE")],
        [dict(FILTER, type="NOPE")],
        [dict(FILTER, conditions=["x"])],
        [dict(FILTER, conditions=[{"operator": "AND", "conditions": [{"nothing": 1}]}])],
    )
    for f in bad_filters:
        op = FakeOpener()
        assert run(monkeypatch, op, filters=f)["failed"] and op.calls == []
    for kw in ({"action": "DELETE"}, {"variant": "NOPE"}, {"scopes": ["NOPE"]}, {"categories": ["NOPE"]}):
        op = FakeOpener()
        assert run(monkeypatch, op, **kw)["failed"] and op.calls == []


def test_config_collision_fails(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, priority=1, config={"priority": 2})
    assert out["failed"] and "priority" in out["msg"] and op.calls == []
    out = run(monkeypatch, op, action="ASSIGN_PROTECTION_POLICY", protection_policy="vm-gold", config={"action": {}})
    assert out["failed"] and op.calls == []
    assert run(monkeypatch, op, config={"id": "x"})["failed"] and op.calls == []


def test_config_passes_extra_keys(monkeypatch):
    op = FakeOpener(listing(), Resp({"id": "r1"}, 201))
    run(monkeypatch, op, config={"filter": {"description": "d"}})
    assert body(op, 1)["filter"] == {"description": "d"}


def test_v2_options_rejected_by_argument_spec(monkeypatch):
    for kw in (
        {"conditions": [{"assetAttributeName": "tag"}]},
        {"condition_connector": "AND"},
        {"inventory_source_type": "VMWARE_VIRTUAL_MACHINE"},
        {"policy": "vm-gold"},
        {"tenant": "t1"},
    ):
        op = FakeOpener()
        out = run(monkeypatch, op, **kw)
        assert out["failed"] and op.calls == []
