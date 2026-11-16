#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: protection_rule_run
short_description: Run a protection rule or preview its conflicts on PowerProtect Data Manager
description:
- Run a protection rule now (C(POST /api/v3/rule-execution)) so that PPDM applies it to the matching assets.
- With I(preview=true) the module instead asks PPDM which conflicts the rule would cause, through C(POST
  /api/v3/protection-policy-rule-conflict-preview). This is read-only, it never changes anything and reports
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
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- The rule is found by name first, then by id; the module fails when several rules match.
- The 20.3.0 OpenAPI documents the 202 answer of the execution endpoint without a body. With I(wait=true)
  the module expects an C(activityId) in the answer, polls it to completion and fails unless the activity
  ends C(OK) or C(SUCCESS) (the warn statuses C(OK_WITH_ERRORS), C(COMPLETED_WITH_EXCEPTIONS) only add
  a warning); an answer without C(activityId) fails the module. Without I(wait) the answer is returned
  as C(response) and nothing is polled.
- Check mode reads the rule but sends no execution request.
seealso:
- module: fjacquet.ppdm.protection_rule
  description: Manage protection rules.
options:
  rule:
    description:
    - Name or id of the protection rule.
    type: str
    required: true
  action_name:
    description:
    - Action of the rules to execute (the C(actionName) field of the execution request).
    - Defaults to the action of the rule, the module fails when that action cannot be executed.
    type: str
    version_added: 0.3.0
    choices:
    - ASSIGN_PROTECTION_POLICY
    - ASSIGN_RESOURCE_GROUP
  object_subtypes:
    description:
    - Object subtypes to run the rule on (the C(objectSubtypes) field). Not sent when omitted.
    type: list
    version_added: 0.3.0
    choices:
    - CLOUD_DIRECTOR_VAPP
    - CLOUD_NATIVE_ENTITY
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
    - POWER_MAX_BLOCK
    - SAP_HANA_DATABASE
    - VMWARE_VIRTUAL_MACHINE
    elements: str
  all_rules_of_action:
    description:
    - PPDM 20.3 cannot run a single C(ASSIGN_PROTECTION_POLICY) rule, it answers HTTP 400 to a request
      with a C(ruleId) (verified on a live lab). It only runs every rule of that action.
    - Set to C(true) to run every C(ASSIGN_PROTECTION_POLICY) rule (limited by I(object_subtypes) when
      set). Without it the module fails for such a rule before any request.
    - Not used for C(ASSIGN_RESOURCE_GROUP) rules, which run by their own C(ruleId).
    type: bool
    version_added: 0.4.1
    default: false
  preview:
    description:
    - Preview the conflicts of the existing I(rule) instead of running it.
    - PPDM 20.3 supports the preview only for C(ASSIGN_PROTECTION_POLICY) rules (HTTP 400 for C(ASSIGN_RESOURCE_GROUP)),
      and answered HTTP 500 for a C(POWERSTORE_BLOCK) template rule on the lab.
    - Cannot be combined with I(wait).
    type: bool
    default: false
  wait:
    description:
    - Wait for the activity of the run to complete.
    - PPDM 20.3 answers the run with a 202 that echoes the request and has no C(activityId) (verified
      on a live lab), so the module fails with a clear message when this is set.
    - Fails unless the activity status is C(OK) or C(SUCCESS); C(OK_WITH_ERRORS) or C(COMPLETED_WITH_EXCEPTIONS)
      warns, and fails when the answer has no C(activityId).
    type: bool
    default: false
  wait_timeout:
    description:
    - Seconds to wait when I(wait=true).
    type: int
    default: 600
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
    rule: gold-vms

- name: Apply a rule to Oracle databases only and wait for it
  fjacquet.ppdm.protection_rule_run:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    rule: gold-vms
    object_subtypes: [ORACLE_DATABASE]
    wait: true

- name: Preview the conflicts of a rule
  fjacquet.ppdm.protection_rule_run:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    rule: gold-vms
    preview: true
  register: conflicts
