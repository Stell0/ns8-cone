#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
repobase="${REPOBASE:-ghcr.io/stell0}"
repobase="${repobase,,}"
module_tag="${IMAGETAG:-dev}"
c1_tag=$(python3 -c 'import json; print(json.load(open("integration-lock.json"))["images"]["c1"]["tag"])')
c1_revision=$(python3 -c 'import json; print(json.load(open("integration-lock.json"))["repositories"]["c1"]["revision"])')
c1_artifacts=$(mktemp -d)
container=""
cleanup() {
    rm -rf "$c1_artifacts"
    if [[ -n "$container" ]]; then buildah rm "$container" >/dev/null; fi
}
trap cleanup EXIT
# Consume the qualified upstream release bytes; rebuilding changes the config digest.
c1_archive="$c1_artifacts/c1.docker.tar.gz"
c1_release=$(python3 -c 'import json; print(json.load(open("integration-lock.json"))["repositories"]["c1"]["version"])')
c1_checksum=$(python3 -c 'import json; print(json.load(open("integration-lock.json"))["images"]["c1"]["archive_sha256"])')
curl --fail --location --retry 3 --max-time 300 \
    "https://github.com/Stell0/c1/releases/download/v${c1_release}/c1-${c1_release}-linux-amd64.docker.tar.gz" \
    --output "$c1_archive"
printf '%s  %s\n' "$c1_checksum" "$c1_archive" | sha256sum --check --status
gzip -dc "$c1_archive" > "$c1_artifacts/c1.docker.tar"
buildah pull "docker-archive:$c1_artifacts/c1.docker.tar"
buildah tag "localhost/c1:${c1_release}" "${repobase}/cone-c1:${c1_tag}"
buildah inspect --type image "${repobase}/cone-c1:${c1_tag}" | python3 -c '
import json, sys
lock = json.load(open("integration-lock.json"))
image = json.load(sys.stdin)
assert image["FromImageID"].removeprefix("sha256:") == lock["images"]["c1"]["config_digest"].removeprefix("sha256:"), "Runtime configuration digest changed"
assert image["OCIv1"]["config"]["Labels"]["org.opencontainers.image.revision"] == lock["repositories"]["c1"]["revision"], "Runtime revision changed"
'
# A prepared dist directory supports the remote test build; CI always rebuilds.
if [[ "${SKIP_UI_BUILD:-0}" != 1 ]]; then
    (
        cd ui
        corepack yarn install --immutable
        NODE_OPTIONS=--openssl-legacy-provider corepack yarn build
    )
fi
test -f ui/dist/index.html
container=$(buildah from scratch)
buildah add "$container" imageroot /imageroot
buildah add "$container" ui/dist /ui
images=$(python3 -c 'import json; d=json.load(open("integration-lock.json")); print(" ".join(d["images"][k]["reference"] for k in ("terminusdb","openfga","postgres")))')
buildah config --entrypoint=/ \
    --label="org.opencontainers.image.source=https://github.com/Stell0/ns8-cone" \
    --label="org.nethserver.authorizations=traefik@node:routeadm idp@any:clientadm cluster:accountconsumer" \
    --label="org.nethserver.min-core=3.21.0" \
    --label="org.nethserver.tcp-ports-demand=1" \
    --label="org.nethserver.rootfull=0" \
    --label="org.nethserver.volumes=cone-pgdata cone-terminus-data" \
    --label="org.nethserver.images=${images} ${repobase}/cone-c1:${c1_tag}" \
    "$container"
buildah commit "$container" "${repobase}/cone:${module_tag}"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    printf 'module_image=%s\nc1_image=%s\n' "${repobase}/cone:${module_tag}" "${repobase}/cone-c1:${c1_tag}" >> "$GITHUB_OUTPUT"
fi
printf 'Built %s and %s\n' "${repobase}/cone:${module_tag}" "${repobase}/cone-c1:${c1_tag}"
