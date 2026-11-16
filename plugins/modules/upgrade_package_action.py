#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: upgrade_package_action
short_description: Precheck, install or revert an upgrade package on PowerProtect Data Manager
description:
- Run the precheck, the upgrade or the revert of an upgrade package, through C(POST .../precheck), C(PUT
  .../{id}) and C(POST .../revert) under C(/api/v2/upgrade-packages).
- Reports C(changed=false) without any request when the package is already C(INSTALLED) (upgrade) or reverted
  (revert). In check mode nothing is sent and C(changed=true) is reported otherwise.
version_added: 0.4.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- The upgrade and the revert are service-affecting, the appliance restarts. The module fails before any
  request or login unless I(confirm=true), for every I(action) and also in check mode.
- The package is read first. A precheck is refused on an installed package, an upgrade needs the state
  C(AVAILABLE) or C(FAILED), and fails on a partly installed package (C(INSTALLED_CORE), C(INSTALLED_WITH_ERRORS),
  C(INSTALLED_WITH_SKIPPED)) instead of reporting it done, a revert needs C(revertSupported=true) and
  a C(HOTFIX) package.
- Only the answer 202 counts as success for the upgrade. The 200 answer of the API schema is an error
  message, so the module fails with it.
- The upgrade request always carries C(forceUpgrade) explicitly, because the API default is C(true).
- I(wait) works with the precheck only. The appliance restarts during an upgrade or a revert, so the module
  cannot poll them and fails when I(wait=true). Poll with M(fjacquet.ppdm.upgrade_package_info) once the
  API is back, see the C(bootstrap.wait_for_api) playbook.
- The passphrase is never returned, logged or sent in a message. The package returned by the module shows
  C(lockboxPassphrase) and C(upgradeToken) masked.
seealso:
- module: fjacquet.ppdm.upgrade_package_info
  description: Get upgrade packages.
options:
  action:
    description:
    - Operation to run on the package.
    type: str
    required: true
    choices:
    - precheck
    - upgrade
    - revert
  id:
    description:
    - ID of the upgrade package. Defaults to the single package of category C(ACTIVE), the module fails
      when there is none or several.
    type: str
  confirm:
    description:
    - Must be C(true) for every I(action), a safeguard against an accidental upgrade.
    type: bool
    default: false
  force:
    description:
    - Sent as the query parameter C(forceUpgrade) of the upgrade, always explicit.
    type: bool
    default: false
  trust_certificate:
    description:
    - Trust the package certificate on the upgrade (C(certificateTrustedByUser)).
    type: bool
    default: false
  accept_eula:
    description:
    - Accept the product and telemetry EULAs on the upgrade.
    type: bool
    default: false
  lockbox_passphrase:
    description:
    - Lockbox passphrase, sent only when set. Needed when the package reports C(lockboxResetRequired).
    type: str
  wait:
    description:
    - Wait for the precheck activity to complete. An error with C(upgrade) and C(revert), see the notes.
    type: bool
    default: false
  wait_timeout:
    description:
    - Seconds to wait for the precheck activity when I(wait=true).
    type: int
    default: 600
attributes:
  platform:
    platforms: all
  check_mode:
    support: full
  diff_mode:
    support: none
'''

EXAMPLES = r'''
- name: Precheck the active upgrade package
  fjacquet.ppdm.upgrade_package_action:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    action: precheck
    confirm: true
    wait: true

- name: Install the active upgrade package
  fjacquet.ppdm.upgrade_package_action:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    action: upgrade
    trust_certificate: true
    accept_eula: true
    confirm: true
'''

RETURN = r'''
upgrade_package:
  description: The package as read, with C(lockboxPassphrase) and C(upgradeToken) masked.
  returned: when the package was read
  type: dict
response:
  description: Answer of PPDM to the request, secrets masked.
  returned: when the request was sent
  type: dict
  sample: {"activityId": "a1", "id": "u1"}
activity:
  description: Final precheck activity when I(wait=true).
  returned: when waited
  type: dict
warnings:
  description: Warn status of the precheck activity.
  returned: when any
  type: list
  elements: str
