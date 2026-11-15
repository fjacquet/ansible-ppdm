# Security audit: fjacquet.ppdm, branch feat/lot1-foundation @ 7699dcc

Date: 2026-11-15. Read-only. The repo was not modified (`git status --short` is empty before and after; HEAD is still 7699dcc). All PoC scripts and build output live in the session scratchpad
(`/private/tmp/claude-501/-Users-fjacquet-Projects-ansible-ppdm/83d0e71b-878a-49b1-83b3-483968f10517/scratchpad/poc/`).

Threat model used for severity: the playbook author is trusted and already holds the admin credentials. PPDM, any reverse proxy or load balancer in front of it, and the network path are only semi-trusted. Repo contents (schemas, OpenAPI) can be changed by contributors through PRs.

## Summary

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 0 |
| Medium | 3 |
| Low | 6 |
| Info | 8 |

## Tools run

| Tool | Result |
|---|---|
| `security-review` skill | Invoked. It failed at preflight: `git log origin/HEAD...` reported "unknown revision", because the repo has no remote. The ref was not created to work around this, since the repo is read-only. The equivalent review of `git diff main...HEAD` was done by hand (this document). |
| `uv run ruff check --select S --no-cache` (ruff 0.17.5, the project pin) | `plugins tools roles`: no issues. The whole tree gives 240 hits: 229 are S101 in tests (allowed). The other 11 are S105/S106 on test fixtures (`"s3cret"`, `"pw-secret"`, `update_password="always"`), all false positives. There is also S307 `eval` at `tests/unit/tools/test_generate_docs.py:39`: a false positive, because it evaluates the generator's own output with `{"dict": dict}` globals and is test-only. (The first run through `uvx` used ruff 0.12.11 and gave the same results.) |
| `osv-scanner scan -L uv.lock` (2.7.1) | 61 packages, "No issues found". |
| `uvx pip-audit -r <uv export --all-groups>` | 61 pinned requirements (ansible-core 2.22.0/2.21.6, cryptography 50.0.2, jinja2 3.1.6, pyyaml 6.0.3), "No known vulnerabilities found". Run with `--no-deps --disable-pip`. |
| `gitleaks detect --redact` (8.30.1) | Git history: 30 commits, no leaks. `--no-git` working tree: no leaks. |
| Manual grep (emails, JWT, private keys, RFC1918 IPs, `/Users/`, `.local/.corp`, default passwords) | See findings L4 and I8. No real secrets or internal IPs found. |
| `ansible-galaxy collection build` into the scratchpad | Contents listed. See L4. |
| Dynamic PoCs (`poc_client.py`, `poc_redirect.py`, `poc_api_gen.py`, `poc_misc.py`) | Outputs are quoted below. |

---

## Medium

### M1. The Bearer token follows redirects to any host and scheme, including plain HTTP (CWE-200 / CWE-319)
- **Where:** `plugins/module_utils/ppdm.py:96-104`. `open_url` is called without `follow_redirects`, so it keeps its default `'urllib2'`, which is the stdlib `HTTPRedirectHandler.redirect_request`. That handler copies every header except Content-Length and Content-Type into the new request, `Authorization` included, and does not check the host or the scheme.
- **What leaks, from the stdlib source read in the .venv (Python 3.13):**
  - GET/HEAD: any 301/302/303/307/308 is followed with the token.
  - POST after login (credential/inventory create, `api` POST): a 301/302/303 is turned into a GET that keeps the headers, so the token leaks.
  - POST 307/308 is not followed (HTTPError).
  - PUT/PATCH/DELETE redirects are not followed.
  - The login **password** is not forwarded. The login POST has no token yet, the body is dropped on 301-303, and 307/308 raise.
  - `validate_certs=true` does not help when the redirect goes to an attacker-owned host with a valid public certificate, or to `http://`.
- **Exploit:** a misconfigured or compromised reverse proxy or load balancer in front of PPDM (or a PPDM endpoint that redirects) answers `302 Location: http://attacker/...`. The next module GET sends `Authorization: Bearer <admin JWT>` in cleartext to the attacker, who can then replay it against PPDM until it expires. A side effect: a POST answered with 302 is turned into a GET, and its response is treated as the create result.
- **Proof** (`poc_redirect.py`): a real local HTTPS "PPDM" with a self-signed CA passed as `ca_path`, `validate_certs=True`, returns 302 to a plain-HTTP listener:
  ```
  result: []
  attacker (plain http) received Authorization: ['Bearer SECRET-JWT-TOKEN']
  ```
