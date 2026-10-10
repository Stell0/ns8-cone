# Protected same-instance recovery

This supervisor transport uses the public C1 `application` contract. It restores
into fresh private backend volumes, preserves instance/issuer/client identity,
and retains the original volumes. It excludes shared IdP persistence.

Only run from the protected module operator context (`runagent -m cone8`).
Stop normal writers; use an application-owned version-2 snapshot containing
`manifest.json`, `initialization.json`, `openfga.pgdump`, and
`terminusdb-storage.tar`, with directory 0700 and files 0600. The snapshot must
come from a trusted encrypted backup. Checksums detect corruption; they do not
establish ownership of arbitrary operator-supplied files.

```sh
runagent -m cone8 cone-recovery restore \
  --directory /protected/snapshot --operator deployment-operator
```

The command verifies integrity and archive paths, records durable intent before
creating owned volumes, imports storage, and invokes `c1-admin application
restore-validate`. The C1 writer stays stopped. Retries reconcile the same
manifest/generation; a different pending recovery is refused. The supervisor
startup guard and C1 journal guard both prevent publication.

Independently verify provider UUID, realm/subject identity and original client
registration against retained continuity evidence. Signing-key rotation alone
is not identity migration. Create a protected version-1 namespace attestation
following the public C1 schema, and obtain a fresh normal access token for the
original approved identity through Code + S256. No IdP administrator credential,
Explorer cookie export, arbitrary forwarded identity, or receipt can release it.

```sh
runagent -m cone8 cone-recovery verify \
  --namespace-evidence /protected/continuity.json --token-file /protected/user-token
runagent -m cone8 cone-recovery release \
  --namespace-evidence /protected/continuity.json --token-file /protected/user-token \
  --accept-security-as-of EXACT_MANIFEST_CREATED_AT \
  --reason incident-reference --operator deployment-operator
```

Release repeats C1 verification, requires explicit acceptance of the exact
security snapshot, and starts the normal guarded service. Check live
`/v1/readyz`, namespace and workflow behavior before publishing the target.
Do not delete original volumes until recovery is qualified and their retention
is decided explicitly. Do not promise image rollback across storage changes.

The native cluster `restore-module` workflow allocates a different module ID.
That would change NS8-owned client identity/lifecycle; this transport deliberately
refuses it pending a qualified client-ownership migration contract. The local
same-instance operator path preserves the original client. An internal cluster
backup fixture verifies encrypted transport but is not an off-node disaster
recovery arrangement. See [verification](verification.md) for actual outcomes.
