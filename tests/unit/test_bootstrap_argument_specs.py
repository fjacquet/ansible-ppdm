import re
from pathlib import Path

import yaml

ROLE = Path(__file__).resolve().parents[2] / "roles" / "bootstrap"


def test_argument_specs_cover_defaults():
    options = yaml.safe_load((ROLE / "meta" / "argument_specs.yml").read_text())["argument_specs"]["main"]["options"]
    text = (ROLE / "defaults" / "main.yml").read_text()
    names = set(re.findall(r"^#?\s*(bootstrap_\w+):", text, re.M))
    assert names and names <= set(options)
    assert options["bootstrap_password"]["no_log"] is True
