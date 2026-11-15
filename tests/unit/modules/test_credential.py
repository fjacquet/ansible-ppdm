import json

from ansible_collections.fjacquet.ppdm.plugins.modules import credential
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    listing,
    methods,
    run_module,
)

ARGS = dict(name="c1", type="OS", cred_username="root", cred_password="pw-secret")
EXISTING = {"id": "1", "name": "c1", "type": "OS", "username": "root", "createdAt": "t"}


def run(monkeypatch, op, **kw):
    return run_module(monkeypatch, credential, op, **dict(ARGS, **kw))


def test_credential_create(monkeypatch):
    op = FakeOpener(listing(), Resp({"id": "9", "name": "c1"}, 201))
    out = run(monkeypatch, op)
    assert out["changed"] and methods(op) == ["GET", "POST"]
    body = json.loads(op.calls[1][1]["data"])
    assert body == {
        "name": "c1",
        "type": "OS",
        "username": "root",
        "password": "pw-secret",
    }


def test_credential_rerun_no_put_when_get_omits_password(monkeypatch):
    op = FakeOpener(listing(EXISTING))
    out = run(monkeypatch, op)
    assert not out["changed"] and methods(op) == ["GET"]


def test_credential_update_on_diff(monkeypatch):
    op = FakeOpener(listing(EXISTING), Resp({"id": "1"}))
    out = run(monkeypatch, op, cred_username="admin")
    assert out["changed"] and methods(op) == ["GET", "PUT"]
    assert json.loads(op.calls[1][1]["data"])["username"] == "admin"


def test_credential_update_password_always(monkeypatch):
    op = FakeOpener(listing(EXISTING), Resp({"id": "1"}))
    out = run(monkeypatch, op, update_password="always")
    assert out["changed"] and methods(op) == ["GET", "PUT"]


def test_credential_check_mode(monkeypatch):
    op = FakeOpener(listing())
    out = run_module(monkeypatch, credential, op, check_mode=True, **ARGS)
    assert out["changed"] and methods(op) == ["GET"]


def test_password_masked_in_diff(monkeypatch):
    op = FakeOpener(listing(), Resp({"id": "9", "name": "c1", "password": "pw-secret"}, 201))
    out = run(monkeypatch, op)
    assert "pw-secret" not in json.dumps(out)


def test_credential_absent_missing_is_noop(monkeypatch):
    op = FakeOpener(listing())
    out = run_module(monkeypatch, credential, op, name="c1", state="absent")
    assert not out["changed"] and methods(op) == ["GET"]


def test_credential_absent_deletes(monkeypatch):
    op = FakeOpener(listing(EXISTING), Resp(None, 204))
    out = run_module(monkeypatch, credential, op, name="c1", state="absent")
    assert out["changed"] and methods(op) == ["GET", "DELETE"]


def test_credential_present_requires_type_and_username(monkeypatch):
    out = run_module(monkeypatch, credential, FakeOpener(), name="c1")
    assert out["failed"] and "type" in out["msg"]
