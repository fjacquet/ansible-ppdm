#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: discovery
short_description: Start a discovery on PowerProtect Data Manager
description:
- Start a discovery of an inventory source through C(POST /api/v2/discoveries).
- The module always reports C(changed=true) when it starts a discovery. In check mode nothing is sent
  and C(changed=true) is reported.
- PPDM answers 409 when a similar discovery is already running. The module then fails, unless I(ignore_running=true),
  in which case it reports C(changed=false).
version_added: 0.2.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- Verified against the v2 spec, the only required field of the Discovery body is C(start), the starting
  resource. The module builds it as C(/inventory-sources/<id>) from I(inventory_source), found by name
  first, then by id. C(level) defaults to C(DataCopies) on the server when omitted.
- The 202 answer is the Discovery object, whose C(taskId) is the id of the discovery activity. With I(wait=true)
  that activity is polled to completion and the module fails unless it ends C(OK) (C(OK_WITH_ERRORS) only
  adds a warning).
seealso:
- module: fjacquet.ppdm.inventory_source
  description: Manage inventory sources.
options:
  inventory_source:
    description:
    - Inventory source name or id to discover from.
    type: str
    required: true
  level:
    description:
    - How deeply to discover. PPDM defaults to C(DataCopies) when omitted.
    type: str
    choices:
    - APPLICATION_SYSTEM
    - APPSERVER
    - ASSET
    - DataCopies
    - Device
    - HOST
    - HOSTFULL
    - INVENTORY_SOURCE
    - ManagementInterface
    - NETWORK_HOST
    - ProtectableData
    - STORAGE_SYSTEM
    - STORAGE_TARGET
  name:
    description:
    - Name of the discovery. PPDM assigns a default when omitted.
    type: str
  description:
    description:
    - Description of the discovery. PPDM assigns a default when omitted.
    type: str
  config:
    description:
    - The module fails when C(config) contains a key that a named option sets (C(start), C(level), C(name)
      and C(description)), use the option instead.
    - The module also fails when C(config) contains C(id) or C(_links), the server owns them.
    - Extra request body fields passed through as is, for example C(extendedDiscoveryData) or C(schedule).
    - Do not put secrets here, values are not masked in return values.
    type: dict
  wait:
    description:
    - Wait for the discovery activity (C(taskId) of the answer) to complete.
    - Fails unless the activity C(result.status) is C(OK) or C(OK_WITH_ERRORS) (the latter only warns).
    type: bool
    default: false
  wait_timeout:
    description:
    - Seconds to wait for the activity when I(wait=true).
    type: int
    default: 600
  ignore_running:
    description:
    - Report C(changed=false) instead of failing when PPDM answers 409 because a similar discovery is
      already running.
    type: bool
    default: false
attributes:
  platform:
    platforms: all
  check_mode:
    support: full
  diff_mode:
    support: none
'''

EXAMPLES = r'''
- name: Discover the vCenter and wait
  fjacquet.ppdm.discovery:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    inventory_source: vcenter.example.com
    level: DataCopies
    wait: true

- name: Start a discovery unless one is already running
  fjacquet.ppdm.discovery:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    inventory_source: vcenter.example.com
    ignore_running: true
'''

RETURN = r'''
discovery:
  description: The Discovery object answered by PPDM, C(taskId) is the activity id.
  returned: when the request was sent
  type: dict
  sample: {"id": "d1", "start": "/inventory-sources/s1", "level": "DataCopies", "taskId": "a1"}
activity:
  description: Final activity when I(wait=true).
  returned: when waited
  type: dict
warnings:
  description: Set when the activity ended OK_WITH_ERRORS.
  returned: when any
  type: list
  elements: str
msg:
  description: Set when I(ignore_running=true) and a discovery was already running.
  returned: when skipped
  type: str
'''

ARGUMENT_SPEC = dict(
    inventory_source=dict(type='str', required=True),
    level=dict(
        type='str',
        choices=[
            'APPLICATION_SYSTEM',
            'APPSERVER',
            'ASSET',
            'DataCopies',
            'Device',
            'HOST',
            'HOSTFULL',
            'INVENTORY_SOURCE',
            'ManagementInterface',
            'NETWORK_HOST',
            'ProtectableData',
            'STORAGE_SYSTEM',
            'STORAGE_TARGET',
        ],
    ),
    name=dict(type='str'),
    description=dict(type='str'),
    config=dict(type='dict'),
    wait=dict(type='bool', default=False),
    wait_timeout=dict(type='int', default=600),
    ignore_running=dict(type='bool', default=False),
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
    quote_id,
)


def find_source(client, ref):
    """The inventory source named ref, else the one with id ref; PpdmError when neither exists."""
    src = client.find_one("inventory-sources", "name", ref) or client.find_one("inventory-sources", "id", ref)
    if not src:
        raise PpdmError("inventory source %s not found" % ref)
    return src


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        supports_check_mode=True,
    )
    p = module.params
    client = client_from_module(module)
    out = {}
    changed = True
    try:
        source = find_source(client, p["inventory_source"])
        named = {
            "start": "/inventory-sources/%s" % quote_id(source["id"]),
            "level": p["level"],
            "name": p["name"],
            "description": p["description"],
        }
        body = merge_config(named, p["config"])
        try:
            res = client.start_action("/api/v2/discoveries", body, module.check_mode)
        except PpdmError as err:
            if err.status != 409:
                raise
            if not p["ignore_running"]:
                raise PpdmError("a similar discovery is already running (HTTP 409): %s" % err.msg, status=409) from None
            changed, out["msg"] = False, "a similar discovery is already running, nothing started"
        else:
            if res["response"] is not None:
                out["discovery"] = res["response"]
            if p["wait"] and not module.check_mode:
                # the 202 answer is a Discovery whose taskId is the activity id (its own id is not one)
                task_id = res["response"].get("taskId") if isinstance(res["response"], dict) else None
                if not task_id:
                    raise PpdmError("discovery answer has no taskId to wait for")
                out.update(client.await_activity(task_id, p["wait_timeout"]))
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=changed, **out)


if __name__ == "__main__":
    main()
