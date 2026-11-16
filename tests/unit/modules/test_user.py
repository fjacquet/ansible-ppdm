import json

import pytest
from ansible.module_utils.testing import patch_module_args
from ansible_collections.fjacquet.ppdm.plugins.module_utils import ppdm
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmClient
from ansible_collections.fjacquet.ppdm.plugins.modules import user, user_info
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    Exit,
    FakeOpener,
    Resp,
    listing,
    methods,
    run_module,
)

SECRET = "user-pw-sentinel"
ROLE = {"id": "r1", "name": "Administrator"}
ARGS = dict(name="jdoe", first_name="Jane", last_name="Doe", email="jdoe@example.com")
EXISTING = {
    "id": "u1",
    "username": "jdoe",
    "firstName": "Jane",
    "lastName": "Doe",
    "emailAddress": "jdoe@example.com",
    "roleId": "r1",
    "createdDate": "2026-01-01",
}


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    return run_module(monkeypatch, user, op, check_mode=check, **dict(ARGS, **kw))


def body(op, i):
    return json.loads(op.calls[i][1]["data"])


def test_create_with_role_name_masks_password(monkeypatch):
    op = FakeOpener(
        listing(ROLE), listing(), listing(), Resp({"id": "u1", "username": "jdoe", "password": SECRET}, 201)
    )
    out = run(monkeypatch, op, user_password=SECRET, role="Administrator", force_password_change=True)
    assert out["changed"] and methods(op) == ["GET", "GET", "GET", "POST"]
    assert op.calls[0][0].split("?")[0].endswith("/api/v2/roles")
    assert op.calls[1][0].split("?")[0].endswith("/api/v2/users")
    assert body(op, 3) == {
        "username": "jdoe",
        "firstName": "Jane",
        "lastName": "Doe",
        "emailAddress": "jdoe@example.com",
        "password": SECRET,
        "forcePasswordChange": True,
        "roleId": "r1",
    }
    assert SECRET not in json.dumps(out)


def test_update_puts_only_on_difference_without_password(monkeypatch):
    op = FakeOpener(listing(EXISTING), listing(EXISTING), Resp({"id": "u1"}))
    out = run(monkeypatch, op, email="new@example.com")
    assert out["changed"] and methods(op) == ["GET", "GET", "PUT"]
    assert op.calls[2][0].endswith("/api/v2/users/u1")
    sent = body(op, 2)
    assert sent["emailAddress"] == "new@example.com" and "password" not in sent
    assert "id" not in sent and "createdDate" not in sent


def test_idempotent_missing_fields_use_existing_user(monkeypatch):
    op = FakeOpener(listing(EXISTING), listing(EXISTING))
    out = run_module(monkeypatch, user, op, name="jdoe")
    assert not out["changed"] and methods(op) == ["GET", "GET"]


def test_idempotent_ignores_password(monkeypatch):
    op = FakeOpener(listing(EXISTING), listing(EXISTING))
    out = run(monkeypatch, op, user_password=SECRET, role_id="r1")
    assert not out["changed"] and methods(op) == ["GET", "GET"]


def test_update_password_always_forces_put(monkeypatch):
    op = FakeOpener(listing(EXISTING), Resp({"id": "u1"}))
    out = run(monkeypatch, op, user_password=SECRET, update_password="always")
    assert out["changed"] and methods(op) == ["GET", "PUT"]
    assert body(op, 1)["password"] == SECRET and SECRET not in json.dumps(out)


def test_absent_deletes(monkeypatch):
    op = FakeOpener(listing(EXISTING), Resp(None, 204))
    out = run_module(monkeypatch, user, op, name="jdoe", state="absent")
    assert out["changed"] and methods(op) == ["GET", "DELETE"]
    assert op.calls[1][0].endswith("/api/v2/users/u1")


def test_check_mode_sends_no_write(monkeypatch):
    op = FakeOpener(listing(), listing())
    out = run(monkeypatch, op, user_password=SECRET, check_mode=True)
    assert out["changed"] and methods(op) == ["GET", "GET"]
    out = run_module(monkeypatch, user, FakeOpener(listing(EXISTING)), name="jdoe", state="absent", check_mode=True)
    assert out["changed"]


def test_unknown_role_fails_without_write(monkeypatch):
    op = FakeOpener(listing())
    out = run(monkeypatch, op, user_password=SECRET, role="Nope")
    assert out["failed"] and "role Nope not found" in out["msg"] and methods(op) == ["GET"]
    assert SECRET not in json.dumps(out)


def test_role_and_role_id_are_mutually_exclusive(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, role="a", role_id="b")
    assert out["failed"] and op.calls == []


@pytest.mark.parametrize("missing", ["email", "first_name", "last_name", "user_password"])
def test_create_with_missing_field_fails_without_write(monkeypatch, missing):
    args = dict(ARGS, user_password=SECRET)
    args.pop(missing, None)
    op = FakeOpener(listing(), listing())
    out = run_module(monkeypatch, user, op, **args)
    assert out["failed"] and methods(op) == ["GET"] and SECRET not in json.dumps(out)


def test_user_info_filters_username_and_drops_password(monkeypatch):
    op = FakeOpener(listing(dict(EXISTING, password=SECRET)))
    client = PpdmClient("h", "u", "s3cret", opener=op, sleep=lambda s: None)
    monkeypatch.setattr(ppdm, "client_from_module", lambda module: client)

    def exit_json(self, **kw):
        raise Exit(kw)

    monkeypatch.setattr(ppdm.AnsibleModule, "exit_json", exit_json)
    with patch_module_args(dict(hostname="h", username="u", password="s3cret", name="jdoe")), pytest.raises(Exit) as e:
        user_info.main()
    out = e.value.kwargs
    assert 'username eq "jdoe"' in op.calls[0][0].replace("%22", '"').replace("+", " ").replace("%20", " ")
    assert out["users"] == [EXISTING] and SECRET not in json.dumps(out)


def test_on_create_existing_user_update_drops_password(monkeypatch):
    op = FakeOpener(listing(EXISTING), listing(EXISTING), Resp({"id": "u1"}))
    out = run(monkeypatch, op, email="new@example.com", user_password=SECRET)
    assert out["changed"] and methods(op) == ["GET", "GET", "PUT"]
    assert "password" not in body(op, 2) and SECRET not in json.dumps(out)


def test_absent_masks_password_in_diff(monkeypatch):
    op = FakeOpener(listing(dict(EXISTING, password=SECRET)), Resp(None, 204))
    out = run_module(monkeypatch, user, op, name="jdoe", state="absent")
    assert SECRET not in json.dumps(out)


def test_passwords_are_registered_as_client_secrets(monkeypatch):
    op = FakeOpener(listing(EXISTING), Resp({"id": "u1"}))
    seen = []
    orig = PpdmClient.add_secret
    monkeypatch.setattr(PpdmClient, "add_secret", lambda self, s: (seen.append(s), orig(self, s))[1])
    run(monkeypatch, op, user_password=SECRET, update_password="always")
    assert SECRET in seen