- **Fix:** in `request()`, pass `follow_redirects="none"` to the opener. A 3xx then becomes HTTPError, and the existing code turns that into a clean `PpdmError` with the status. Add a unit test that checks the opener kwargs. (The alternative `unredirected_headers=["Authorization"]` still follows redirects to foreign hosts, so it is weaker.)

### M2. `find_one` trusts the server-side filter, so `ensure`/`remove` can PUT or DELETE a different object (CWE-20 / CWE-639: integrity)
- **Where:** `plugins/module_utils/ppdm.py:174-179`. The result of `filter=name eq "..."` is used as is: there is no client-side check that `o[key] == value`. `ensure` (l.204, 231) PUTs to `existing["id"]`, and `remove` (l.243-248) DELETEs `existing["id"]`.
- **Precondition:** the server ignores or loosens the filter. Possible causes:
  - unsupported field or escape syntax silently ignored;
  - case-insensitive or `lk`-like matching;
  - a proxy dropping the query string;
  - the `filter_eq` escaping not matching PPDM's grammar.

  The OpenAPI does not document filter escaping, which the code itself admits at l.30. Example: `filter_eq('name', 'x" or name ne "')` produces `name eq "x\" or name ne \""`. If PPDM does not honour `\"`, the extra clause escapes the string.
- **Exploit:** a playbook ensures the credential `dd-lab`. PPDM returns exactly one object, the unrelated `vcenter-prod`. The module renames it, overwrites its username, and writes the new password into it. With `state: absent` it deletes the wrong object. Neither case raises an error.
- **Proof** (`poc_client.py` section 4):
  ```
  GET https://h:8443/api/v2/credentials?filter=name%20eq%20%22dd-lab%22&page=1&pageSize=100 None
  PUT https://h:8443/api/v2/credentials/cred-OTHER {"id": "cred-OTHER", "name": "dd-lab", "type": "DATADOMAIN", "username": "sysadmin", "password": "newpw"}
  ```
- **Fix:** in `find_one`, add `found = [o for o in found if o.get(key) == value]` before the count check. This is one line and protects `ensure`, `remove` and `storage_system`'s existence check. `info_main` with `name` should apply the same post-filter.

### M3. Bootstrap failure message can print initial-configuration secrets echoed by PPDM (CWE-532)
- **Where:**
  - `roles/bootstrap/tasks/main.yml`, "Fail when the configuration was refused", prints `__bootstrap_put.msg`.
  - That msg is built at `ppdm.py:116-118` from the server's `message`.
  - `_scrub` only removes the **login** password.
  - Ansible's `remove_values` only masks the `api` module's no_log params. `body` is not no_log, which is documented.

  The PUT task itself is `no_log`, but the following `fail` task is not.
- **Precondition:** PPDM (Spring-style validation) echoes a rejected value in `message`. This is unverified on a live 20.3.0. The body carries `osUsers[].newPassword/password`, `lockbox.passphrase/newPassphrase` and `applicationUserPassword` (from the OpenAPI `SystemConfiguration` schema).
- **Proof** (`poc_misc.py`, after applying Ansible's own `remove_values` with the module's no_log values):
  ```
  api module msg after Ansible no_log masking: PUT /api/v2/configurations/1 failed: HTTP 400: osUsers[0].newPassword 'Lockb0x-New!' violates the password policy
  ```
- **Fix:** print only `status` in the role's fail message. Alternatively, collect the string leaves of `bootstrap_configuration` whose key matches `pass|secret|phrase|key` and replace them in the message. Or add `no_log: true` to that fail task and keep the HTTP status in a separate non-secret `debug`.

## Low

