# ns8-cone

C1 for NethServer 8, using the shared NS8 IdP and upstream External OIDC
Provider Support (M14c). The runtime is the unmodified, qualified C1
`0.1.0rc2` release artifact; [integration-lock.json](integration-lock.json)
records its source revision, archive checksum and configuration digest.

The module retains private credentials and stable instance identity, registers
its own confidential IdP client through native actions, initializes dedicated
TerminusDB/OpenFGA persistence through public C1 commands, and exposes guarded
Explorer setup over HTTPS. Only an operator-approved exact OIDC identity may
confirm initial administrator enrollment. Readiness comes from the live C1
consistency/readiness contract, never a bootstrap receipt.

**Development integration:** upstream Gate A/B qualification does not qualify
NS8 lifecycle or recovery automatically. Cross-module automatic restore remains unavailable;
same-instance protected recovery uses `cone-recovery` and must pass its own
real-service verification before production use.

Read [integration contracts](docs/integration-contracts.md),
[settings inventory](docs/settings-inventory.md), and
[verification results](docs/verification.md). Historical upstream proposals under
[upstream](upstream/README.md) describe earlier requirements, not current capabilities.

Build with `bash build-images.sh` (Buildah, curl, Python, Node/Corepack). It
verifies and imports the published Docker archive instead of rebuilding C1.
The module image is `ghcr.io/stell0/cone:<module-tag>`; the separate C1 runtime
retains the released bytes. Only linux/amd64 is supported by the pinned artifact.

Install with native `add-module`/`update-module`, then call `configure-module`.
Inspect `get-configuration` and `get-integration-status`. Pending setup links to
`/explorer/login`; completed installations link to `/explorer/`. Approve the
exact administrator issuer/subject locally through the public C1 enrollment
command, then have that user sign in and explicitly confirm. Additional grants
use normal authorized C1 administration.

Run local checks:

```sh
python3 -m unittest discover -s tests/unit -v
(cd ui && NODE_OPTIONS=--openssl-legacy-provider corepack yarn build)
(cd ui && corepack yarn test:settings)
bash -n build-images.sh
```

Local tests cannot establish live browser authentication or recoverability.
Record PASS, FAIL and NOT_RUN separately in the verification report.
