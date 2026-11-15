#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: protection_rule
short_description: Manage protection rules on PowerProtect Data Manager
description:
- Create, update or remove a protection rule, identified by its name, through the v3 rules API.
- A rule selects assets with I(filters) and applies its I(action), for example assigning them to a protection
  policy (I(action=ASSIGN_PROTECTION_POLICY)) or to a resource group (I(action=ASSIGN_RESOURCE_GROUP)).
- Updates use PATCH.
- Rule names are assumed to be unique (the rule is found by exact name); if two rules share the name the
  module fails and lists the IDs.
version_added: 0.3.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- The C(Rule) schema of the 20.3.0 OpenAPI has no required field.
- The server-owned fields C(createdAt), C(updatedAt), C(lastRunAt), C(lastMigratedAt), C(status) and C(uniqueHash)
  are never sent and are ignored by the idempotence check.
- I(filters) replaces the whole list on PPDM, and is compared in order. A run is unchanged when each desired
  filter is a subset of the existing one at the same index (same list length), so fields PPDM adds do
  not cause a change.
- The same subset rule applies to the action, including the C(args) list (same order and length).
- The nested C(fieldData) of a relational condition is passed to PPDM as given, only the operators and
  the enum values are checked.
- The rule is applied to the assets by PPDM on its own schedule, or on demand with M(fjacquet.ppdm.protection_rule_run).
seealso:
- module: fjacquet.ppdm.protection_rule_info
  description: List protection rules.
- module: fjacquet.ppdm.protection_rule_run
  description: Run protection rules or preview their conflicts.
- module: fjacquet.ppdm.protection_policy
  description: Manage protection policies.
options:
  state:
    description:
    - Whether the rule must exist.
    type: str
    choices:
    - present
    - absent
    default: present
  name:
    description:
    - Rule name, used as the key.
    type: str
    required: true
  description:
    description:
    - Rule description.
    type: str
  priority:
    description:
    - Priority of the rule, 1 is the highest priority.
    type: int
  action:
    description:
    - Action name of the rule (the C(action.name) field).
    - I(protection_policy) and I(protection_policy_id) require C(ASSIGN_PROTECTION_POLICY), I(resource_group)
      and I(resource_group_id) require C(ASSIGN_RESOURCE_GROUP).
    type: str
    choices:
    - ASSIGN_PROTECTION_POLICY
    - ASSIGN_RESOURCE_GROUP
    - SELECT_ASSETS_FOR_RESTORE_PLAN
    - SELECT_COPIES
    - SELECT_COPIES_FOR_RESTORE_PLAN
    - SELECT_FILES
  protection_policy:
    description:
    - Name of the protection policy the matching assets are assigned to, resolved to its id (sent as the
      C(PROTECTION_POLICY_ID) action argument). The module fails when no policy or several policies have
      this name. Mutually exclusive with I(protection_policy_id).
    type: str
  protection_policy_id:
    description:
    - Id of the protection policy, used as is. Mutually exclusive with I(protection_policy).
    type: str
  resource_group:
    description:
    - Name of the resource group the matching assets are assigned to, resolved to its id (sent as the
      C(RESOURCE_GROUP_ID) action argument). The module fails when no group or several groups have this
      name. Mutually exclusive with I(resource_group_id).
    type: str
  resource_group_id:
    description:
    - Id of the resource group, used as is. Mutually exclusive with I(resource_group).
    type: str
  variant:
    description:
    - Variant of the rule.
    type: str
    choices:
    - ADVANCED
    - EXCLUDE_FILE_NAME_AND_PATH
    - INCLUDE_EXCLUDE_ALL_FIELDS
    - INCLUDE_FILE_NAME_AND_PATH
    - INCLUDE_FILE_PATH
    - SIMPLE
  scopes:
    description:
    - Scopes of the rule.
    type: list
    choices:
    - ASSET
    - GENERAL
    - POLICY
    elements: str
  categories:
    description:
    - Categories of the rule.
    type: list
    choices:
    - LIST_VIEW
    - TREE_VIEW
    elements: str
  filters:
    description:
    - Filters that select the assets, passed to PPDM as is after validation (the C(filters) field). The
      list replaces the whole list on PPDM and is compared in order.
    - Each filter is a dict with C(objectType), C(objectSubtype), C(type) (C(INCLUDE) or C(EXCLUDE)),
      C(operator) and C(conditions). Each condition is either logical (C(operator) C(AND) or C(OR) and
      a nested C(conditions) list) or relational (C(fieldName), C(operator) and C(fieldData)). The enum
      values are checked, nesting is limited to 8 levels.
    type: list
    elements: dict
  config:
    description:
    - Extra request body fields passed through as is, for example C(filter).
    - The module fails when C(config) contains C(id) or C(_links), the server owns them.
    - The module fails when C(config) contains a key that a named option sets (C(name), C(description),
      C(priority), C(action), C(variant), C(scopes), C(categories) and C(filters)), use the option instead.
    - Each top-level key replaces the whole value of that field, the merge with the existing object is
      shallow (top-level keys only).
    - Do not put secrets here, values are not masked in diff or return values.
    type: dict
attributes:
  platform:
    platforms: all
  check_mode:
    support: full
  diff_mode:
    support: full
