# Upstream integration work

The C1 requirements patch below is historical and superseded by approved,
implemented M14c and released C1 `0.1.0rc2`. Do not apply the old M19 proposal.
See [current integration contracts](../docs/integration-contracts.md).


The focused claim-extension draft PR is
[NethServer/ns8-idp#4](https://github.com/NethServer/ns8-idp/pull/4), based on
`81454e350d600ecbe0b6d0163090ef51bb34acb3`, with candidate commit
`3e801d22e307142e9cc989def400b6615bd8dc02`.

[ns8-idp-access-token-claims.patch](ns8-idp-access-token-claims.patch) contains the
same implementation, schemas, ownership/idempotency regressions, documentation
and real Keycloak checks. Thirteen local checks and eleven real Keycloak checks
pass; the PR claim-check CI also passes. The complete NS8 IdP realm suite has not
been run for this branch, and no compatible released IdP version is assigned yet.
The PR is draft, with no reviewers requested. GitHub denied self-assignment via
both the CLI and assignee API (403); an upstream maintainer must set the assignee.

[c1-external-idp-requirements.patch](c1-external-idp-requirements.patch) applies to
C1 `bcaf67bcefd024d0a14fb5e37c4a0ccd89af0a90` and changes **only** `PLAN.md` and
`docs/milestones/M19.md`. It proposes an unimplemented milestone for the five
requirements, and identifies existing public maintenance commands to qualify
before adding equivalents. It does not implement C1 operations or invent command
or environment contracts. The patch has been checked for applicability to the
pinned roadmap and has not been published to the C1 default branch.

The ns8-cone production gate stays blocked until compatible upstream releases
and full real-service qualification are available. A passing Keycloak test does
not establish external-IdP C1 bootstrap, NS8 browser readiness or recovery.
