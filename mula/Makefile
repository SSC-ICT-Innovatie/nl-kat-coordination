SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules
# Makefile Reference: https://tech.davis-hansson.com/p/make/

.PHONY: all help mypy check black done lint env debian ubuntu clean itest utest test migrations HIDE

# use HIDE to run commands invisibly, unless VERBOSE defined
HIDE:=$(if $(VERBOSE),,@)

# Export cmd line args:
export VERBOSE
export m
export build
export file

# Export Docker buildkit options
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

ci-docker-compose := docker compose --project-directory . -f .ci/docker-compose.yml

##
##+------------------------------------------------------------------------+
##| Help                                                                   |
##+------------------------------------------------------------------------+
help: ## Show this help.
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/ ##/			/' | sed -e 's/##//'

##
##+------------------------------------------------------------------------+
##| Development                                                            |
##+------------------------------------------------------------------------+

check: ## Check the code style using black, mypy and pylint.
	make black
	make mypy
	make pylint

mypy: ## Check code style using mypy.
	docker compose run --rm scheduler \
		python -m mypy --cache-dir /home/scheduler/.mypy_cache /app/scheduler/scheduler

black: ## Check code style with black.
	docker compose run --rm scheduler \
		black --check --diff .

pylint: ## Rate the code with pylint.
	$(ci-docker-compose) run --rm ci_scheduler_unit \
		pylint --rcfile pyproject.toml scheduler

fmt: ## Format the code using black.
	docker compose run --rm scheduler \
		black .

done: ## Prepare for a commit.
	make lint
	make check
	make test

cov: ## Generate a test coverage report
	$(ci-docker-compose) run --rm ci_scheduler_integration \
		python -m pytest \
		--cov-report term-missing:skip-covered \
		--cov=scheduler tests/

##
##+------------------------------------------------------------------------+
##| Migrations                                                             |
##+------------------------------------------------------------------------+

sql: ## Generate raw sql for the migrations.
	docker compose run --rm scheduler \
		alembic --config /app/scheduler/scheduler/storage/migrations/alembic.ini \
		upgrade $(rev1):$(rev2) --sql

migrations: ## Create migration.
ifeq ($(m),)
	$(HIDE) (echo "ERROR: Specify a message with m={message} and a rev-id with revid={revid} (e.g. 0001 etc.)"; exit 1)
else ifeq ($(revid),)
	$(HIDE) (echo "ERROR: Specify a message with m={message} and a rev-id with revid={revid} (e.g. 0001 etc.)"; exit 1)
else
	docker compose run --rm scheduler \
		alembic --config /app/scheduler/scheduler/storage/migrations/alembic.ini \
		revision --autogenerate \
		-m "$(m)" --rev-id "$(revid)"
endif

migrate: ## Run migrations using alembic.
	docker compose run scheduler \
		alembic --config /app/scheduler/scheduler/storage/migrations/alembic.ini \
		upgrade head

##
##+------------------------------------------------------------------------+
##| Testing                                                                |
##+------------------------------------------------------------------------+

utest: ## Run the unit tests.
ifneq ($(file),)
	$(ci-docker-compose) run --rm ci_scheduler_unit python -m pytest -v tests/unit/${file} $(if $(function),-k $(function))
else
	$(ci-docker-compose) run --rm ci_scheduler_unit python -m pytest -v tests/unit
endif
	$(ci-docker-compose) down --remove-orphans

itest: ## Run the integration tests.
ifneq ($(file),)
	$(ci-docker-compose) run --rm ci_scheduler_integration python -m pytest -v tests/integration/${file} $(if $(function),-k $(function))
else
	$(ci-docker-compose) run --rm ci_scheduler_integration python -m pytest -v tests/integration
endif
	$(ci-docker-compose) down --remove-orphans

test: ## Run all tests.
	make utest
	make itest

##
##+------------------------------------------------------------------------+
##| Building                                                               |
##+------------------------------------------------------------------------+
debian12:
	mkdir -p build
	docker run --rm \
	--env PKG_NAME=kat-mula \
	--env BUILD_DIR=./build \
	--env REPOSITORY=SSC-ICT-Innovatie/nl-kat-coordination \
	--env RELEASE_VERSION=${RELEASE_VERSION} \
	--env RELEASE_TAG=${RELEASE_TAG} \
	--mount type=bind,src=${CURDIR},dst=/app \
	--workdir /app \
	kat-debian12-build-image \
	packaging/scripts/build-debian-package.sh

ubuntu22.04:
	mkdir -p build
	docker run --rm \
	--env PKG_NAME=kat-mula \
	--env BUILD_DIR=./build \
	--env REPOSITORY=SSC-ICT-Innovatie/nl-kat-coordination \
	--env RELEASE_VERSION=${RELEASE_VERSION} \
	--env RELEASE_TAG=${RELEASE_TAG} \
	--mount type=bind,src=${CURDIR},dst=/app \
	--workdir /app \
	kat-ubuntu22.04-build-image \
	packaging/scripts/build-debian-package.sh

debian13:
	mkdir -p build
	docker run --rm \
	--env PKG_NAME=kat-mula \
	--env BUILD_DIR=./build \
	--env REPOSITORY=SSC-ICT-Innovatie/nl-kat-coordination \
	--env RELEASE_VERSION=${RELEASE_VERSION} \
	--env RELEASE_TAG=${RELEASE_TAG} \
	--mount type=bind,src=${CURDIR},dst=/app \
	--workdir /app \
	kat-debian13-build-image \
	packaging/scripts/build-debian-package.sh

ubuntu24.04:
	mkdir -p build
	docker run --rm \
	--env PKG_NAME=kat-mula \
	--env BUILD_DIR=./build \
	--env REPOSITORY=SSC-ICT-Innovatie/nl-kat-coordination \
	--env RELEASE_VERSION=${RELEASE_VERSION} \
	--env RELEASE_TAG=${RELEASE_TAG} \
	--mount type=bind,src=${CURDIR},dst=/app \
	--workdir /app \
	kat-ubuntu24.04-build-image \
	packaging/scripts/build-debian-package.sh

clean: ## clean
	rm -rf build
	rm -rf debian/kat-*/ debian/.debhelper debian/files *.egg-info/ dist/
	rm -f debian/debhelper-build-stamp
	rm -f debian/*.*.debhelper
	rm -f debian/*.substvars
	rm -f debian/*.debhelper.log
	rm -f debian/changelog
