import json

from ansible_collections.fjacquet.ppdm.plugins.modules import eula
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    methods,
    run_module,
)


def test_eula_already_accepted_no_patch(monkeypatch):
    op = FakeOpener(Resp({"accepted": True}))
    out = run_module(monkeypatch, eula, op)
    assert not out["changed"] and methods(op) == ["GET"]
    assert op.calls[0][0].endswith("/api/v2/eulas/PPDM")


def test_eula_accepts_when_not_accepted(monkeypatch):
    op = FakeOpener(Resp({"accepted": False}), Resp({"accepted": True}))
    out = run_module(monkeypatch, eula, op, name="TELEMETRY")
    assert out["changed"] and methods(op) == ["GET", "PATCH"]
    assert op.calls[1][0].endswith("/api/v2/eulas/TELEMETRY")
    assert json.loads(op.calls[1][1]["data"]) == {"accepted": True}
    assert out["eula"]["accepted"] is True


def test_eula_check_mode_sends_nothing(monkeypatch):
    op = FakeOpener(Resp({"accepted": False}))
    out = run_module(monkeypatch, eula, op, check_mode=True)
    assert out["changed"] and methods(op) == ["GET"]


def test_eula_invalid_name_rejected(monkeypatch):
    op = FakeOpener()
    out = run_module(monkeypatch, eula, op, name="nope")
    assert out["failed"] and not op.calls


def test_eula_unaccept_fails(monkeypatch):
    op = FakeOpener(Resp({"accepted": True}))
    out = run_module(monkeypatch, eula, op, accepted=False)
    assert out["failed"] and methods(op) == ["GET"]


def test_eula_missing_accepted_field_is_not_accepted(monkeypatch):
    op = FakeOpener(Resp({}), Resp({"accepted": True}))
    out = run_module(monkeypatch, eula, op)
    assert out["changed"] and methods(op) == ["GET", "PATCH"]


def test_eula_missing_accepted_field_and_accepted_false_is_unchanged(monkeypatch):
    op = FakeOpener(Resp({}))
    out = run_module(monkeypatch, eula, op, accepted=False)
    assert not out["changed"] and methods(op) == ["GET"]


def test_eula_non_dict_response_fails_cleanly(monkeypatch):
    out = run_module(monkeypatch, eula, FakeOpener(Resp([1])))
    assert out["failed"] and "unexpected response" in out["msg"]