### L1. `_scrub` corrupts JSON for short or JSON-structural passwords and crashes the module on every error path (CWE-755)
- **Where:** `ppdm.py:70-77`. The replacement runs on the serialized JSON **text**, so a password equal to a structural token, number, literal or key fragment breaks the JSON, and `json.loads` raises `JSONDecodeError`. That exception is raised inside the `except HTTPError` handler, so it escapes `request()`. Every module then dies with a traceback instead of `fail_json`. `info_main`'s 404 handling also crashes instead of returning `[]`. The URLError branch crashes the same way for a password of `"`.
- **Leak check:** the traceback does not contain the password. The JSONDecodeError message is positional only, and the chained HTTPError/StopIteration have no body. This matters because an uncaught traceback bypasses Ansible's no_log masking. Note also that a password such as `a` breaks the key `message`, so `detail` disappears.
- **Proof** (`poc_client.py` section 1, `poc_misc.py`):
  ```
  pw='a'   -> UNCAUGHT JSONDecodeError: Expecting value: line 1 column 106 (char 105)
  pw='e'   -> UNCAUGHT JSONDecodeError: Expecting value: line 1 column 99 (char 98)
  pw='"'   -> UNCAUGHT JSONDecodeError: Expecting property name enclosed in double quotes ...
  pw=':'   -> UNCAUGHT JSONDecodeError: Expecting ':' delimiter ...
  pw='401' -> UNCAUGHT JSONDecodeError: Expecting value: line 1 column 10 (char 9)
  pw='\\' / 'null' / 's3cret' / 'péss' -> PpdmError ... ******** leak=False
  1b (URLError, pw='"'): UNCAUGHT JSONDecodeError: Expecting value: line 1 column 1 (char 0)
  ```
  A numeric password that also appears as a JSON number (status code, timestamp) is a realistic trigger.
- **Fix:** walk the parsed structure (dict, list, str) and run `str.replace(secret, "********")` on string leaves (and keys) only, for `{password, token}`. There is no need for a JSON-escaped variant once you work on the decoded strings.

