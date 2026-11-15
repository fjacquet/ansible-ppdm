"""Make plain ``uv run pytest`` import the repo as ``ansible_collections.fjacquet.ppdm``.

Only applies when the package is not already importable (for example when pytest
runs from a ``.../ansible_collections/fjacquet/ppdm`` path). ``ansible-test units``
uses its own loader and is unaffected.
"""

import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _register_collection_packages() -> None:
    try:
        import ansible_collections.fjacquet.ppdm  # noqa: F401

        return
    except ImportError:
        pass

    for name in ("ansible_collections", "ansible_collections.fjacquet"):
        pkg = types.ModuleType(name)
        pkg.__path__ = []
        sys.modules[name] = pkg
        parent, _unused, child = name.rpartition(".")
        if parent:
            setattr(sys.modules[parent], child, pkg)

    ppdm = types.ModuleType("ansible_collections.fjacquet.ppdm")
    ppdm.__path__ = [str(REPO_ROOT)]
    sys.modules[ppdm.__name__] = ppdm
    sys.modules["ansible_collections.fjacquet"].ppdm = ppdm


_register_collection_packages()
