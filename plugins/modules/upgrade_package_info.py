#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: upgrade_package_info
short_description: Get upgrade packages from PowerProtect Data Manager
description:
- Read-only query of upgrade packages. Never changes anything.
- Returns every matching object, all pages.
- The secret fields C(lockboxPassphrase) and C(upgradeToken) are never returned.
version_added: 0.4.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- Use this module to follow an upgrade started with M(fjacquet.ppdm.upgrade_package_action), the appliance
  restarts during the upgrade, so poll it after the API is back (see the C(bootstrap.wait_for_api) playbook).
seealso:
- module: fjacquet.ppdm.upgrade_package_action
  description: Precheck, install or revert an upgrade package.
options:
  name:
    description:
    - Return only the object whose name equals this value exactly (case-sensitive, checked again on the
      result, whatever the server filter returns). Mutually exclusive with I(filter) and I(id).
    type: str
  filter:
    description:
    - PPDM filter string, for example C(state eq "AVAILABLE"). It is passed to PPDM unchanged and its
      result is not re-checked. Mutually exclusive with I(name) and I(id).
    type: str
  id:
    description:
    - Return only the object with this ID. Mutually exclusive with I(name) and I(filter). A 404 answer
      gives an empty list.
    type: str
  category:
    description:
    - Return only packages of this category (exact match, combined with I(name) or I(filter) when given).
    type: str
    choices:
    - ACTIVE
    - HISTORY
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
- name: Get the active upgrade package
  fjacquet.ppdm.upgrade_package_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    category: ACTIVE
  register: result
'''

RETURN = r'''
upgrade_packages:
  description: Matching upgrade packages, an empty list when nothing matches.
  returned: always
  type: list
  elements: dict
  sample: [{"id": "u1", "name": "dellemc-ppdm-upgrade-sles-20.3.0-1.pkg", "state": "AVAILABLE", "category": "ACTIVE"}]
'''

ARGUMENT_SPEC = dict(
    name=dict(type='str'),
    filter=dict(type='str'),
    id=dict(type='str'),
    category=dict(type='str', choices=['ACTIVE', 'HISTORY']),
)
# fmt: on
# END GENERATED

from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import info_main


def main():
    info_main(
        "upgrade-packages",
        "upgrade_packages",
        ARGUMENT_SPEC,
        secret_fields=("lockboxPassphrase", "upgradeToken"),
        extra_eq={"category": "category"},
    )


if __name__ == "__main__":
    main()
