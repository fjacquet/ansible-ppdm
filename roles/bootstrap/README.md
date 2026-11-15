# fjacquet.ppdm.bootstrap

Brings a freshly deployed PowerProtect Data Manager 20.3.0 to a configured state: waits for the REST API, optionally accepts the EULA, applies the initial configuration and waits for it to finish. Orchestration only, all work is done by `fjacquet.ppdm.api` and `fjacquet.ppdm.eula`. The port 14443 upgrade flow is out of scope.

## Variables

| Variable | Default | Description |
|---|---|---|
| `bootstrap_hostname` | required | PPDM host. |
| `bootstrap_username` | required | PPDM user. |
| `bootstrap_password` | required (`no_log`) | PPDM password, supplied by you. |
| `bootstrap_port` | `8443` | REST port. |
| `bootstrap_validate_certs` | `true` | Validate the TLS certificate. |
| `bootstrap_ca_path` | unset | CA bundle. |
| `bootstrap_wait_timeout` | `3000` | Seconds to wait for the API, and again for the configuration. |
| `bootstrap_wait_delay` | `30` | Seconds between attempts. |
| `bootstrap_eula_accept` | `false` | Accept the PPDM EULA (must be explicit). |
| `bootstrap_configuration` | unset | SystemConfiguration fields merged over the current configuration and sent with `PUT /api/v2/configurations/{id}`. |

## Tags

`bootstrap_wait`, `bootstrap_eula` and `bootstrap_config` select a stage. The readiness poll provides the configuration the later stages read, so it runs with every one of these tags.

`bootstrap_configuration` may contain passwords (for example `osUsers`). It is not `no_log` in `argument_specs` because that would hide the whole dictionary from validation errors and output; the tasks that handle it are `no_log` instead. Source it from Ansible Vault and do not print it.

## Example

See `docs/examples/bootstrap.yml`. Certificates are not handled by the role; call `fjacquet.ppdm.certificate` yourself afterwards:

```yaml
- name: Trust the PPDM certificate
  fjacquet.ppdm.certificate:
    hostname: ppdm.example.com
    username: admin
    password: "{{ lookup('ansible.builtin.env', 'PPDM_PASSWORD') }}"
    # see the module documentation for the remaining options
```

## Idempotency

Re-runs are safe: the EULA module only patches when not accepted, and the configuration PUT is skipped when `gettingStartedCompleted` is already `true` (PPDM allows the initial configuration only once). The readiness and status polls are read-only. Check mode: the readiness poll and EULA module run (the latter per its own check mode), the PUT is skipped by the `api` module and the status poll is skipped.

The PUT body is the GET configuration (without `_links`) with `bootstrap_configuration` merged over it: dictionaries merge recursively, lists (`ntpServers`, `networks`, ...) are replaced, not merged. Other read-only fields are sent back as GET returned them (unverified against a live PPDM, which may reject them).

Failures: a 401/403 at readiness fails immediately; a refused connection retries until `bootstrap_wait_timeout`. The PUT task is `no_log`; its failure message shows only the HTTP status and a fixed text (the response is hidden because PPDM may echo initial passwords in it; see the PPDM logs). The readiness and configuration-status polls are `no_log` too (they read the system configuration, which may contain secrets), and the configuration-failed message prints the status only, never the status message.

## Testing

Needs a live PPDM; not covered by Molecule.
