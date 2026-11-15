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