### L2. The access token is not scrubbed from error text (CWE-532)
- **Where:** `ppdm.py:70-77`. `_scrub` covers only `self.password`. The token is not a module param, so Ansible's no_log does not mask it either.
- **Exploit:** a gateway or PPDM error that echoes request headers puts the admin JWT into `msg`/`body`. These end up in the task output, `-v` logs, AWX job output, and callback plugins.
- **Proof** (`poc_client.py` section 2): `token in msg: True | msg: GET /api/v2/x failed: HTTP 400: bad request, headers: Authorization=Bearer eyJhbGciOiJIUzI1NiJ9.FAKE.FAKE`
- **Fix:** add `self.token` to the scrubbed set (with L1's structural walk).

### L3. Unbounded pagination and response handling against a hostile or buggy server (CWE-400 / CWE-835)
- **Where:** `ppdm.py:138-158` (no page cap; `totalPages` trusted, type not checked), `ppdm.py:105` (`resp.read()` with no size limit), `ppdm.py:127` (`json.loads` accepts `NaN` and deep nesting).
- **Precondition:** a hostile or buggy server or proxy.
- **Proof** (`poc_client.py` section 3):
  ```
  3a totalPages=NaN, empty pages: still looping after 5000 requests: no page cap   (infinite loop)
  3b totalPages=1e9, 1 item/page: still looping after 5000 requests                 (unbounded memory/time)
  3c totalPages="5":  UNCAUGHT TypeError: '>=' not supported between instances of 'int' and 'str'
  3d [[[[...]]]] x100000: UNCAUGHT RecursionError
  ```
  Also, a non-list `content` (a string or dict) is `extend`ed character by character or key by key.
- **Fix:**
  - Require `isinstance(total, int)` and `isinstance(content, list)`.
  - Stop when `page > total` or when a page comes back empty.
  - Cap the number of pages, for example at `10000` (that is 1M items at pageSize 100), and raise `PpdmError` beyond it.
  - Catch `RecursionError` next to `ValueError` at l.128.
  - Optionally use `resp.read(limit)`.

### L4. The Galaxy tarball ships local paths and dev files (CWE-538, PII)
- **Where:** `galaxy.yml` `build_ignore`. `ansible-galaxy build` does not honour `.gitignore`. The test build, from the working tree, shipped:
  - `.ruff_cache/` (pre-existing: created at 11:40 and 11:51, not by this audit, which ran with `--no-cache`). Its binary entries contain absolute paths such as `<repo>/plugins/...` and `docs/superpowers/specs/...`.
  - `CLAUDE.md`, which contains `~/Projects/ansible-ppdm`.
  - `uv.lock`, `pyproject.toml`, `.pre-commit-config.yaml`.
  - `tests/unit/tools/*`, which import the excluded `tools/` package and so break in the artifact.

  `__pycache__`/`.pyc` are excluded by the defaults, and `.venv`, `.pytest_cache`, `.superpowers`, `docs/superpowers` and `docs/openapi` are excluded as intended. The MANIFEST.json grep hit is only the public `repository`/`issues` GitHub URL, which is fine.
- **Proof:** `tar tzf fjacquet-ppdm-0.1.0.tar.gz` lists `.ruff_cache/0.17.5/...`. `strings` on those files shows `<repo>/...`.
- **Fix:** add `.ruff_cache`, `CLAUDE.md`, `uv.lock`, `pyproject.toml`, `.pre-commit-config.yaml` and `tests/unit/tools` to `build_ignore`. Add `.ruff_cache/` to `.gitignore`. Build releases only from a clean CI checkout (`git clean -xdf` or a fresh clone). Extend the existing "tarball must not contain" check to `.ruff_cache` and `CLAUDE.md`.

### L5. Pre-commit supply chain: mutable refs and unpinned npm dependencies (CWE-1357 / CWE-829)
- **Where:** `.pre-commit-config.yaml`.
  - Every `rev:` is a tag (`1.1.1`, `v4.4.0`, `v3.0.0`, `"v3.0.0"`, `v0.17.5`), not a commit SHA.
  - `pre-commit/mirrors-prettier` is archived upstream.
  - `additional_dependencies: [prettier, prettier-plugin-toml]` has no versions, so each fresh install runs whatever npm "latest" is at that moment, inside a `bash -c` entry.
  - `ansible-network/collection_prep` (`update-docs`) runs code on every commit.
- **Exploit:** a compromised npm release of `prettier`/`prettier-plugin-toml`, or a re-tagged hook repo, runs on the maintainer's workstation, which holds the Galaxy token and the SSH keys.
- **Fix:** run `pre-commit autoupdate --freeze` (SHA pins with a tag comment), pin `prettier@x.y.z` and `prettier-plugin-toml@x.y.z`, and replace or remove `mirrors-prettier`.
- **No GitHub Actions exist yet** (`.github/` is absent), so there are no workflows to pin. The spec plans a publish-on-tag job with `ANSIBLE_GALAXY_API_KEY`. When it is added, pin actions by SHA, give it `permissions: contents: read`, run it only on tags in a protected environment, and never on `pull_request_target`.

### L6. `certificate`: unquoted server-supplied id in PUT/DELETE, and a trust-store write before the pin check (CWE-22 / CWE-367)
- **Where:**
  - `plugins/modules/certificate.py:191` and `:213` build `"%s/%s" % (PATH, cert["id"])` directly. This bypasses `_route`'s `quote(..., safe="")`. An `id` such as `../credentials/X` or `x?y=` coming from PPDM or a proxy makes the module PUT/DELETE another path, with PUT's body being the certificate.
  - The real `present` run does the GET **without** `nocache` (l.164-167). Per the API, that already stores the remote certificate in the trust store (as non-ACCEPTED) **before** the pin is compared. On a pin mismatch the module fails but leaves an entry behind. This is documented as "intended", but it is a residual.
  - GET→PUT TOCTOU: the module verifies the server-reported `fingerprint`, then PUTs `dict(cert, state="ACCEPTED")` by id. Whether PPDM trusts the body's `certificateChain`/`fingerprint` or whatever it holds under that id at PUT time is not verifiable without a lab.
- **Fix:**
  - Use `quote(str(cert["id"]), safe="")`, or add a `certificates` route through `_route`.
  - After the PUT/POST, check that the returned `fingerprint` (if present) still equals the pin, and fail loudly otherwise.
  - Optionally compute SHA-1/SHA-256 of the DER in `certificateChain` locally (`ssl.PEM_cert_to_DER_cert` + `hashlib`) and compare it with the pin, so the module does not depend on PPDM's own report.
  - Optionally clean up the cached entry when the pin mismatches.

## Info

- **I1. The `api` path gate is a footgun guard, not a security boundary** (`plugins/modules/api.py:137`). The author already has admin credentials. `poc_api_gen.py` shows these paths are accepted:
  - `/api/%252e%252e/%252e%252e/actuator` (double encoding)
  - `/api/．．/x` (U+FF0E)
  - `/api/.․/x` (U+2024)
  - `/api/v2/%2f%2f`, `/api//evil`
  - `/api/v2/x%00.json`
  - `/api/v2/x;jsessionid=1`
  - `/api/v2/x%23frag`, `/api/v2/x%3fq=1`

  These are rejected: literal `..`, `%2e`, `\..\`. A literal NUL passes the gate but `http.client` refuses it (InvalidURL is a ValueError, which the code catches). The host cannot change, because the path is appended to the fixed `base_url`, so `//`/`@` are harmless. If the gate is meant seriously: reject `%25`, `%2f`, `%5c`, `%00`, `;` and any non-ASCII character, and allow only `^/api/v\d+/[A-Za-z0-9._~/{}-]+$` plus `%XX` that is not one of `2e/2f/5c/25/00`.
- **I2. `hostname` is not validated** (`ppdm.py:59`). `ppdm.example.com@evil.example` produces `https://ppdm.example.com@evil.example:8443/...` (it connects to evil.example). `evil.example:443/x#` overrides the port. A bare IPv6 address is not bracketed. The input is author-controlled (a var or `PPDM_HOSTNAME`), so the risk is low. A typo or a templated value from an untrusted inventory source could still send the password to another host. Fix: reject `/ @ ? # \` and whitespace, and bracket IPv6 addresses (`ipaddress.ip_address`).
- **I3. Generator: option names are interpolated raw into Python source** (`tools/generate.py:135, 140`). `poc_api_gen.py`: an option key like `x=dict(type='str'), **{__import__('os').system('echo INJECTED-CODE-RAN') ...}, y` generated `ARGUMENT_SPEC = dict(x=dict(type='str'), **{__import__('os').system(...)...}, y=dict(type='str'),)`, and executing it printed `INJECTED-CODE-RAN`. The schemas are repo-controlled and the output is committed and reviewable, so this matters for a malicious PR that hides code in a generated block. Fix: in `validate_schema`, require `name.isidentifier() and not keyword.iskeyword(name)`.
  - Everything else in the generator is safe: values use `repr()`, the `'''` check protects the r-strings (texts always end in `\n`, so no trailing `\` before the closing quote), `yaml.safe_load` and `json.loads` are used, and the target path is `modules_dir/<module>.py` with `module == path.stem` enforced, so there is no traversal.
  - Residual: a cyclic `$ref` in an OpenAPI file loops forever in `_resolve` (l.31). This is a dev tool, so it only means a DoS of that tool.
- **I4. `api` results are returned verbatim.** A `GET` in check mode is still sent. Some GETs have side effects: `GET /api/v2/certificates` without `nocache` writes the trust store. A POST to `/api/v2/login` (or any token endpoint) returns `access_token` unmasked in `result`. Consider documenting both points, and masking `access_token`/`refresh_token` keys in `result`.
- **I5. Secret masking is top-level only** (`_mask`, `info_main` `secret_fields`). Credential `extraInfo` and nested objects are not masked. This is already ledgered and is not worse than reported. The OpenAPI `Credential` has `secretId` (a lockbox pointer, not a secret) and `password` at the top level only.
- **I6. `certificate` does not send `strict=true`.** The API's `strict` parameter checks that the host is in the certificate's SAN. With `accept_any_certificate=true` (an opt-in, ledgered), a certificate for any name is accepted. With a pin, this does not matter. The fingerprint hash algorithm reported by PPDM (SHA-1 vs SHA-256) is not documented in the OpenAPI. If it is SHA-1, consider recommending a local SHA-256 check (see L6).
- **I7. Bootstrap readiness task output.** `register: __bootstrap_configurations` (not no_log) holds the full `GET /api/v2/configurations` object, which is printed at `-v`. Whether PPDM returns `osUsers[].password`, `lockbox.passphrase` or `applicationUserPassword` populated or masked is unverified. Check this on the lab. If they are populated, set `no_log: true` on that task and expose only `status`/`id`/`gettingStartedCompleted` via `set_fact`.
- **I8. PII:** the author's email `fred@ljf.ch` appears only in `galaxy.yml` `authors` (intended) and in the git author metadata of all 30 commits (public once pushed: this is the author's choice; GitHub's noreply address is an alternative). `docs/superpowers/plans/...:57` contains `<csm-powerscale-demo>/...`. It is not shipped in the tarball (build_ignore), but it is public on GitHub. Test fixtures use dummy secrets only. There are no factory default passwords, RFC1918 IPs, internal hostnames, private keys or JWTs in tracked files outside `docs/openapi` (gitleaks covered `docs/openapi`, which came back clean).

## Checked and safe

| Area | How verified | Verdict |
|---|---|---|
| Token never in module output | Read `ppdm.py`. `self.token` is used only in the header (l.94-95). No module returns the client, headers or token. `fail_from` sends only msg/status/body. | Safe (except echo cases, see L2, and redirects, see M1). |
| Token or password in `__context__` or tracebacks | `PpdmError` is raised `from None`, caught in every module and converted to `fail_json`. The uncaught L1/L3 tracebacks were inspected: they hold only positional or type messages. | Safe. |
| Login password in `invocation`/output | `password` has `no_log=True` (`ppdm.py:288`), so Ansible's `remove_values` masks it everywhere, even a 1-char `a` (`poc_misc.py`: `'b********d login for ********dmin: ********'`). `_scrub` adds defence in depth for PpdmError text. | Safe. |
| Password with escaping / non-ASCII | `poc_client.py`: `\`, `null`, `s3cret`, `péss` are scrubbed, `leak=False` (a JSON-escaped variant is matched). | Safe (crash cases in L1). |
| TLS | `validate_certs` defaults to `True` in the argspec (l.292), the client (l.53) and the bootstrap role (`defaults/main.yml`, argument_specs). `ca_path` is passed through. A grep for `validate_certs=False`, `CERT_NONE` and `check_hostname` in plugins/roles found nothing. No code path downgrades to http (`base_url` is always `https://`). | Safe. |
| Query construction | `urlencode(query, quote_via=quote)` encodes `&`, `=`, `#` and spaces. Users cannot inject a raw query except through `api.query` (by design). `filter_eq` escapes `\` and `"`. The key is code-controlled. | Safe on the client side. Server semantics are in M2. |
| `_route` id quoting | `quote(str(obj_id), safe="")` encodes `/`, `?`, `#` and `..` segments. An empty id is rejected. | Safe (except the certificate module, see L6). |
| `eula` path | `"/api/v2/eulas/" + name`, where `name` has choices `PPDM`/`TELEMETRY`/`data-manager`. | Safe. |
| `api` method/body/wait | `method` has a choice list. Non-GET calls in check mode exit before login. `wait_activity` is bounded by `wait_timeout`, `interval > 0` is enforced, and the activity id is quoted via `_route`. A non-OK status fails. | Safe. |
| Certificate trust gate | `present` without a pin and without `accept_any_certificate` fails before login. The pin must be hex and match exactly after stripping `:` and whitespace: no prefix or partial match. With a pin, an already ACCEPTED certificate with a different fingerprint fails. `accept_any` accepts only `UNKNOWN` and warns. More than one match fails. `absent` deletes only ACCEPTED entries and uses `nocache`. Check mode uses `nocache` and does not write. | Safe (residuals in L6). |
| `credential` secrets | `cred_password` is `no_log`. `update_password` is a choice param (not a secret; the `no_log` heuristic warning is not suppressed, so no masking side effect). `diff`/`object` mask `password` via `_mask`. A server echo of `cred_password` in errors is masked by Ansible's no_log. `credential_info` strips `password`. `update_secrets` semantics match the docs (`on_create` sends the password only when another field changes, `always` forces). | Safe. |
| `inventory_source`/`storage_system` `config` | Not masked: ledgered, and not worse than reported. | Known. |
| Bootstrap role | `bootstrap_password` is `no_log` in argument_specs and is passed through `module_defaults` into a `no_log` module param. `set_fact` of the body and the PUT are `no_log`. Default `validate_certs: true`. EULA acceptance is opt-in (`false`). Retries are bounded (`timeout/delay`, at least 1, both validated > 0). Check mode skips the PUT and the status poll. The example playbook takes the password from the environment. No `debug` of secrets. | Safe (except M3 and I7). |
| Python-level | Grep for `eval`/`exec`/`pickle`/`subprocess`/`os.system`/`shell=True`/`tempfile`/`chmod`/`logging`/`module.log`/`module.debug` in plugins/roles/tools: none (ruff S rules are clean). `module.warn` texts contain only activity ids and static strings. | Safe. |
| Generator I/O | `yaml.safe_load`, `json.loads`, `repr()` for values, the `'''` guard, the output path pinned to `modules_dir/<stem>.py`. | Safe (except option names, see I3). |
| Dependencies | osv-scanner and pip-audit are clean. The collection has no runtime dependencies beyond ansible-core (`dependencies: {}`, `[project] dependencies = []`). | Safe. |
| Secrets in git | gitleaks on 30 commits and the working tree: clean. | Safe. |
