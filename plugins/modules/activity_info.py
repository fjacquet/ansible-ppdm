#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: activity_info
short_description: Get activities from PowerProtect Data Manager
description:
- Read-only query of activities (jobs). Never changes anything.
- Without I(id), returns every matching activity, all pages. An unfiltered list pages through every activity
  (up to the client limit), so pass a I(filter).
- The C(state) of an activity is one of C(QUEUED), C(RUNNING), C(CANCELING), C(RETRYING), C(COMPLETED).
  The C(result.status) is one of C(SUCCESS), C(COMPLETED_WITH_EXCEPTIONS), C(FAILED), C(CANCELED), C(SKIPPED),
  C(RETRIED).
version_added: 0.4.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
options:
  id:
    description:
    - Return only the activity with this ID. Mutually exclusive with I(filter). A 404 answer gives an
      empty list.
    type: str
  filter:
    description:
    - PPDM filter string, for example C(state eq "RUNNING"). It is passed to PPDM unchanged and its result
      is not re-checked. Mutually exclusive with I(id).
    type: str
  steps:
    description:
    - Also fetch the steps of the activity and return them as C(steps) of the activity. Only valid with
      I(id).
    type: bool
    default: false
attributes:
  platform:
    platforms: all
  check_mode:
    support: full
    details: Read-only, behaves the same in check mode.
  diff_mode:
    support: none
'''

EXAMPLES = r'''
- name: Failed activities of the last day
  fjacquet.ppdm.activity_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    filter: 'result.status eq "FAILED" and startTime gt "2026-11-15T00:00:00.000Z"'
  register: result

- name: One activity with its steps
  fjacquet.ppdm.activity_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    id: "{{ activity_id }}"
    steps: true
'''

RETURN = r'''
activities:
  description: Matching activities, an empty list when nothing matches. With I(steps) each one has a C(steps) list.
  returned: always
  type: list
  elements: dict
  sample: [{"id": "a1", "name": "Protect VM", "state": "COMPLETED", "result": {"status": "OK"}}]
'''

ARGUMENT_SPEC = dict(
    id=dict(type='str'),
    filter=dict(type='str'),
    steps=dict(type='bool', default=False),
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


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        supports_check_mode=True,
        mutually_exclusive=[("id", "filter")],
    )
    p = module.params
    if p["steps"] and p["id"] is None:
        module.fail_json(msg="steps requires id")
    client = client_from_module(module)
    try:
        if p["id"] is not None:
            try:
                body = client.request("GET", client._route("activities", "GET", p["id"]))
            except PpdmError as err:
                if err.status != 404:
                    raise
                body = None
            if body is not None and not isinstance(body, dict):
                raise PpdmError("GET activities/%s failed: unexpected response" % p["id"])
            found = [] if body is None else [body]
            if found and p["steps"]:
                found[0]["steps"] = client.get_all("/api/v3/activities/%s/steps" % quote_id(p["id"]))
        else:
            found = client.list_all("activities", filter=p["filter"])
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=False, activities=found)


if __name__ == "__main__":
    main()
