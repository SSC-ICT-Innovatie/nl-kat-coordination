#!/bin/bash

set -e

# TODO: generate proper changelog
echo "Create changelog file"
cat > debian/changelog << EOF
${PKG_NAME} (${RELEASE_VERSION}) unstable; urgency=low
  * view changes: https://github.com/${REPOSITORY}/releases/tag/${RELEASE_TAG}

 -- OpenKAT <maintainer@librekat.nl>  $(LANG=C date -R)

EOF

dpkg-buildpackage -us -uc -b

mkdir -p /app/build
mv /"${PKG_NAME}"_"${RELEASE_VERSION}"_*.deb /app/build/
