#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: asset_info
short_description: Get assets from PowerProtect Data Manager
description:
- Read-only query of assets. Never changes anything.
- Returns every matching object, all pages.
- The C(credentials) field of each asset is never returned, because its C(extraInfo) name/value pairs
  are free-form and could carry secrets. C(credentialId) (a reference only) is kept.
version_added: 0.3.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- The C(credentials) field is never returned. The 20.3.0 schema of assets has no password or token field,
  this is a precaution for the free-form C(credentials[].extraInfo).
options:
  asset_type:
    description:
    - Return only assets of this type (exact match, combined with I(name) or I(filter) when given).
    type: str
    choices:
    - AVAMAR_ASSET
    - CLOUD_DIRECTOR_VAPP
    - CLOUD_NATIVE_ENTITY
    - DR
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
  name:
    description:
    - Return only the object whose name equals this value exactly (case-sensitive, checked again on the
      result, whatever the server filter returns). Mutually exclusive with I(filter) and I(id).
    type: str
  filter:
    description:
    - PPDM filter string, for example C(name lk "prod%"). It is passed to PPDM unchanged and its result
      is not re-checked. Mutually exclusive with I(name) and I(id).
    type: str
  id:
    description:
    - Return only the object with this ID. Mutually exclusive with I(name) and I(filter). A 404 answer
      gives an empty list, a 404 also happens when this PPDM version does not support the endpoint.
    type: str
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
- name: List all assets
  fjacquet.ppdm.asset_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
  register: result

- name: List file system assets
  fjacquet.ppdm.asset_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    asset_type: FILE_SYSTEM
'''

RETURN = r'''
assets:
  description: Matching objects, an empty list when nothing matches.
  returned: always
  type: list
  elements: dict
  sample: [{"id": "a1", "name": "vm01", "type": "VMWARE_VIRTUAL_MACHINE"}]
'''

ARGUMENT_SPEC = dict(
    asset_type=dict(
        type='str',
        choices=[
            'AVAMAR_ASSET',
            'CLOUD_DIRECTOR_VAPP',
            'CLOUD_NATIVE_ENTITY',
            'DR',
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
    ),
    name=dict(type='str'),
    filter=dict(type='str'),
    id=dict(type='str'),
)
# fmt: on
# END GENERATED

from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import info_main


def main():
    info_main("assets", "assets", ARGUMENT_SPEC, secret_fields=("credentials",), extra_eq={"asset_type": "type"})


if __name__ == "__main__":
    main()
