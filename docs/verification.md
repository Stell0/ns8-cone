# Verification — account acceptance and CI deployment, 2026-10-10

The owner requested `foo1` as C1 administrator, `foo2` as a normal user,
automated acceptance, fixes, commit/push, successful CI, deployment of its
artifact, and repetition of all checks. The owner explicitly authorized a
reset. The previous instance metadata/snapshot and backend resources were
retained; a fresh instance was initialized with new identity/database/store
identifiers. This is an explicit reset, not a silent configuration migration.

`foo1` was approved by exact OIDC issuer/subject and confirmed through the normal
Explorer setup flow. A wrong `foo2` login was rejected during pending enrollment.
Both existing LDAP accounts authenticate with the supplied password; their
profiles and groups were preserved. Passwords and tokens are absent from source,
evidence, CI and commit messages.

| Check | Result | Evidence / limitation |
| --- | --- | --- |
| C1 local `make check` | PASS | 1,081 tests passed, 168 service-dependent checks skipped; Ruff, strict mypy, secret, baseline, profiles, OpenAPI and license checks pass |
| NS8 module unit tests | PASS, 23 tests | File/namespace safety, image pin, readiness, sanitized failures, bounded idempotent registration retry and restore refusal |
| UI settings tests | PASS, 3 tests | Saved selections, round-trip settings and discovery failure |
| UI lint/build | PASS | Lint now targets `src`; production build retains vendor-size warnings |
| Foo account enrollment | PASS | Exact approved `foo1`; incorrect first `foo2` login rejected; explicit authenticated confirmation; two initial instance roles only |
| Live account/API/Explorer suite | PASS, 19 checks after fresh-volume recovery | `tests/integration/live_oidc.py`; real TLS Code + S256; both accounts; all six Explorer pages, reviewed create/modify, self-review denial, attribution, idempotency and immediate revocation |
| CI and deployment | PASS | Local checks, publishing and all six real lifecycle cases on both Debian 13 and Rocky 9; immutable `dbbca92f856793fbbeff430b7c4c7ef29599c006` deployed through native `update-module` |
| Native encrypted backup and fresh persistence restore | PASS, same instance | Native backup job 8, Restic full data check, encrypted transport extraction, corruption refusal, interrupted import and retry, nine guarded-recovery/release checks; original volumes retained |
| Complete pod restart | PASS | Starting the enabled application unit pulled up required backends; restored volume references and real readiness preserved |
| Shared node reboot | NOT_RUN | A service/pod restart is not a reboot; the shared node was not rebooted |

The live suite uses protected operator-supplied credential files and server-side
client configuration inside the released image. Its HTTP form checks do not
claim JavaScript/browser-engine automation. Actual Explorer browser navigation
was confirmed by the owner earlier. Checks cover ID-token rejection, invalid
PKCE, unsupported grants, refresh, CSRF, secure headers, local logout, normal
administration denial, scope permissions, separately reviewed ChangeSets,
attribution, idempotent apply, context and immediate revocation.

The first fixture used an unsupported canonical identifier; C1 correctly rejected
it. The fixture now uses the documented UUIDv4 suffix. Draft creation is not a
knowledge commit: unauthorized publication is tested at submission/validation.
The logout fixture now sends Origin/CSRF and expects the documented local signed-out
page, without weakening application checks.

The adapter avoids re-binding an unchanged domain and retries only transient
native registration exits, at most three attempts. Validation/ownership refusals
remain final, and client secrets are not rotated during retry. This addresses the
observed Keycloak federation/update race. The direct readiness probe remains
bounded at 15 seconds; the original 3-second probe was shorter than measured
valid readiness execution.

## Reproducible site evidence and limits

[Sanitized acceptance evidence](evidence/makako-account-recovery.json) records
account roles, source/runtime pins and executed checks. The deployment uses C1
`v0.1.0rc2` at `d6d9f8614c8dfd52591ec1d2402438f7b6a626f7`; its configuration
digest is `d3d2f8c47461865dfecda5f4b9c27eb5d07c1de0d6c7f52b135a2fb750738127`.
The module OCI archive checksum is
`91dafa6edd8ef6d6da9a2c715636695613dc402b356263ce9822e088caf54b42`.
Backend digests and declared versions are in `integration-lock.json`; this site
uses the NS8 IdP development claim extension `3e801d22` and Keycloak 26.7.4.
Its upstream provider release remains pending; no stable-provider certification
or general production qualification is implied.

