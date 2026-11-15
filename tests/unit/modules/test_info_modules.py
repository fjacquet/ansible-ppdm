import json
from urllib.parse import parse_qs, urlsplit

import pytest
from ansible.module_utils.testing import patch_module_args
from ansible_collections.fjacquet.ppdm.plugins.module_utils import ppdm
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (
    PpdmClient,
    filter_eq,
)
from ansible_collections.fjacquet.ppdm.plugins.modules import (
    certificate_info,
    credential_info,
    inventory_source_info,
    protection_policy_info,
    protection_rule_info,
    storage_system_info,
)
from ansible_collections.fjacquet.ppdm.tests.unit.helpers import (
    Exit,
    FakeOpener,
    Resp,
    http_error,
)

CONN = dict(hostname="h", username="u", password="s3cret")
MODULES = [
    (credential_info, "/api/v2/credentials", "credentials"),
    (inventory_source_info, "/api/v2/inventory-sources", "inventory_sources"),
    (storage_system_info, "/api/v2/storage-systems", "storage_systems"),
    (certificate_info, "/api/v2/certificates", "certificates"),
    (protection_policy_info, "/api/v3/protection-policies", "protection_policies"),
    (protection_rule_info, "/api/v3/rules", "protection_rules"),
]
ALL = pytest.mark.parametrize(
    "mod,base,key", MODULES, ids=[m.__name__.rsplit(".", 1)[1] for m, _unused, _unused in MODULES]
)


