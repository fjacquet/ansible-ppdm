#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: credential
short_description: Manage credentials on PowerProtect Data Manager
description:
- Create, update or remove a credential, identified by its name.
- The password is never returned by PPDM and never shown in the result or the diff.
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
- The password is write-only, it is never part of the idempotency comparison and is masked in the returned
  object and diff.
seealso:
- module: fjacquet.ppdm.credential_info
  description: List credentials.
options:
  state:
    description:
    - Whether the credential must exist.
    type: str
    choices:
    - present
    - absent
    default: present
  name:
    description:
    - Credential name, used as the unique key.
    type: str
    required: true
  type:
    description:
    - Credential account type. Required when I(state=present).
    type: str
    choices:
    - DATADOMAIN
    - POWERPROTECT
    - DBUSER
    - OS
    - RMAN
    - STANDARD
    - VCENTER
    - KUBERNETES
    - CDR
    - SAPHANA_DB_USER
    - SAPHANA_SYSTEMDB_USER
    - DDBOOST
    - NAS
    - CLOUD_SNAPSHOT_MANAGER
    - CLOUD_DIRECTOR
    - AVAMAR
    - HYPERV
    - DELL_ECS
    - NUTANIX
    - NATIVE_EDGE
    - MS_AZURE
    - MS_GMSA
    - NT_AUTHORITY
    - AMAZON_S3
    - GENERIC_S3
  method:
    description:
    - Credential method.
    type: str
    choices:
    - BASIC
    - TOKEN
    - CONFIG
    - USER_KEY
    - OIDC_REFRESH_TOKEN
  cred_username:
    description:
    - Username of the stored credential account. This is not the PPDM login, which is the connection option
      C(username).
    - Required when I(state=present).
    type: str
  cred_password:
    description:
    - Password of the stored credential account. This is not the PPDM login, which is the connection option
      C(password).
    type: str
  update_password:
    description:
    - C(on_create) never compares the password and never causes a change by itself; it is sent on create
      and whenever an update is sent for another difference.
    - C(always) forces an update on every run (always reports changed) and sends the password, because
      PPDM never returns it.
    type: str
    choices:
    - on_create
    - always
    default: on_create
'''

EXAMPLES = r'''
- name: Ensure a Data Domain credential
  fjacquet.ppdm.credential:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: dd01
    type: DATADOMAIN
    cred_username: sysadmin
    cred_password: "{{ dd_password }}"
'''

RETURN = r'''
credential:
  description: The managed credential, password masked.
  returned: success
  type: dict
  sample: {"id": "c1", "name": "vc-admin", "type": "VCENTER", "username": "svc", "password": "VALUE_SPECIFIED_IN_NO_LOG_PARAMETER"}
diff:
  description: Before and after, password masked.
  returned: success
  type: dict
  sample: {"before": {}, "after": {"name": "vc-admin", "type": "VCENTER"}}
'''

ARGUMENT_SPEC = dict(
    state=dict(type='str', choices=['present', 'absent'], default='present'),
    name=dict(type='str', required=True),
    type=dict(
        type='str',
        choices=[
            'DATADOMAIN',
            'POWERPROTECT',
            'DBUSER',
            'OS',
            'RMAN',
            'STANDARD',
            'VCENTER',
            'KUBERNETES',
            'CDR',
            'SAPHANA_DB_USER',
            'SAPHANA_SYSTEMDB_USER',
            'DDBOOST',
            'NAS',
            'CLOUD_SNAPSHOT_MANAGER',
            'CLOUD_DIRECTOR',
            'AVAMAR',
            'HYPERV',
            'DELL_ECS',
            'NUTANIX',
            'NATIVE_EDGE',
            'MS_AZURE',
            'MS_GMSA',
            'NT_AUTHORITY',
            'AMAZON_S3',
            'GENERIC_S3',
        ],
    ),
    method=dict(type='str', choices=['BASIC', 'TOKEN', 'CONFIG', 'USER_KEY', 'OIDC_REFRESH_TOKEN']),
    cred_username=dict(type='str'),
    cred_password=dict(type='str', no_log=True),
    update_password=dict(type='str', choices=['on_create', 'always'], default='on_create'),
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


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        supports_check_mode=True,
        required_if=[("state", "present", ("type", "cred_username"))],
    )
    p = module.params
    client = client_from_module(module)
    try:
        if p["state"] == "absent":
            res = client.remove(
                "credentials", "name", p["name"], check_mode=module.check_mode, secret_keys=("password",)
            )
        else:
            desired = {
                "name": p["name"],
                "type": p["type"],
                "username": p["cred_username"],
                "method": p["method"],
                "password": p["cred_password"],
            }
            desired = {k: v for k, v in desired.items() if v is not None}
            res = client.ensure(
                "credentials",
                desired,
                check_mode=module.check_mode,
                secret_keys=("password",),
                update_secrets=p["update_password"],
            )
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=res["changed"], credential=res.get("object", {}), diff=res["diff"])


if __name__ == "__main__":
    main()