CI evidence: [local checks](https://github.com/Stell0/ns8-cone/actions/runs/38055510275),
[publication](https://github.com/Stell0/ns8-cone/actions/runs/38055510311),
[real QEMU lifecycle](https://github.com/Stell0/ns8-cone/actions/runs/38055577878),
and [schema documentation](https://github.com/Stell0/ns8-cone/actions/runs/38050881129).
Earlier failing runs exposed test keyword/JSON transport issues, duplicate
configuration output, and an expected guard refusal exhausting the systemd start
limit. These were corrected, committed, published and retested. Recovery release
now resets the failed unit only after C1 verification/release succeeds.

Executed operator commands included:

```sh
api-cli run update-module --data '{"module_url":"ghcr.io/stell0/cone:dbbca92f856793fbbeff430b7c4c7ef29599c006","instances":["cone8"]}'
api-cli run run-backup --data '{"id":8}'
runagent -m cone8 restic-wrapper --backup 8 check --read-data
runagent -m cone8 systemctl --user stop cone.service
runagent -m cone8 systemctl --user start cone-app.service
```

Recovery used the documented `cone-recovery restore`, `verify`, and `release`
commands against an extracted encrypted version-2 snapshot, with protected
continuity evidence and fresh normal user tokens. The exact security snapshot
accepted was `2026-10-10T12:57:33.498591+00:00`. Verification refused wrong
namespace, stale attestation, the wrong user's token and changed proof; startup
remained guarded until fresh verification and explicit release. Identity,
instance/IRI, store/model identifiers and internal credentials survived updates,
restart and recovery.

The internal cluster repository qualifies encrypted transport and local
same-instance recovery; it is not off-node disaster recovery. Native restoration
into a new module ID remains guarded pending an original-client ownership
migration contract. Shared-node reboot and browser-engine automation are NOT_RUN.
Keep `production_ready=false` until those broader lifecycle/provider requirements
are qualified. The historical sections below describe their earlier revisions.

## Earlier operational update — before owner-authorized reset

See [earlier sanitized site evidence](evidence/makako-m14c-update.json).
It records the previous `stefano` enrollment, original namespace and temporary
artifact pins. Those values are historical after the explicit `foo1` reset.
The previous module OCI archive is retained, and the temporary transfer registry
was removed. The old idle root C1 proof-stack containers remain stopped with their
volumes retained; voice and other shared services were left running.

## Historical verification — 2026-10-06


The repository contains a **guarded development skeleton**, not a qualified C1
production release. The source revisions and images are pinned in
[`integration-lock.json`](../integration-lock.json).

| Check | Result | Evidence / limitation |
| --- | --- | --- |
| Module safety tests | PASS, 10 tests | Private state permissions, stable identity/secrets across retry, distinct instance audiences, safe environment serialization, schema bounds, sanitized output, atomic single-file replacement, relevant provider events and unforgeable release-owned startup guard |
| IdP schema/regression tests | PASS, 13 tests | Ownership, claim restrictions, disabled grants, idempotency, secret and disabled-state preservation, partial removal retry and Keycloak normalization |
| Real Keycloak token checks | PASS, 11 checks | [Sanitized evidence](evidence/keycloak-claims.json); actual signed tokens from Code + PKCE, refresh, ID-token exclusion, prohibited grants and mapper preservation. Isolated localhost HTTP fixture; not cross-node TLS qualification |
| IdP PR claim CI | PASS | [Workflow run](https://github.com/NethServer/ns8-idp/actions/runs/37345211953) runs local checks and actual Keycloak token checks |
| C1 runtime build | PASS | Unmodified pinned upstream `deployment/reference/Containerfile`, locked runtime dependencies; image labels identify revision `bcaf67bcefd0` |
| NS8 3.21.0 skeleton lifecycle | PASS | [Sanitized evidence](evidence/ns8-lifecycle.json); two disposable rootless instances, installation, permissions, unavailable IdP/invalid settings, distinct identities/audiences, ordered backend startup, loopback-only application port, restart preservation, guarded startup/backup, no routes and removal |
| UI build | PASS | Production Vue build succeeds; inherited vendor-size warnings remain. No live browser acceptance is claimed |
| Settings UI regression checks | PASS, 3 tests | Shipped combo-box lifecycle in a DOM: reopen saved settings, save/reload with numeric conversion, and failed discovery while retaining saved selections |
| Installed settings fix | PASS | [Sanitized evidence](evidence/settings-reload.json); native `update-module` on `cone8`, requested IdP/domain saved and read back, identity/credentials preserved, served frontend bundle matches installed artifact, startup guard preserved |
| Action schemas, Python/shell syntax, diff whitespace | PASS | JSON Schema Draft 7 validation, action syntax checks, `bash -n build-images.sh`, `git diff --check` |
| C1 requirement patch applicability | PASS | Applies to the pinned roadmap; only `PLAN.md` and the new unimplemented `docs/milestones/M19.md` change |

The real Keycloak check initially exposed normalized `userinfo.token.claim=false`
in audience mappers. The ownership comparison and regression test were corrected,
then both the live check and CI passed. The initial browser-fixture cookie issue
was corrected only in the isolated localhost test harness; no production token,
application or provider verification was weakened.

The real NS8 test initially exposed absent rootless CPU-controller delegation.
CPU limits were removed from the units; memory limits and bounded readiness remain.
The corrected backend startup and explicit all-unit restart pass. This was a
service restart test, not a node reboot. The temporary modules, registry and scoped
registry configuration were removed. Existing services were not reconfigured.

## Historical limitations — 2026-10-06

- Full C1 installation, external-IdP enrollment and retry-safe bootstrap: required
  C1 contracts are absent at the pinned release.
- Complete NS8 IdP realm suite and full NS8–IdP–C1 interoperability: not established
  by the isolated Keycloak fixture. The candidate shared IdP is now installed and
  healthy on the supplied test node, but C1 initialization remains guarded. The
  compatibility PR remains draft and its required release is unassigned.
- One named supported user-authorized agent/client: not yet available/verified.
  Generic Code + PKCE token tests do not establish compatibility with any agent.
- Application authorization, audit and independent-review integration; full
  Explorer login/expiry/logout; invalid/expired/wrong-purpose token checks against
  C1; valid cross-node TLS/CA trust: release qualification pending.
- Consistent backup, integrity checks, guarded restore, identity mismatch and
  acceptance, database migrations during upgrade, recovery after failure and node
  reboot: production lifecycle blocked by the upstream maintenance/recovery
  contract. The passing guard test demonstrates refusal, not successful recovery.

NS8-00 contracts and the guarded NS8-01 packaging work are reviewable. NS8-02 has a
focused implementation and passing token checks in
[NethServer/ns8-idp#4](https://github.com/NethServer/ns8-idp/pull/4), pending upstream
review, complete NS8 qualification and release. NS8-03–NS8-06 are incomplete.
No production readiness, arbitrary-agent compatibility or safe image rollback is
advertised. No C1 runtime/source modification was made.

The 2026-10-06 settings fix loads discovered options before assigning combo-box
values and preserves saved selections when discovery fails. The existing draft
uses `idp1` at `idp.makako.sf.nethserver.net` and domain
`makako.sf.nethserver.net`. C1 stays stopped with no application route: HTTP 404
is expected until the upstream bootstrap and recovery prerequisites are met.
Saving a draft does not request a certificate. A separate supported Traefik
`set-certificate` request was rejected by Let's Encrypt with HTTP 429: the
registered-domain issuance limit for `nethserver.net`. The latest response allows
a retry after `2026-10-06T07:30:06Z` (09:30:06 CEST); no certificate was obtained.
The temporary transfer registry and scoped registry setting were removed after
the successful native update. Browser interaction was unavailable; the DOM
regression checks and deployed-bundle verification do not replace live browser
or OAuth acceptance tests.
