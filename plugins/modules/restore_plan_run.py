#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: restore_plan_run
short_description: Execute a restore plan on PowerProtect Data Manager
description:
- Execute a restore plan now or schedule its execution, through C(POST /api/v2/restore-plans/{id}/execute).
- The module is not idempotent, it reports C(changed=true) when it sends the request. In check mode nothing
  is sent and C(changed=true) is reported.
version_added: 0.4.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- Executing a restore plan is service-affecting, the module fails before any request or login unless I(confirm=true),
  also in check mode.
- The plan is found by name first, then by id; the module fails when several plans match.
- PPDM answers 201 for an immediate run and 202 for a scheduled one, with the activities started (C(activities),
  each with an C(activityId) and a C(restoreGroupId)). It answers 409 when the plan is already running,
  the module then fails with the PPDM message.
- With I(wait=true) every activity is polled to completion and the module fails unless each one ends C(OK)
  or C(SUCCESS) (the warn statuses C(OK_WITH_ERRORS), C(COMPLETED_WITH_EXCEPTIONS) only add a warning).
  One failure does not hide the others. An answer without activities, or an entry without C(activityId),
  fails the module with I(wait) and only warns without it.
- I(wait=true) cannot be combined with I(execution_type=SCHEDULE), the module fails before any request.
seealso:
- module: fjacquet.ppdm.restore_plan
  description: Manage restore plans.
options:
  plan:
    description:
    - Name or id of the restore plan.
    type: str
    required: true
  execution_type:
    description:
    - Run the plan now, or at I(schedule_time).
    type: str
    choices:
    - IMMEDIATELY
    - SCHEDULE
    default: IMMEDIATELY
  schedule_time:
    description:
    - Time to run the plan, ISO 8601 (for example C(2026-12-01T22:00:00Z)).
    - Required with I(execution_type=SCHEDULE), refused with C(IMMEDIATELY).
    type: str
  confirm:
    description:
    - Must be C(true), a safeguard against an accidental restore.
    type: bool
    default: false
  wait:
    description:
    - Wait for every started activity to complete (see the notes).
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
- name: Execute a restore plan now and wait for it
  fjacquet.ppdm.restore_plan_run:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    plan: dr-web
    confirm: true
    wait: true

- name: Schedule a restore plan
  fjacquet.ppdm.restore_plan_run:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    plan: dr-web
    execution_type: SCHEDULE
    schedule_time: "2026-12-01T22:00:00Z"
    confirm: true
'''

RETURN = r'''
result:
  description: Answer of PPDM, C({executionType, activities}).
  returned: when the request was sent
  type: dict
  sample: {"executionType": "IMMEDIATELY", "activities": [{"activityId": "a1", "restoreGroupId": "g1"}]}
activities:
  description: Final activities when I(wait=true).
  returned: when waited
  type: list
  elements: dict
warnings:
  description: Warn-status activities, and answers or entries without activity (when not waiting).
  returned: when any
  type: list
  elements: str
'''

ARGUMENT_SPEC = dict(
    plan=dict(type='str', required=True),
    execution_type=dict(type='str', choices=['IMMEDIATELY', 'SCHEDULE'], default='IMMEDIATELY'),
    schedule_time=dict(type='str'),
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


def find_plan(client, ref):
    """The restore plan named ref, else the one with id ref; PpdmError when neither exists."""
    plan = client.find_one("restore-plans", "name", ref) or client.find_one("restore-plans", "id", ref)
    if not plan:
        raise PpdmError(client.scrub_text("restore plan %s not found" % ref, 200))
    return plan


def main():
    module = AnsibleModule(argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC), supports_check_mode=True)
    p = module.params
    # all of this fails before any request or login
    if not p["confirm"]:
        module.fail_json(msg="executing a restore plan needs confirm=true")
    scheduled = p["execution_type"] == "SCHEDULE"
    if scheduled != bool(p["schedule_time"]):
        module.fail_json(msg="schedule_time is required with execution_type=SCHEDULE and refused with IMMEDIATELY")
    if scheduled and p["wait"]:
        module.fail_json(msg="wait cannot be used with execution_type=SCHEDULE")
    client = client_from_module(module)
    out = {}
    failures = []
    try:
        plan = find_plan(client, p["plan"])
        body = {"executionType": p["execution_type"]}
        if scheduled:
            body["scheduleTime"] = p["schedule_time"]
        res = client.start_action("/api/v2/restore-plans/%s/execute" % quote_id(plan["id"]), body, module.check_mode)
        resp = res["response"]
        warnings, activities = [], []
        if isinstance(resp, dict):
            out["result"] = resp
            entries = [a for a in resp.get("activities") or [] if isinstance(a, dict)]
            if p["wait"] and not entries:
                failures.append("PPDM answered no activities, nothing to wait for")
            for a in entries:
                if not a.get("activityId"):
                    # with wait the run must have started: an entry without activity is a failure, else a warning
                    (failures if p["wait"] else warnings).append(
                        client.scrub_text("restore group %s started no activity" % a.get("restoreGroupId"), 500)
                    )
                elif p["wait"]:
                    try:
                        done = client.await_activity(a["activityId"], p["wait_timeout"])
                    except PpdmError as err:  # poll every activity: a failure must not hide the others
                        failures.append(err.msg)
                        if isinstance(err.body, dict):
                            activities.append(err.body)
                    else:
                        activities.append(done["activity"])
                        warnings += done.get("warnings", [])
            if not entries and not p["wait"]:
                warnings.append("PPDM answered no activities")
        if p["wait"] and resp is not None:
            out["activities"] = activities
        if warnings:
            out["warnings"] = warnings
    except PpdmError as err:
        fail_from(module, err)
    if failures:
        module.fail_json(msg="; ".join(failures), **out)
    module.exit_json(changed=True, **out)


if __name__ == "__main__":
    main()
