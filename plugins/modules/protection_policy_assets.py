#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: protection_policy_assets
short_description: Assign or unassign assets to a protection policy on PowerProtect Data Manager
description:
- Assign assets to a protection policy (I(state=present)) or unassign them from it (I(state=absent)),
  through C(/api/v2/protection-policies/<id>/asset-assignments) and C(asset-unassignments).
- The module reads the assets currently protected by the policy and sends only the missing ids (present)
  or the assigned ids (absent), so it is idempotent.
- Only the listed assets are touched, other assets assigned to the policy are left alone.
version_added: 0.2.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- 'Idempotence mode, delta: the v2 API offers C(GET /protection-policies/<id>/asset-assignments) (the
  assets protected by the policy), so the module computes the delta and sends nothing when there is nothing
  to do.'
- The policy is found by name first, then by id. Asset ids are not validated, PPDM rejects an unknown
  asset.
seealso:
- module: fjacquet.ppdm.protection_policy
  description: Manage protection policies.
options:
  state:
    description:
    - Whether the assets must be assigned to the policy.
    type: str
    choices:
    - present
    - absent
    default: present
  policy:
    description:
    - Protection policy name or id.
    type: str
    required: true
  asset_ids:
    description:
    - Ids of the assets to assign or unassign.
    type: list
    required: true
    elements: str
attributes:
  platform:
    platforms: all
  check_mode:
    support: full
  diff_mode:
    support: full
'''

EXAMPLES = r'''
- name: Protect two VMs with the gold policy
  fjacquet.ppdm.protection_policy_assets:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    policy: vm-gold
    asset_ids:
      - 11111111-2222-3333-4444-555555555555
      - 66666666-7777-8888-9999-000000000000

- name: Remove a VM from the policy
  fjacquet.ppdm.protection_policy_assets:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    policy: vm-gold
    state: absent
    asset_ids:
      - 11111111-2222-3333-4444-555555555555
'''

RETURN = r'''
assigned:
  description: Ids of the listed assets that are assigned to the policy after the run.
  returned: success
  type: list
  elements: str
  sample: ["11111111-2222-3333-4444-555555555555"]
diff:
  description: Before and after, restricted to the listed assets.
  returned: success
  type: dict
  sample: {"before": {"assigned": []}, "after": {"assigned": ["11111111-2222-3333-4444-555555555555"]}}
'''

ARGUMENT_SPEC = dict(
    state=dict(type='str', choices=['present', 'absent'], default='present'),
    policy=dict(type='str', required=True),
    asset_ids=dict(type='list', required=True, elements='str'),
)
# fmt: on
# END GENERATED

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (
    PpdmError,
    client_from_module,
    connection_argument_spec,
    fail_from,
    quote_id,
)


def find_policy(client, ref):
    """The policy named ref, else the one with id ref; PpdmError when neither exists."""
    policy = client.find_one("protection-policies", "name", ref) or client.find_one("protection-policies", "id", ref)
    if not policy:
        raise PpdmError(client.scrub_text("protection policy %s not found" % ref, 200))
    return policy


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        supports_check_mode=True,
    )
    p = module.params
    client = client_from_module(module)
    wanted = list(dict.fromkeys(p["asset_ids"]))
    present = p["state"] == "present"
    try:
        policy = find_policy(client, p["policy"])
        base = "/api/v2/protection-policies/%s" % quote_id(policy["id"])
        current = {
            a["id"]
            for a in client.get_all(base + "/asset-assignments") or []
            if isinstance(a, dict) and isinstance(a.get("id"), str)
        }
        before = [i for i in wanted if i in current]
        todo = [i for i in wanted if (i not in current) == present]
        after = wanted if present else []
        if todo and not module.check_mode:
            client.request("POST", base + ("/asset-assignments" if present else "/asset-unassignments"), body=todo)
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(
        changed=bool(todo), assigned=after, diff={"before": {"assigned": before}, "after": {"assigned": after}}
    )


if __name__ == "__main__":
    main()
