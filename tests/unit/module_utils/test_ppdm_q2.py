"""Q2 client residuals: id encoding, scrub of server text, response bounds, hostname validation."""

import io
import json
import urllib.error

import pytest
from ansible_collections.fjacquet.ppdm.plugins.module_utils import ppdm
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmClient, PpdmError, quote_id
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import FakeOpener, Resp, http_error


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


# Fix round 1

TOK = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.sig"


def _no_run_of_8(text, secret):
    return not any(secret[i : i + 8] in text for i in range(len(secret) - 7))


def _logged(pw):
    c, _ = mk(Resp({"access_token": TOK}), password=pw)
    c.login()
    return c


@pytest.mark.parametrize(
    "pw",
    [
        "echo Bearer " + TOK[:38],  # left edge overlap
        TOK[10:] + " tail",  # right edge overlap
        "x" + TOK[10:30] + "y",  # middle
        "Bearer " + TOK[:20],
        TOK[:25],
    ],
)
def test_scrub_overlap_leaves_no_token_run(pw):
    c = _logged(pw)
    for text in ("echo Bearer " + TOK, TOK + " " + pw, pw + TOK):
        out = c.scrub(text)
        assert TOK[38:] not in out and _no_run_of_8(out, TOK), (pw, text, out)


def test_scrub_equal_length_overlapping_secrets():
    c, _ = mk(password="abcdefghij")
    c.token = "efghijklmn"
    out = c.scrub("..abcdefghijklmn..")
    assert out == "..********.." and "klmn" not in out


@pytest.mark.parametrize("which", ["password", "token"])
@pytest.mark.parametrize("shape", ["key", "nested", "list", "detail_key"])
def test_scrub_covers_dict_keys_and_messages(which, shape):
    c = _logged("S3cret!")
    secret = "S3cret!" if which == "password" else TOK
    value = {
        "key": {secret: 1},
        "nested": {"a": [{secret: 1}]},
        "list": [secret, [secret]],
        "detail_key": {"message": {secret: 1}},
    }[shape]
    assert secret not in repr(c.scrub(value))
    # totalPages and HTTP error detail
    c2 = _logged("S3cret!")
    c2.opener = FakeOpener(page([], value))
    with pytest.raises(PpdmError) as e:
        c2.list_all("credentials")
    assert secret not in e.value.msg
    c2.opener = FakeOpener(
        __import__("ansible_collections.fjacquet.ppdm.tests.unit.helpers", fromlist=["x"]).http_error(
            400, {"message": value}
        )
    )
    with pytest.raises(PpdmError) as e:
        c2.request("GET", "/x")
    assert secret not in e.value.msg and secret not in repr(e.value.body)


def test_scrub_never_raises_on_odd_secrets():
    c, _ = mk(password=12345)
    c.token = ["x"]
    assert c.scrub("a 12345 b") == "a 12345 b"


@pytest.mark.parametrize("tok", [12345, [], "", None, {"a": 1}])
def test_login_requires_string_token(tok):
    c, _ = mk(Resp({"access_token": tok}))
    with pytest.raises(PpdmError, match="access_token"):
        c.login()
    assert c.token is None


@pytest.mark.parametrize("bad", [None, ""])
def test_item_verbs_never_fall_back_to_collection(bad):
    c, _ = mk()
    for verb in ("PUT", "DELETE", "PATCH"):
        if verb in ppdm.ROUTES["credentials"]["methods"]:
            with pytest.raises(PpdmError):
                c._route("credentials", verb, bad)


@pytest.mark.parametrize(
    "entry", [{"name": "a", "id": None}, {"name": "a"}, {"name": "a", "id": ""}, {"name": "a", "id": 5}]
)
def test_remove_and_ensure_require_string_id(entry):
    c, op = mk(page([entry], 1))
    with pytest.raises(PpdmError, match="id"):
        c.remove("credentials", "name", "a")
    assert len(op.calls) == 1  # the listing only
    c, op = mk(page([entry], 1))
    with pytest.raises(PpdmError, match="id"):
        c.ensure("credentials", {"name": "a", "type": "x"})
    assert len(op.calls) == 1


