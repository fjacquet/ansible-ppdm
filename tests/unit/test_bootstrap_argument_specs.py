import re
from pathlib import Path

import yaml

ROLE = Path(__file__).resolve().parents[2] / "roles" / "bootstrap"


def test_argument_specs_cover_defaults():
    options = yaml.safe_load((ROLE / "meta" / "argument_specs.yml").read_text())["argument_specs"]["main"]["options"]
    text = (ROLE / "defaults" / "main.yml").read_text()
    names = set(re.findall(r"^#?\s*(bootstrap_\w+):", text, re.MULTILINE))
    assert names and names <= set(options)
    assert options["bootstrap_password"]["no_log"] is True


def test_every_argument_spec_option_has_a_default_or_is_required():
    options = yaml.safe_load((ROLE / "meta" / "argument_specs.yml").read_text())["argument_specs"]["main"]["options"]
    text = (ROLE / "defaults" / "main.yml").read_text()
    in_defaults = set(re.findall(r"^#?\s*(bootstrap_\w+):", text, re.MULTILINE))
    undeclared = [n for n, o in options.items() if not o.get("required") and n not in in_defaults]
    assert not undeclared
    active = set(re.findall(r"^(bootstrap_\w+):", text, re.MULTILINE))
    assert [n for n, o in options.items() if "default" in o and n not in active] == []


def test_stages_are_tagged_and_failure_message_is_limited():
    text = (ROLE / "tasks" / "main.yml").read_text()
    for tag in ("bootstrap_wait", "bootstrap_eula", "bootstrap_config"):
        assert tag in text
    assert "{{ __bootstrap_config_status.result }}" not in text
