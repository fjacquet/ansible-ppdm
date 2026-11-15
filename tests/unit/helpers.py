import io
import json
from urllib.error import HTTPError


class Resp:
    def __init__(self, payload=None, status=200):
        self.status = status
        self._raw = b"" if payload is None else json.dumps(payload).encode()

    def read(self):
        return self._raw


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
