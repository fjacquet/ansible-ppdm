#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: copy_info
short_description: Get copies (backups) from PowerProtect Data Manager
description:
- Read-only query of copies. Never changes anything.
- Exactly one of I(id), I(asset_id) or I(latest_asset_ids) selects what to read.
- With I(asset_id), returns every copy of that asset, all pages.
- With I(latest_asset_ids), returns the latest copies of those assets in one request.
version_added: 0.4.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- Reading a copy by I(id) uses an endpoint that is restricted to the Administrator role.
options:
  id:
    description:
    - Return only the copy with this ID. An empty answer gives an empty list; PPDM documents no 404 for
      an unknown ID, so it may fail with a 400 or 500 error instead. Mutually exclusive with I(asset_id)
      and I(latest_asset_ids).
    type: str
  asset_id:
    description:
    - Return the copies of the asset with this ID. Mutually exclusive with I(id) and I(latest_asset_ids).
    type: str
  latest_asset_ids:
    description:
    - Return the latest copy of each of these asset IDs. Must not be empty. Mutually exclusive with I(id)
      and I(asset_id).
    type: list
    elements: str
  filter:
    description:
    - PPDM filter string, ANDed (in parentheses) with the asset selection. Only valid with I(asset_id)
      or I(latest_asset_ids). It is passed to PPDM unchanged and its result is not re-checked.
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
- name: Copies of an asset
  fjacquet.ppdm.copy_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    asset_id: "{{ asset_id }}"
  register: result

- name: Latest copy of two assets
  fjacquet.ppdm.copy_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    latest_asset_ids:
      - "{{ asset_a }}"
      - "{{ asset_b }}"
'''

RETURN = r'''
copies:
  description: Matching copies, an empty list when nothing matches.
  returned: always
  type: list
  elements: dict
  sample: [{"id": "c1", "assetId": "a1", "state": "ACTIVE"}]
'''

ARGUMENT_SPEC = dict(
    id=dict(type='str'),
    asset_id=dict(type='str'),
    latest_asset_ids=dict(type='list', elements='str'),
    filter=dict(type='str'),
)
# fmt: on
# END GENERATED

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (
    PpdmError,
    client_from_module,
    connection_argument_spec,
    fail_from,
    filter_quote,
    quote_id,
)

LATEST_CHUNK = 50


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        supports_check_mode=True,
        mutually_exclusive=[("id", "asset_id", "latest_asset_ids")],
        required_one_of=[("id", "asset_id", "latest_asset_ids")],
    )
    p = module.params
    if p["filter"] is not None and p["id"] is not None:
        module.fail_json(msg="filter requires asset_id or latest_asset_ids")
    if p["latest_asset_ids"] is not None and not p["latest_asset_ids"]:
        module.fail_json(msg="latest_asset_ids must not be empty")
    client = client_from_module(module)
    try:
        if p["id"] is not None:
            try:
                body = client.request("GET", "/api/v3/copies/%s" % quote_id(p["id"]))
            except PpdmError as err:
                if err.status != 404:
                    raise
                body = None
            if body is not None and not isinstance(body, dict):
                raise PpdmError("GET copies/%s failed: unexpected response" % p["id"])
            copies = [] if body is None else [body]
        elif p["asset_id"] is not None:
            copies = client.get_all(
                "/api/v2/assets/%s/copies" % quote_id(p["asset_id"]),
                query={"filter": p["filter"]} if p["filter"] else None,
            )
        else:
            copies = []
            ids = list(dict.fromkeys(p["latest_asset_ids"]))
            # the spec gives latest-copies a filter only, no paging: bound each request by chunking the ids
            for start in range(0, len(ids), LATEST_CHUNK):
                flt = "assetId in (%s)" % ", ".join(filter_quote(i) for i in ids[start : start + LATEST_CHUNK])
                if p["filter"]:
                    flt += " and (%s)" % p["filter"]
                body = client.request("GET", "/api/v2/latest-copies", query={"filter": flt})
                if not isinstance(body, dict) or not isinstance(body.get("content"), list):
                    raise PpdmError("GET latest-copies failed: unexpected response")
                copies += body["content"]
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=False, copies=copies)


if __name__ == "__main__":
    main()
