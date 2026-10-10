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
| NS8 module unit tests | PASS, 19 tests | File/namespace safety, image pin, readiness, sanitized failures, bounded idempotent registration retry and restore refusal |
| UI settings tests | PASS, 3 tests | Saved selections, round-trip settings and discovery failure |
| UI lint/build | PASS | Lint now targets `src`; production build retains vendor-size warnings |
| Foo account enrollment | PASS | Exact approved `foo1`; incorrect first `foo2` login rejected; explicit authenticated confirmation; two initial instance roles only |
| Live account/API/Explorer suite | PASS, with separate protocol/workflow runs | `tests/integration/live_oidc.py`; real TLS Code + S256; two accounts; reviewed create/modify, attribution, idempotency and immediate revocation; full deployed repetition still required |
| CI and deployed-artifact retest | NOT_RUN | Required after source commit/push; outcome will be updated from actual CI/deployment |
| Native encrypted backup and fresh persistence restore | NOT_RUN | Fixture preparation in progress; no production recovery claim |
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

## Not run / blocked

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