def test_wait_activity_timeout_scrubs_state():
    c = _logged("S3cret!")
    c.opener = FakeOpener(Resp({"id": "a", "state": TOK}))
    with pytest.raises(PpdmError) as e:
        c.wait_activity("a", 0)
    assert TOK not in e.value.msg


@pytest.mark.parametrize(
    "host",
    [
        "a\x00b",
        "a\x7fb",
        "a;b",
        "a<b",
        "a>b",
        'a"b',
        "a{b}",
        "a|b",
        "a^b",
        "a​b",
        "a．b",
        "bücher.de",
        "a" * 5000,
        "a.b\n",
        "-a.b",
        "a-.b",
        "a..b",
        "a b",
        "[1.2.3.4]",
        "fe80::1%eth0",
        "::g",
        "[::1]x",
        "a" * 64 + ".com",
    ],
)
def test_hostname_allowlist_rejects(host):
    with pytest.raises(PpdmError, match="hostname"):
        mk(host=host)


@pytest.mark.parametrize(
    "host", ["localhost", "a-b.c1.example.com", "host.", "1.2.3.4", "A.B", "a" * 63, "[2001:DB8::1]"]
)
def test_hostname_allowlist_accepts(host):
    mk(host=host)


def test_hostname_ipv6_normalised():
    c, _ = mk(host="2001:DB8:0:0:0:0:0:1")
    assert c.base_url == "https://[2001:db8::1]:8443"


# Fix round 2: repr escapes must not hide a secret from the scrubber

NASTY = ["p\\w", "a\nb", "it's\"x", "z​z", "\x07bell", "t\tab", "smile\U0001f600x"]


def _forms(secret):
    return {secret, repr(secret)[1:-1], json.dumps(secret)[1:-1], json.dumps(secret, ensure_ascii=False)[1:-1]}


def _shapes(secret):
    return {
        "key": {secret: 1},
        "nested": {"a": [{secret: [secret]}]},
        "list": [secret, [secret]],
        "plain": secret,
    }


def _leaks(secret, text):
    return [f for f in _forms(secret) if f in text]


@pytest.fixture(params=NASTY)
def nasty(request):
    return request.param


@pytest.mark.parametrize("shape", ["key", "nested", "list", "plain"])
@pytest.mark.parametrize("which", ["password", "token"])
def test_messages_hide_escaped_secrets(nasty, shape, which):
    pw, tok = (nasty, TOK) if which == "password" else ("S3cret!", nasty)
    secret = nasty
    c, _ = mk(Resp({"access_token": tok}), password=pw)
    c.login()
    value = _shapes(secret)[shape]
    msgs = []
    # totalPages
    c.opener = FakeOpener(page([], value))
    with pytest.raises(PpdmError) as e:
        c.list_all("credentials")
    msgs.append(e.value.msg)
    # HTTP error detail
    c.opener = FakeOpener(http_error(400, {"message": value}))
    with pytest.raises(PpdmError) as e:
        c.request("GET", "/x")
    msgs += [e.value.msg, repr(e.value.body)]
    # find_one duplicates
    c.opener = FakeOpener(page([{"id": value, "name": "a"}, {"id": value, "name": "a"}], 1))
    with pytest.raises(PpdmError) as e:
        c.find_one("credentials", "name", "a")
    msgs.append(e.value.msg)
    # wait_activity timeout
    c.opener = FakeOpener(Resp({"id": "a", "state": value}))
    with pytest.raises(PpdmError) as e:
        c.wait_activity(value, 0)
    msgs.append(e.value.msg)
    for m in msgs:
        assert not _leaks(secret, m), (secret, shape, m)


def test_huge_error_body_is_bounded_and_fast():
    import time

    big = '{"message": "' + "a" * (5 * 1024 * 1024) + '"}'
    err = urllib.error.HTTPError("u", 500, "x", {}, io.BytesIO(big.encode()))
    c, _ = mk(err, password="a")
    t = time.time()
    with pytest.raises(PpdmError) as e:
        c.request("GET", "/x")
    assert time.time() - t < 1.0
    assert len(e.value.msg) <= 70 * 1024 and "a" not in e.value.msg.split("HTTP 500", 1)[1]
