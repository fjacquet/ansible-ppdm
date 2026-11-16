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

RULE = {"id": "r1", "name": "gold-vms", "action": {"name": "ASSIGN_RESOURCE_GROUP"}, "filters": []}
STARTED = Resp({"activityId": "a1"}, 202)


def act(status):
    return Resp({"id": "a1", "state": "COMPLETED", "result": {"status": status}})


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    kw.setdefault("rule", "gold-vms")
    return run_module(monkeypatch, protection_rule_run, op, check_mode=check, **kw)


def post_body(op, i):
    return json.loads(op.calls[i][1]["data"])


def test_run_by_name_exact_body(monkeypatch):
    op = FakeOpener(listing(RULE), STARTED)
    out = run(monkeypatch, op)
    assert out["changed"] and methods(op) == ["GET", "POST"]
    assert urlsplit(op.calls[1][0]).path == "/api/v3/rule-execution"
    assert post_body(op, 1) == {"ruleId": "r1", "actionName": "ASSIGN_RESOURCE_GROUP", "objectType": "ASSET"}
    assert out["response"] == {"activityId": "a1"}


def test_run_by_id_and_explicit_action_and_subtypes(monkeypatch):
    op = FakeOpener(listing(), listing(RULE), STARTED)
    run(monkeypatch, op, rule="r1", action_name="ASSIGN_RESOURCE_GROUP", object_subtypes=["ORACLE_DATABASE"])
    assert post_body(op, 2) == {
        "ruleId": "r1",
        "actionName": "ASSIGN_RESOURCE_GROUP",
        "objectType": "ASSET",
        "objectSubtypes": ["ORACLE_DATABASE"],
    }


def test_action_not_executable_fails(monkeypatch):
    rule = dict(RULE, action={"name": "OTHER"})
    op = FakeOpener(listing(rule))
    out = run(monkeypatch, op)
    assert out["failed"] and "action_name" in out["msg"] and methods(op) == ["GET"]
    op = FakeOpener(listing(dict(RULE, action=None)))
    assert run(monkeypatch, op)["failed"] and methods(op) == ["GET"]


def test_unknown_rule_fails_without_post(monkeypatch):
    op = FakeOpener(listing(), listing())
    out = run(monkeypatch, op)
    assert out["failed"] and "not found" in out["msg"] and methods(op) == ["GET", "GET"]


def test_ambiguous_rule_fails(monkeypatch):
    op = FakeOpener(listing(RULE, dict(RULE, id="r9")))
    out = run(monkeypatch, op)
    assert out["failed"] and "r9" in out["msg"] and methods(op) == ["GET"]


def test_check_mode_sends_no_execution(monkeypatch):
    op = FakeOpener(listing(RULE))
    out = run(monkeypatch, op, check_mode=True)
    assert out["changed"] and methods(op) == ["GET"]


def test_preview_sends_rule_even_in_check_mode(monkeypatch):
    conflicts = {"content": [{"name": "other"}]}
    server = dict(RULE, createdAt="t", updatedAt="t", lastRunAt="t", lastMigratedAt="t", status="OK", uniqueHash="h")
    server["_links"] = {"self": {"href": "x"}}
    op = FakeOpener(listing(server), Resp(conflicts))
    out = run(monkeypatch, op, preview=True, check_mode=True)
    assert out["changed"] is False and out["preview"] == conflicts and methods(op) == ["GET", "POST"]
    assert urlsplit(op.calls[1][0]).path == "/api/v3/protection-policy-rule-conflict-preview"
    sent = post_body(op, 1)["rule"]
    assert sent == RULE  # id kept
    assert not {"createdAt", "updatedAt", "lastRunAt", "lastMigratedAt", "status", "uniqueHash", "_links"} & set(sent)


def test_preview_with_wait_fails_before_any_request(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, preview=True, wait=True)
    assert out["failed"] and "wait" in out["msg"] and op.calls == []


def test_wait_polls_activity(monkeypatch):
    op = FakeOpener(listing(RULE), STARTED, act("OK"))
    out = run(monkeypatch, op, wait=True)
    assert out["changed"] and out["activities"][0]["id"] == "a1" and methods(op) == ["GET", "POST", "GET"]


def test_wait_failed_activity_fails(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(RULE), STARTED, act("FAILED")), wait=True)
    assert out["failed"] and "FAILED" in out["msg"]


def test_wait_ok_with_errors_warns(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(RULE), STARTED, act("OK_WITH_ERRORS")), wait=True)
    assert not out["failed"] and out["warnings"]


def test_wait_without_activity_id_fails(monkeypatch):
    for resp in (Resp(None, 202), Resp({"results": []}, 202)):
        out = run(monkeypatch, FakeOpener(listing(RULE), resp), wait=True)
        assert out["failed"] and "activityId" in out["msg"]


def test_no_wait_without_activity_id_is_fine(monkeypatch):
    out = run(monkeypatch, FakeOpener(listing(RULE), Resp(None, 202)))
    assert not out["failed"] and out["changed"] and "response" not in out


def test_invalid_choices_fail_before_any_request(monkeypatch):
    for kw in ({"action_name": "NOPE"}, {"object_subtypes": ["NOPE"]}):
        op = FakeOpener()
        assert run(monkeypatch, op, **kw)["failed"] and op.calls == []


def test_v2_options_rejected_by_argument_spec(monkeypatch):
    for kw in ({"rules": ["x"]}, {"inventory_source_type": "KUBERNETES"}, {"preview_action": "EDIT"}):
        op = FakeOpener()
        assert run(monkeypatch, op, **kw)["failed"] and op.calls == []


def test_policy_rule_refused_without_all_rules_of_action(monkeypatch):
    op = FakeOpener(listing(dict(RULE, action={"name": "ASSIGN_PROTECTION_POLICY"})))
    out = run(monkeypatch, op)
    assert out["failed"] and "all_rules_of_action" in out["msg"] and methods(op) == ["GET"]


def test_policy_rule_runs_every_rule_of_the_action_without_rule_id(monkeypatch):
    op = FakeOpener(listing(dict(RULE, action={"name": "ASSIGN_PROTECTION_POLICY"})), STARTED)
    out = run(monkeypatch, op, all_rules_of_action=True, object_subtypes=["POWERSTORE_BLOCK"])
    assert out["changed"] and post_body(op, 1) == {
        "actionName": "ASSIGN_PROTECTION_POLICY",
        "objectType": "ASSET",
        "objectSubtypes": ["POWERSTORE_BLOCK"],
    }