def run(monkeypatch, mod, opener, check_mode=False, **args):
    client = PpdmClient("h", "u", "s3cret", opener=opener, sleep=lambda s: None)
    monkeypatch.setattr(ppdm, "client_from_module", lambda module: client)

    def exit_json(self, **kw):
        raise Exit(dict(kw, failed=False))

    def fail_json(self, **kw):
        raise Exit(dict(kw, failed=True))

    monkeypatch.setattr(ppdm.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(ppdm.AnsibleModule, "fail_json", fail_json)
    with patch_module_args(dict(CONN, _ansible_check_mode=check_mode, **args)):
        with pytest.raises(Exit) as e:
            mod.main()
    return e.value.kwargs


def page(items, n, total):
    return Resp({"content": items, "page": {"totalPages": total, "number": n}})


@ALL
def test_info_returns_all_pages(monkeypatch, mod, base, key):
    items = [{"id": str(i), "name": "n%d" % i} for i in range(250)]
    op = FakeOpener(page(items[:100], 1, 3), page(items[100:200], 2, 3), page(items[200:], 3, 3))
    out = run(monkeypatch, mod, op)
    assert out["failed"] is False and out["changed"] is False
    assert [i["id"] for i in out[key]] == [i["id"] for i in items]
    assert len(op.calls) == 3 and urlsplit(op.calls[0][0]).path == base


@ALL
def test_info_empty_is_empty_list(monkeypatch, mod, base, key):
    out = run(monkeypatch, mod, FakeOpener(page([], 1, 0)))
    assert out["failed"] is False and out["changed"] is False and out[key] == []


@ALL
def test_info_works_in_check_mode(monkeypatch, mod, base, key):
    out = run(monkeypatch, mod, FakeOpener(page([{"id": "1"}], 1, 1)), check_mode=True)
    assert out[key] == [{"id": "1"}] and out["changed"] is False


@ALL
def test_info_by_name_builds_filter(monkeypatch, mod, base, key):
    op = FakeOpener(page([{"id": "1", "name": "x"}], 1, 1))
    out = run(monkeypatch, mod, op, name="x")
    assert out[key] == [{"id": "1", "name": "x"}]
    assert parse_qs(urlsplit(op.calls[0][0]).query)["filter"] == ['name eq "x"']


@ALL
def test_info_by_name_keeps_exact_matches_only(monkeypatch, mod, base, key):
    op = FakeOpener(
        page([{"id": "1", "name": "x"}, {"id": "2", "name": "xy"}, {"id": "3", "name": "X"}, {"id": "4"}], 1, 1)
    )
    out = run(monkeypatch, mod, op, name="x")
    assert out[key] == [{"id": "1", "name": "x"}]


@ALL
def test_info_passes_filter(monkeypatch, mod, base, key):
    op = FakeOpener(page([], 1, 0))
    run(monkeypatch, mod, op, filter='name lk "p%"')
    assert parse_qs(urlsplit(op.calls[0][0]).query)["filter"] == ['name lk "p%"']


@ALL
def test_info_name_with_quote_and_backslash_is_escaped(monkeypatch, mod, base, key):
    op = FakeOpener(page([], 1, 0))
    out = run(monkeypatch, mod, op, name='a"b\\c')
    assert out["failed"] is False and out[key] == []
    assert parse_qs(urlsplit(op.calls[0][0]).query)["filter"] == ['name eq "a\\"b\\\\c"']


def test_filter_eq_escapes():
    assert filter_eq("name", 'a"b\\c') == 'name eq "a\\"b\\\\c"'


@ALL
def test_info_by_id_found(monkeypatch, mod, base, key):
    op = FakeOpener(Resp({"id": "abc", "name": "x"}))
    out = run(monkeypatch, mod, op, id="abc")
    assert out[key] == [{"id": "abc", "name": "x"}]
    assert urlsplit(op.calls[0][0]).path == base + "/abc"


@ALL
def test_info_by_id_404_is_empty(monkeypatch, mod, base, key):
    out = run(monkeypatch, mod, FakeOpener(http_error(404, {"message": "nope"})), id="zz")
    assert out["failed"] is False and out[key] == []


@ALL
def test_info_by_id_other_error_fails(monkeypatch, mod, base, key):
    out = run(monkeypatch, mod, FakeOpener(http_error(500, {"message": "boom"})), id="zz")
    assert out["failed"] and out["status"] == 500


@ALL
@pytest.mark.parametrize("extra", [{"name": "x"}, {"filter": "f"}])
def test_info_id_conflicts_with_name_or_filter(monkeypatch, mod, base, key, extra):
    op = FakeOpener()
    out = run(monkeypatch, mod, op, id="abc", **extra)
    assert out["failed"] and "mutually exclusive" in out["msg"]
    assert op.calls == []


def test_credential_info_has_no_secret_fields(monkeypatch):
    cred = {
        "id": "1",
        "name": "c",
        "username": "u",
        "password": "hunter2",
        "secretId": "s",
    }
    out = run(monkeypatch, credential_info, FakeOpener(page([cred], 1, 1)))
    assert "password" not in out["credentials"][0] and "hunter2" not in json.dumps(out)
    out = run(monkeypatch, credential_info, FakeOpener(Resp(dict(cred))), id="1")
    assert "password" not in out["credentials"][0]


@ALL
def test_info_name_conflicts_with_filter(monkeypatch, mod, base, key):
    op = FakeOpener()
    out = run(monkeypatch, mod, op, name="x", filter="f")
    assert out["failed"] and "mutually exclusive" in out["msg"]
    assert op.calls == []


@ALL
def test_info_empty_id_fails_instead_of_listing(monkeypatch, mod, base, key):
    op = FakeOpener()
    out = run(monkeypatch, mod, op, id="")
    assert out["failed"] and op.calls == []


@ALL
@pytest.mark.parametrize("body", [[{"id": "a"}], "text"])
def test_info_non_dict_body_for_id_fails_cleanly(monkeypatch, mod, base, key, body):
    out = run(monkeypatch, mod, FakeOpener(Resp(body)), id="abc")
    assert out["failed"] and "unexpected response" in out["msg"]


def test_protection_policy_info_asset_type_is_exact_and_filtered(monkeypatch):
    items = [{"id": "1", "assetType": "FILE_SYSTEM"}, {"id": "2", "assetType": "KUBERNETES"}]
    op = FakeOpener(page(items, 1, 1))
    out = run(monkeypatch, protection_policy_info, op, asset_type="FILE_SYSTEM")
    assert [p["id"] for p in out["protection_policies"]] == ["1"]
    assert parse_qs(urlsplit(op.calls[0][0]).query)["filter"] == ['assetType eq "FILE_SYSTEM"']


def test_protection_policy_info_name_and_asset_type_are_anded(monkeypatch):
    op = FakeOpener(page([], 1, 0))
    run(monkeypatch, protection_policy_info, op, name="g", asset_type="KUBERNETES")
    assert parse_qs(urlsplit(op.calls[0][0]).query)["filter"] == ['name eq "g" and assetType eq "KUBERNETES"']


def test_protection_policy_info_user_filter_is_parenthesised(monkeypatch):
    op = FakeOpener(page([], 1, 0))
    run(monkeypatch, protection_policy_info, op, filter='name lk "a%" or name lk "b%"', asset_type="KUBERNETES")
    assert parse_qs(urlsplit(op.calls[0][0]).query)["filter"] == [
        '(name lk "a%" or name lk "b%") and assetType eq "KUBERNETES"'
    ]


def test_protection_policy_info_asset_type_ignores_non_dict_items(monkeypatch):
    op = FakeOpener(page(["junk", {"id": "1", "assetType": "FILE_SYSTEM"}], 1, 1))
    out = run(monkeypatch, protection_policy_info, op, asset_type="FILE_SYSTEM")
    assert [p["id"] for p in out["protection_policies"]] == ["1"]
