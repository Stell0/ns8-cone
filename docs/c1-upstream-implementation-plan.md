> Historical proposal, superseded by upstream M14c and C1 `0.1.0rc2`.
> Its M19 IDs are not current roadmap items or executable test names.
> Use `docs/integration-contracts.md` and the upstream M14c plan/report.

# C1 upstream implementation plan: external OIDC and NS8 IdP

**Status:** draft implementation plan; no implementation or passing integration gate is implied.
**Proposed milestone:** M19, subject to upstream roadmap approval. Do not reopen completed milestones.
**Inspected upstream revision:** `50f23a0bae2febb65ffffdfb46cd4278b523c181`.
**Currently packaged revision:** `bcaf67bcefd024d0a14fb5e37c4a0ccd89af0a90` (`0.1.0rc1`).

## 1. Goal and accepted scope

Make C1 installable and usable with an independently managed OIDC provider, including NS8 IdP. A user must be able to sign in through the existing Explorer, administer explicitly granted permissions, and perform normal knowledge and ChangeSet workflows.

Browser SSO and the existing API are the first delivery target. An agent-specific authentication flow, separate machine identity, or separate agent HTTP route is **not a dependency**. Existing service-principal behavior must retain its validation and regressions; this milestone does not provision machine clients.

Requests using a user's access token remain attributed to that user and use that user's current C1 permissions. The `human` classification describes the user-authentication contract; it does not prove that a person manually performed the operation. Do not claim arbitrary-agent compatibility or separate agent attribution.

## 2. Starting state and boundaries

The inspected bootstrap creates a Keycloak realm, clients, and an administrator before initializing OpenFGA and the knowledge/workflow databases. Its host wrapper also owns the reference Compose stack. This prevents direct use with the shared NS8 IdP.

Existing Explorer OIDC, token validation, authorization, knowledge semantics, and recovery guards remain authoritative. Upstream C1 owns the missing initialization and operational contracts. NS8 packaging must consume a released C1 implementation without source patches or private imports.

| Component | Responsibility |
| --- | --- |
| C1 | Initialization, administrator enrollment, authorization, consistency, recovery guards, existing Explorer and API |
| NS8 IdP | Authentication, user-domain federation, supported client registration, audience and constrained claim mapping |
| ns8-cone | Domain binding, registration calls, private configuration, containers, routing, certificates, lifecycle and backup transport |

No private Keycloak, authentication proxy, password automation, management daemon, or rewritten Explorer is introduced. C1 never receives shared Keycloak administrator credentials. NS8 administrator status confers no C1 knowledge permissions.

## 3. Preserve the authentication contract

Retain signature, exact issuer, audience, subject, expiry, issued-at and supported access-token-purpose checks. Missing or invalid `c1_principal_kind` remains an error; do not default an unclassified token to `human`.

For the Explorer registration, the deployment supervisor requests Authorization Code with PKCE, the exact existing callback URL, the configured API audience, and `c1_principal_kind=human`. Password grants, service accounts and implicit flow remain disabled.

Verify Explorer discovery, callback, refresh, session expiry and logout against NS8 IdP. Remove any demonstrated provider-specific assumption through a focused upstream change, while retaining state, PKCE, nonce where applicable, CSRF protection, secure cookies and browser security headers. Document the actual logout behavior rather than promising global session or JWT invalidation.

## 4. Work packages and implementation order

### W1 — Define supported deployment-independent contracts

Inventory the existing public CLI, configuration and operational reports. Reuse and qualify `c1-admin internal state`, `consistency`, `guard-set`, `dr-verify` and `dr-release` before adding equivalents.

Define versioned inputs, sanitized JSON results, stable failure categories, bounded timeouts and compatibility rules for initialization, enrollment and recovery. Decide exact command names and schemas during implementation review; this plan does not claim that new commands or environment options already exist.

Keep operator enrollment approval separate from ordinary runtime settings. Publish which operations require the application writer to be stopped and which credentials they consume.

### W2 — Separate C1 initialization from IdP provisioning

Move application initialization into a supported upstream operation that uses already configured TerminusDB and OpenFGA endpoints. It must initialize the core profile, workflow state and authorization store/model without calling an IdP administration API or starting Compose services.

Keep the reference deployment working through a thin adapter: its existing Keycloak provisioning supplies identity/client configuration to the same C1 initialization contract. Avoid duplicate bootstrap implementations.

Persist initialization intent before durable side effects. Track instance ID, IRI base, issuer alias, issuer, API audience, backend identifiers, schema/model versions and completed steps. Reconcile backend state with that record after retries.

Distinguish empty, partial, awaiting-enrollment, complete and incompatible states. Retry after uncertain outcomes must discover owned resources before creating more. Ambiguous ownership fails closed. Existing content, grants, stores, model identifiers, credentials and persistent identity must not be reset by a retry.

### W3 — Enroll one explicitly approved existing administrator

Use a guarded enrollment mode in the existing Explorer authentication flow:

1. An authorized deployment operator supplies the exact approved issuer and subject through the supported local operator contract.
2. C1 initializes its application state and records a durable enrollment guard. Ordinary protected operations remain unavailable and normal readiness remains false.
3. The deployment may expose only the upstream-defined guarded setup surface: existing login, callback, required static assets and enrollment confirmation. C1 enforces this restriction itself; routing alone is not the security boundary.
4. The designated account signs in through the registered Explorer client. C1 validates the returned access token using its normal authentication contract and matches issuer/subject to the explicit approval.
5. The user confirms enrollment. C1 grants only `access_admin` and `schema_admin` on the instance, records completion durably, and verifies consistency before lifting the initialization guard.

An arbitrary first login, email/username match, browser-supplied identity field, forwarded header, or NS8 administrator session cannot enroll an administrator. Other users cannot consume or alter enrollment approval. Tokens and session secrets must not enter receipts, ordinary output or public evidence.

