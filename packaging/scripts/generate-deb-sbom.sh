#!/usr/bin/env bash

set -euo pipefail

DEB_FILE="$(realpath "${1:?Missing Debian package}")"
DISTRIBUTION="${2:?Missing target distribution}"

PACKAGE="$(dpkg-deb -f "$DEB_FILE" Package)"
VERSION="$(dpkg-deb -f "$DEB_FILE" Version)"
ARCHITECTURE="$(dpkg-deb -f "$DEB_FILE" Architecture)"
SHA256="$(sha256sum "$DEB_FILE" | cut -d ' ' -f1)"
SYFT_VERSION="$(syft version | awk '/^Version:/ {print $2}')"

SBOM_FILE="${DEB_FILE}.spdx.json"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "Generating SBOM"
echo "  Package:      $PACKAGE"
echo "  Version:      $VERSION"
echo "  Architecture: $ARCHITECTURE"
echo "  Distribution: $DISTRIBUTION"
echo "  SHA256:       $SHA256"
echo "  Syft version: $SYFT_VERSION"

dpkg-deb -x "$DEB_FILE" "$STAGE"

syft scan "dir:$STAGE" \
    --override-default-catalogers image \
    --source-name "$PACKAGE-$DISTRIBUTION" \
    --source-version "$VERSION" \
    -o "spdx-json=$SBOM_FILE"

test -s "$SBOM_FILE"

echo "Generated $SBOM_FILE"
