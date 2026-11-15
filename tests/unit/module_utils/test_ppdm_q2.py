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
    c, _ = mk(password=pw)
    c.token = tok  # set directly: login() refuses a non-printable token, a hostile echo must still be hidden
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


# Fix round 3

NASTY3 = NASTY + ["plain-secret-1"]


def _err(body, pw, status=400):
    raw = body if isinstance(body, bytes) else body.encode()
    c, _ = mk(urllib.error.HTTPError("u", status, "x", {}, io.BytesIO(raw)), password=pw)
    with pytest.raises(PpdmError) as e:
        c.request("GET", "/x")
    return e.value


def _leak_check(pw, err):
    text = err.msg + "\n" + (err.body if isinstance(err.body, str) else json.dumps(err.body, ensure_ascii=False))
    assert not _leaks(pw, text), (pw, text[:200])


@pytest.mark.parametrize("pw", NASTY3)
@pytest.mark.parametrize("delta", [0, 1, 70000])
def test_json_error_body_around_the_cut_hides_escaped_secret(pw, delta):
    base = len(json.dumps({"message": pw, "pad": ""}).encode())
    body = json.dumps({"message": pw, "pad": "x" * (ppdm.MAX_ERROR_TEXT - base + delta)})
    assert len(body.encode()) == ppdm.MAX_ERROR_TEXT + delta
    _leak_check(pw, _err(body, pw))


@pytest.mark.parametrize("pw", NASTY3)
def test_non_json_error_body_hides_json_escaped_secret(pw):
    _leak_check(pw, _err("oops " + json.dumps(pw) + " / " + json.dumps(pw, ensure_ascii=False) + " / " + repr(pw), pw))


def test_secret_straddling_the_cut_leaves_no_prefix():
    pw = "hunter2SuperSecret"
    body = "x" * (ppdm.MAX_ERROR_TEXT - 17) + pw + "y" * 5000
    err = _err(body, pw)
    for text in (err.body, err.msg):
        assert not any(text.endswith(pw[:k]) or pw[:k] + "y" in text for k in range(3, len(pw) + 1)), text[-40:]
    assert len(err.body) <= ppdm.MAX_ERROR_TEXT


def test_error_body_over_scrub_limit_is_omitted():
    big = b"A" * (2 * 1024 * 1024) + b"secret-Q"
    err = _err(big, "secret-Q")
    assert err.body == "<error body of %d bytes omitted>" % len(big)
    assert "AAAA" not in err.msg and "AAAA" not in err.body


@pytest.mark.parametrize("tok", ["a\nb", "a\rb", "a b", "a\x00b", "café", "a\x7fb", "a\tb"])
def test_login_rejects_non_printable_token(tok):
    c, _ = mk(Resp({"access_token": tok}))
    with pytest.raises(PpdmError, match="invalid access_token"):
        c.login()
    assert c.token is None


def test_request_build_error_never_echoes_the_header():
    import http.client

    def opener(url, headers=None, **kw):
        conn = http.client.HTTPConnection("h")
        conn.putrequest("GET", "/x")
        for k, v in headers.items():
            conn.putheader(k, v)

    c = PpdmClient("h", "u", "pw", opener=opener)
    c.token = "abc\ndef"
    with pytest.raises(PpdmError) as e:
        c.request("GET", "/x")
    assert "abc" not in e.value.msg and "def" not in e.value.msg and "ValueError" in e.value.msg


def test_scrub_text_is_bounded_on_a_huge_value():
    import time

    c, _ = mk(password="a")
    t = time.time()
    out = c.scrub_text("ab" * 2_500_000, 64)  # over MAX_SCRUB_TEXT: the length marker only, nothing scrubbed
    assert time.time() - t < 1.0 and out == "<... of 5000000 characters omitted>"


def test_scrub_text_cut_does_not_leave_a_secret_prefix():
    c, _ = mk(password="hunter2SuperSecret")
    out = c.scrub_text("x" * 60 + "hunter2SuperSecret", 70)
    assert "hunter2" not in out


# Fix round 4: no pre-cut before the scrub (a masked run shrinks the text and pulls a cut-off prefix in)

SAFE = "QWZKJXV#$%&@!~^"  # characters absent from the fixed message text and from the filler "y"
REPS = [1, 2, 5, 8, 50, 400]
LENGTHS = [1, 5, 18, 64, 1200]


def _secret(n, seed):
    import random

    rnd = random.Random(seed)
    return "".join(rnd.choice(SAFE) for _ in range(n))


def _runs(secret, text, k=8):
    """Any run of k consecutive characters of secret (the whole secret when shorter) found in text."""
    k = min(k, len(secret))
    return [secret[i : i + k] for i in range(len(secret) - k + 1) if secret[i : i + k] in text]


def _err_as(body, secret, which, status=400):
    raw = body if isinstance(body, bytes) else body.encode()
    op = FakeOpener(urllib.error.HTTPError("u", status, "x", {}, io.BytesIO(raw)))
    c = PpdmClient("ppdm.local", "admin", secret if which == "password" else "pw", opener=op)
    if which == "token":
        c.token = secret
    with pytest.raises(PpdmError) as e:
        c.request("GET", "/x")
    return e.value


def _out(err):
    return err.msg + "\n" + (err.body if isinstance(err.body, str) else json.dumps(err.body, ensure_ascii=False))


