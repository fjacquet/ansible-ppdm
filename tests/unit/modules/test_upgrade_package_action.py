import json
from urllib.parse import parse_qs, urlsplit

import pytest
from ansible_collections.fjacquet.ppdm.plugins.modules import upgrade_package_action
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    http_error,
    listing,
    methods,
    run_module,
)

PP = "pp-sentinel-123"
TOK = "tok-sentinel-456"


def pkg(state="AVAILABLE", **extra):
    return Resp(
        dict(
            {
                "id": "u1",
                "category": "ACTIVE",
                "state": state,
                "type": "UPGRADE",
                "upgradeToken": TOK,
                "lockboxPassphrase": PP,
                "_links": {"self": "x"},
            },
            **extra,
        )
    )


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    kw.setdefault("id", "u1")
    kw.setdefault("action", "upgrade")
    kw.setdefault("confirm", True)
    return run_module(monkeypatch, upgrade_package_action, op, check_mode=check, **kw)


def test_without_confirm_never_connects(monkeypatch):
    for action in ("precheck", "upgrade", "revert"):
        for check in (False, True):
            op = FakeOpener()
            out = run(monkeypatch, op, action=action, confirm=False, check_mode=check)
            assert out["failed"] and "confirm" in out["msg"] and op.calls == [] and op.connects == 0


def test_default_id_from_single_active(monkeypatch):
    active = {"id": "u1", "category": "ACTIVE"}
    op = FakeOpener(listing(active), pkg(), Resp({"id": "u1"}, 202))
    out = run(monkeypatch, op, id=None)
    assert out["changed"] and urlsplit(op.calls[1][0]).path == "/api/v2/upgrade-packages/u1"


def test_two_active_packages_fail(monkeypatch):
    op = FakeOpener(listing({"id": "a", "category": "ACTIVE"}, {"id": "b", "category": "ACTIVE"}))
    out = run(monkeypatch, op, id=None)
    assert out["failed"] and methods(op) == ["GET"]


def test_upgrade_put_body_and_force_query(monkeypatch):
    op = FakeOpener(pkg(), Resp({"id": "u1", "upgradeToken": TOK}, 202))
    out = run(monkeypatch, op, trust_certificate=True, accept_eula=True, lockbox_passphrase="newpass-9")
    assert out["changed"] and methods(op) == ["GET", "PUT"]
    url = urlsplit(op.calls[1][0])
    assert url.path == "/api/v2/upgrade-packages/u1" and parse_qs(url.query) == {"forceUpgrade": ["false"]}
    assert json.loads(op.calls[1][1]["data"]) == {
        "id": "u1",
        "category": "ACTIVE",
        "state": "INSTALLED",
        "type": "UPGRADE",
        "upgradeToken": TOK,
        "certificateTrustedByUser": True,
        "eula": {"productEulaAccepted": True, "telemetryEulaAccepted": True},
        "lockboxPassphrase": "newpass-9",
    }
    assert "newpass-9" not in json.dumps(out)


def test_upgrade_without_passphrase_drops_it_and_force_true(monkeypatch):
    op = FakeOpener(pkg(), Resp({"id": "u1"}, 202))
    run(monkeypatch, op, force=True)
    assert parse_qs(urlsplit(op.calls[1][0]).query) == {"forceUpgrade": ["true"]}
    assert "lockboxPassphrase" not in json.loads(op.calls[1][1]["data"])


def test_upgrade_installed_is_noop(monkeypatch):
    op = FakeOpener(pkg("INSTALLED"))
    out = run(monkeypatch, op)
    assert not out["failed"] and not out["changed"] and methods(op) == ["GET"]


def test_upgrade_processing_fails(monkeypatch):
    op = FakeOpener(pkg("PROCESSING"))
    out = run(monkeypatch, op)
    assert out["failed"] and "PROCESSING" in out["msg"] and methods(op) == ["GET"]


def test_upgrade_200_answer_fails(monkeypatch):
    op = FakeOpener(pkg(), Resp({"message": "boom"}, 200))
    out = run(monkeypatch, op)
    assert out["failed"] and "boom" in out["msg"]


def test_upgrade_check_mode_sends_nothing(monkeypatch):
    op = FakeOpener(pkg())
    out = run(monkeypatch, op, check_mode=True)
    assert out["changed"] and methods(op) == ["GET"]


def test_partly_installed_upgrade_fails(monkeypatch):
    for state in ("INSTALLED_CORE", "INSTALLED_WITH_ERRORS", "INSTALLED_WITH_SKIPPED"):
        op = FakeOpener(pkg(state))
        out = run(monkeypatch, op)
        assert out["failed"] and state in out["msg"] and methods(op) == ["GET"]


def test_active_package_without_id_fails(monkeypatch):
    op = FakeOpener(listing({"category": "ACTIVE"}))
    out = run(monkeypatch, op, id=None)
    assert out["failed"] and methods(op) == ["GET"]


