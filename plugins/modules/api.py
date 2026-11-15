#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: api
short_description: Call any PowerProtect Data Manager REST endpoint
description:
- Escape hatch for endpoints without a dedicated module.
- GET requests never change anything. Any other method always reports C(changed=true).
- In check mode non-GET requests are not sent (this includes POST-based queries), so C(result) and C(status)
  are null.
- I(body) is not masked, as with M(ansible.builtin.uri). Do not put secrets there that you do not want
  echoed in verbose output.
version_added: 1.0.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
options:
  method:
    description:
    - HTTP method.
    type: str
    choices:
    - GET
    - POST
    - PUT
    - PATCH
    - DELETE
    default: GET
  path:
    description:
    - Request path, must start with C(/api/), for example C(/api/v3/alerts).
    type: str
    required: true
  query:
    description:
    - Query string parameters.
    type: dict
  body:
    description:
    - JSON request body.
    type: dict
  all_pages:
    description:
    - For GET, fetch every page when the response is a paginated C(content)/C(page) envelope.
    - The result is then the concatenated C(content) list.
    - A caller-supplied C(page) or C(pageSize) in I(query) is overridden, and I(body) is ignored (a warning
      is issued).
    type: bool
    default: true
  wait:
    description:
    - When the response contains an C(activityId), wait for that activity to complete.
    - Fails unless the activity C(result.status) is C(OK) or C(OK_WITH_ERRORS) (the latter only warns).
    type: bool
    default: false
  wait_timeout:
    description:
    - Seconds to wait for the activity when I(wait=true).
    type: int
    default: 600
'''

EXAMPLES = r'''
- name: List all alerts
  fjacquet.ppdm.api:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    path: /api/v3/alerts

- name: Run a call and wait for its activity
  fjacquet.ppdm.api:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    method: POST
    path: /api/v3/activities/abc/interventions
    body: {}
    wait: true
'''

RETURN = r'''
status:
  description: HTTP status code of the response (null in check mode for non-GET).
  returned: always
  type: int
result:
  description: Parsed JSON response, or the concatenated C(content) list for paginated GETs.
  returned: always
  type: raw
skipped_write:
  description: True when a non-GET request was not sent because of check mode.
  returned: when check mode skipped a write
  type: bool
activity:
  description: Final activity when I(wait=true) and the response carried an C(activityId).
  returned: when waited
  type: dict
'''

ARGUMENT_SPEC = dict(
    method=dict(type='str', choices=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], default='GET'),
    path=dict(type='str', required=True),
    query=dict(type='dict'),
    body=dict(type='dict'),
    all_pages=dict(type='bool', default=True),
    wait=dict(type='bool', default=False),
    wait_timeout=dict(type='int', default=600),
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
)


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        supports_check_mode=True,
    )
    p = module.params
    method, path = p["method"], p["path"]
    if not path.startswith("/api/") or re.search(r"\.\.|%2e|[?#\s]", path, re.IGNORECASE):
        module.fail_json(
            msg="path must start with /api/ and contain no '..', '%2e', '?', '#' or whitespace "
            "(use the query option for parameters)"
        )
    if method != "GET" and module.check_mode:
        module.exit_json(changed=True, skipped_write=True, status=None, result=None)
    client = client_from_module(module)
    try:
        if method == "GET" and p["all_pages"]:
            if p["body"]:
                module.warn("body is ignored for a GET with all_pages=true")
            result = client.get_all(path, p["query"])
        else:
            result = client.request(method, path, query=p["query"], body=p["body"])
        out = dict(changed=method != "GET", status=client.last_status, result=result)
        # activityId is where the 20.3.0 OpenAPI carries it (ActivityInterventionResponse).
        activity_id = result.get("activityId") if isinstance(result, dict) else None
        if p["wait"] and not activity_id:
            module.warn("wait=true but the response has no activityId, nothing to wait for")
        if p["wait"] and activity_id:
            activity = client.wait_activity(activity_id, p["wait_timeout"])
            out["activity"] = activity
            status = (activity.get("result") or {}).get("status")
            if status == "OK_WITH_ERRORS":
                module.warn("activity %s completed with errors" % activity_id)
            elif status != "OK":
                module.fail_json(
                    msg="activity %s finished with status %s" % (activity_id, status),
                    **out,
                )
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(**out)


if __name__ == "__main__":
    main()
