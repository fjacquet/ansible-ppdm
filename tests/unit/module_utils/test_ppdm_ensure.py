import json
from urllib.parse import parse_qs, urlsplit

import pytest
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (
    PpdmClient,
    PpdmError,
    strip_readonly,
)
from ansible_collections.fjacquet.ppdm.tests.unit.module_utils.test_ppdm_client import (
    FakeOpener,
    Resp,
    page,
)


def mk(*responses):
    op = FakeOpener(*responses)
    sleeps = []
    c = PpdmClient("ppdm.local", "admin", "S3cret!", opener=op, sleep=sleeps.append)
    return c, op, sleeps


def writes(op):
    return [(u, k) for u, k in op.calls if k["method"] != "GET"]


def test_ensure_creates_when_absent():
    c, op, _unused = mk(page([], 1, 0), Resp({"id": "1", "name": "c1", "type": "X"}, 201))
    r = c.ensure("credentials", {"name": "c1", "type": "X"})
    assert r["changed"] and r["object"]["id"] == "1"
    assert r["diff"] == {"before": {}, "after": {"name": "c1", "type": "X"}}
    url, kw = writes(op)[0]
    assert kw["method"] == "POST" and url.endswith("/api/v2/credentials")


def test_ensure_no_put_when_identical():
    obj = {"id": "1", "name": "c1", "type": "X", "createdAt": "t", "_links": {}}
    c, op, _unused = mk(page([obj], 1, 1))
    r = c.ensure("credentials", {"name": "c1", "type": "X"})
    assert not r["changed"] and writes(op) == []


def test_ensure_puts_when_different_and_strips_links():
    obj = {
        "id": "1",
        "name": "c1",
        "type": "X",
        "createdAt": "t",
        "_links": {"self": 1},
    }
    c, op, _unused = mk(page([obj], 1, 1), Resp({"id": "1", "name": "c1", "type": "Y"}))
    r = c.ensure("credentials", {"name": "c1", "type": "Y"})
    assert r["changed"]
    url, kw = writes(op)[0]
    assert kw["method"] == "PUT" and url.endswith("/api/v2/credentials/1")
    assert json.loads(kw["data"]) == {"id": "1", "name": "c1", "type": "Y"}
    assert r["diff"]["before"]["type"] == "X" and r["diff"]["after"]["type"] == "Y"


def test_ensure_check_mode_reports_change_without_writing():
    obj = {"id": "1", "name": "c1", "type": "X"}
    c, op, _unused = mk(page([obj], 1, 1), page([], 1, 0))
    assert c.ensure("credentials", {"name": "c1", "type": "Y"}, check_mode=True)["changed"]
    assert c.ensure("credentials", {"name": "c2"}, check_mode=True)["changed"]
    assert writes(op) == []


def test_ensure_secret_omitted_by_get_is_idempotent():
    c, op, _unused = mk(page([{"id": "1", "name": "c1"}], 1, 1))
    r = c.ensure("credentials", {"name": "c1", "password": "pw"}, secret_keys=["password"])
    assert not r["changed"] and writes(op) == []


def test_ensure_secret_masked_by_get_is_idempotent():
    c, op, _unused = mk(page([{"id": "1", "name": "c1", "password": "****"}], 1, 1))
    assert not c.ensure("credentials", {"name": "c1", "password": "pw"}, secret_keys=["password"])["changed"]
    assert writes(op) == []


def test_ensure_put_includes_secret_and_masks_diff():
    obj = {"id": "1", "name": "c1", "type": "X"}
    c, op, _unused = mk(page([obj], 1, 1), Resp({"id": "1", "name": "c1", "type": "Y"}))
    r = c.ensure(
        "credentials",
        {"name": "c1", "type": "Y", "password": "pw"},
        secret_keys=["password"],
    )
    assert r["changed"] and json.loads(writes(op)[0][1]["data"])["password"] == "pw"
    assert "pw" not in json.dumps(r)


