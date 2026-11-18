#!/usr/bin/env bash
# Load a local Docker image into every node of a kind cluster.
#
# `kind load docker-image` imports with `ctr images import --all-platforms`.
# With Docker's containerd image store, `docker save` of a multi-platform image
# only contains the host platform's layers, so that import fails. Save just the
# host platform and import it directly instead.
#
# Usage: e2e/kind_load_image.sh <cluster-name> <image> [<image> ...]
set -euo pipefail

cluster="$1"
shift
platform="$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}')"
for image in "$@"; do
  for node in $(kind get nodes --name "$cluster"); do
    docker save --platform "$platform" "$image" \
      | docker exec -i "$node" ctr --namespace=k8s.io images import --digests --snapshotter=overlayfs -
  done
done
