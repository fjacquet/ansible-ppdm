#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
DOCUMENTATION = r'''
module: certificate
short_description: Trust or remove a host certificate on PowerProtect Data Manager
description:
- Manage the trust store entry of a remote host certificate (C(/api/v2/certificates)).
- With C(state=present) the certificate presented by I(host):I(port) is fetched through PPDM and, unless
  its state is already C(ACCEPTED), accepted with a PUT.
- With C(state=absent) the entry is deleted when it is currently C(ACCEPTED).
- Idempotence key is I(host) and I(port) (the trust store keys on them), pin the presented certificate
  with I(fingerprint).
version_added: 1.0.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
options:
  state:
    description:
    - C(present) accepts (trusts) the certificate, C(absent) removes it from the trust store.
    type: str
    choices:
    - present
    - absent
    default: present
  host:
    description:
    - Host name or IP address presenting the certificate.
    type: str
    required: true
  port:
    description:
    - TLS port of the host.
    type: int
    default: 443
  type:
    description:
    - Certificate type to fetch.
    type: str
    choices:
    - HOST
    - ROOT
    - INTERMEDIATE
    default: HOST
  fingerprint:
    description:
    - Expected fingerprint. When set, the module fails instead of trusting a certificate with a different
      fingerprint.
    type: str
'''

EXAMPLES = r'''
- name: Trust the certificate of a Data Domain
  fjacquet.ppdm.certificate:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    host: dd01.example.com
    port: 3009
    fingerprint: "AB:CD:..."

- name: Remove the trust
  fjacquet.ppdm.certificate:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    host: dd01.example.com
    port: 3009
    state: absent
'''

RETURN = r'''
certificate:
  description: The certificate entry (empty when absent and nothing was trusted).
  returned: success
  type: dict
diff:
  description: Before and after.
  returned: success
  type: dict
'''

ARGUMENT_SPEC = dict(
    state=dict(type='str', choices=['present', 'absent'], default='present'),
    host=dict(type='str', required=True),
    port=dict(type='int', default=443),
    type=dict(type='str', choices=['HOST', 'ROOT', 'INTERMEDIATE'], default='HOST'),
    fingerprint=dict(type='str'),
)
# END GENERATED

from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (  # noqa: E402
    PpdmError, client_from_module, connection_argument_spec, fail_from,
)

PATH = "/api/v2/certificates"


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC), supports_check_mode=True
    )
    p = module.params
    client = client_from_module(module)
    try:
        found = client.get_all(PATH, {"host": p["host"], "port": p["port"], "type": p["type"]})
        found = found if isinstance(found, list) else []
        # The trust store keys a certificate on host and port.
        cert = next((c for c in found if c.get("host", p["host"]) == p["host"]
                     and str(c.get("port", p["port"])) == str(p["port"])), None)
        trusted = cert is not None and cert.get("state") == "ACCEPTED"
        if p["state"] == "absent":
            if not trusted or not cert.get("id"):
                module.exit_json(changed=False, certificate={}, diff={"before": {}, "after": {}})
            if not module.check_mode:
                client.request("DELETE", "%s/%s" % (PATH, cert["id"]))
            module.exit_json(changed=True, certificate={}, diff={"before": cert, "after": {}})
        if cert is None:
            module.fail_json(msg="PPDM returned no certificate for %s:%s" % (p["host"], p["port"]))
        if p["fingerprint"] and cert.get("fingerprint") != p["fingerprint"]:
            module.fail_json(msg="certificate fingerprint %s does not match the expected %s"
                             % (cert.get("fingerprint"), p["fingerprint"]))
        if trusted:
            module.exit_json(changed=False, certificate=cert, diff={"before": cert, "after": cert})
        after = dict(cert, state="ACCEPTED")
        if not module.check_mode:
            if cert.get("id"):
                after = client.request("PUT", "%s/%s" % (PATH, cert["id"]), body=after) or after
            else:
                after = client.request("POST", PATH, body=after) or after
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=True, certificate=after, diff={"before": cert, "after": after})


if __name__ == "__main__":
    main()
