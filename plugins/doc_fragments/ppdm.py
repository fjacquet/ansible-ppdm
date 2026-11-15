# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations


class ModuleDocFragment:
    # Keep in sync with connection_argument_spec() (checked by a unit test).
    DOCUMENTATION = r"""
options:
  hostname:
    description:
      - PPDM host name or IP address.
      - Falls back to the E(PPDM_HOSTNAME) environment variable.
    type: str
    required: true
  port:
    description:
      - PPDM REST API port.
      - Falls back to the E(PPDM_PORT) environment variable.
    type: int
    default: 8443
  username:
    description:
      - PPDM user name.
      - Falls back to the E(PPDM_USERNAME) environment variable.
    type: str
    required: true
  password:
    description:
      - PPDM password.
      - Falls back to the E(PPDM_PASSWORD) environment variable.
    type: str
    required: true
  validate_certs:
    description:
      - Verify the PPDM TLS certificate.
    type: bool
    default: true
  ca_path:
    description:
      - Path to a CA bundle used to verify the PPDM TLS certificate.
    type: path
  timeout:
    description:
      - HTTP timeout in seconds.
    type: int
    default: 30
"""
