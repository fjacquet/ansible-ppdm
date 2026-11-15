#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: protection_policy_run
short_description: Run a protection policy now on PowerProtect Data Manager
description:
- Trigger an on-demand (protect now) run of a protection policy on assets or protection groups, through
  C(POST /api/v3/protections).
- The module always reports C(changed=true) when it sends the request, it is not idempotent. In check
  mode nothing is sent and C(changed=true) is reported.
version_added: 0.2.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- The policy is found by name first, then by id.
- 'The 202 answer of PPDM is C({results: [{activityId, objectiveId, status, reason, remediation}]}), one
  entry per started activity, not a single activity. With I(wait=true) every C(activityId) is polled to
  completion, the module fails unless each activity ends C(OK) (C(OK_WITH_ERRORS) only adds a warning).
  An entry without C(activityId) (the run was not started) adds a warning with its C(reason).'
- At least one of I(asset_ids) and I(protection_group_ids) is required, the module fails before any request
  otherwise.
seealso:
- module: fjacquet.ppdm.protection_policy
  description: Manage protection policies.
- module: fjacquet.ppdm.protection_policy_assets
  description: Assign assets to a protection policy.
options:
  policy:
    description:
    - Protection policy name or id.
    type: str
    required: true
  objective_ids:
    description:
    - Ids of the policy objectives to run. All the objectives of the policy when omitted.
    type: list
    elements: str
  asset_ids:
    description:
    - Ids of the assets to protect.
    type: list
    elements: str
  protection_group_ids:
    description:
    - Ids of the protection groups to protect.
    type: list
    elements: str
  wait:
    description:
    - Wait for every started activity to complete.
    - Fails unless each activity C(result.status) is C(OK) or C(OK_WITH_ERRORS) (the latter only warns).
    type: bool
    default: false
  wait_timeout:
    description:
    - Seconds to wait for each activity when I(wait=true).
    type: int
    default: 600
attributes:
  platform:
    platforms: all
  check_mode:
    support: full
  diff_mode:
    support: none
'''

EXAMPLES = r'''
- name: Back up two VMs now with the gold policy
  fjacquet.ppdm.protection_policy_run:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    policy: vm-gold
    asset_ids:
      - 11111111-2222-3333-4444-555555555555
      - 66666666-7777-8888-9999-000000000000
    wait: true

- name: Run one objective on a protection group
  fjacquet.ppdm.protection_policy_run:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    policy: vm-gold
    objective_ids: ["{{ objective_id }}"]
    protection_group_ids: ["{{ group_id }}"]
'''

RETURN = r'''
results:
  description: Entries of the PPDM answer, one per objective run.
  returned: when the request was sent
  type: list
  elements: dict
  sample: [{"activityId": "a1", "objectiveId": "o1", "status": "SUCCESS"}]
activities:
  description: Final activities when I(wait=true).
  returned: when waited
  type: list
  elements: dict
warnings:
  description: Entries that did not start an activity, and activities that ended OK_WITH_ERRORS (when waited).
  returned: when any
  type: list
  elements: str
'''

ARGUMENT_SPEC = dict(
    policy=dict(type='str', required=True),
    objective_ids=dict(type='list', elements='str'),
    asset_ids=dict(type='list', elements='str'),
    protection_group_ids=dict(type='list', elements='str'),
    wait=dict(type='bool', default=False),
    wait_timeout=dict(type='int', default=600),
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


def find_policy(client, ref):
    """The policy named ref, else the one with id ref; PpdmError when neither exists."""
    policy = client.find_one("protection-policies", "name", ref) or client.find_one("protection-policies", "id", ref)
    if not policy:
        raise PpdmError("protection policy %s not found" % ref)
    return policy


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        supports_check_mode=True,
    )
    p = module.params
    client = client_from_module(module)
    out = {}
    try:
        if not (p["asset_ids"] or p["protection_group_ids"]):
            raise PpdmError("at least one of asset_ids and protection_group_ids is required")
        policy = {"id": find_policy(client, p["policy"])["id"]}
        if p["objective_ids"]:
            policy["objectives"] = [{"id": i} for i in p["objective_ids"]]
        source = {
            k: v for k, v in (("assetIds", p["asset_ids"]), ("protectionGroupIds", p["protection_group_ids"])) if v
        }
        res = client.start_action("/api/v3/protections", {"policy": policy, "source": source}, module.check_mode)
        # the 202 answer is {results: [{activityId, ...}]}, not an activity: wait on each activityId here
        results = (res["response"] or {}).get("results") or []
        warnings, activities = [], []
        for r in results:
            if r.get("activityId"):
                if p["wait"]:
                    done = client.await_activity(r["activityId"], p["wait_timeout"])
                    activities.append(done["activity"])
                    warnings += done.get("warnings", [])
            elif p["wait"]:
                warnings.append(
                    client.scrub_text("not started: %s %s" % (r.get("reason"), r.get("remediation") or ""), 500)
                )
        if res["response"] is not None:
            out["results"] = results
        if p["wait"]:
            out["activities"] = activities
        if warnings:
            out["warnings"] = warnings
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=True, **out)


if __name__ == "__main__":
    main()
