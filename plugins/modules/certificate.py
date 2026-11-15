#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: certificate
short_description: Trust or remove a host certificate on PowerProtect Data Manager
description:
- Manage the trust store entry of a remote host certificate (C(/api/v2/certificates)).
- With C(state=present) the certificate presented by I(host):I(port) is fetched through PPDM and accepted
  with a PUT (a POST when the entry has no ID).
- Secure by default, C(state=present) requires I(fingerprint), the presented fingerprint must match it.
  Without it the module fails unless I(accept_any_certificate=true).
- With a I(fingerprint) pin, the states C(UNKNOWN), C(MISMATCHED) and C(REJECTED) are accepted, C(EXPIRED),
  C(MALFORMED) and any other state fail. A certificate already C(ACCEPTED) with a different fingerprint
  than the pin fails, it is never reported as unchanged.
- With I(accept_any_certificate=true) only C(UNKNOWN) is accepted, every other non-C(ACCEPTED) state fails.
- With C(state=absent) the entry is deleted when it is currently C(ACCEPTED).
- A real C(state=present) run does the GET without C(nocache), per the API this retrieves the remote certificate
  and stores it in the trust store in a non-accepted state, BEFORE the I(fingerprint) pin is checked,
  and the entry stays there when the pin does not match (by design, PPDM exposes no side-effect-free way
  to read the presented certificate). Check mode and C(state=absent) use C(nocache=true) so they never
  write to the trust store.
- Entries are matched on exact I(host) (case-insensitive), I(port) and I(type). More than one match fails.
- With C(state=absent) an API entry without a C(type) is not matched, so C(changed=false) can mean "not
  found by this module".
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
    - Expected fingerprint of the presented certificate, as shown by PPDM (hex, with or without C(:) separators,
      case-insensitive). Whitespace and C(:) are ignored, what remains must be one or more hex digits,
      otherwise the module fails before sending any request.
    - Required for C(state=present) unless I(accept_any_certificate=true).
    type: str
  accept_any_certificate:
    description:
    - Insecure, trusts whatever certificate the host presents (only state C(UNKNOWN)). A warning is issued
      when used.
    - Only for C(state=present) without I(fingerprint).
    type: bool
    default: false
'''

EXAMPLES = r'''
- name: Trust the certificate of a Data Domain
  fjacquet.ppdm.certificate:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    host: dd01.example.com
    port: 3009
    fingerprint: "AB:CD:EF:..."

- name: Trust whatever the host presents (insecure)
  fjacquet.ppdm.certificate:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    host: lab-dd.example.com
    port: 3009
    accept_any_certificate: true

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
    accept_any_certificate=dict(type='bool', default=False),
)
# fmt: on
# END GENERATED

import re

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (
    PpdmError,
    client_from_module,
    connection_argument_spec,
    fail_from,
    quote_id,
)

PATH = "/api/v2/certificates"
PIN_ACCEPTS = ("UNKNOWN", "MISMATCHED", "REJECTED")


def item_path(cert_id):
    if not isinstance(cert_id, str) or not cert_id:
        raise PpdmError("the certificate has no usable id")
    return "%s/%s" % (PATH, quote_id(cert_id))  # the id comes from the server: it must not change the path


def norm(fp):
    return re.sub(r"[:\s]", "", fp or "").lower()


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        supports_check_mode=True,
    )
    p = module.params
    present = p["state"] == "present"
    if present and not p["fingerprint"] and not p["accept_any_certificate"]:
        module.fail_json(
            msg="state=present requires fingerprint, or set accept_any_certificate=true "
            "(insecure: trusts whatever certificate the host presents)"
        )
    if present and p["fingerprint"] and not re.fullmatch(r"[0-9a-f]+", norm(p["fingerprint"])):
        module.fail_json(msg="fingerprint must be hex digits, optionally with ':' separators or whitespace")
    if present and p["accept_any_certificate"]:
        module.warn("accept_any_certificate=true trusts whatever certificate the host presents")
    client = client_from_module(module)
    query = {"host": p["host"], "port": p["port"], "type": p["type"]}
    if module.check_mode or not present:
        query["nocache"] = "true"  # never write to the trust store
    try:
        found = client.get_all(PATH, query)
        found = found if isinstance(found, list) else []
        matches = [
            c
            for c in found
            if str(c.get("host") or "").lower() == p["host"].lower()
            and str(c.get("port")) == str(p["port"])
            and str(c.get("type") or "").lower() == p["type"].lower()
        ]
        if len(matches) > 1:
            module.fail_json(
                msg="more than one certificate matches %s:%s: %s"
                % (
                    p["host"],
                    p["port"],
                    ", ".join(
                        "%s (%s)" % (client.scrub_text(c.get("id"), 64), client.scrub_text(c.get("fingerprint"), 128))
                        for c in matches[:10]
                    ),
                )
            )
        cert = matches[0] if matches else None
        state = cert.get("state") if cert else None
        if not present:
            if state != "ACCEPTED" or not cert.get("id"):
                module.exit_json(changed=False, certificate={}, diff={"before": {}, "after": {}})
            if not module.check_mode:
                client.request("DELETE", item_path(cert["id"]))
            module.exit_json(changed=True, certificate={}, diff={"before": cert, "after": {}})
        if cert is None:
            module.fail_json(msg="PPDM returned no certificate for %s:%s" % (p["host"], p["port"]))
        if p["fingerprint"]:
            if norm(cert.get("fingerprint")) != norm(p["fingerprint"]):
                module.fail_json(
                    msg="certificate fingerprint %s does not match the expected %s (state %s)"
                    % (client.scrub_text(cert.get("fingerprint"), 128), p["fingerprint"], client.scrub_text(state, 64))
                )
            acceptable = PIN_ACCEPTS
        else:
            acceptable = ("UNKNOWN",)
        if state == "ACCEPTED":
            module.exit_json(changed=False, certificate=cert, diff={"before": cert, "after": cert})
        if state not in acceptable:
            module.fail_json(
                msg="certificate for %s:%s is in state %s, refusing to accept it"
                % (p["host"], p["port"], client.scrub_text(state, 64))
            )
        after = dict(cert, state="ACCEPTED")
        if not module.check_mode:
            if cert.get("id"):
                after = client.request("PUT", item_path(cert["id"]), body=after) or after
            else:
                after = client.request("POST", PATH, body=after) or after
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=True, certificate=after, diff={"before": cert, "after": after})


if __name__ == "__main__":
    main()
