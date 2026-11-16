#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: activity_action
short_description: Cancel or retry an activity on PowerProtect Data Manager
description:
- Cancel a running activity or retry a failed one, through C(POST /api/v3/activities/{id}/cancel) or C(POST
  /api/v3/activities/{id}/retry).
- The module is not idempotent, it reports C(changed=true) when it sends the request. In check mode nothing
  is sent and C(changed=true) is reported. Cancelling an activity that is already C(COMPLETED) reports
  C(changed=false).
version_added: 0.4.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- Cancelling is service-affecting, the module fails before any request unless I(confirm=true).
- The action must be listed in C(supportedActions) of the activity, otherwise the module fails with the
  activity state and sends nothing.
- With I(wait=true) a retry polls the new activity started by PPDM and fails unless it ends C(OK) or C(SUCCESS)
  (the warn statuses only add a warning). A cancel polls the cancelled activity until it is C(COMPLETED),
  whatever its result (C(CANCELED) is the expected one).
seealso:
- module: fjacquet.ppdm.activity_info
  description: List and query activities.
options:
  id:
    description:
    - Id of the activity.
    type: str
    required: true
  action:
    description:
    - Action to run on the activity.
    type: str
    required: true
    choices:
    - cancel
    - retry
  retry_options:
    description:
    - Retry options, used only with I(action=retry). Not sent when omitted.
    type: list
    choices:
    - ALL
    - FROM_FAILED_STEP
    - NO_AUDIT_LOG
    - VIRTUAL_GROUP
    elements: str
  confirm:
    description:
    - Must be C(true) for I(action=cancel), a safeguard against an accidental cancel.
    type: bool
    default: false
  wait:
    description:
    - Wait for the activity to complete (see the notes).
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
  diff_mode:
    support: none
'''

EXAMPLES = r'''
- name: Cancel an activity
  fjacquet.ppdm.activity_action:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    id: "{{ activity_id }}"
    action: cancel
    confirm: true
    wait: true

- name: Retry a failed activity from the failed step
  fjacquet.ppdm.activity_action:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    id: "{{ activity_id }}"
    action: retry
    retry_options: [FROM_FAILED_STEP]
'''

RETURN = r'''
activity:
  description: The activity before the action, or the final activity when waited.
  returned: always
  type: dict
response:
  description: PPDM answer of the action, C({activityId}). For a retry it is the id of the new activity.
  returned: when the request was sent
  type: dict
  sample: {"activityId": "a2"}
'''

ARGUMENT_SPEC = dict(
    id=dict(type='str', required=True),
    action=dict(type='str', required=True, choices=['cancel', 'retry']),
    retry_options=dict(
        type='list',
        choices=['ALL', 'FROM_FAILED_STEP', 'NO_AUDIT_LOG', 'VIRTUAL_GROUP'],
        elements='str',
    ),
    confirm=dict(type='bool', default=False),
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
    quote_id,
)


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        supports_check_mode=True,
    )
    p = module.params
    verb = p["action"].upper()
    if p["action"] == "cancel" and not p["confirm"]:  # before login: nothing is sent without confirm
        module.fail_json(msg="cancelling an activity needs confirm=true")
    client = client_from_module(module)
    out = {}
    try:
        path = "/api/v3/activities/" + quote_id(p["id"])
        act = client.request("GET", path)
        if not isinstance(act, dict):
            raise PpdmError("GET %s failed: unexpected response" % path)
        out["activity"] = act
        if p["action"] == "cancel" and act.get("state") == "COMPLETED":
            module.exit_json(changed=False, **out)
        if verb not in (act.get("supportedActions") or []):
            raise PpdmError(
                client.scrub_text("activity %s cannot %s in state %s" % (p["id"], p["action"], act.get("state")), 300)
            )
        body = {}
        if p["action"] == "retry" and p["retry_options"]:
            body["retryOptions"] = p["retry_options"]
        res = client.start_action(path + "/" + p["action"], body, module.check_mode)
        resp = res["response"]
        if resp is not None:
            out["response"] = resp
            if p["wait"]:
                if p["action"] == "cancel":
                    out["activity"] = client.wait_activity(p["id"], p["wait_timeout"])  # CANCELED is expected
                else:
                    new_id = resp.get("activityId") if isinstance(resp, dict) else None
                    if not new_id:
                        raise PpdmError("PPDM answered no activityId, nothing to wait for")
                    done = client.await_activity(new_id, p["wait_timeout"])
                    out["activity"] = done["activity"]
                    if done.get("warnings"):
                        out["warnings"] = done["warnings"]
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=True, **out)


if __name__ == "__main__":
    main()
