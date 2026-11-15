from pathlib import Path

from tools.generate import build_routes

SPECS = Path(__file__).resolve().parents[3] / "docs" / "openapi"


def test_protection_policies_routes_to_v3():
    r = build_routes(SPECS)["protection-policies"]
    assert r["version"] == "v3"
    assert r["base"] == "/api/v3/protection-policies"


def test_credentials_v2_and_methods():
    r = build_routes(SPECS)["credentials"]
    assert r["version"] == "v2"
    assert {"GET", "POST"} <= r["methods"]
    assert r["item"] == "/api/v2/credentials/{id}"


def test_readonly_fields_from_schema():
    assert "createdAt" in build_routes(SPECS)["credentials"]["readonly"]


def test_item_param_normalized_and_eulas_skipped():
    routes = build_routes(SPECS)
    assert "eulas" not in routes
    assert all(r["item"].endswith("/{id}") for r in routes.values() if r["item"])
