import json
from urllib.parse import urlsplit

from ansible_collections.fjacquet.ppdm.plugins.modules import protection_group
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    listing,
    methods,
    run_module,
)

GROUP = {
    "id": "g1",
    "name": "ora-dg",
    "description": "d",
    "type": "ORACLE_DATA_GUARD",
    "naturalIds": ["n1"],
    "autoAssignToPolicy": True,
    "protectionPolicyRef": {"id": "p1", "name": "oracle-gold", "backupMechanism": "SBT"},
    "createdAt": "2026-01-01T00:00:00Z",
    "updatedAt": "2026-01-01T00:00:00Z",
    "lastAvailableCopyTime": "2026-01-01T00:00:00Z",
    "lastDiscoveryStatus": "DETECTED",
    "protectionStatus": "PROTECTED",
    "operatingSystems": ["Linux"],
    "supportedProtectionProtocols": ["DDBOOST"],
}
POLICY = {"id": "p1", "name": "oracle-gold"}


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    kw.setdefault("name", "ora-dg")
    return run_module(monkeypatch, protection_group, op, check_mode=check, **kw)


def body(op, i):
    return json.loads(op.calls[i][1]["data"])


def test_create_with_policy_name(monkeypatch):
    op = FakeOpener(listing(POLICY), listing(), Resp({"id": "g1", "name": "ora-dg"}, 200))
    out = run(
        monkeypatch,
        op,
        description="d",
        type="ORACLE_DATA_GUARD",
        subtype="GENERIC",
        member_asset_type="ORACLE_DATABASE",
        backup_strategy="BACKUP_PRIMARY_ONLY",
        auto_assign_to_policy=True,
        protection_policy="oracle-gold",
        natural_ids=["n1"],
    )
    assert out["changed"] and out["protection_group"]["id"] == "g1"
    assert methods(op) == ["GET", "GET", "POST"]
    assert urlsplit(op.calls[0][0]).path == "/api/v3/protection-policies"
    assert urlsplit(op.calls[2][0]).path == "/api/v2/protection-groups"
    assert body(op, 2) == {
        "name": "ora-dg",
        "description": "d",
        "type": "ORACLE_DATA_GUARD",
        "subtype": "GENERIC",
        "memberAssetType": "ORACLE_DATABASE",
        "backupStrategy": "BACKUP_PRIMARY_ONLY",
        "autoAssignToPolicy": True,
        "protectionPolicyRef": {"id": "p1"},
        "naturalIds": ["n1"],
    }


def test_policy_id_used_as_is(monkeypatch):
    op = FakeOpener(listing(), Resp({"id": "g1"}, 200))
    run(monkeypatch, op, protection_policy_id="p9")
    assert methods(op) == ["GET", "POST"] and body(op, 1)["protectionPolicyRef"] == {"id": "p9"}


def test_idempotent_ignores_readonly_and_server_ref_fields(monkeypatch):
    op = FakeOpener(listing(POLICY), listing(GROUP))
    out = run(monkeypatch, op, description="d", protection_policy="oracle-gold", natural_ids=["n1"])
    assert not out["changed"] and methods(op) == ["GET", "GET"]


def test_update_patches_only_on_diff(monkeypatch):
    op = FakeOpener(listing(GROUP), Resp(dict(GROUP, description="new"), 200))
    out = run(monkeypatch, op, description="new")
    assert out["changed"] and methods(op) == ["GET", "PATCH"]
    assert urlsplit(op.calls[1][0]).path == "/api/v2/protection-groups/g1"
    b = body(op, 1)
    ro = {"id", "createdAt", "updatedAt", "lastAvailableCopyTime", "lastDiscoveryStatus", "protectionStatus"}
    assert b["description"] == "new" and not ro & set(b)
    assert not {"operatingSystems", "supportedProtectionProtocols"} & set(b)


def test_absent(monkeypatch):
    op = FakeOpener(listing(GROUP), Resp(None, 204))
    assert run(monkeypatch, op, state="absent")["changed"] and methods(op) == ["GET", "DELETE"]
    assert urlsplit(op.calls[1][0]).path == "/api/v2/protection-groups/g1"
    assert not run(monkeypatch, FakeOpener(listing()), state="absent")["changed"]


def test_check_mode_sends_no_write(monkeypatch):
    op = FakeOpener(listing(POLICY), listing())
    assert run(monkeypatch, op, check_mode=True, protection_policy="oracle-gold")["changed"]
    assert methods(op) == ["GET", "GET"]
    op = FakeOpener(listing(GROUP))
    assert run(monkeypatch, op, check_mode=True, description="x")["changed"] and methods(op) == ["GET"]
    op = FakeOpener(listing(GROUP))
    assert run(monkeypatch, op, check_mode=True, state="absent")["changed"] and methods(op) == ["GET"]


def test_unknown_or_ambiguous_policy_fails_without_write(monkeypatch):
    op = FakeOpener(listing())
    out = run(monkeypatch, op, protection_policy="nope")
    assert out["failed"] and "not found" in out["msg"] and methods(op) == ["GET"]
    op = FakeOpener(listing(POLICY, dict(POLICY, id="p2")))
    out = run(monkeypatch, op, protection_policy="oracle-gold")
    assert out["failed"] and "p1" in out["msg"] and "p2" in out["msg"] and methods(op) == ["GET"]


def test_policy_name_and_id_mutually_exclusive(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, protection_policy="a", protection_policy_id="b")
    assert out["failed"] and op.calls == []


def test_bad_type_rejected_before_request(monkeypatch):
    op = FakeOpener()
    assert run(monkeypatch, op, type="VMWARE")["failed"] and op.calls == []


def test_ambiguous_group_fails(monkeypatch):
    op = FakeOpener(listing(GROUP, dict(GROUP, id="g2")))
    out = run(monkeypatch, op)
    assert out["failed"] and "g2" in out["msg"] and methods(op) == ["GET"]


def test_config_collision_fails_before_request(monkeypatch):
    op = FakeOpener()
    assert run(monkeypatch, op, description="a", config={"description": "b"})["failed"]
    assert run(monkeypatch, op, config={"protectionPolicyRef": {"id": "x"}})["failed"]
    assert run(monkeypatch, op, config={"id": "x"})["failed"] and op.calls == []


def test_config_passes_extra_keys(monkeypatch):
    op = FakeOpener(listing(), Resp({"id": "g1"}, 200))
    run(monkeypatch, op, config={"dataBackupRole": {"x": 1}})
    assert body(op, 1) == {"name": "ora-dg", "dataBackupRole": {"x": 1}}
