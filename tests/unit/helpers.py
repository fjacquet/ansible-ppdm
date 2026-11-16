import io
import json
from urllib.error import HTTPError


class Resp:
    def __init__(self, payload=None, status=200):
        self.status = status
        self._raw = b"" if payload is None else json.dumps(payload).encode()

    def read(self, size=-1):
        return self._raw if size < 0 else self._raw[:size]


class FakeOpener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def http_error(status, payload):
    return HTTPError("u", status, "err", {}, io.BytesIO(json.dumps(payload).encode()))


class Exit(Exception):
    def __init__(self, kwargs):
        self.kwargs = kwargs


def run_module(monkeypatch, mod, opener, check_mode=False, **args):
    """Run mod.main() against a fake opener; returns the exit_json/fail_json kwargs (failed flag added)."""
    import pytest
    from ansible.module_utils.testing import patch_module_args
    from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmClient

    client = PpdmClient("h", "u", "s3cret", opener=opener, sleep=lambda s: None)
    opener.connects = 0  # how many times the module asked for a client (login)

    def connect(module):
        opener.connects += 1
        return client

    monkeypatch.setattr(mod, "client_from_module", connect)

    def exit_json(self, **kw):
        raise Exit(dict(kw, failed=False))

    def fail_json(self, **kw):
        raise Exit(dict(kw, failed=True))

    monkeypatch.setattr(mod.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(mod.AnsibleModule, "fail_json", fail_json)
    with (
        patch_module_args(
            dict(
                hostname="h",
                username="u",
                password="s3cret",
                _ansible_check_mode=check_mode,
                **args,
            )
        ),
        pytest.raises(Exit) as e,
    ):
        mod.main()
    return e.value.kwargs


def listing(*items):
    return Resp({"content": list(items), "page": {"totalPages": 1}})


def methods(opener):
    return [kw["method"] for _unused, kw in opener.calls]
