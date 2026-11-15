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


def _tasks(items):
    for t in items:
        yield t
        yield from _tasks(t.get("block", []))


def _tags(task):
    tags = task.get("tags", [])
    return set([tags] if isinstance(tags, str) else tags)


def test_stages_are_tagged():
    tasks = {t["name"]: t for t in _tasks(yaml.safe_load((ROLE / "tasks" / "main.yml").read_text()))}
    everything = {"bootstrap_wait", "bootstrap_eula", "bootstrap_config"}
    assert "bootstrap_eula" in _tags(tasks["Accept the PPDM EULA"])
    for name in (
        "Validate the wait settings",
        "Wait for the PPDM REST API",
        "Fail when authentication is refused",
        "Fail when the API did not become ready",
    ):
        assert _tags(tasks[name]) == everything, name
    # the tasks inside the block inherit bootstrap_config from their parent
    assert "bootstrap_config" in _tags(tasks["Apply the initial configuration"])


def test_failure_message_is_limited():
    text = (ROLE / "tasks" / "main.yml").read_text()
    assert "{{ __bootstrap_config_status.result }}" not in text


def test_put_refusal_message_hides_the_response():
    tasks = {t["name"]: t for t in _tasks(yaml.safe_load((ROLE / "tasks" / "main.yml").read_text()))}
    msg = tasks["Fail when the configuration was refused"]["ansible.builtin.fail"]["msg"]
    assert "__bootstrap_put.status" in msg and "see PPDM logs" in msg
    assert not re.search(r"__bootstrap_put\.(msg|body|result|content)|__bootstrap_put\b(?!\.status)", msg)
    assert tasks["Apply the initial configuration"] and tasks["Submit the configuration"]["no_log"] is True
