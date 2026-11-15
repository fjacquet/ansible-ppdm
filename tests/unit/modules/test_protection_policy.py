import json
from urllib.parse import urlsplit

import pytest
from ansible_collections.fjacquet.ppdm.plugins.modules import protection_policy
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    listing,
    methods,
    run_module,
)

OBJECTIVE = {"type": "BACKUP", "retentions": [{"time": [{"type": "RETENTION", "unitType": "DAY", "unitValue": 30}]}]}
ARGS = dict(name="gold", asset_type="VMWARE_VIRTUAL_MACHINE", description="d", objectives=[OBJECTIVE])
EXISTING = {
    "id": "p1",
    "name": "gold",
    "assetType": "VMWARE_VIRTUAL_MACHINE",
    "description": "d",
    "objectives": [OBJECTIVE],
}


def run(monkeypatch, op, **kw):
    return run_module(monkeypatch, protection_policy, op, **dict(ARGS, **kw))


def test_create_posts_v3_with_asset_type(monkeypatch):
    op = FakeOpener(listing(), listing(), Resp({"id": "9"}, 201))
    out = run(monkeypatch, op, purpose="CENTRALIZED", disabled=False)
    assert out["changed"] and methods(op) == ["GET", "GET", "POST"]
    assert urlsplit(op.calls[2][0]).path == "/api/v3/protection-policies"
    assert json.loads(op.calls[2][1]["data"]) == {
        "name": "gold",
        "assetType": "VMWARE_VIRTUAL_MACHINE",
        "description": "d",
        "purpose": "CENTRALIZED",
        "disabled": False,
        "objectives": [OBJECTIVE],
    }


def test_idempotent(monkeypatch):
    op = FakeOpener(listing(EXISTING), listing(EXISTING))
    out = run(monkeypatch, op)
    assert not out["changed"] and set(methods(op)) == {"GET"}


def test_description_change_patches_item(monkeypatch):
    op = FakeOpener(listing(EXISTING), listing(EXISTING), Resp({"id": "p1"}))
    out = run(monkeypatch, op, description="new")
    assert out["changed"] and methods(op) == ["GET", "GET", "PATCH"]
    assert urlsplit(op.calls[2][0]).path == "/api/v3/protection-policies/p1"
    assert json.loads(op.calls[2][1]["data"])["description"] == "new"


def test_asset_type_change_fails(monkeypatch):
    op = FakeOpener(listing(EXISTING))
    out = run(monkeypatch, op, asset_type="FILE_SYSTEM")
    assert out["failed"] and "delete and recreate" in out["msg"] and methods(op) == ["GET"]


@pytest.mark.parametrize(
    "objectives,needle",
    [
        ([{"type": "BOGUS"}], "objectives[0]"),
        ([OBJECTIVE, {"retentions": []}], "objectives[1]"),
    ],
)
def test_bad_objective_fails_without_request(monkeypatch, objectives, needle):
    op = FakeOpener()
    out = run(monkeypatch, op, objectives=objectives)
    assert out["failed"] and needle in out["msg"] and op.calls == []


def test_objective_without_id_is_accepted(monkeypatch):
    op = FakeOpener(listing(), listing(), Resp({"id": "9"}, 201))
    assert run(monkeypatch, op, objectives=[{"type": "SNAPSHOT"}])["changed"]


def test_config_collision_fails(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, config={"name": "x"})
    assert out["failed"] and op.calls == []


def test_config_passthrough(monkeypatch):
    op = FakeOpener(listing(), listing(), Resp({"id": "9"}, 201))
    run(monkeypatch, op, config={"extra": 1})
    assert json.loads(op.calls[2][1]["data"])["extra"] == 1


def test_absent_deletes(monkeypatch):
    op = FakeOpener(listing(EXISTING), Resp(None, 204))
    out = run_module(
        monkeypatch, protection_policy, op, name="gold", asset_type="VMWARE_VIRTUAL_MACHINE", state="absent"
    )
    assert out["changed"] and methods(op) == ["GET", "DELETE"]


def test_absent_check_mode_sends_nothing(monkeypatch):
    op = FakeOpener(listing(EXISTING))
    out = run_module(
        monkeypatch,
        protection_policy,
        op,
        check_mode=True,
        name="gold",
        asset_type="VMWARE_VIRTUAL_MACHINE",
        state="absent",
    )
    assert out["changed"] and methods(op) == ["GET"]
