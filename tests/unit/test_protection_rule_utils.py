import copy

import pytest
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmError
from ansible_collections.fjacquet.ppdm.plugins.module_utils.protection_rule import (
    validate_filters,
    validate_rule_body,
)

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
    ],
)
def test_invalid_filters_raise(bad):
    with pytest.raises(PpdmError):
        validate_filters(bad)


def _nested(depth):
    cond = dict(REL)
    for _ in range(depth):
        cond = {"operator": "AND", "conditions": [cond]}
    return [{"objectType": "ASSET", "conditions": [cond]}]


def test_nesting_limit_eight():
    validate_filters(_nested(7))  # filter conditions at level 1 .. relational at level 8
    with pytest.raises(PpdmError, match="deeper"):
        validate_filters(_nested(8))


def test_rule_body_v3():
    validate_rule_body(
        {
            "action": {"name": "ASSIGN_PROTECTION_POLICY"},
            "variant": "ADVANCED",
            "scopes": ["ASSET"],
            "categories": ["TREE_VIEW"],
            "filters": [FILTER],
        }
    )
    for bad in (
        {"action": {"name": "NOPE"}},
        {"variant": "NOPE"},
        {"scopes": ["NOPE"]},
        {"categories": ["NOPE"]},
        {"filters": ["x"]},
        {"scopes": "ASSET"},
    ):
        with pytest.raises(PpdmError):
            validate_rule_body(bad)
