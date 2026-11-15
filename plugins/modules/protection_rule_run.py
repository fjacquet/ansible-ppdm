#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: protection_rule_run
short_description: Run protection rules or preview their conflicts on PowerProtect Data Manager
description:
- Run protection rules now (C(POST /api/v2/protection-rules-execution)) so that PPDM applies them to the
  matching assets.
- With I(preview=true) the module instead asks PPDM which conflicts a rule would cause, through C(POST
  /api/v2/protection-rules-conflicts-preview). This is read-only, it never changes anything and reports
  C(changed=false), also in check mode.
- A run always reports C(changed=true) when it sends the request, it is not idempotent. In check mode
  nothing is sent and C(changed=true) is reported.
version_added: 0.2.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- The v2 protection rule API is deprecated since PPDM 20.2 and removed in 20.6, the module will move to
  the v3 API in a later release.
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- The execution endpoint answers 200 without a body in the 20.3.0 OpenAPI, it does not return an activity.
  There is nothing to wait for, so the module has no I(wait) option, the rules are applied by PPDM asynchronously.
- At least one of I(rules) and I(inventory_source_type) is required to run, the module fails before any
  request otherwise. A preview needs I(rule).
- Rules are found by name first, then by id.
seealso:
- module: fjacquet.ppdm.protection_rule
  description: Manage protection rules.
options:
  rules:
    description:
    - Names or ids of the rules to run (sent as C(assetRuleIds)).
    type: list
    elements: str
  inventory_source_type:
    description:
    - Run the rules of this inventory source type (the C(inventorySourceType) field of the execution request).
    type: str
    choices:
    - CLOUD_DIRECTOR_VAPP
    - CLOUD_NATIVE_ENTITY
    - DR
    - FILE_SYSTEM
    - GENERIC_APPLICATION_ASSET
    - HYPERV_VIRTUAL_MACHINE
    - KUBERNETES
    - MICROSOFT_EXCHANGE_DATABASE
    - MICROSOFT_SQL_DATABASE
    - NAS_SHARE
    - NATIVEEDGE_VIRTUAL_MACHINE
    - NUTANIX_VIRTUAL_MACHINE
    - ORACLE_DATABASE
    - POWERSTORE_BLOCK
    - SAP_HANA_DATABASE
    - VMWARE_VIRTUAL_MACHINE
  preview:
    description:
    - Preview the conflicts of I(rule) instead of running rules.
    type: bool
    default: false
  preview_action:
    description:
    - Whether I(rule) is a rule to create or an edit of an existing rule (the C(previewAction) field).
      Used with I(preview=true) only, C(CREATE) when omitted.
    type: str
    choices:
    - CREATE
    - EDIT
  rule:
    description:
    - Protection rule body to preview, in the PPDM C(ProtectionRule) format (C(name), C(action), C(inventorySourceType),
      C(actionResult), C(conditions)...). Required with I(preview=true), include its C(id) for I(preview_action=EDIT).
    - C(action), C(inventorySourceType), C(conditionConnector) and the C(operator) of each condition are
      checked before any request.
    type: dict
attributes:
  platform:
    platforms: all
  check_mode:
    support: full
    details: A preview is read-only and is sent in check mode too.
  diff_mode:
    support: none
'''

EXAMPLES = r'''
- name: Apply a rule now
  fjacquet.ppdm.protection_rule_run:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    rules: [gold-vms]

- name: Preview the conflicts of a new rule
  fjacquet.ppdm.protection_rule_run:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    preview: true
    rule:
      name: gold-vms
      action: MOVE_TO_GROUP
      inventorySourceType: VMWARE_VIRTUAL_MACHINE
      actionResult: "{{ policy_id }}"
      conditions:
        - assetAttributeName: tag
          operator: EQUALS
          assetAttributeValues: ["gold"]
  register: conflicts
'''

RETURN = r'''
response:
  description: Answer of PPDM to the execution request (usually empty).
  returned: when the server returned a body
  type: raw
preview:
  description: Answer of PPDM to the conflicts preview, the protection rules in conflict (C(content)).
  returned: when I(preview=true)
  type: dict
  sample: {"content": [{"id": "1", "name": "other-rule"}]}
'''

ARGUMENT_SPEC = dict(
    rules=dict(type='list', elements='str'),
    inventory_source_type=dict(
        type='str',
        choices=[
            'CLOUD_DIRECTOR_VAPP',
            'CLOUD_NATIVE_ENTITY',
            'DR',
            'FILE_SYSTEM',
            'GENERIC_APPLICATION_ASSET',
            'HYPERV_VIRTUAL_MACHINE',
            'KUBERNETES',
            'MICROSOFT_EXCHANGE_DATABASE',
            'MICROSOFT_SQL_DATABASE',
            'NAS_SHARE',
            'NATIVEEDGE_VIRTUAL_MACHINE',
            'NUTANIX_VIRTUAL_MACHINE',
            'ORACLE_DATABASE',
            'POWERSTORE_BLOCK',
            'SAP_HANA_DATABASE',
            'VMWARE_VIRTUAL_MACHINE',
        ],
    ),
    preview=dict(type='bool', default=False),
    preview_action=dict(type='str', choices=['CREATE', 'EDIT']),
    rule=dict(type='dict'),
)
# fmt: on
# END GENERATED

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (
    PpdmError,
    client_from_module,
    connection_argument_spec,
    fail_from,
)
from ansible_collections.fjacquet.ppdm.plugins.module_utils.protection_rule import validate_rule_body


def find_rule(client, ref):
    """The rule named ref, else the one with id ref; PpdmError when neither exists."""
    rule = client.find_one("protection-rules", "name", ref) or client.find_one("protection-rules", "id", ref)
    if not rule:
        raise PpdmError("protection rule %s not found" % client.scrub_text(ref, 200))
    return rule


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        supports_check_mode=True,
    )
    p = module.params
    client = client_from_module(module)
    out = {}
    try:
        if p["preview"] and (p["rules"] or p["inventory_source_type"]):
            raise PpdmError("rules and inventory_source_type cannot be used with preview")
        if not p["preview"] and (p["rule"] or p["preview_action"]):
            raise PpdmError("rule and preview_action can only be used with preview")
        if p["preview"]:
            if not p["rule"]:
                raise PpdmError("rule is required with preview")
            validate_rule_body(p["rule"])
            # read-only: sent even in check mode, never changes anything
            body = {"previewAction": p["preview_action"] or "CREATE", "protectionRule": p["rule"]}
            out["preview"] = client.request("POST", "/api/v2/protection-rules-conflicts-preview", body=body)
            module.exit_json(changed=False, **out)
        if not (p["rules"] or p["inventory_source_type"]):
            raise PpdmError("at least one of rules and inventory_source_type is required")
        body = {}
        if p["rules"]:
            body["assetRuleIds"] = [find_rule(client, r)["id"] for r in p["rules"]]
        if p["inventory_source_type"]:
            body["inventorySourceType"] = p["inventory_source_type"]
        # the 200 answer has no body (not an activity), so there is nothing to wait for
        res = client.start_action("/api/v2/protection-rules-execution", body, module.check_mode)
        if res["response"] is not None:
            out["response"] = res["response"]
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=True, **out)


if __name__ == "__main__":
    main()
