# NS8 integration contracts — M14c

Updated 2026-10-10. [integration-lock.json](../integration-lock.json) pins
C1 `0.1.0rc2` at `d6d9f8614c8dfd52591ec1d2402438f7b6a626f7` and its published
linux/amd64 Docker archive. C1's public configuration contract is version 1;
its backup manifest is version 2. Upstream Gate A/B qualification covers the
released C1 interfaces, not this module's transport or site lifecycle.

## Runtime and identity

Use dedicated, digest-pinned TerminusDB, PostgreSQL and OpenFGA persistence.
The rootless pod maps the module user to C1 UID/GID 10001; backend containers
run as pod root. The app is read-only, drops capabilities, and mounts only its
private application state and configured CA. Only C1's loopback port is published.
Same-node IdP DNS uses the pod host gateway while retaining exact issuer hostname
and TLS verification. Never disable certificate verification to fix networking.

Retain instance ID, IRI base, issuer alias, exact issuer, provider UUID/domain,
API audience, backend identifiers and registration across retries/updates. A
changed namespace requires explicit migration; email and username are not identity.
Keep credentials in mode-0600 files under mode-0700 `AGENT_STATE_DIR/private`.
Never store secrets with `agent.set_env()` or include them in action results.

## Native IdP registration

Discover `oidc/http` providers, retain the selected UUID, and bind the selected
user domain before calling the provider's public `register-client` action.
The caller owns the client; do not pass `module_id` or use provider administrator
credentials in the module. Request the exact Explorer callback, logout callback,
web origin, retained API audience, and access-only `c1_principal_kind=human`.
Do not rotate its secret during normal reconciliation. The selected IdP must
support this claims contract and disable password, implicit and service-account
grants for the Explorer client. Successful registration does not prove login.

## Public C1 operations

`c1-admin application contract`, `oidc-check`, `initialize`,
`enrollment-approve`, `state` and `consistency` are invoked from the pinned
runtime. Initialization reuses durable owned resources. Startup checks the
image configuration digest, revision, public qualification and initialization
state. Pending setup is allowed; ordinary protected operations and readiness
stay guarded inside C1 until enrollment and consistency succeed.

An operator resolves the approved account's exact trusted issuer/subject and
records approval through the protected local CLI, with a bounded lifetime.
The approved user must authenticate and explicitly confirm in Explorer.
Only `access_admin` and `schema_admin` are initially granted. Provider roles,
first login, forwarded headers, username and email never grant C1 permissions.
For pending setup use `/explorer/login`; `/explorer/` is the ordinary guarded UI.
Browser flows use Code + S256 PKCE. ID tokens never authenticate API requests.

## Maintenance and recovery boundary

Backup hooks require completed enrollment, stop the C1 writer, check consistency,
dump OpenFGA PostgreSQL, cold-snapshot dedicated TerminusDB storage, and invoke
public `backup-manifest`. Include protected initialization/configuration and
registration continuity metadata. Exclude all external IdP databases, signing
keys and users. Local snapshots are secret-bearing and retained until an operator
applies their retention policy; native backup transport must encrypt them.

Native NS8 restore fails before Restic overwrites files: this transport has not
been qualified. Upstream recovery requires an isolated target, checksummed
artifacts, `restore-validate`, independent identity-namespace continuity evidence,
a fresh normal user access token, explicit snapshot acceptance, `dr-verify` and
`dr-release`, followed by live readiness. Never publish merely from a receipt or
silently restore grants as current. See upstream
[external-provider recovery](https://github.com/Stell0/c1/blob/v0.1.0rc2/docs/operations/external-oidc-recovery.md).

## Site qualification

Record actual module/core/IdP/runtime pins, executed native actions and real
browser/authorization/lifecycle/recovery results in [verification](verification.md).
The Makako IdP currently uses a development claims extension, not a released
NS8 provider contract. Do not claim production support from mocks or upstream
qualification alone. Agent-specific authentication is outside M14c's scope;
normal user API tokens remain attributed to the user and current C1 permissions.
