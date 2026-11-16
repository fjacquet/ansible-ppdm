#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: user
short_description: Manage local users of PowerProtect Data Manager
description:
- Create, update or remove a local PPDM user.
- The password is never returned by PPDM and never shown in the result or the diff.
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
  C(/api/v3/identity-access-provisions). This module stays on v2.
- The password is write-only, it is never part of the idempotency comparison and is masked in the returned
  object and diff.
- On create, I(first_name), I(last_name), I(email) and I(user_password) are required. When one of them
  is missing, the module fails if the user does not exist, without any write.
seealso:
- module: fjacquet.ppdm.user_info
  description: Read users.
- module: fjacquet.ppdm.role_info
  description: Read roles.
options:
  state:
    description:
    - Whether the user must exist.
    type: str
    choices:
    - present
    - absent
    default: present
  name:
    description:
    - User name (the C(username) field), the key of the user.
    type: str
    required: true
  first_name:
    description:
    - First name.
    type: str
  last_name:
    description:
    - Last name.
    type: str
  email:
    description:
    - Email address.
    type: str
  user_password:
    description:
    - Password of the user. This is not the PPDM login, which is the connection option C(password). PPDM
      20.3 requires 9 to 100 characters with a lower case letter, an upper case letter, a digit and a
      special character (verified on a live lab).
    type: str
  update_password:
    description:
    - C(on_create) sends the password only when the user is created; an existing user's password is never
      compared, sent or changed.
    - C(always) forces an update on every run (always reports changed) and sends the password, because
      PPDM never returns it.
    type: str
    choices:
    - on_create
    - always
    default: on_create
  force_password_change:
    description:
    - Whether the user must change the password at next login.
    type: bool
  role:
    description:
    - Name of the role. Resolved to its ID, the module fails when no role has this name. Mutually exclusive
      with I(role_id).
    type: str
  role_id:
    description:
    - ID of the role. Mutually exclusive with I(role).
    type: str
  config:
    description:
    - The module also fails when C(config) contains C(id) or C(_links), the server owns them.
    - The module fails when C(config) contains a key that a named option sets (C(username), C(firstName),
      C(lastName), C(emailAddress), C(password), C(forcePasswordChange) and C(roleId)), use the option
      instead.
    - Extra request body fields passed through as is.
    - Each top-level key replaces the whole value of that field, the merge with the existing object is
      shallow (top-level keys only), nested values are not merged.
    - Do not put secrets here, values are not masked in diff or return values.
    type: dict
attributes:
  platform:
    platforms: all
  check_mode:
    support: full
  diff_mode:
    support: full
'''

EXAMPLES = r'''
- name: Create a user with a role
  fjacquet.ppdm.user:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: jdoe
    first_name: Jane
    last_name: Doe
    email: jdoe@example.com
    user_password: "{{ jdoe_secret }}"
    role: Administrator
'''

RETURN = r'''
user:
  description: The managed user, password masked. Empty with I(state=absent).
  returned: success
  type: dict
  sample: {"id": "u1", "username": "jdoe", "password": "VALUE_SPECIFIED_IN_NO_LOG_PARAMETER"}
diff:
  description: Before and after, password masked.
  returned: success
  type: dict
  sample: {"before": {}, "after": {"username": "jdoe"}}
'''

ARGUMENT_SPEC = dict(
    state=dict(type='str', choices=['present', 'absent'], default='present'),
    name=dict(type='str', required=True),
    first_name=dict(type='str'),
    last_name=dict(type='str'),
    email=dict(type='str'),
    user_password=dict(type='str', no_log=True),
    update_password=dict(type='str', choices=['on_create', 'always'], default='on_create'),
    force_password_change=dict(type='bool'),
    role=dict(type='str'),
    role_id=dict(type='str'),
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

READONLY = ("id", "createdDate")


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        supports_check_mode=True,
        mutually_exclusive=[("role", "role_id")],
    )
    p = module.params
    client = client_from_module(module)
    client.add_secret(p["user_password"])
    try:
        if p["state"] == "absent":
            res = client.remove("users", "username", p["name"], check_mode=module.check_mode, secret_keys=("password",))
            module.exit_json(changed=res["changed"], diff=res["diff"])
        role_id = p["role_id"]
        if p["role"] is not None:
            role = client.find_one("roles", "name", p["role"])
            if role is None:
                raise PpdmError("role %s not found" % client.scrub_text(p["role"], 200))
            role_id = role["id"]
        desired = merge_config(
            {
                "username": p["name"],
                "firstName": p["first_name"],
                "lastName": p["last_name"],
                "emailAddress": p["email"],
                "password": p["user_password"],
                "forcePasswordChange": p["force_password_change"],
                "roleId": role_id,
            },
            p["config"],
        )
        required = ("firstName", "lastName", "emailAddress", "password")
        drop_password = "password" in desired and p["update_password"] != "always"
        known = {}  # the looked-up user, handed to ensure so it is fetched once
        if drop_password or any(k not in desired for k in required):
            found = client.find_one("users", "username", p["name"])
            known["existing"] = found
            if found is None and any(k not in desired for k in required):
                raise PpdmError(
                    client.scrub_text(
                        "creating user %s needs first_name, last_name, email and user_password" % p["name"]
                    )
                )
            if found is not None and drop_password:
                desired.pop("password")  # on_create never touches an existing password
        res = client.ensure(
            "users",
            desired,
            key="username",
            check_mode=module.check_mode,
            secret_keys=("password",),
            update_secrets=p["update_password"],
            readonly=READONLY,
            **known,
        )
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=res["changed"], user=res["object"], diff=res["diff"])


if __name__ == "__main__":
    main()
