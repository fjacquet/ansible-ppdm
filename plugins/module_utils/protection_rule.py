# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

from ansible_collections.fjacquet.ppdm.plugins.module_utils._enums import ENUMS
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmError


def _check(value, enum, label):
    if value is not None and value not in ENUMS[enum]:
        raise PpdmError("%s must be one of %s, got %r" % (label, ", ".join(ENUMS[enum]), value))


def validate_conditions(conditions):
    """Fail before any request when a condition is not a dict or its operator is not a known one."""
    if conditions is not None and not isinstance(conditions, list):
        raise PpdmError("conditions must be a list")
    for i, cond in enumerate(conditions or []):
        if not isinstance(cond, dict):
            raise PpdmError("conditions[%d] must be a dict" % i)
        _check(cond.get("operator"), "condition.operator", "conditions[%d]: operator" % i)


def validate_rule_body(rule):
    """Same checks on a raw ProtectionRule body (preview), where the argument spec cannot check them."""
    _check(rule.get("action"), "protection_rule.action", "rule.action")
    _check(rule.get("inventorySourceType"), "protection_rule.inventory_source_type", "rule.inventorySourceType")
    _check(rule.get("conditionConnector"), "protection_rule.condition_connector", "rule.conditionConnector")
    validate_conditions(rule.get("conditions"))


MAX_CONDITION_DEPTH = 8


def _check_list(values, enum, label):
    if values is None:
        return
    if not isinstance(values, list):
        raise PpdmError("%s must be a list" % label)
    for v in values:
        _check(v, enum, label)


def _validate_condition(cond, label, depth):
    if depth > MAX_CONDITION_DEPTH:
        raise PpdmError("%s: conditions nested deeper than %d levels" % (label, MAX_CONDITION_DEPTH))
    if not isinstance(cond, dict):
        raise PpdmError("%s must be a dict" % label)
    if "conditions" in cond:  # logical condition
        _check(cond.get("operator"), "rule_condition.logical_operator", "%s: operator" % label)
        _validate_conditions(cond["conditions"], label + ".conditions", depth + 1)
    elif "fieldName" in cond:  # relational condition; fieldData shape is not validated
        _check(cond.get("operator"), "rule_condition.operator", "%s: operator" % label)
    else:
        raise PpdmError("%s must be a logical (conditions) or relational (fieldName) condition" % label)


def _validate_conditions(conditions, label, depth):
    if not isinstance(conditions, list):
        raise PpdmError("%s must be a list" % label)
    for i, cond in enumerate(conditions):
        _validate_condition(cond, "%s[%d]" % (label, i), depth)


def validate_filters(filters):
    """Fail before any request when v3 rule filters are malformed or use values outside the spec enums."""
    if filters is None:
        return
    if not isinstance(filters, list):
        raise PpdmError("filters must be a list")
    for i, f in enumerate(filters):
        label = "filters[%d]" % i
        if not isinstance(f, dict):
            raise PpdmError("%s must be a dict" % label)
        _check(f.get("objectType"), "rule_filter.object_type", label + ": objectType")
        _check(f.get("objectSubtype"), "rule_filter.object_subtype", label + ": objectSubtype")
        _check(f.get("type"), "rule_filter.type", label + ": type")
        _check(f.get("operator"), "rule_filter.operator", label + ": operator")
        if f.get("conditions") is not None:
            _validate_conditions(f["conditions"], label + ".conditions", 1)


def validate_rule_body_v3(rule):
    """Checks on a raw v3 Rule body; the argument spec cannot check nested values."""
    action = rule.get("action")
    if action is not None:
        if not isinstance(action, dict):
            raise PpdmError("rule.action must be a dict")
        _check(action.get("name"), "rule.action_name", "rule.action.name")
    _check(rule.get("variant"), "rule.variant", "rule.variant")
    _check_list(rule.get("scopes"), "rule.scope", "rule.scopes")
    _check_list(rule.get("categories"), "rule.category", "rule.categories")
    validate_filters(rule.get("filters"))
