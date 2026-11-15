import json

from ansible_collections.fjacquet.ppdm.plugins.modules import certificate
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import FakeOpener, Resp, methods, run_module

BASE = {"id": "c1", "host": "dd01", "port": "3009", "type": "HOST", "fingerprint": "AB:CD"}
UNTRUSTED = [dict(BASE, state="UNKNOWN")]
TRUSTED = [dict(BASE, state="ACCEPTED")]


def run(monkeypatch, op, **kw):
    return run_module(monkeypatch, certificate, op, **dict(dict(host="dd01", port=3009), **kw))


def test_certificate_accepts_untrusted(monkeypatch):
    op = FakeOpener(Resp(UNTRUSTED), Resp(TRUSTED[0]))
    out = run(monkeypatch, op)
    assert out["changed"] and methods(op) == ["GET", "PUT"]
    assert "host=dd01" in op.calls[0][0] and "port=3009" in op.calls[0][0] and "type=HOST" in op.calls[0][0]
    assert op.calls[1][0].endswith("/api/v2/certificates/c1")
    assert json.loads(op.calls[1][1]["data"])["state"] == "ACCEPTED"
    assert out["certificate"]["state"] == "ACCEPTED"


def test_certificate_idempotent(monkeypatch):
    op = FakeOpener(Resp(TRUSTED))
    out = run(monkeypatch, op)
    assert not out["changed"] and methods(op) == ["GET"]


def test_certificate_check_mode_sends_no_write(monkeypatch):
    op = FakeOpener(Resp(UNTRUSTED))
    out = run(monkeypatch, op, check_mode=True)
    assert out["changed"] and methods(op) == ["GET"]


def test_certificate_fingerprint_mismatch_fails(monkeypatch):
    op = FakeOpener(Resp(UNTRUSTED))
    out = run(monkeypatch, op, fingerprint="XX")
    assert out["failed"] and methods(op) == ["GET"]


def test_certificate_none_presented_fails(monkeypatch):
    out = run(monkeypatch, FakeOpener(Resp([])))
    assert out["failed"]


def test_certificate_absent_deletes(monkeypatch):
    op = FakeOpener(Resp(TRUSTED), Resp(None, 204))
    out = run(monkeypatch, op, state="absent")
    assert out["changed"] and methods(op) == ["GET", "DELETE"]
    assert op.calls[1][0].endswith("/api/v2/certificates/c1")


def test_certificate_absent_missing_is_noop(monkeypatch):
    for listing in ([], UNTRUSTED):
        op = FakeOpener(Resp(listing))
        out = run(monkeypatch, op, state="absent")
        assert not out["changed"] and methods(op) == ["GET"]


def test_certificate_absent_check_mode(monkeypatch):
    op = FakeOpener(Resp(TRUSTED))
    out = run(monkeypatch, op, state="absent", check_mode=True)
    assert out["changed"] and methods(op) == ["GET"]
