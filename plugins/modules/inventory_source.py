#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: inventory_source
short_description: Manage inventory sources on PowerProtect Data Manager
description:
- Create, update or remove an inventory source (vCenter, Kubernetes, Data Domain, ...), identified by
  its name.
- In PPDM 20.3.0 a Data Domain is added as an inventory source of type C(DDSYSTEM).
- Names are not enforced unique by the API; if two inventory sources share the name the module fails and
  lists both IDs.
version_added: 0.1.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
attributes:
  check_mode:
    support: full
  diff_mode:
    support: full
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
seealso:
- module: fjacquet.ppdm.inventory_source_info
  description: List inventory sources.
options:
  state:
    description:
    - Whether the inventory source must exist.
    type: str
    choices:
    - present
    - absent
    default: present
  name:
    description:
    - Inventory source name, used as the key.
    type: str
    required: true
  type:
    description:
    - Inventory source type. Required when I(state=present).
    type: str
    choices:
    - APP_HOST
    - CLOUD_DIRECTOR
    - CLOUD_SNAPSHOT_MANAGER
    - CDR
    - DATA_MANAGER_APPLIANCE
    - DATA_MANAGER_APPLIANCE_CLUSTER
    - DATADOMAINMANAGEMENTCENTER
    - DDSYSTEM
    - DEFAULTAPPGROUP
    - EXTERNALDATADOMAIN
    - GENERICNASMANAGEMENTSERVER
    - HYPERV_CLUSTER
    - HYPERV_SERVER
    - KUBERNETES
    - NATIVEEDGE_CLUSTER
    - NATIVEEDGE_ENDPOINT
    - NATIVEEDGE_ORCHESTRATOR
    - NETAPP_MANAGEMENT_SERVER
    - NUTANIX_CLUSTER
    - NUTANIX_SERVER
    - ORACLEGROUP
    - POWERSCALEMANAGEMENTSERVER
    - POWERSTOREMANAGEMENTSERVER
    - PPDM
    - PRISM_CENTRAL
    - SQLGROUPS
    - UNITYMANAGEMENTSERVER
    - UNISPHERE
    - VCENTER
  address:
    description:
    - IP address or hostname of the inventory source.
    type: str
  source_port:
    description:
    - Port of the inventory source.
    type: int
  credential_id:
    description:
    - ID of the credential used to reach the inventory source (see M(fjacquet.ppdm.credential_info)).
    type: str
  config:
    description:
    - The module also fails when C(config) contains C(id) or C(_links), the server owns them.
    - The module fails when C(config) contains a key that a named option sets (C(name), C(type), C(address),
      C(port) and C(credentials)), use the option instead.
    - Extra request body fields passed through as is, for example C(details) for type-specific settings
      such as C(details.vCenter).
    - The 20.3.0 request body has no certificate trust field, trust is handled with M(fjacquet.ppdm.certificate).
    - Each top-level key replaces the whole value of that field, the merge with the existing object is
      shallow (top-level keys only), nested values are not merged.
    - Do not put secrets here, values are not masked in diff or return values.
    type: dict
'''

EXAMPLES = r'''
- name: Ensure a vCenter inventory source
  fjacquet.ppdm.inventory_source:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: vc01
    type: VCENTER
    address: vc01.example.com
    source_port: 443
    credential_id: "{{ cred.credential.id }}"

- name: Pass type-specific vCenter settings through config
  fjacquet.ppdm.inventory_source:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: vc01
    type: VCENTER
    address: vc01.example.com
    credential_id: "{{ cred.credential.id }}"
    config:
      details:
        vCenter:
          assetSource: false
'''

RETURN = r'''
inventory_source:
  description: The managed inventory source.
  returned: success
  type: dict
  sample: {"id": "1", "name": "vc1", "type": "VCENTER", "address": "vc.example.com", "port": 443}
diff:
  description: Before and after.
  returned: success
  type: dict
  sample: {"before": {}, "after": {"name": "vc1", "type": "VCENTER"}}
'''

ARGUMENT_SPEC = dict(
    state=dict(type='str', choices=['present', 'absent'], default='present'),
    name=dict(type='str', required=True),
    type=dict(
        type='str',
        choices=[
            'APP_HOST',
            'CLOUD_DIRECTOR',
            'CLOUD_SNAPSHOT_MANAGER',
            'CDR',
            'DATA_MANAGER_APPLIANCE',
            'DATA_MANAGER_APPLIANCE_CLUSTER',
            'DATADOMAINMANAGEMENTCENTER',
            'DDSYSTEM',
            'DEFAULTAPPGROUP',
            'EXTERNALDATADOMAIN',
            'GENERICNASMANAGEMENTSERVER',
            'HYPERV_CLUSTER',
            'HYPERV_SERVER',
            'KUBERNETES',
            'NATIVEEDGE_CLUSTER',
            'NATIVEEDGE_ENDPOINT',
            'NATIVEEDGE_ORCHESTRATOR',
            'NETAPP_MANAGEMENT_SERVER',
            'NUTANIX_CLUSTER',
            'NUTANIX_SERVER',
            'ORACLEGROUP',
            'POWERSCALEMANAGEMENTSERVER',
            'POWERSTOREMANAGEMENTSERVER',
            'PPDM',
            'PRISM_CENTRAL',
            'SQLGROUPS',
            'UNITYMANAGEMENTSERVER',
            'UNISPHERE',
            'VCENTER',
        ],
    ),
    address=dict(type='str'),
    source_port=dict(type='int'),
    credential_id=dict(type='str'),
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


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        supports_check_mode=True,
        required_if=[("state", "present", ("type",))],
    )
    p = module.params
    client = client_from_module(module)
    try:
        if p["state"] == "absent":
            res = client.remove("inventory-sources", "name", p["name"], check_mode=module.check_mode)
        else:
            named = {
                "name": p["name"],
                "type": p["type"],
                "address": p["address"],
                "port": p["source_port"],
                "credentials": None if p["credential_id"] is None else {"id": p["credential_id"]},
            }
            desired = merge_config(named, p["config"])
            res = client.ensure("inventory-sources", desired, check_mode=module.check_mode)
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=res["changed"], inventory_source=res.get("object", {}), diff=res["diff"])


if __name__ == "__main__":
    main()