def test_ensure_update_secrets_always_forces_put():
    c, op, _unused = mk(page([{"id": "1", "name": "c1"}], 1, 1), Resp({"id": "1", "name": "c1"}))
    r = c.ensure(
        "credentials",
        {"name": "c1", "password": "pw"},
        secret_keys=["password"],
        update_secrets="always",
    )
    assert r["changed"] and writes(op)[0][1]["method"] == "PUT"
    assert json.loads(writes(op)[0][1]["data"])["password"] == "pw"


def test_ensure_update_secrets_always_check_mode_sends_nothing():
    c, op, _unused = mk(page([{"id": "1", "name": "c1"}], 1, 1))
    assert c.ensure(
        "credentials",
        {"name": "c1", "password": "pw"},
        secret_keys=["password"],
        update_secrets="always",
        check_mode=True,
    )["changed"]
    assert writes(op) == []


def test_ensure_create_includes_secret():
    c, op, _unused = mk(page([], 1, 0), Resp({"id": "1", "name": "c1"}, 201))
    r = c.ensure("credentials", {"name": "c1", "password": "pw"}, secret_keys=["password"])
    assert json.loads(writes(op)[0][1]["data"])["password"] == "pw" and "pw" not in json.dumps(r)


def test_ensure_invalid_update_secrets_rejected():
    c, op, _unused = mk()
    with pytest.raises(PpdmError, match="update_secrets"):
        c.ensure("credentials", {"name": "c1"}, update_secrets="never")
    assert op.calls == []


def test_ensure_missing_verb_raises_without_sending():
    c, op, _unused = mk(page([], 1, 0))
    with pytest.raises(PpdmError, match="POST"):
        c.ensure("storage-systems", {"name": "s"})
    assert writes(op) == []


def test_find_one_duplicate_names_fails_with_both_ids():
    c, op, _unused = mk(page([{"id": "a", "name": "n"}, {"id": "b", "name": "n"}], 1, 1))
    with pytest.raises(PpdmError) as e:
        c.find_one("credentials", "name", "n")
    assert "a" in e.value.msg and "b" in e.value.msg
    assert parse_qs(urlsplit(op.calls[0][0]).query)["filter"] == ['name eq "n"']


def test_remove_absent_is_noop():
    c, op, _unused = mk(page([], 1, 0))
    assert c.remove("credentials", "name", "n")["changed"] is False
    assert writes(op) == []


def test_remove_deletes_and_check_mode_does_not():
    obj = {"id": "1", "name": "n"}
    c, op, _unused = mk(page([obj], 1, 1), Resp(None, 204), page([obj], 1, 1))
    assert c.remove("credentials", "name", "n")["changed"]
    assert writes(op)[0][1]["method"] == "DELETE"
    assert c.remove("credentials", "name", "n", check_mode=True)["changed"]
    assert len(writes(op)) == 1


def test_strip_readonly_pure():
    src = {"a": 1, "_links": {}, "createdAt": "t"}
    assert strip_readonly("credentials", src) == {"a": 1}
    assert "_links" in src


def test_wait_activity_returns_on_terminal_state():
    c, op, sleeps = mk(
        Resp({"state": "RUNNING"}),
        Resp({"state": "COMPLETED", "result": {"status": "OK"}}),
    )
    assert c.wait_activity("x", timeout=60)["state"] == "COMPLETED"
    assert op.calls[0][0].endswith("/api/v3/activities/x") and len(sleeps) == 1


def test_wait_activity_times_out():
    c, _unused, sleeps = mk(*[Resp({"state": "RUNNING"})] * 10)
    with pytest.raises(PpdmError, match="timeout|timed out"):
        c.wait_activity("x", timeout=10, interval=5)
    assert sum(sleeps) >= 10


@pytest.mark.parametrize("interval", [0, -5])
def test_wait_activity_rejects_non_positive_interval(interval):
    c, op, _unused = mk()
    with pytest.raises(PpdmError, match="interval"):
        c.wait_activity("x", timeout=10, interval=interval)
    assert op.calls == []


