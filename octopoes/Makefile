.PHONY: debian ubuntu clean

debian12:
	mkdir -p build
	docker run --rm \
	--env PKG_NAME=kat-octopoes \
	--env BUILD_DIR=./build \
	--env REPOSITORY=minvws/nl-kat-octopoes \
	--env RELEASE_VERSION=${RELEASE_VERSION} \
	--env RELEASE_TAG=${RELEASE_TAG} \
	--mount type=bind,src=${CURDIR},dst=/app \
	--workdir /app \
	kat-debian12-build-image \
	packaging/scripts/build-debian-package.sh

ubuntu22.04:
	mkdir -p build
	docker run --rm \
	--env PKG_NAME=kat-octopoes \
	--env BUILD_DIR=./build \
	--env REPOSITORY=minvws/nl-kat-octopoes \
	--env RELEASE_VERSION=${RELEASE_VERSION} \
	--env RELEASE_TAG=${RELEASE_TAG} \
	--mount type=bind,src=${CURDIR},dst=/app \
	--workdir /app \
	kat-ubuntu22.04-build-image \
	packaging/scripts/build-debian-package.sh

format:
	black .
	robotidy tests/robot

clean:
	rm -rf build
	rm -fr debian/kat-*/ debian/.debhelper debian/files *.egg-info/ dist/
	rm -f debian/debhelper-build-stamp
	rm -f debian/*.*.debhelper
	rm -f debian/*.substvars
	rm -f debian/*.debhelper.log
	rm -f debian/changelog

check:
	pre-commit run --all-files --show-diff-on-failure --color always

test:
	pytest

rtest:
	docker compose --project-directory . -f .ci/docker-compose.yml down --remove-orphans
	docker compose --project-directory . -f .ci/docker-compose.yml up -d --build ci_octopoes ci_octopoes_api_worker
	sleep 2
	robot -d reports tests/robot

ctest:
	docker compose --project-directory . -f .ci/docker-compose.yml kill
	docker compose --project-directory . -f .ci/docker-compose.yml down --remove-orphans
	docker compose --project-directory . -f .ci/docker-compose.yml build $(build_args)
	docker compose --project-directory . -f .ci/docker-compose.yml run --rm octopoes_pytest

itest:
	docker compose --project-directory . -f .ci/docker-compose.yml kill
	docker compose --project-directory . -f .ci/docker-compose.yml down --remove-orphans
	docker compose --project-directory . -f .ci/docker-compose.yml build $(build_args)
	docker compose --project-directory . -f .ci/docker-compose.yml run --rm octopoes_integration
