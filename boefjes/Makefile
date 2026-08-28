SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules
# Makefile Reference: https://tech.davis-hansson.com/p/make/

.PHONY: help sql migrate migrations debian ubuntu clean images

# use HIDE to run commands invisibly, unless VERBOSE defined
HIDE:=$(if $(VERBOSE),,@)

export m		# Message for alembic migration
export revid	# Revision id to generate raw sql for
export rev1		# Previous revision id for generating migrations
export rev2		# New revision id for the new migration file

# We set this to build images with the right target platform in the `images` target. This prevents arm systems such as
# systems with an Apple silicon chip to build images they cannot use.
export DOCKER_DEFAULT_PLATFORM=$(shell docker system info --format '{{.OSType}}/{{.Architecture}}')

##
##|------------------------------------------------------------------------|
##			Help
##|------------------------------------------------------------------------|
help: ## Show this help.
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/:\(.*\)##/:			/' | sed -e 's/##//'


##
##|------------------------------------------------------------------------|
##			Development
##|------------------------------------------------------------------------|

build: images

base-image:
	docker build -f **/base.Dockerfile -t openkat/boefje-base:latest .

export REGISTRY=ghcr.io/minvws/openkat

images: base-image # Build the images for the containerized boefjes
	docker build -f */*/kat_dnssec/boefje.Dockerfile -t $(REGISTRY)/dns-sec:latest -t openkat/dns-sec .
	docker build -f */*/kat_nmap_tcp/boefje.Dockerfile -t $(REGISTRY)/nmap:latest -t openkat/nmap .
	docker build -f */*/kat_export_http/boefje.Dockerfile -t $(REGISTRY)/export-http:latest -t openkat/export-http .
	docker build -f */*/kat_nikto/boefje.Dockerfile -t $(REGISTRY)/nikto:latest .
	docker build -f */generic.Dockerfile -t $(REGISTRY)/generic:latest -t openkat/generic .

##
##|------------------------------------------------------------------------|
##			Migrations
##|------------------------------------------------------------------------|

migrations: ## Generate a migration using alembic
ifeq ($(m),)
	$(HIDE) (echo "Specify a message with m={message} and a rev-id with revid={revid} (e.g. 0001 etc.)"; exit 1)
else
	docker compose run --rm katalogus python -m alembic --config /app/boefjes/boefjes/alembic.ini revision --autogenerate -m "$(m)"
endif


sql: ## Generate raw sql for the migrations
	docker compose run --rm katalogus python -m alembic --config /app/boefjes/boefjes/alembic.ini upgrade $(rev1):$(rev2) --sql

check:
	pre-commit run --all-files --color always

##
##|------------------------------------------------------------------------|
##			Tests
##|------------------------------------------------------------------------|

ci-docker-compose := docker compose --project-directory . -f .ci/docker-compose.yml


test: itest ## Run all tests.

itest: ## Run the integration tests.
	$(ci-docker-compose) build
	$(ci-docker-compose) down --remove-orphans
	$(ci-docker-compose) run --rm katalogus_integration
	$(ci-docker-compose) stop

migration_bench:  ## Run the migration benchmark.
	$(ci-docker-compose) build
	$(ci-docker-compose) down --remove-orphans
	$(ci-docker-compose) run --rm migration_bench
	$(ci-docker-compose) stop

bench:  ## Run the other benchmarks
	$(ci-docker-compose) build
	$(ci-docker-compose) down --remove-orphans
	$(ci-docker-compose) run --rm katalogus_integration \
	python -m cProfile -o .ci/bench_$$(date +%Y_%m_%d-%H:%M:%S).pstat -m pytest -m slow --no-cov tests/integration
	$(ci-docker-compose) stop

debian12:
	docker run --rm \
	--env PKG_NAME=kat-boefjes \
	--env BUILD_DIR=./build \
	--env REPOSITORY=minvws/nl-kat-boefjes \
	--env RELEASE_VERSION=${RELEASE_VERSION} \
	--env RELEASE_TAG=${RELEASE_TAG} \
	--mount type=bind,src=${CURDIR},dst=/app \
	--mount type=bind,src=${CURDIR}/../octopoes,dst=/octopoes \
	--workdir /app \
	kat-debian12-build-image \
	packaging/scripts/build-debian-package.sh

ubuntu22.04:
	mkdir -p build
	docker run --rm \
	--env PKG_NAME=kat-boefjes \
	--env BUILD_DIR=./build \
	--env REPOSITORY=minvws/nl-kat-boefjes \
	--env RELEASE_VERSION=${RELEASE_VERSION} \
	--env RELEASE_TAG=${RELEASE_TAG} \
	--mount type=bind,src=${CURDIR},dst=/app \
	--mount type=bind,src=${CURDIR}/../octopoes,dst=/octopoes \
	--workdir /app \
	kat-ubuntu22.04-build-image \
	packaging/scripts/build-debian-package.sh

clean:
	rm -rf build
	rm -rf debian/kat-*/ debian/.debhelper debian/files *.egg-info/ dist/
	rm -f debian/debhelper-build-stamp
	rm -f debian/*.*.debhelper
	rm -f debian/*.substvars
	rm -f debian/*.debhelper.log
	rm -f debian/changelog
