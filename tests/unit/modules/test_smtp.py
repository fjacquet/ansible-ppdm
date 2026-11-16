import json

import pytest
from ansible.module_utils.testing import patch_module_args
from ansible_collections.fjacquet.ppdm.plugins.module_utils import ppdm
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmClient
from ansible_collections.fjacquet.ppdm.plugins.modules import smtp, smtp_info
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    Exit,
    FakeOpener,
    Resp,
    listing,
    methods,
    run_module,
)

SECRET = "smtp-pw-sentinel"
ARGS = dict(mail_server="smtp.example.com", mail_from="ppdm@example.com", smtp_port=587, start_tls=True)
EXISTING = {
    "id": "s1",
    "mailServer": "smtp.example.com",
    "mailFrom": "ppdm@example.com",
    "port": 587,
    "isStartTls": True,
}


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    return run_module(monkeypatch, smtp, op, check_mode=check, **dict(ARGS, **kw))


def body(op, i):
    return json.loads(op.calls[i][1]["data"])


def test_create_masks_password(monkeypatch):
    op = FakeOpener(listing(), Resp({"id": "s1", "mailServer": "smtp.example.com", "password": SECRET}, 200))
    out = run(monkeypatch, op, smtp_password=SECRET, smtp_username="relay")
    assert out["changed"] and methods(op) == ["GET", "POST"]
    assert body(op, 1) == {
        "mailServer": "smtp.example.com",
        "mailFrom": "ppdm@example.com",
        "port": 587,
        "isStartTls": True,
        "username": "relay",
        "password": SECRET,
    }
    assert out["smtp"]["password"] != SECRET and out["diff"]["after"]["password"] != SECRET
    assert SECRET not in json.dumps(out)


def test_update_puts_to_existing_id(monkeypatch):
    op = FakeOpener(listing(EXISTING), Resp({"id": "s1"}))
    out = run(monkeypatch, op, mail_server="smtp2.example.com")
    assert out["changed"] and methods(op) == ["GET", "PUT"]
    assert op.calls[1][0].endswith("/api/v2/smtp/s1")
    assert body(op, 1)["mailServer"] == "smtp2.example.com" and "id" not in body(op, 1)


def test_idempotent_without_password(monkeypatch):
    op = FakeOpener(listing(EXISTING))
    out = run(monkeypatch, op)
    assert not out["changed"] and methods(op) == ["GET"]


def test_update_password_always_forces_put(monkeypatch):
    op = FakeOpener(listing(EXISTING), Resp({"id": "s1"}))
    out = run(monkeypatch, op, smtp_password=SECRET, update_password="always")
    assert out["changed"] and methods(op) == ["GET", "PUT"]
    assert body(op, 1)["password"] == SECRET and SECRET not in json.dumps(out)


def test_absent_deletes(monkeypatch):
    op = FakeOpener(listing(EXISTING), Resp(None, 204))
    out = run_module(monkeypatch, smtp, op, state="absent")
    assert out["changed"] and methods(op) == ["GET", "DELETE"]
    assert op.calls[1][0].endswith("/api/v2/smtp/s1")


def test_absent_missing_is_noop(monkeypatch):
    op = FakeOpener(listing())
    out = run_module(monkeypatch, smtp, op, state="absent")
    assert not out["changed"] and methods(op) == ["GET"]


def test_two_existing_configs_fail(monkeypatch):
    op = FakeOpener(listing(EXISTING, dict(EXISTING, id="s2")))
    out = run(monkeypatch, op)
    assert out["failed"] and methods(op) == ["GET"]


def test_present_requires_mail_server(monkeypatch):
    out = run_module(monkeypatch, smtp, FakeOpener())
    assert out["failed"] and "mail_server" in out["msg"]


def test_test_sent_after_ensure(monkeypatch):
    op = FakeOpener(listing(EXISTING), Resp({"id": "s1"}), Resp(None, 200))
    out = run(monkeypatch, op, recipient="ops@example.com", smtp_password=SECRET, test=True)
    assert methods(op) == ["GET", "PUT", "POST"]  # the recipient is new, so the ensure PUTs before the test
    assert op.calls[-1][0].endswith("/api/v2/smtp/test")
    assert body(op, -1) == {
        "mailServer": "smtp.example.com",
        "mailFrom": "ppdm@example.com",
        "port": 587,
        "recipient": "ops@example.com",
        "password": SECRET,
    }
    assert out["changed"] and SECRET not in json.dumps(out)


def test_test_alone_does_not_change(monkeypatch):
    op = FakeOpener(listing(dict(EXISTING, recipient="ops@example.com")), Resp(None, 200))
    out = run(monkeypatch, op, recipient="ops@example.com", test=True)
    assert not out["changed"] and methods(op) == ["GET", "POST"]
    assert "password" not in body(op, 1)


def test_test_skipped_in_check_mode(monkeypatch):
    op = FakeOpener(listing(EXISTING))
    out = run(monkeypatch, op, recipient="ops@example.com", test=True, check_mode=True)
    assert out["changed"] and methods(op) == ["GET"]


def test_test_without_recipient_fails_before_any_request(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, test=True)
    assert out["failed"] and "recipient" in out["msg"] and op.calls == []


def test_smtp_info_drops_password(monkeypatch):
    op = FakeOpener(listing(dict(EXISTING, password=SECRET)))
    client = PpdmClient("h", "u", "s3cret", opener=op, sleep=lambda s: None)
    monkeypatch.setattr(ppdm, "client_from_module", lambda module: client)

    def exit_json(self, **kw):
        raise Exit(kw)

    monkeypatch.setattr(ppdm.AnsibleModule, "exit_json", exit_json)
    with patch_module_args(dict(hostname="h", username="u", password="s3cret")), pytest.raises(Exit) as e:
        smtp_info.main()
    out = e.value.kwargs
    assert out["smtp"] == [EXISTING] and SECRET not in json.dumps(out)


def test_config_cannot_supply_mail_server(monkeypatch):
    """merge_config refuses named keys in config, so required_if(mail_server) never demands what config could give."""
    out = run_module(monkeypatch, smtp, FakeOpener(), config={"mailServer": "smtp.example.com"})
    assert out["failed"] and "mail_server" in out["msg"]


def test_test_with_username_needs_password(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, recipient="ops@example.com", smtp_username="relay", test=True)
    assert out["failed"] and "smtp_password" in out["msg"] and op.calls == []


def test_test_with_stored_username_needs_password(monkeypatch):
    op = FakeOpener(listing(dict(EXISTING, recipient="ops@example.com", username="relay")))
    out = run(monkeypatch, op, recipient="ops@example.com", test=True)
    assert out["failed"] and "smtp_password" in out["msg"] and methods(op) == ["GET"]


def test_test_uses_stored_configuration(monkeypatch):
    op = FakeOpener(listing(dict(EXISTING, recipient="ops@example.com")), Resp(None, 200))
    run_module(monkeypatch, smtp, op, recipient="ops@example.com", test=True, mail_server="smtp.example.com")
    assert body(op, 1)["mailFrom"] == "ppdm@example.com" and body(op, 1)["port"] == 587
