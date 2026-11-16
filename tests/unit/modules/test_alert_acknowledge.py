import json
from urllib.parse import urlsplit

from ansible_collections.fjacquet.ppdm.plugins.modules import alert_acknowledge
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    http_error,
    methods,
    run_module,
)


def alert(i, state="UNACKNOWLEDGED"):
    return Resp({"id": i, "acknowledgement": {"acknowledgeState": state}})


def run(monkeypatch, op, **kw):
    check = kw.pop("check_mode", False)
    return run_module(monkeypatch, alert_acknowledge, op, check_mode=check, **kw)


def bulk(*items):
    return Resp({"bulkResults": list(items)}, 207)


def test_acknowledge_skips_already_acknowledged(monkeypatch):
    op = FakeOpener(alert("a"), alert("b", "ACKNOWLEDGED"), bulk({"id": "a"}))
    out = run(monkeypatch, op, ids=["a", "b"])
    assert out["changed"] and out["updated_ids"] == ["a"] and out["results"] == [{"id": "a"}]
    assert methods(op) == ["GET", "GET", "POST"]
    assert urlsplit(op.calls[2][0]).path == "/api/v2/alerts/acknowledgements"
    assert json.loads(op.calls[2][1]["data"]) == {
        "messageIds": ["a"],
        "acknowledgement": {"acknowledgeState": "ACKNOWLEDGED"},
    }


def test_all_acknowledged_is_noop(monkeypatch):
    op = FakeOpener(alert("a", "ACKNOWLEDGED"))
    out = run(monkeypatch, op, ids=["a"])
    assert not out["changed"] and out["updated_ids"] == [] and methods(op) == ["GET"]


def test_unacknowledge(monkeypatch):
    op = FakeOpener(alert("a", "ACKNOWLEDGED"), bulk({"id": "a"}))
    out = run(monkeypatch, op, ids=["a"], acknowledge_state="UNACKNOWLEDGED")
    assert out["changed"]
    assert json.loads(op.calls[1][1]["data"])["acknowledgement"] == {"acknowledgeState": "UNACKNOWLEDGED"}


def test_partial_error_fails_and_keeps_results(monkeypatch):
    op = FakeOpener(alert("a"), alert("b"), bulk({"id": "a"}, {"id": "b", "errorResponseObject": {"message": "boom"}}))
    out = run(monkeypatch, op, ids=["a", "b"])
    assert out["failed"] and "boom" in out["msg"] and len(out["results"]) == 2


def test_missing_id_fails_before_write(monkeypatch):
    op = FakeOpener(alert("a"), http_error(404, {"message": "nope"}))
    out = run(monkeypatch, op, ids=["a", "zz"])
    assert out["failed"] and "zz" in out["msg"] and methods(op) == ["GET", "GET"]


def test_check_mode_sends_no_post(monkeypatch):
    op = FakeOpener(alert("a"))
    out = run(monkeypatch, op, ids=["a"], check_mode=True)
    assert out["changed"] and out["updated_ids"] == ["a"] and methods(op) == ["GET"]


def test_empty_ids_fails(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, ids=[])
    assert out["failed"] and op.calls == []


def test_fewer_acknowledged_than_sent_fails(monkeypatch):
    op = FakeOpener(alert("a"), alert("b"), alert("c"), Resp({"acknowledgementCount": 1, "bulkResults": []}, 207))
    out = run(monkeypatch, op, ids=["a", "b", "c"])
    assert out["failed"] and "1 of 3" in out["msg"]


def test_bulk_error_id_is_scrubbed(monkeypatch):
    bad = "id-s3cret-9"  # contains the connection password
    op = FakeOpener(alert(bad), bulk({"id": bad, "errorResponseObject": {"message": "x"}}))
    out = run(monkeypatch, op, ids=[bad])
    assert out["failed"] and "s3cret" not in out["msg"]
