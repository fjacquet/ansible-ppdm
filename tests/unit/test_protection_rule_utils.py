import copy

import pytest
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmError
from ansible_collections.fjacquet.ppdm.plugins.module_utils.protection_rule import validate_filters

# fieldData shape is not validated (spec RuleFilterFieldData); this is a representative payload.
REL = {"fieldName": "name", "operator": "EQUALS", "fieldData": {"type": "STRING", "values": ["vm1"]}}
FILTER = {
    "objectType": "ASSET",
    "objectSubtype": "VMWARE_VIRTUAL_MACHINE",
    "type": "INCLUDE",
    "operator": "AND",
    "conditions": [{"operator": "AND", "conditions": [REL]}],
}


def _filter(**over):
    f = copy.deepcopy(FILTER)
    f.update(over)
    return [f]


def test_valid_filter_and_none_accepted():
    validate_filters([FILTER])
    validate_filters(None)
    validate_filters([])


@pytest.mark.parametrize(
    "bad",
    [
        "x",
        {"a": 1},
        ["x"],
        _filter(objectType="NOPE"),
        _filter(objectSubtype="NOPE"),
        _filter(type="NOPE"),
        _filter(operator="XOR"),
        _filter(conditions="x"),
        _filter(conditions=["x"]),
        _filter(conditions=[{"operator": "AND", "conditions": [{"fieldName": "n", "operator": "BAD"}]}]),
        _filter(conditions=[{"operator": "BAD", "conditions": []}]),
        _filter(conditions=[{"foo": "bar"}]),
        _filter(conditions=[REL]),  # relational condition directly under a filter
        _filter(conditions=[{"operator": "AND", "conditions": [{"operator": "AND", "conditions": [REL]}]}]),
        _filter(conditions=[{"operator": "AND", "conditions": "x"}]),
        _filter(conditions=[{"operator": "AND", "conditions": ["x"]}]),
    ],
)
def test_invalid_filters_raise(bad):
    with pytest.raises(PpdmError):
        validate_filters(bad)
