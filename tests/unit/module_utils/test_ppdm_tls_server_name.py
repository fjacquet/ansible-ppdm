import socket
import ssl
import subprocess
import threading

import pytest
from ansible_collections.fjacquet.ppdm.plugins.module_utils import ppdm
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmClient, PpdmError

BODY = b'{"access_token": "tok"}'


@pytest.fixture
def tls_server(tmp_path, monkeypatch):
    """Local TLS server whose certificate is issued for ppdm-core only (not for 127.0.0.1)."""
    # macOS system proxy lookup aborts in the forked ansible-test child
    monkeypatch.setattr("urllib.request.getproxies", dict)
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=ppdm-core"]
        + ["-addext", "subjectAltName=DNS:ppdm-core", "-keyout", str(key), "-out", str(cert)],
        check=True,
        capture_output=True,
    )
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(5)

    def serve():
        while True:
            try:
                conn, _addr = sock.accept()
            except OSError:
                return
            try:
                with ctx.wrap_socket(conn, server_side=True) as tls:
                    tls.recv(65536)
                    tls.sendall(
                        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n"
                        b"Connection: close\r\n\r\n%s" % (len(BODY), BODY)
                    )
            except (ssl.SSLError, OSError):
                pass

    threading.Thread(target=serve, daemon=True).start()
    yield sock.getsockname()[1], str(cert)
    sock.close()


def make(port, cert, name):
    return PpdmClient("127.0.0.1", "u", "p", port=port, ca_path=cert, timeout=5, tls_server_name=name)


def test_default_still_fails_on_name_mismatch(tls_server):
    port, cert = tls_server
    with pytest.raises(PpdmError):
        make(port, cert, None).login()


def test_tls_server_name_verifies_against_that_name(tls_server):
    port, cert = tls_server
    c = make(port, cert, "ppdm-core")
    c.login()
    assert c.token == "tok"


def test_wrong_tls_server_name_still_fails_verification(tls_server):
    port, cert = tls_server
    with pytest.raises(PpdmError):
        make(port, cert, "other.example").login()


def test_unset_keeps_default_opener():
    assert make(1, None, None).opener is ppdm.open_url


def test_injected_opener_is_kept():
    def op(url, **kw):
        raise AssertionError

    assert PpdmClient("h", "u", "p", opener=op, tls_server_name="x").opener is op


def test_option_in_connection_spec_with_env_fallback():
    assert ppdm.connection_argument_spec()["tls_server_name"]["fallback"][1] == ["PPDM_TLS_SERVER_NAME"]