'''

RETURN = r'''
response:
  description: Answer of PPDM to the execution request.
  returned: when the server returned a body
  type: raw
activities:
  description: Final activity when I(wait=true).
  returned: when waited
  type: list
  elements: dict
warnings:
  description: OK_WITH_ERRORS or COMPLETED_WITH_EXCEPTIONS activities (when waited).
  returned: when any
  type: list
  elements: str
preview:
  description: Answer of PPDM to the conflicts preview, the rules in conflict (C(content)).
  returned: when I(preview=true)
  type: dict
  sample: {"content": [{"id": "1", "name": "other-rule"}]}
'''

ARGUMENT_SPEC = dict(
    rule=dict(type='str', required=True),
    action_name=dict(type='str', choices=['ASSIGN_PROTECTION_POLICY', 'ASSIGN_RESOURCE_GROUP']),
    object_subtypes=dict(
        type='list',
        choices=[
            'CLOUD_DIRECTOR_VAPP',
            'CLOUD_NATIVE_ENTITY',
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
            'POWER_MAX_BLOCK',
            'SAP_HANA_DATABASE',
            'VMWARE_VIRTUAL_MACHINE',
        ],
        elements='str',
    ),
    all_rules_of_action=dict(type='bool', default=False),
    preview=dict(type='bool', default=False),
    wait=dict(type='bool', default=False),
    wait_timeout=dict(type='int', default=600),
)
# fmt: on
# END GENERATED

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.fjacquet.ppdm.plugins.module_utils._enums import ENUMS
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (
    PpdmError,
    client_from_module,
    connection_argument_spec,
    fail_from,
    strip_readonly,
)
from ansible_collections.fjacquet.ppdm.plugins.module_utils.protection_rule import READONLY


def find_rule(client, ref):
    """The rule named ref, else the one with id ref; PpdmError when neither exists."""
    rule = client.find_one("rules", "name", ref) or client.find_one("rules", "id", ref)
    if not rule:
        raise PpdmError(client.scrub_text("protection rule %s not found" % ref, 200))
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
        if p["preview"] and p["wait"]:
            raise PpdmError("wait cannot be used with preview")
        rule = find_rule(client, p["rule"])
        if p["preview"]:
            # read-only: sent even in check mode, never changes anything
            body = {"rule": strip_readonly("rules", rule, READONLY)}
            out["preview"] = client.request("POST", "/api/v3/protection-policy-rule-conflict-preview", body=body)
            module.exit_json(changed=False, **out)
        action = p["action_name"] or (rule.get("action") or {}).get("name")
        if action not in ENUMS["rule_run.action_name"]:
            raise PpdmError(client.scrub_text("rule action %s cannot be executed, set action_name" % action, 200))
        if action == "ASSIGN_PROTECTION_POLICY":
            # PPDM 20.3 refuses ruleId for this action (HTTP 400): it only runs every rule of the action
            if not p["all_rules_of_action"]:
                raise PpdmError(
                    "PPDM 20.3 cannot run a single ASSIGN_PROTECTION_POLICY rule, it runs every rule of the action; "
                    "set all_rules_of_action=true to do that"
                )
            body = {"actionName": action, "objectType": "ASSET"}
        else:
            body = {"ruleId": rule["id"], "actionName": action, "objectType": "ASSET"}
        if p["object_subtypes"]:
            body["objectSubtypes"] = p["object_subtypes"]
        res = client.start_action("/api/v3/rule-execution", body, module.check_mode)
        resp = res["response"]
        if resp is not None:
            out["response"] = resp
        # the 202 answer shape is not documented: an activityId is expected at the top level
        activity_id = resp.get("activityId") if isinstance(resp, dict) else None
        if p["wait"] and not module.check_mode:
            if not activity_id:
                raise PpdmError("PPDM answered no activityId, nothing to wait for")
            done = client.await_activity(activity_id, p["wait_timeout"])
            out["activities"] = [done["activity"]]
            if done.get("warnings"):
                out["warnings"] = done["warnings"]
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=True, **out)


if __name__ == "__main__":
    main()
