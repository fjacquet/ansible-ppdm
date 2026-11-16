#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: user_info
short_description: Get users from PowerProtect Data Manager
description:
- Read-only query of local users. Never changes anything.
- The C(password) field is dropped from the result, not masked.
version_added: 0.4.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- The users API (C(/api/v2/users)) is deprecated in the PPDM 20.3.0 specification, its replacement is
  C(/api/v3/identity-access-provisions).
seealso:
- module: fjacquet.ppdm.user
  description: Manage users.
options:
  name:
    description:
    - Return only the user whose C(username) equals this value exactly (case-sensitive, checked again
      on the result, whatever the server filter returns). Mutually exclusive with I(filter) and I(id).
    type: str
  filter:
    description:
    - PPDM filter string, for example C(username lk "a%"). It is passed to PPDM unchanged and its result
      is not re-checked. Mutually exclusive with I(name) and I(id).
    type: str
  id:
    description:
    - Return only the user with this ID. Mutually exclusive with I(name) and I(filter). A 404 answer gives
      an empty list.
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
- name: Get one user
  fjacquet.ppdm.user_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: jdoe
  register: result
'''

RETURN = r'''
users:
  description: Matching users, an empty list when nothing matches.
  returned: always
  type: list
  elements: dict
  sample: [{"id": "u1", "username": "jdoe", "emailAddress": "jdoe@example.com"}]
'''

ARGUMENT_SPEC = dict(
    name=dict(type='str'),
    filter=dict(type='str'),
    id=dict(type='str'),
)
# fmt: on
# END GENERATED

from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import info_main


def main():
    info_main("users", "users", ARGUMENT_SPEC, secret_fields=("password",), name_key="username")


if __name__ == "__main__":
    main()
