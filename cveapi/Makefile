REPOSITORY ?= $(or $(GITHUB_REPOSITORY),$(shell git remote get-url origin 2>/dev/null | sed -E 's%^(https://github.com/|git@github.com:)%%; s%\.git$$%%'),SSC-ICT-Innovatie/nl-kat-coordination)

debian13:
	mkdir -p build
	docker run --rm \
	--env PKG_NAME=kat-cveapi \
	--env BUILD_DIR=./build \
	--env REPOSITORY=$(REPOSITORY) \
	--env RELEASE_VERSION=${RELEASE_VERSION} \
	--env RELEASE_TAG=${RELEASE_TAG} \
	--mount type=bind,src=${CURDIR},dst=/app \
	--workdir /app \
	kat-debian13-build-image \
	packaging/scripts/build-debian-package.sh

clean:
	rm -rf build
	rm -rf debian/kat-*/ debian/.debhelper debian/files *.egg-info/ dist/
	rm -f debian/debhelper-build-stamp
	rm -f debian/*.*.debhelper
	rm -f debian/*.substvars
	rm -f debian/*.debhelper.log
	rm -f debian/changelog
