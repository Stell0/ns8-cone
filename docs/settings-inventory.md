# Pinned C1 runtime settings

All names read by `Settings.from_env` and `ExplorerSettings.from_env` at the pinned
revision are classified below. Module Settings currently saves a draft only.

| Environment | Classification | Module source |
| --- | --- | --- |
| `C1_AUDIENCE` | derived | provider/bootstrap or persistent module identity |
| `C1_BACKEND_TIMEOUT_S` | editable | backend_timeout_s |
| `C1_CRASH_AFTER` | unsupported | excluded |
| `C1_CURSOR_SECRET` | generated secret | private module file or provider registration |
| `C1_ENABLE_PROBE_ROUTES` | unsupported | forced false |
| `C1_EXPLORER_CLIENT_ID` | derived | provider/bootstrap or persistent module identity |
| `C1_EXPLORER_CLIENT_SECRET` | generated secret | private module file or provider registration |
| `C1_EXPLORER_ENABLED` | editable | explorer_enabled |
| `C1_EXPLORER_ORIGIN` | derived | provider/bootstrap or persistent module identity |
| `C1_EXPLORER_SESSION_IDLE_S` | editable | session_idle_s |
| `C1_EXPLORER_SESSION_MAX_S` | editable | session_max_s |
| `C1_FGA_MODEL` | derived | provider/bootstrap or persistent module identity |
| `C1_FGA_STORE` | derived | provider/bootstrap or persistent module identity |
| `C1_FGA_TOKEN` | generated secret | private module file or provider registration |
| `C1_FGA_URL` | derived | provider/bootstrap or persistent module identity |
| `C1_INDEPENDENT_REVIEW` | editable | independent_review |
| `C1_INSTANCE_ID` | derived | provider/bootstrap or persistent module identity |
| `C1_INSTANCE_IRI_BASE` | derived | provider/bootstrap or persistent module identity |
| `C1_ISSUER` | derived | provider/bootstrap or persistent module identity |
| `C1_ISSUER_ALIAS` | derived | provider/bootstrap or persistent module identity |
| `C1_ISSUER_CA_FILE` | editable | optional validated PEM upload, fixed container path |
| `C1_KNOWLEDGE_DATABASE` | derived | provider/bootstrap or persistent module identity |
| `C1_LOCK_PATH` | derived | provider/bootstrap or persistent module identity |
| `C1_MAX_READABLE_SCOPES` | editable | max_readable_scopes |
| `C1_ORGANIZATION` | derived | provider/bootstrap or persistent module identity |
| `C1_QUERY_CANDIDATE_LIMIT` | editable | query_candidate_limit |
| `C1_QUERY_TIME_BUDGET_MS` | editable | query_time_budget_ms |
| `C1_TERMINUS_PASSWORD` | generated secret | private module file or provider registration |
| `C1_TERMINUS_URL` | derived | provider/bootstrap or persistent module identity |
| `C1_WORKFLOW_DATABASE` | derived | provider/bootstrap or persistent module identity |
| `C1_CURSOR_SECRET_FILE` | unsupported | Alternative upstream secret-file representation; this skeleton selects direct values in private Podman env files. If selected later, exact 0400/0440 non-symlink files are required inside the C1 container. |
| `C1_EXPLORER_CLIENT_SECRET_FILE` | unsupported | Alternative upstream secret-file representation; this skeleton selects direct values in private Podman env files. If selected later, exact 0400/0440 non-symlink files are required inside the C1 container. |
| `C1_FGA_TOKEN_FILE` | unsupported | Alternative upstream secret-file representation; this skeleton selects direct values in private Podman env files. If selected later, exact 0400/0440 non-symlink files are required inside the C1 container. |
| `C1_TERMINUS_PASSWORD_FILE` | unsupported | Alternative upstream secret-file representation; this skeleton selects direct values in private Podman env files. If selected later, exact 0400/0440 non-symlink files are required inside the C1 container. |

Public host/certificate and provider/domain selection are NS8 settings, not extra
C1 environment APIs. Initial-administrator enrollment is a separate upstream
setup contract; no runtime environment name is invented for it. Fixed internal
URLs, database names, instance ID/IRI base, issuer alias and audience are derived.
OpenFGA store/model are retained from a verified bootstrap receipt once supported.
C1 image entrypoint drops to UID 10001; direct environment secrets are supported.
A private CA mount and its container readability must be qualified before startup.
Reference-only Compose, Keycloak, probe, crash and password-development settings
are not exposed. Arbitrary environment injection is rejected.
