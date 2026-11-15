"""Pre-publication hygiene: unserialisable bodies, total item cap, empty name in info modules."""

import pytest
from ansible_collections.fjacquet.ppdm.plugins.module_utils import ppdm
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmClient, PpdmError
from ansible_collections.fjacquet.ppdm.plugins.modules import credential_info
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import FakeOpener, Resp, listing
from ansible_collections.fjacquet.ppdm.tests.unit.modules.test_info_modules import run


def test_request_maps_unserialisable_body_to_ppdm_error():
    op = FakeOpener()
    c = PpdmClient("ppdm.local", "u", "p", opener=op)
    with pytest.raises(PpdmError, match="could not build the request"):
        c.request("POST", "/api/v2/x", body={"a": object()})
    assert op.calls == []


def test_get_all_caps_total_items_across_pages(monkeypatch):
    monkeypatch.setattr(ppdm, "MAX_ITEMS", 150)
    full = [{"i": i} for i in range(ppdm.PAGE_SIZE)]
    op = FakeOpener(*[Resp({"content": full, "page": {"totalPages": 3}})] * 3)
    c = PpdmClient("ppdm.local", "u", "p", opener=op)
    with pytest.raises(PpdmError, match="more than 150 items"):
        c.get_all("/api/v2/credentials")
    assert len(op.calls) == 2  # stopped as soon as the cap is crossed


def test_max_items_is_one_million():
    assert ppdm.MAX_ITEMS == 1_000_000


def test_info_empty_name_is_rejected_not_list_all(monkeypatch):
    op = FakeOpener(listing({"id": "1", "name": "a"}))
    out = run(monkeypatch, credential_info, op, name="")
    assert out["failed"] and "name must not be empty" in out["msg"]
    assert op.calls == []
