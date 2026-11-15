#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
DOCUMENTATION = r'''
module: eula
short_description: Accept an end user license agreement on PowerProtect Data Manager
description:
- Accept one of the PowerProtect Data Manager EULAs (C(/api/v2/eulas/<name>)).
- Singleton, there is no I(state) option, the module only ever accepts. The PATCH is sent only when the
  EULA is not already accepted.
- A EULA cannot be un-accepted through the API, I(accepted=false) fails when the EULA is currently accepted.
version_added: 1.0.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
options:
  name:
    description:
    - Which EULA.
    type: str
    choices:
    - PPDM
    - TELEMETRY
    - data-manager
    default: PPDM
  accepted:
    description:
    - Desired acceptance.
    type: bool
    default: true
'''

EXAMPLES = r'''
- name: Accept the PPDM EULA
  fjacquet.ppdm.eula:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
'''

RETURN = r'''
eula:
  description: The EULA after the change.
  returned: success
  type: dict
diff:
  description: Before and after.
  returned: success
  type: dict
'''

ARGUMENT_SPEC = dict(
    name=dict(type='str', choices=['PPDM', 'TELEMETRY', 'data-manager'], default='PPDM'),
    accepted=dict(type='bool', default=True),
)
# END GENERATED

from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (  # noqa: E402
    PpdmError, client_from_module, connection_argument_spec, fail_from,
)


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC), supports_check_mode=True
    )
    p = module.params
    path = "/api/v2/eulas/" + p["name"]
    client = client_from_module(module)
    try:
        before = client.request("GET", path) or {}
        if before.get("accepted") == p["accepted"]:
            module.exit_json(changed=False, eula=before, diff={"before": before, "after": before})
        if not p["accepted"]:
            module.fail_json(msg="EULA %s is accepted and the API cannot un-accept it" % p["name"])
        after = dict(before, accepted=True)
        if not module.check_mode:
            after = client.request("PATCH", path, body={"accepted": True}) or after
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=True, eula=after, diff={"before": before, "after": after})


if __name__ == "__main__":
    main()
