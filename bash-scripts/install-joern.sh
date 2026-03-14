#!/bin/bash

set -euo pipefail

BASE_DIR="./joerns"
VERSIONS=(
	"v1.1.1298"
	"latest"
)
INSTALLER_URL="https://github.com/joernio/joern/releases/latest/download/joern-install.sh"

mkdir -p "${BASE_DIR}"
for version in "${VERSIONS[@]}"; do
	mkdir -p "${BASE_DIR}/${version}"
done

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

curl -fsSL "${INSTALLER_URL}" -o "${TMP_DIR}/joern-install.sh"
chmod u+x "${TMP_DIR}/joern-install.sh"

# Install each Joern version into ./joerns/<version>
for version in "${VERSIONS[@]}"; do
	if [[ "${version}" == "latest" ]]; then
		"${TMP_DIR}/joern-install.sh" --install-dir="${BASE_DIR}/${version}"
	else
		"${TMP_DIR}/joern-install.sh" --version="${version}" --install-dir="${BASE_DIR}/${version}"
	fi
done