def test_remove_masks_secrets_in_diff_before():
    obj = {"id": "1", "name": "n", "password": "hunter2"}
    c, _unused, _unused = mk(page([obj], 1, 1), Resp(None, 204))
    r = c.remove("credentials", "name", "n", secret_keys=["password"])
    assert r["diff"]["before"]["password"] == "VALUE_SPECIFIED_IN_NO_LOG_PARAMETER"
    assert "hunter2" not in json.dumps(r)


def test_item_path_id_is_quoted():
    c, _unused, _unused = mk()
    assert c._route("credentials", "GET", "../x?y#z").endswith("/..%2Fx%3Fy%23z")


def test_item_path_empty_id_raises():
    c, _unused, _unused = mk()
    with pytest.raises(PpdmError, match="id"):
        c._route("credentials", "GET", "")


def test_ensure_create_false_fails_on_missing_without_post():
    c, op, _unused = mk(page([], 1, 0))
    with pytest.raises(PpdmError, match="c1 not found"):
        c.ensure("credentials", {"name": "c1"}, create=False)
    assert writes(op) == []


def test_ensure_put_never_sends_back_a_masked_write_only_field():
    obj = {"id": "1", "name": "c1", "type": "X", "password": "****", "secretKey": "****"}
    c, op, _unused = mk(page([obj], 1, 1), Resp({"id": "1", "name": "c1", "type": "Y"}))
    r = c.ensure("credentials", {"name": "c1", "type": "Y"}, secret_keys=["password"])
    assert r["changed"]
    assert json.loads(writes(op)[0][1]["data"]) == {"id": "1", "name": "c1", "type": "Y"}


def test_ensure_put_keeps_a_write_only_field_the_caller_supplied():
    obj = {"id": "1", "name": "c1", "type": "X", "password": "****", "userKey": "****"}
    c, op, _unused = mk(page([obj], 1, 1), Resp({"id": "1", "name": "c1", "type": "Y"}))
    c.ensure("credentials", {"name": "c1", "type": "Y", "password": "pw"}, secret_keys=["password"])
    body = json.loads(writes(op)[0][1]["data"])
    assert body["password"] == "pw" and "userKey" not in body


POLICY = {"id": "p1", "name": "pol", "description": "old"}


def test_ensure_uses_patch_when_route_has_no_put():
    c, op, _unused = mk(page([POLICY], 1, 1), Resp({"id": "p1", "name": "pol", "description": "new"}))
    r = c.ensure("protection-policies", {"name": "pol", "description": "new"})
    assert r["changed"]
    url, kw = writes(op)[0]
    assert kw["method"] == "PATCH" and url.endswith("/api/v3/protection-policies/p1")


def test_ensure_explicit_verb_not_in_route_fails():
    c, op, _unused = mk(page([POLICY], 1, 1))
    with pytest.raises(PpdmError, match="does not support PUT"):
        c.ensure("protection-policies", {"name": "pol", "description": "new"}, update_verb="PUT")
    assert writes(op) == []


def test_ensure_put_unchanged_for_existing_resources():
    obj = {"id": "1", "name": "c1", "type": "X"}
    c, op, _unused = mk(page([obj], 1, 1), Resp({"id": "1", "name": "c1", "type": "Y"}))
    c.ensure("credentials", {"name": "c1", "type": "Y"})
    assert writes(op)[0][1]["method"] == "PUT"


def test_start_action_check_mode_sends_nothing():
    c, op, _unused = mk()
    r = c.start_action("/api/v3/protections", {"a": 1}, check_mode=True)
    assert r == {"changed": True, "response": None} and op.calls == []


def test_start_action_returns_response():
    c, op, _unused = mk(Resp({"id": "a1", "state": "QUEUED"}, 202))
    r = c.start_action("/api/v3/protections", {"a": 1}, check_mode=False)
    assert r["changed"] and r["response"] == {"id": "a1", "state": "QUEUED"}
    assert op.calls[0][1]["method"] == "POST"


