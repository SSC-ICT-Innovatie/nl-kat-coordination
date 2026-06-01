#!/bin/bash

set -e

# TODO: generate proper changelog using a tool like git-dch
echo "Create changelog file"
cat > debian/changelog << EOF
${PKG_NAME} (${RELEASE_VERSION}) unstable; urgency=low
  * view changes: https://github.com/${REPOSITORY}/releases/tag/v${RELEASE_VERSION}

 -- OpenKAT <maintainer@librekat.nl>  $(LANG=C date -R)

EOF

echo "Build frontend"
yarn
yarn build

dpkg-buildpackage -us -uc -b

mv /"${PKG_NAME}"_"${RELEASE_VERSION}"_*.deb /app/build/