'''

ARGUMENT_SPEC = dict(
    action=dict(type='str', required=True, choices=['precheck', 'upgrade', 'revert']),
    id=dict(type='str'),
    confirm=dict(type='bool', default=False),
    force=dict(type='bool', default=False),
    trust_certificate=dict(type='bool', default=False),
    accept_eula=dict(type='bool', default=False),
    lockbox_passphrase=dict(type='str', no_log=True),
    wait=dict(type='bool', default=False),
    wait_timeout=dict(type='int', default=600),
)
# fmt: on
# END GENERATED

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (
    PpdmError,
    _mask,
    client_from_module,
    connection_argument_spec,
    fail_from,
    quote_id,
)

SECRET_KEYS = ("lockboxPassphrase", "upgradeToken")
MIN_SERVER_SECRET = 8  # a shorter server-supplied value would mask unrelated text, so it is not registered


def main():
    module = AnsibleModule(argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC), supports_check_mode=True)
    p = module.params
    # all of this fails before any request or login
    if not p["confirm"]:
        module.fail_json(msg="%s of an upgrade package needs confirm=true" % p["action"])
    if p["wait"] and p["action"] != "precheck":
        module.fail_json(msg="wait only works with action=precheck, the appliance restarts during %s" % p["action"])
    client = client_from_module(module)
    client.add_secret(p["lockbox_passphrase"])
    if p["lockbox_passphrase"]:  # never add "": remove_values would mangle every result string
        module.no_log_values.add(p["lockbox_passphrase"])

    out = {}
    try:
        pkg_id = p["id"]
        if pkg_id is None:
            active = client.list_all("upgrade-packages", filter='category eq "ACTIVE"')
            active = [o for o in active if isinstance(o, dict) and o.get("category") == "ACTIVE"]
            if len(active) != 1:
                raise PpdmError("expected exactly one ACTIVE upgrade package, found %d" % len(active))
            pkg_id = active[0].get("id")
            if not pkg_id:
                raise PpdmError("the ACTIVE upgrade package has no id")
        path = "/api/v2/upgrade-packages/" + quote_id(pkg_id)
        pkg = client.request("GET", path)
        if not isinstance(pkg, dict):
            raise PpdmError("GET %s failed: unexpected response" % path)
        for key in SECRET_KEYS:
            if isinstance(pkg.get(key), str) and len(pkg[key]) >= MIN_SERVER_SECRET:
                client.add_secret(pkg[key])
                module.no_log_values.add(pkg[key])
        out["upgrade_package"] = _mask(pkg, SECRET_KEYS)
        state = str(pkg.get("state"))
        action = p["action"]
        if action == "precheck" and state.startswith("INSTALLED"):
            raise PpdmError("upgrade package %s is already installed, a precheck is refused" % pkg_id)
        if action == "upgrade":
            if state == "INSTALLED":
                module.exit_json(changed=False, **out)
            if state.startswith("INSTALLED"):  # INSTALLED_CORE, INSTALLED_WITH_ERRORS, INSTALLED_WITH_SKIPPED
                raise PpdmError(
                    "upgrade package %s is only partly installed (state %s), not reported as done" % (pkg_id, state)
                )
            if state not in ("AVAILABLE", "FAILED"):
                raise PpdmError(
                    "upgrade package %s is in state %s, an upgrade needs AVAILABLE or FAILED" % (pkg_id, state)
                )
        if action == "revert":
            if state == "REVERTED":
                module.exit_json(changed=False, **out)
            if pkg.get("revertSupported") is not True or pkg.get("type") != "HOTFIX":
                raise PpdmError("upgrade package %s cannot be reverted (needs a HOTFIX with revertSupported)" % pkg_id)
        resp = None
        if action == "upgrade":
            body = {k: v for k, v in pkg.items() if k not in ("_links", "lockboxPassphrase")}
            body.update(
                state="INSTALLED",
                certificateTrustedByUser=p["trust_certificate"],
                eula={"productEulaAccepted": p["accept_eula"], "telemetryEulaAccepted": p["accept_eula"]},
            )
            if p["lockbox_passphrase"]:
                body["lockboxPassphrase"] = p["lockbox_passphrase"]
            if not module.check_mode:
                resp = client.request("PUT", path, query={"forceUpgrade": "true" if p["force"] else "false"}, body=body)
                if client.last_status != 202:  # the spec gives 200 the ErrorMessage schema
                    detail = resp.get("message") if isinstance(resp, dict) else resp
                    raise PpdmError("PUT %s answered %s, not 202: %s" % (path, client.last_status, detail))
        else:
            resp = client.start_action(path + "/" + action, None, module.check_mode)["response"]
        if resp is not None:
            out["response"] = _mask(resp, SECRET_KEYS) if isinstance(resp, dict) else resp
            if p["wait"]:
                act_id = resp.get("activityId") if isinstance(resp, dict) else None
                if not act_id:
                    raise PpdmError("PPDM answered no activityId, nothing to wait for")
                done = client.await_activity(act_id, p["wait_timeout"])
                out["activity"] = done["activity"]
                if done.get("warnings"):
                    out["warnings"] = done["warnings"]
    except PpdmError as err:
        # messages raised here carry server text: scrub them (and the body) with the late-registered secrets
        fail_from(module, PpdmError(client.scrub_text(err.msg, 1000), err.status, client.scrub(err.body)))
    module.exit_json(changed=True, **out)


if __name__ == "__main__":
    main()
