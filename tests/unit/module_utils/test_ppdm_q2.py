"""Q2 client residuals: id encoding, scrub of server text, response bounds, hostname validation."""

import pytest
from ansible_collections.fjacquet.ppdm.plugins.module_utils import ppdm
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmClient, PpdmError, quote_id
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import FakeOpener, Resp


def mk(*responses, password="S3cret!", host="ppdm.local"):
    op = FakeOpener(*responses)
    return PpdmClient(host, "admin", password, opener=op, sleep=lambda s: None), op


def page(items, total):
    return Resp({"content": items, "page": {"totalPages": total}})


# Q2.1


@pytest.mark.parametrize(
    "value,expected",
    [
        ("..", "%2E%2E"),
        (".", "%2E"),
        ("a.b", "a.b"),
        ("a/b", "a%2Fb"),
        ("a?b", "a%3Fb"),
        ("%2e%2e", "%252e%252e"),
        ("é", "%C3%A9"),
        ("...", "..."),
    ],
)
def test_quote_id(value, expected):
    assert quote_id(value) == expected


def test_quote_id_refuses_empty():
    with pytest.raises(PpdmError, match="empty"):
        quote_id("")


@pytest.mark.parametrize("bad", ["..", "."])
def test_route_encodes_dot_ids(bad):
    c, _ = mk()
    assert c._route("credentials", "DELETE", bad).endswith("/" + quote_id(bad))
    assert not c._route("credentials", "DELETE", bad).endswith("/..")


def test_certificate_item_path_keeps_inner_dots():
    from ansible_collections.fjacquet.ppdm.plugins.modules import certificate

    assert certificate.item_path("a.b-1") == "/api/v2/certificates/a.b-1"
    assert certificate.item_path("..") == "/api/v2/certificates/%2E%2E"


# Q2.3


def test_total_pages_error_does_not_echo_secrets():
    c, _ = mk(page([], "x" + "S3cret!"))
    with pytest.raises(PpdmError) as e:
        c.list_all("credentials")
    assert "S3cret!" not in e.value.msg


def test_duplicate_message_scrubs_server_values():
    c, _ = mk(
        Resp({"access_token": "TOK-123456"}),
        page([{"id": "S3cret!1", "name": "a"}, {"id": "2", "name": "a"}], 1),
    )
    c.login()
    with pytest.raises(PpdmError) as e:
        c.find_one("credentials", "name", "a")
    assert "S3cret!" not in e.value.msg


def test_scrub_single_pass_password_overlapping_token_edge():
    tok = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.sig"
    pw = "echo Bearer " + tok[:38]
    c, _ = mk(Resp({"access_token": tok}), password=pw)
    c.login()
    out = c._scrub("echo Bearer " + tok)
    assert tok[30:] not in out and tok[:12] not in out


# Q2.4


def test_page_with_too_many_items_rejected():
    c, _ = mk(page(list(range(ppdm.PAGE_SIZE + 1)), 1))
    with pytest.raises(PpdmError, match="items"):
        c.list_all("credentials")


def test_page_at_page_size_ok():
    c, _ = mk(page(list(range(ppdm.PAGE_SIZE)), 1))
    assert len(c.list_all("credentials")) == ppdm.PAGE_SIZE


def test_oversized_body_rejected(monkeypatch):
    monkeypatch.setattr(ppdm, "MAX_BODY_BYTES", 10)
    big = Resp()
    big._raw = b'{"a": "' + b"x" * 20 + b'"}'
    c, _ = mk(big)
    with pytest.raises(PpdmError, match="too large"):
        c.request("GET", "/x")


def test_body_at_limit_ok(monkeypatch):
    monkeypatch.setattr(ppdm, "MAX_BODY_BYTES", 8)
    r = Resp()
    r._raw = b'{"a": 1}'
    c, _ = mk(r)
    assert c.request("GET", "/x") == {"a": 1}


# Q2.9


@pytest.mark.parametrize(
    "host,netloc",
    [
        ("a.b.c", "a.b.c"),
        ("10.0.0.1", "10.0.0.1"),
        ("[::1]", "[::1]"),
        ("::1", "[::1]"),
        ("2001:db8::1", "[2001:db8::1]"),
    ],
)
def test_hostname_accepted(host, netloc):
    c, _ = mk(host=host)
    assert c.base_url == "https://%s:8443" % netloc


@pytest.mark.parametrize(
    "host",
    [
        "user@host",
        "https://host",
        "host:8443",
        "host/path",
        "host?x",
        "host#f",
        " ",
        "a b",
        "",
        "[::1",
        "[host]",
        "a\\b",
    ],
)
def test_hostname_rejected(host):
    with pytest.raises(PpdmError, match="hostname"):
        mk(host=host)


def test_client_from_module_fails_cleanly_on_bad_hostname():
    class M:
        params = dict(
            hostname="user@host", username="u", password="p", port=8443, validate_certs=True, ca_path=None, timeout=5
        )

        def fail_json(self, **kw):
            raise SystemExit(kw["msg"])

    with pytest.raises(SystemExit, match="hostname"):
        ppdm.client_from_module(M())