@pytest.mark.parametrize("which", ["password", "token"])
@pytest.mark.parametrize("n", LENGTHS)
@pytest.mark.parametrize("reps", REPS)
@pytest.mark.parametrize("kind", ["json", "text"])
def test_repeated_echoed_secret_never_leaks(kind, reps, n, which):
    tok = _secret(n, n * 1000 + reps)
    msg = "; ".join("invalid Authorization header 'Bearer %s'" % tok for _ in range(reps))
    if kind == "json":
        body = json.dumps({"code": 401, "message": msg})
    else:  # non-JSON body between 64 KiB and 1 MiB
        body = msg + " " + "y" * max(0, ppdm.MAX_ERROR_TEXT + 100 - len(msg))
        assert ppdm.MAX_ERROR_TEXT < len(body) <= ppdm.MAX_SCRUB_TEXT
    err = _err_as(body, tok, which, 401)
    assert not _runs(tok, _out(err)), (kind, reps, n, which, err.msg[:300])


PW7 = "hunter2SuperSecret"


def _old_bound(limit):
    return limit + 4096 + len(PW7)


def _straddle(target, off, tail=200):
    """PW7 repeated (one merged mask), filler, then a copy starting off characters before target."""
    head = PW7 * max(0, min(400, (target - off - 10) // len(PW7)))
    return head + "y" * (target - off - len(head)) + PW7 + "y" * tail


TARGETS = [
    _old_bound(64),
    _old_bound(1000),
    _old_bound(ppdm.MAX_ERROR_TEXT),
    64,
    1000,
    ppdm.MAX_ERROR_TEXT,
    ppdm.MAX_SCRUB_TEXT,
]


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("off", [1, 5, 9, 17])
@pytest.mark.parametrize("limit", [64, 1000, ppdm.MAX_ERROR_TEXT])
def test_scrub_text_straddle_after_merged_masks(target, off, limit):
    c, _ = mk(password=PW7)
    out = c.scrub_text(_straddle(target, off), limit)
    assert len(out) <= limit and not _runs(PW7, out, 4), (target, off, limit, out[-40:])


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("off", [1, 5, 9, 17])
@pytest.mark.parametrize("which", ["password", "token"])
def test_error_body_straddle_after_merged_masks(target, off, which):
    text = _straddle(target, off)
    for body in (text, json.dumps({"message": text})):
        err = _err_as(body, PW7, which)
        assert not _runs(PW7, _out(err), 4), (target, off, which, err.msg[-40:])


def test_scrub_text_over_limit_gives_only_the_marker():
    import time

    c, _ = mk(password="Q")
    t = time.time()
    out = c.scrub_text("Q" * (5 * 1000 * 1000), 10**7)
    assert time.time() - t < 0.5
    assert out == "<... of 5000000 characters omitted>"
    assert c.scrub_text("y" * (ppdm.MAX_SCRUB_TEXT + 1), 10) == "<... of 10"
    assert c.scrub_text(["y" * ppdm.MAX_SCRUB_TEXT], 10**7).startswith("<... of ")  # structure too


def test_scrub_text_at_the_limit_is_scrubbed_in_full():
    c, _ = mk(password=PW7)
    text = "y" * (ppdm.MAX_SCRUB_TEXT - len(PW7)) + PW7
    assert c.scrub_text(text, 10**7) == "y" * (ppdm.MAX_SCRUB_TEXT - len(PW7)) + "********"
    err = _err(PW7 + "y" * (ppdm.MAX_SCRUB_TEXT - 2 * len(PW7)) + PW7, PW7)
    assert err.body.startswith("********yyy") and len(err.body) == ppdm.MAX_ERROR_TEXT
    assert PW7 not in err.msg and "yyy" in err.msg


def test_huge_structure_is_not_scrubbed():
    import time

    c, _ = mk(password="Q")
    t = time.time()
    out = c.scrub_text(["Q"] * 6_000_000, 64)
    assert time.time() - t < 1.0 and out.startswith("<... of ") and "Q" not in out


@pytest.mark.parametrize("pw", ["caféX", "\x1fbell", "smile\U0001f600x"])
def test_uppercase_json_escape_is_masked(pw):
    upper = json.dumps(pw)[1:-1]
    upper = __import__("re").sub(r"\\u([0-9a-f]{4})", lambda m: "\\u" + m.group(1).upper(), upper)
    assert upper != json.dumps(pw)[1:-1]
    c, _ = mk(password=pw)
    assert upper not in c.scrub_text("x " + upper + " y", 1000)
    err = _err("oops " + upper, pw)
    assert upper not in _out(err)


def test_scrub_text_property_random():
    import random
    import re

    rnd = random.Random(20261115)
    alphabet = "ab\\\"'\n\x07é\U0001f600 y"

    def forms(s):
        j = json.dumps(s)[1:-1]
        return _forms(s) | {re.sub(r"\\u([0-9a-f]{4})", lambda m: "\\u" + m.group(1).upper(), j)}

    for _ in range(2000):
        pw = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(1, 6)))
        tok = "".join(rnd.choice("abcXY") for _ in range(rnd.randint(1, 12)))
        c, _ = mk(password=pw)
        c.token = tok
        pieces = sorted(forms(pw) | forms(tok))
        chunks = []
        for _ in range(rnd.randint(0, 40)):
            r = rnd.random()
            if r < 0.4:
                chunks.append(rnd.choice(pieces) * rnd.randint(1, 3))
            elif r < 0.6:
                p = rnd.choice(pieces)
                chunks.append(p[: rnd.randint(0, len(p))])
            else:
                chunks.append("".join(rnd.choice(alphabet + "XYz") for _ in range(rnd.randint(0, 30))))
        text = "".join(chunks)
        for limit in (0, 1, 8, 40, 100, 64 * 1024):
            out = c.scrub_text(text, limit)
            assert len(out) <= limit, (limit, out)
            hits = [f for f in forms(pw) | forms(tok) if f in out]
            assert not hits, (pw, tok, text, limit, out, hits)
