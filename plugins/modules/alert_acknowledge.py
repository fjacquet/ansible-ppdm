#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: alert_acknowledge
short_description: Acknowledge or unacknowledge alerts on PowerProtect Data Manager
description:
- Set the acknowledge state of alerts with one call to C(POST /api/v2/alerts/acknowledgements).
- Alerts that already have the desired state are left alone. The module reports C(changed=false) when
  there is nothing to change.
version_added: 0.4.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- Every alert is read first. The module fails before any write when an id does not exist.
- PPDM answers 207 with one result per alert, the module fails when any result carries an error, the results
  are still returned.
seealso:
- module: fjacquet.ppdm.alert_info
  description: List and query alerts.
options:
  ids:
    description:
    - Ids of the alerts, at least one.
    type: list
    required: true
    elements: str
  acknowledge_state:
    description:
    - Desired acknowledge state.
    type: str
    choices:
    - ACKNOWLEDGED
    - UNACKNOWLEDGED
    default: ACKNOWLEDGED
attributes:
  platform:
    platforms: all
  check_mode:
    support: full
  diff_mode:
    support: none
'''

EXAMPLES = r'''
- name: Acknowledge two alerts
  fjacquet.ppdm.alert_acknowledge:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    ids: ["{{ alert_a }}", "{{ alert_b }}"]

- name: Unacknowledge an alert
  fjacquet.ppdm.alert_acknowledge:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    ids: ["{{ alert_a }}"]
    acknowledge_state: UNACKNOWLEDGED
'''

RETURN = r'''
updated_ids:
  description: Ids of the alerts whose state changed (or would change in check mode).
  returned: always
  type: list
  elements: str
results:
  description: C(bulkResults) of the PPDM answer, failures only, one per alert that PPDM could not update.
  returned: when the request was sent
  type: list
  elements: dict
'''

ARGUMENT_SPEC = dict(
    ids=dict(type='list', required=True, elements='str'),
    acknowledge_state=dict(type='str', choices=['ACKNOWLEDGED', 'UNACKNOWLEDGED'], default='ACKNOWLEDGED'),
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
    if not p["ids"]:
        module.fail_json(msg="ids must not be empty")
    client = client_from_module(module)
    state = p["acknowledge_state"]
    out = {}
    try:
        alerts, missing = [], []
        for alert_id in dict.fromkeys(p["ids"]):  # unique, in order
            try:
                alerts.append((alert_id, client.request("GET", "/api/v2/alerts/" + quote_id(alert_id))))
            except PpdmError as err:
                if err.status != 404:
                    raise
                missing.append(alert_id)
        if missing:
            raise PpdmError(client.scrub_text("alerts not found: %s" % ", ".join(missing), 500))
        todo = [
            i
            for i, a in alerts
            if not isinstance(a, dict) or (a.get("acknowledgement") or {}).get("acknowledgeState") != state
        ]
        out["updated_ids"] = todo
        if not todo:
            module.exit_json(changed=False, **out)
        if not module.check_mode:
            body = {"messageIds": todo, "acknowledgement": {"acknowledgeState": state}}
            resp = client.request("POST", "/api/v2/alerts/acknowledgements", body=body)
            results = (
                [r for r in (resp.get("bulkResults") or []) if isinstance(r, dict)] if isinstance(resp, dict) else []
            )
            out["results"] = client.scrub(results)
            errors = [
                "%s: %s" % (client.scrub_text(r.get("id"), 64), client.scrub_text(r["errorResponseObject"], 300))
                for r in results
                if r.get("errorResponseObject")
            ]
            if errors:
                module.fail_json(msg="acknowledge failed for " + "; ".join(errors), **out)
            count = resp.get("acknowledgementCount") if isinstance(resp, dict) else None
            if isinstance(count, int) and count < len(todo):
                module.fail_json(msg="PPDM acknowledged %d of %d alerts" % (count, len(todo)), **out)
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=True, **out)


if __name__ == "__main__":
    main()