'''

EXAMPLES = r'''
- name: Assign every VM tagged gold to the vm-gold policy
  fjacquet.ppdm.protection_rule:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: gold-vms
    priority: 10
    action: ASSIGN_PROTECTION_POLICY
    protection_policy: vm-gold
    filters:
      - objectType: ASSET
        objectSubtype: VMWARE_VIRTUAL_MACHINE
        type: INCLUDE
        operator: AND
        conditions:
          - operator: AND
            conditions:
              - fieldName: tags
                operator: EQUALS
                fieldData:
                  type: STRING
                  values: ["gold"]

- name: Remove a rule
  fjacquet.ppdm.protection_rule:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: gold-vms
    state: absent
'''

RETURN = r'''
protection_rule:
  description: The managed protection rule.
  returned: success
  type: dict
  sample: {"id": "1", "name": "gold-vms", "action": {"name": "ASSIGN_PROTECTION_POLICY"}}
diff:
  description: Before and after.
  returned: success
  type: dict
  sample: {"before": {}, "after": {"name": "gold-vms"}}
'''

ARGUMENT_SPEC = dict(
    state=dict(type='str', choices=['present', 'absent'], default='present'),
    name=dict(type='str', required=True),
    description=dict(type='str'),
    priority=dict(type='int'),
    action=dict(
        type='str',
        choices=[
            'ASSIGN_PROTECTION_POLICY',
            'ASSIGN_RESOURCE_GROUP',
            'SELECT_ASSETS_FOR_RESTORE_PLAN',
            'SELECT_COPIES',
            'SELECT_COPIES_FOR_RESTORE_PLAN',
            'SELECT_FILES',
        ],
    ),
    protection_policy=dict(type='str'),
    protection_policy_id=dict(type='str'),
    resource_group=dict(type='str'),
    resource_group_id=dict(type='str'),
    variant=dict(
        type='str',
        choices=[
            'ADVANCED',
            'EXCLUDE_FILE_NAME_AND_PATH',
            'INCLUDE_EXCLUDE_ALL_FIELDS',
            'INCLUDE_FILE_NAME_AND_PATH',
            'INCLUDE_FILE_PATH',
            'SIMPLE',
        ],
    ),
    scopes=dict(type='list', choices=['ASSET', 'GENERAL', 'POLICY'], elements='str'),
    categories=dict(type='list', choices=['LIST_VIEW', 'TREE_VIEW'], elements='str'),
    filters=dict(type='list', elements='dict'),
    config=dict(type='dict'),
)
# fmt: on
# END GENERATED

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (
    PpdmError,
    client_from_module,
    connection_argument_spec,
    fail_from,
    merge_config,
)
from ansible_collections.fjacquet.ppdm.plugins.module_utils.protection_rule import validate_filters

# server-owned, never sent (ROUTES lists none for rules)
READONLY = ("createdAt", "updatedAt", "lastRunAt", "lastMigratedAt", "status", "uniqueHash")

# (action, name option, id option, resource, action argument name)
TARGETS = (
    (
        "ASSIGN_PROTECTION_POLICY",
        "protection_policy",
        "protection_policy_id",
        "protection-policies",
        "PROTECTION_POLICY_ID",
    ),
    ("ASSIGN_RESOURCE_GROUP", "resource_group", "resource_group_id", "resource-groups", "RESOURCE_GROUP_ID"),
)


def build_action(client, p):
    """The action body, with the policy or group name resolved to an id; None when no option sets it."""
    args = []
    for _action, name_opt, id_opt, resource, arg in TARGETS:
        if p[name_opt] is None and p[id_opt] is None:
            continue
        target = p[id_opt]
        if target is None:
            found = client.find_one(resource, "name", p[name_opt])
            if not found:
                raise PpdmError("%s %s not found" % (name_opt.replace("_", " "), client.scrub_text(p[name_opt], 200)))
            target = found["id"]
        args.append({"name": arg, "values": [target]})
    if p["action"] is None:
        return None
    return {"name": p["action"], "args": args} if args else {"name": p["action"]}


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        mutually_exclusive=[("protection_policy", "protection_policy_id"), ("resource_group", "resource_group_id")],
        supports_check_mode=True,
    )
    p = module.params
    client = client_from_module(module)
    try:
        if p["state"] == "absent":
            res = client.remove("rules", "name", p["name"], check_mode=module.check_mode)
        else:
            validate_filters(p["filters"])
            named = {
                "name": p["name"],
                "description": p["description"],
                "priority": p["priority"],
                "variant": p["variant"],
                "scopes": p["scopes"],
                "categories": p["categories"],
                "filters": p["filters"],
                "action": None,
            }
            desired = merge_config(named, p["config"])  # before any request: bad input sends nothing
            for action, name_opt, id_opt, _resource, _arg in TARGETS:  # still before any request
                if (p[name_opt] is not None or p[id_opt] is not None) and p["action"] != action:
                    raise PpdmError("%s and %s require action=%s" % (name_opt, id_opt, action))
            action_body = build_action(client, p)
            if action_body is not None:
                desired["action"] = action_body
            res = client.ensure(
                "rules",
                desired,
                check_mode=module.check_mode,
                readonly=READONLY,
                subset_keys=("action", "filters"),
            )
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=res["changed"], protection_rule=res.get("object", {}), diff=res["diff"])


if __name__ == "__main__":
    main()
