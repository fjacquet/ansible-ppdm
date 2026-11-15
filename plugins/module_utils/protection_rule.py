# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

from ansible_collections.fjacquet.ppdm.plugins.module_utils._enums import ENUMS
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import PpdmError


def _check(value, enum, label):
    if value is not None and value not in ENUMS[enum]:
        raise PpdmError("%s must be one of %s, got %r" % (label, ", ".join(ENUMS[enum]), value))


def _validate_conditions(conditions, label):
    """Spec shape: filter.conditions are logical, and each logical condition holds relational ones."""
    if not isinstance(conditions, list):
        raise PpdmError("%s must be a list" % label)
    for i, cond in enumerate(conditions):
        clabel = "%s[%d]" % (label, i)
        if not isinstance(cond, dict):
            raise PpdmError("%s must be a dict" % clabel)
        if "conditions" not in cond:
            raise PpdmError("%s must be a logical condition (operator and conditions)" % clabel)
        _check(cond.get("operator"), "rule_condition.logical_operator", "%s: operator" % clabel)
        rels = cond["conditions"]
        if not isinstance(rels, list):
            raise PpdmError("%s.conditions must be a list" % clabel)
        for j, rel in enumerate(rels):
            rlabel = "%s.conditions[%d]" % (clabel, j)
            if not isinstance(rel, dict) or "fieldName" not in rel:
                raise PpdmError("%s must be a relational condition (fieldName, operator, fieldData)" % rlabel)
            _check(rel.get("operator"), "rule_condition.operator", "%s: operator" % rlabel)


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
            _validate_conditions(f["conditions"], label + ".conditions")


# server-owned, never sent (ROUTES lists none for rules)
READONLY = ("createdAt", "updatedAt", "lastRunAt", "lastMigratedAt", "status", "uniqueHash")