def test_start_action_409_keeps_status():
    from ansible_collections.fjacquet.ppdm.tests.unit.module_utils.test_ppdm_client import http_error

    c, _op, _unused = mk(http_error(409, {"message": "already running"}))
    with pytest.raises(PpdmError) as ei:
        c.start_action("/api/v3/protections", {}, check_mode=False)
    assert ei.value.status == 409


def done(status, error=None):
    return Resp({"id": "a", "state": "COMPLETED", "result": {"status": status, "error": error}})


@pytest.mark.parametrize("status", ["OK", "SUCCESS"])
def test_await_activity_success(status):
    c, _unused, _unused = mk(done(status))
    assert "warnings" not in c.await_activity("a", 10)


@pytest.mark.parametrize("status", ["OK_WITH_ERRORS", "COMPLETED_WITH_EXCEPTIONS"])
def test_await_activity_warns(status):
    c, _unused, _unused = mk(done(status, "boom"))
    assert len(c.await_activity("a", 10)["warnings"]) == 1


@pytest.mark.parametrize("status", ["FAILED", "CANCELED", "SKIPPED", "RETRIED", None])
def test_await_activity_failing_status_raises_with_body(status):
    c, _unused, _unused = mk(done(status))
    with pytest.raises(PpdmError, match=str(status)) as e:
        c.await_activity("a", 10)
    assert e.value.body["result"]["status"] == status


SMTP = {"id": "s1", "server": "mail", "port": 25}


def test_ensure_singleton_creates_when_none():
    c, op, _unused = mk(page([], 1, 0), Resp({"id": "s1", "server": "mail"}, 201))
    assert c.ensure("smtp", {"server": "mail"}, key=None)["changed"]
    url, kw = writes(op)[0]
    assert kw["method"] == "POST" and url.endswith("/api/v2/smtp")


def test_ensure_singleton_puts_on_difference():
    c, op, _unused = mk(page([SMTP], 1, 1), Resp(SMTP))
    assert c.ensure("smtp", {"server": "other"}, key=None)["changed"]
    url, kw = writes(op)[0]
    assert kw["method"] == "PUT" and url.endswith("/api/v2/smtp/s1")


def test_ensure_singleton_same_no_write():
    c, op, _unused = mk(page([SMTP], 1, 1))
    assert not c.ensure("smtp", {"server": "mail"}, key=None)["changed"]
    assert writes(op) == []


def test_ensure_singleton_many_fails_without_write():
    c, op, _unused = mk(page([SMTP, dict(SMTP, id="s2")], 1, 1))
    with pytest.raises(PpdmError, match="smtp: 2 objects exist, expected at most one") as e:
        c.ensure("smtp", {"server": "mail"}, key=None)
    assert "s1" in e.value.msg and writes(op) == []


def test_ensure_singleton_create_false_message():
    c, _unused, _unused = mk(page([], 1, 0))
    with pytest.raises(PpdmError, match="smtp: no object exists"):
        c.ensure("smtp", {"server": "mail"}, key=None, create=False)


def test_remove_singleton():
    c, op, _unused = mk(page([SMTP], 1, 1), Resp(None, 204))
    assert c.remove("smtp", None, None)["changed"]
    url, kw = writes(op)[0]
    assert kw["method"] == "DELETE" and url.endswith("/api/v2/smtp/s1")


def test_remove_singleton_none_is_noop():
    c, op, _unused = mk(page([], 1, 0))
    assert c.remove("smtp", None, None)["changed"] is False
    assert writes(op) == []


def test_await_activity_failure_message_falls_back_to_issues():
    c, _unused, _unused = mk(
        Resp({"id": "a", "state": "COMPLETED", "result": {"status": "FAILED", "issues": "disk full"}})
    )
    with pytest.raises(PpdmError, match="disk full"):
        c.await_activity("a", 10)
