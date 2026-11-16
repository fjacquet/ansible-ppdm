from urllib.parse import parse_qs, urlsplit

from ansible_collections.fjacquet.ppdm.plugins.modules import activity_info
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    http_error,
    run_module,
)


def run(monkeypatch, opener, check_mode=False, **args):
    return run_module(monkeypatch, activity_info, opener, check_mode=check_mode, **args)


def test_by_id(monkeypatch):
    op = FakeOpener(Resp({"id": "a/1", "state": "COMPLETED"}))
    out = run(monkeypatch, op, id="a/1")
    assert out["failed"] is False and out["changed"] is False
    assert out["activities"] == [{"id": "a/1", "state": "COMPLETED"}]
    assert urlsplit(op.calls[0][0]).path == "/api/v3/activities/a%2F1"


def test_by_id_with_steps(monkeypatch):
    steps = {"content": [{"name": "s1"}, {"name": "s2"}], "page": {"totalPages": 1, "number": 1}}
    op = FakeOpener(Resp({"id": "a1"}), Resp(steps))
    out = run(monkeypatch, op, id="a1", steps=True)
    assert out["activities"] == [{"id": "a1", "steps": [{"name": "s1"}, {"name": "s2"}]}]
    assert [urlsplit(c[0]).path for c in op.calls] == ["/api/v3/activities/a1", "/api/v3/activities/a1/steps"]


def test_404_is_empty(monkeypatch):
    op = FakeOpener(http_error(404, {"message": "nope"}))
    out = run(monkeypatch, op, id="zz", steps=True)
    assert out["failed"] is False and out["activities"] == []
    assert len(op.calls) == 1


def test_filter_forwarded(monkeypatch):
    op = FakeOpener(Resp({"content": [{"id": "1"}], "page": {"totalPages": 1, "number": 1}}))
    out = run(monkeypatch, op, filter='state eq "RUNNING"')
    assert out["activities"] == [{"id": "1"}]
    assert parse_qs(urlsplit(op.calls[0][0]).query)["filter"] == ['state eq "RUNNING"']


def test_steps_without_id_fails_before_any_request(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, steps=True)
    assert out["failed"] and "steps" in out["msg"] and op.calls == []


def test_id_and_filter_exclusive(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, id="a", filter="f")
    assert out["failed"] and "mutually exclusive" in out["msg"] and op.calls == []


def test_check_mode_identical(monkeypatch):
    out = run(monkeypatch, FakeOpener(Resp({"id": "a1"})), check_mode=True, id="a1")
    assert out["activities"] == [{"id": "a1"}] and out["changed"] is False