def test_error_cut_does_not_leave_secret_prefix(monkeypatch):
    for secret in ("newpass-9", TOK, PP):
        for filler in range(930, 960, 3):  # the message length (with its prefix) crosses the 1000 character cut
            op = FakeOpener(pkg(), http_error(400, {"message": "x" * filler + secret}))
            out = run(monkeypatch, op, lockbox_passphrase="newpass-9")
            assert out["failed"] and secret[:4] not in out["msg"]


def test_error_non_string_message_hides_escaped_passphrase(monkeypatch):
    weird = "pa\\ss'w\"d"
    op = FakeOpener(pkg(), http_error(400, {"message": {"m": "bad " + weird}}))
    out = run(monkeypatch, op, lockbox_passphrase=weird)
    assert out["failed"] and repr(weird)[1:-1] not in out["msg"] and weird not in out["msg"]


def test_http_error_message_hides_passphrase(monkeypatch):
    op = FakeOpener(pkg(), http_error(400, {"message": "bad passphrase newpass-9"}))
    out = run(monkeypatch, op, lockbox_passphrase="newpass-9")
    assert out["failed"] and "newpass-9" not in json.dumps(out)


def test_revert_refused_when_not_revertable(monkeypatch):
    for extra in ({"type": "HOTFIX"}, {"revertSupported": True}):
        op = FakeOpener(pkg("INSTALLED", **extra))
        out = run(monkeypatch, op, action="revert")
        assert out["failed"] and methods(op) == ["GET"]


def test_revert_posts_and_reverted_is_noop(monkeypatch):
    op = FakeOpener(pkg("INSTALLED", type="HOTFIX", revertSupported=True), Resp({"activityId": "a1", "id": "u1"}, 202))
    out = run(monkeypatch, op, action="revert")
    assert out["changed"] and out["response"] == {"activityId": "a1", "id": "u1"}
    assert urlsplit(op.calls[1][0]).path == "/api/v2/upgrade-packages/u1/revert"
    op = FakeOpener(pkg("REVERTED"))
    out = run(monkeypatch, op, action="revert")
    assert not out["changed"] and methods(op) == ["GET"]


def test_precheck_wait_polls_activity(monkeypatch):
    done = Resp({"id": "a1", "state": "COMPLETED", "result": {"status": "OK"}})
    op = FakeOpener(pkg(), Resp({"id": "u1", "activityId": "a1"}, 202), done)
    out = run(monkeypatch, op, action="precheck", wait=True)
    assert out["changed"] and out["activity"]["id"] == "a1"
    assert urlsplit(op.calls[1][0]).path == "/api/v2/upgrade-packages/u1/precheck"
    assert op.calls[1][1]["data"] is None


def test_precheck_on_installed_refused(monkeypatch):
    out = run(monkeypatch, FakeOpener(pkg("INSTALLED")), action="precheck")
    assert out["failed"]


def test_wait_with_upgrade_or_revert_fails_before_login(monkeypatch):
    for action in ("upgrade", "revert"):
        op = FakeOpener()
        out = run(monkeypatch, op, action=action, wait=True)
        assert out["failed"] and "wait" in out["msg"] and op.calls == [] and op.connects == 0


def test_secrets_never_in_output(monkeypatch):
    op = FakeOpener(pkg(), Resp({"id": "u1", "upgradeToken": TOK, "lockboxPassphrase": PP}, 202))
    out = run(monkeypatch, op)
    text = json.dumps(out)
    assert PP not in text and TOK not in text
    assert out["upgrade_package"]["upgradeToken"] == "VALUE_SPECIFIED_IN_NO_LOG_PARAMETER"


def test_no_empty_no_log_value_so_result_strings_stay_intact(monkeypatch):
    """Real remove_values path: an empty string in no_log_values would turn every result string into garbage."""
    from ansible.module_utils.basic import AnsibleModule
    from ansible.module_utils.common.parameters import remove_values
    from ansible.module_utils.testing import patch_module_args
    from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmClient
    from ansible_collections.fjacquet.ppdm.tests.unit.helpers import Exit

    op = FakeOpener(pkg("INSTALLED"))
    client = PpdmClient("h", "u", "s3cret", opener=op, sleep=lambda s: None)
    monkeypatch.setattr(upgrade_package_action, "client_from_module", lambda module: client)

    def exit_json(self, **kw):
        raise Exit(remove_values(kw, self.no_log_values))

    monkeypatch.setattr(AnsibleModule, "exit_json", exit_json)
    args = dict(hostname="h", username="u", password="s3cret", id="u1", action="upgrade", confirm=True)
    with patch_module_args(args), pytest.raises(Exit) as e:
        upgrade_package_action.main()
    assert e.value.kwargs["upgrade_package"]["state"] == "INSTALLED"
    assert e.value.kwargs["upgrade_package"]["category"] == "ACTIVE"
