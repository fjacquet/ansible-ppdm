#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: smtp_info
short_description: Get the SMTP configuration from PowerProtect Data Manager
description:
- Read-only query of the SMTP configuration. Never changes anything.
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
- The password field is never returned.
seealso:
- module: fjacquet.ppdm.smtp
  description: Manage the SMTP configuration.
options: {}
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
- name: Read the SMTP configuration
  fjacquet.ppdm.smtp_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
  register: result
'''

RETURN = r'''
smtp:
  description: The SMTP configuration, a list of at most one item, empty when none is set.
  returned: always
  type: list
  elements: dict
  sample: [{"id": "s1", "mailServer": "smtp.example.com", "port": 587}]
'''

ARGUMENT_SPEC = dict(
)
# fmt: on
# END GENERATED

from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import info_main


def main():
    info_main("smtp", "smtp", ARGUMENT_SPEC, secret_fields=("password",))


if __name__ == "__main__":
    main()