Define bounded enrollment lifetime and explicit cancellation/replacement before completion. After completion, routine configuration cannot rerun first-administrator enrollment. Normal authorized administration remains responsible for subsequent grants.

### W4 — Qualify a working human browser installation

Validate normal readiness against configuration, backends, identity discovery/JWKS, installed application state and consistency. A receipt file alone cannot declare readiness.

With real NS8 IdP, verify login, callback, refresh, expiry, logout and both permitted and denied application operations. Use Explorer's existing administration pages to create scopes and grant a least-privilege account access. Exercise a complete ChangeSet workflow with distinct submitting and approving principals when independent review is enabled.

The existing API remains available to appropriately authenticated user clients; no agent-specific endpoint is required. No user token, browser cookie or Explorer client secret is exported as an agent credential.

### W5 — Maintenance and recovery without shared IdP ownership

Qualify deployment-independent state and consistency operations using the existing C1 implementation. Add only demonstrated gaps; NS8 continues to own writer quiescing, backend backup procedures and backup transport.

Define a versioned recovery manifest for knowledge/workflow state, authorization persistence, stable application identity and the external identity namespace. Exclude shared IdP databases, realms and users. Keep secrets in protected backup configuration rather than diagnostic manifests.

Restore with publication guarded. Verify integrity, schema/model compatibility, application consistency and identity-namespace compatibility before release. Matching issuer text alone is insufficient if the provider's identity namespace was recreated; require evidence of subject continuity and explicit operator acceptance. Normal signing-key rotation must not be treated as a namespace migration.

Preserve instance ID, IRI base and issuer alias across a different destination NS8 module ID. Reconcile client registration through the provider contract. Never remap principals by username/email or automatically release restored authorization snapshots.

Retain explicit acceptance of the restored security snapshot and a fresh consistency check at release. Document migration failure and recovery; do not advertise image rollback after incompatible storage changes.

## 5. Delivery gates

| Gate | Required result | Permitted use |
| --- | --- | --- |
| A — Human SSO test | W1–W4 pass with real services; retry-safe initialization and verified enrollment; normal readiness true; no authentication bypass | Disposable NS8 browser/API testing; production and recovery support remain unqualified |
| B — Production integration | W5 and all required lifecycle/recovery regressions pass; compatible upstream artifact released and pinned | Production qualification by ns8-cone |

Gate A is not blocked by deferred agent integration or incomplete recovery qualification. It does require correct initialization, identity verification, authorization and consistency. An existing restored deployment stays guarded until its required recovery checks pass.

NS8 packaging may enable Gate A only after consuming the upstream implementation and verifying its declared capabilities. Replace the current unconditional startup blocker with checks based on qualified upstream capabilities and actual deployment state. Do not introduce a generic `force-ready` or receipt-based bypass. Backup/restore must report unavailable until qualified.

## 6. Required verification

These test IDs are proposed acceptance contracts, not existing executable tests.

| ID | Scenario and passing condition |
| --- | --- |
| M19-T01 | Clean external initialization creates C1 application state without IdP administration calls or Keycloak master credentials |
| M19-T02 | Intended issuer/subject enrolls once; wrong identity, arbitrary first login and NS8 administrator status grant nothing |
| M19-T03 | Interrupt every durable initialization/enrollment boundary; retries preserve identities and do not duplicate resources or broaden grants |
| M19-T04 | Repeated completed setup and runtime configuration preserve data, credentials, stores and administrator state |
| M19-T05 | Real NS8 IdP login, callback, refresh, expiry and documented logout succeed; invalid state/PKCE and wrong token purpose fail |
| M19-T06 | Wrong issuer/audience, expired/invalid signature, missing/invalid classification and ID tokens are rejected |
| M19-T07 | Human client cannot use password grants, implicit flow or client credentials |
| M19-T08 | Least-privilege access, denied administration, permission removal and independent-review enforcement pass through Explorer and API |
| M19-T09 | Pending enrollment exposes no knowledge or ordinary protected operations; readiness stays false until verified completion |
| M19-T10 | Two instances remain isolated; unavailable IdP, delayed backends, restart and valid cross-node TLS are handled without weakened checks |
| M19-T11 | Public maintenance operations work without reference Compose or IdP ownership; consistency failures remain actionable and guarded |
| M19-T12 | Interrupted/corrupt backup, fresh-node restore, identity mismatch, stale verification and unreleased guards fail safely; verified explicit release succeeds |
| M19-T13 | Existing reference deployment and relevant M03, M04, M12, M13 and current write-path regressions pass; no AI credentials are required |

Use unit tests for validation and state transitions, and real pinned C1, NS8, NS8 IdP, TerminusDB, OpenFGA and PostgreSQL for interoperability and recovery. Record PASS, FAIL and NOT_RUN separately. Gate A requires T01–T10 and applicable T13 regressions; Gate B also requires T11–T12 and complete lifecycle qualification. Mocks cannot establish either integration gate.

## 7. Deliverables and handoff

Produce the approved milestone plan, focused upstream changes, operator/configuration contracts, external-IdP installation and recovery documentation, named tests and a reproducible milestone report. Coordinate changes with ongoing M14a work; optional M15–M18 features are not dependencies.

The report records exact source/image revisions, command invocations, service versions, fixtures, sanitized evidence, unresolved issues and each gate outcome. Release and pin the compatible C1 artifact before packaging enables it.

The NS8 handoff uses `idp.makako.sf.nethserver.net`, domain `makako.sf.nethserver.net` and `cone.makako.sf.nethserver.net`, with a separately approved administrator subject. Certificate issuance and shared IdP availability remain platform prerequisites, not C1 bootstrap responsibilities.
