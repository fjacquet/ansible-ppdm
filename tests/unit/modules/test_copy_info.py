from urllib.parse import parse_qs, urlsplit

from ansible_collections.fjacquet.ppdm.plugins.modules import copy_info
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    http_error,
    run_module,
)


def run(monkeypatch, opener, check_mode=False, **args):
    return run_module(monkeypatch, copy_info, opener, check_mode=check_mode, **args)


def query(op, n=0):
    return parse_qs(urlsplit(op.calls[n][0]).query)


def test_by_id(monkeypatch):
    op = FakeOpener(Resp({"id": "c/1"}))
    out = run(monkeypatch, op, id="c/1")
    assert out["failed"] is False and out["changed"] is False
    assert out["copies"] == [{"id": "c/1"}]
    assert urlsplit(op.calls[0][0]).path == "/api/v3/copies/c%2F1"


def test_by_id_404_is_empty(monkeypatch):
    op = FakeOpener(http_error(404, {"message": "nope"}))
    out = run(monkeypatch, op, id="zz")
    assert out["failed"] is False and out["copies"] == []


def test_by_id_204_is_empty(monkeypatch):
    out = run(monkeypatch, FakeOpener(Resp(None, status=204)), id="zz")
    assert out["failed"] is False and out["copies"] == []


def test_by_asset_id_paged(monkeypatch):
    op = FakeOpener(Resp({"content": [{"id": "1"}], "page": {"totalPages": 1, "number": 1}}))
    out = run(monkeypatch, op, asset_id="a/1", filter='state eq "X"')
    assert out["copies"] == [{"id": "1"}]
    assert urlsplit(op.calls[0][0]).path == "/api/v2/assets/a%2F1/copies"
    assert query(op)["filter"] == ['state eq "X"']
    assert "page" in query(op)


def test_latest_asset_ids(monkeypatch):
    op = FakeOpener(Resp({"content": [{"id": "1"}, {"id": "2"}]}))
    out = run(monkeypatch, op, latest_asset_ids=["a", "b"])
    assert out["copies"] == [{"id": "1"}, {"id": "2"}]
    assert len(op.calls) == 1
    assert urlsplit(op.calls[0][0]).path == "/api/v2/latest-copies"
    assert query(op) == {"filter": ['assetId in ("a", "b")']}


def test_latest_asset_ids_with_filter_escaped(monkeypatch):
    op = FakeOpener(Resp({"content": []}))
    out = run(monkeypatch, op, latest_asset_ids=['a"b'], filter="x eq 1")
    assert out["copies"] == []
    assert query(op)["filter"] == ['assetId in ("a\\"b") and (x eq 1)']


def test_modes_exclusive(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, id="a", asset_id="b")
    assert out["failed"] and "mutually exclusive" in out["msg"] and op.calls == []


def test_none_given(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op)
    assert out["failed"] and op.calls == []


def test_empty_latest_asset_ids_fails(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, latest_asset_ids=[])
    assert out["failed"] and op.calls == []


def test_filter_with_id_fails(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, id="a", filter="f")
    assert out["failed"] and "filter" in out["msg"] and op.calls == []


def test_latest_asset_ids_are_chunked(monkeypatch):
    ids = ["a%d" % i for i in range(120)]
    op = FakeOpener(*(Resp({"content": [{"id": "c%d" % i}]}) for i in range(3)))
    out = run(monkeypatch, op, latest_asset_ids=ids)
    assert len(op.calls) == 3 and [c["id"] for c in out["copies"]] == ["c0", "c1", "c2"]
    assert query(op, 0)["filter"][0].count('"a') == 50 and query(op, 2)["filter"][0].count('"a') == 20
