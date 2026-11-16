#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: smtp
short_description: Manage the SMTP configuration of PowerProtect Data Manager
description:
- Create, update or remove the SMTP configuration. PPDM allows only one.
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
- The password is write-only, it is never part of the idempotency comparison and is masked in the returned
  object and diff.
- The module fails when PPDM holds more than one SMTP configuration.
seealso:
- module: fjacquet.ppdm.smtp_info
  description: Read the SMTP configuration.
options:
  state:
    description:
    - Whether the SMTP configuration must exist.
    type: str
    choices:
    - present
    - absent
    default: present
  mail_server:
    description:
    - Host name or address of the mail server. Required when I(state=present).
    type: str
  mail_from:
    description:
    - Sender address of the emails.
    type: str
  recipient:
    description:
    - Recipient address of the emails. Required when I(test=true).
    type: str
  smtp_port:
    description:
    - Port of the mail server.
    type: int
  smtp_username:
    description:
    - User name for the mail server. This is not the PPDM login, which is the connection option C(username).
    type: str
  smtp_password:
    description:
    - Password for the mail server. This is not the PPDM login, which is the connection option C(password).
    type: str
  start_tls:
    description:
    - Whether to use STARTTLS.
    type: bool
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
  test:
    description:
    - Send a test email with the desired values after the configuration is ensured.
    - Skipped in check mode, because it sends a real email. It never sets C(changed) by itself.
    - Requires I(recipient).
    type: bool
    default: false
  config:
    description:
    - The module also fails when C(config) contains C(id) or C(_links), the server owns them.
    - The module fails when C(config) contains a key that a named option sets (C(mailServer), C(mailFrom),
      C(recipient), C(port), C(username), C(password) and C(isStartTls)), use the option instead.
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
- name: Configure SMTP and send a test email
  fjacquet.ppdm.smtp:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    mail_server: smtp.example.com
    mail_from: ppdm@example.com
    recipient: ops@example.com
    smtp_port: 587
    start_tls: true
    smtp_username: relay
    smtp_password: "{{ smtp_secret }}"
    test: true
'''

RETURN = r'''
smtp:
  description: The managed SMTP configuration, password masked. Absent with I(state=absent).
  returned: success
  type: dict
  sample: {"id": "s1", "mailServer": "smtp.example.com", "port": 587, "password": "VALUE_SPECIFIED_IN_NO_LOG_PARAMETER"}
diff:
  description: Before and after, password masked.
  returned: success
  type: dict
  sample: {"before": {}, "after": {"mailServer": "smtp.example.com"}}
'''

ARGUMENT_SPEC = dict(
    state=dict(type='str', choices=['present', 'absent'], default='present'),
    mail_server=dict(type='str'),
    mail_from=dict(type='str'),
    recipient=dict(type='str'),
    smtp_port=dict(type='int'),
    smtp_username=dict(type='str'),
    smtp_password=dict(type='str', no_log=True),
    start_tls=dict(type='bool'),
    update_password=dict(type='str', choices=['on_create', 'always'], default='on_create'),
    test=dict(type='bool', default=False),
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
        required_if=[("state", "present", ("mail_server",)), ("test", True, ("recipient",))],
    )
    p = module.params
    client = client_from_module(module)
    client.add_secret(p["smtp_password"])
    try:
        if p["state"] == "absent":
            res = client.remove("smtp", None, None, check_mode=module.check_mode, secret_keys=("password",))
            module.exit_json(changed=res["changed"], diff=res["diff"])
        desired = merge_config(
            {
                "mailServer": p["mail_server"],
                "mailFrom": p["mail_from"],
                "recipient": p["recipient"],
                "port": p["smtp_port"],
                "username": p["smtp_username"],
                "password": p["smtp_password"],
                "isStartTls": p["start_tls"],
            },
            p["config"],
        )
        res = client.ensure(
            "smtp",
            desired,
            key=None,
            check_mode=module.check_mode,
            secret_keys=("password",),
            update_secrets=p["update_password"],
            readonly=("id",),
        )
        if p["test"] and not module.check_mode:  # a real email, so never in check mode
            fields = ("mailServer", "mailFrom", "recipient", "port", "username", "password")
            client.request("POST", "/api/v2/smtp/test", body={k: desired[k] for k in fields if k in desired})
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=res["changed"], smtp=res["object"], diff=res["diff"])


if __name__ == "__main__":
    main()
