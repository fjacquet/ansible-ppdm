import json

import pytest
from ansible_collections.fjacquet.ppdm.plugins.modules import certificate
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    FakeOpener,
    Resp,
    methods,
    run_module,
)

BASE = {
    "id": "c1",
    "host": "dd01",
    "port": "3009",
    "type": "HOST",
    "fingerprint": "AB:CD",
}


def cert(state, **kw):
    return dict(BASE, state=state, **kw)


def run(monkeypatch, op, **kw):
    return run_module(
        monkeypatch,
        certificate,
        op,
        **dict(dict(host="dd01", port=3009, fingerprint="AB:CD"), **kw),
    )


def test_present_without_fingerprint_fails_before_any_request(monkeypatch):
    op = FakeOpener()
    out = run(monkeypatch, op, fingerprint=None)
    assert out["failed"] and not op.calls and "accept_any_certificate" in out["msg"]


def test_accept_any_warns_and_accepts_unknown(monkeypatch):
    warns = []
    monkeypatch.setattr(
        certificate.AnsibleModule,
        "warn",
        lambda self, m: warns.append(m),
        raising=False,
    )
    op = FakeOpener(Resp([cert("UNKNOWN")]), Resp(cert("ACCEPTED")))
    out = run(monkeypatch, op, fingerprint=None, accept_any_certificate=True)
    assert out["changed"] and methods(op) == ["GET", "PUT"] and warns
    assert "nocache" not in op.calls[0][0]


@pytest.mark.parametrize("state", ["MISMATCHED", "EXPIRED", "MALFORMED", "REJECTED"])
def test_accept_any_refuses_other_states(monkeypatch, state):
    op = FakeOpener(Resp([cert(state)]))
    out = run(monkeypatch, op, fingerprint=None, accept_any_certificate=True)
    assert out["failed"] and state in out["msg"] and methods(op) == ["GET"]


@pytest.mark.parametrize("state", ["UNKNOWN", "MISMATCHED", "REJECTED"])
def test_pin_match_accepts(monkeypatch, state):
    op = FakeOpener(Resp([cert(state)]), Resp(cert("ACCEPTED")))
    out = run(monkeypatch, op)
    assert out["changed"] and methods(op) == ["GET", "PUT"]
    assert op.calls[1][0].endswith("/api/v2/certificates/c1")
    body = json.loads(op.calls[1][1]["data"])
    assert body["state"] == "ACCEPTED" and body["fingerprint"] == "AB:CD" and body["host"] == "dd01"
    assert out["certificate"]["state"] == "ACCEPTED"


def test_pin_mismatch_fails_no_write(monkeypatch):
    op = FakeOpener(Resp([cert("UNKNOWN")]))
    out = run(monkeypatch, op, fingerprint="XX")
    assert out["failed"] and methods(op) == ["GET"]


@pytest.mark.parametrize("state", ["EXPIRED", "MALFORMED"])
def test_pin_match_expired_malformed_fail(monkeypatch, state):
    op = FakeOpener(Resp([cert(state)]))
    out = run(monkeypatch, op)
    assert out["failed"] and state in out["msg"] and methods(op) == ["GET"]


def test_fingerprint_normalised(monkeypatch):
    op = FakeOpener(Resp([cert("UNKNOWN")]), Resp(cert("ACCEPTED")))
    assert run(monkeypatch, op, fingerprint="ab:cd")["changed"]
    op = FakeOpener(Resp([cert("UNKNOWN", fingerprint="abcd")]), Resp(cert("ACCEPTED")))
    assert run(monkeypatch, op, fingerprint="AB:CD")["changed"]


def test_idempotent(monkeypatch):
    op = FakeOpener(Resp([cert("ACCEPTED")]))
    out = run(monkeypatch, op)
    assert not out["changed"] and methods(op) == ["GET"]


def test_accepted_with_different_fingerprint_fails(monkeypatch):
    op = FakeOpener(Resp([cert("ACCEPTED")]))
    out = run(monkeypatch, op, fingerprint="EE:FF")
    assert out["failed"] and methods(op) == ["GET"]


def test_ambiguous_fails(monkeypatch):
    op = FakeOpener(Resp([cert("UNKNOWN"), cert("UNKNOWN", id="c2")]))
    out = run(monkeypatch, op)
    assert out["failed"] and "c1" in out["msg"] and "c2" in out["msg"] and methods(op) == ["GET"]


def test_matching_is_exact_host_port_type(monkeypatch):
    nohost = {k: v for k, v in cert("UNKNOWN").items() if k != "host"}
    for other in (nohost, cert("UNKNOWN", port="1"), cert("UNKNOWN", type="ROOT")):
        out = run(monkeypatch, FakeOpener(Resp([other])))
        assert out["failed"] and "no certificate" in out["msg"]
    op = FakeOpener(Resp([cert("UNKNOWN", host="DD01")]), Resp(cert("ACCEPTED")))
    assert run(monkeypatch, op)["changed"]


def test_no_id_posts(monkeypatch):
    c = {k: v for k, v in cert("UNKNOWN").items() if k != "id"}
    op = FakeOpener(Resp([c]), Resp(cert("ACCEPTED")))
    out = run(monkeypatch, op)
    assert out["changed"] and methods(op) == ["GET", "POST"]
    assert json.loads(op.calls[1][1]["data"])["state"] == "ACCEPTED"


def test_check_mode_uses_nocache_no_write(monkeypatch):
    op = FakeOpener(Resp([cert("UNKNOWN")]))
    out = run(monkeypatch, op, check_mode=True)
    assert out["changed"] and methods(op) == ["GET"] and "nocache=true" in op.calls[0][0]


def test_absent_deletes_with_nocache(monkeypatch):
    op = FakeOpener(Resp([cert("ACCEPTED")]), Resp(None, 204))
    out = run(monkeypatch, op, state="absent", fingerprint=None)
    assert out["changed"] and methods(op) == ["GET", "DELETE"]
    assert "nocache=true" in op.calls[0][0] and op.calls[1][0].endswith("/api/v2/certificates/c1")


def test_absent_missing_is_noop(monkeypatch):
    for listing in ([], [cert("UNKNOWN")]):
        op = FakeOpener(Resp(listing))
        out = run(monkeypatch, op, state="absent", fingerprint=None)
        assert not out["changed"] and methods(op) == ["GET"]


def test_absent_check_mode(monkeypatch):
    op = FakeOpener(Resp([cert("ACCEPTED")]))
    out = run(monkeypatch, op, state="absent", check_mode=True, fingerprint=None)
    assert out["changed"] and methods(op) == ["GET"]


@pytest.mark.parametrize("fp", [":", "::"])
def test_fingerprint_normalising_to_empty_is_rejected(monkeypatch, fp):
    op = FakeOpener()
    out = run(monkeypatch, op, fingerprint=fp)
    assert out["failed"] and "fingerprint" in out["msg"] and not op.calls
