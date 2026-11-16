import importlib
from pathlib import Path

import pytest
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import connection_argument_spec

MODULES = sorted(
    p.stem for p in (Path(__file__).parents[3] / "plugins" / "modules").glob("*.py") if p.stem != "__init__"
)


# certificate.port (TLS port of the host) shadows the connection port: a known clash, fixed by a rename later.
KNOWN = {"certificate": pytest.mark.xfail(strict=True, reason="certificate.port shadows the connection port")}


@pytest.mark.parametrize("name", [pytest.param(n, marks=KNOWN.get(n, ())) for n in MODULES])
def test_module_options_do_not_collide_with_connection_options(name):
    mod = importlib.import_module("ansible_collections.fjacquet.ppdm.plugins.modules." + name)
    spec = getattr(mod, "ARGUMENT_SPEC", None)
    if spec is not None:
        assert set(spec) & set(connection_argument_spec()) == set()
