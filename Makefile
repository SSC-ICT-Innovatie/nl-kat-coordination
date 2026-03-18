SHELL := bash
.ONESHELL:
.NOTPARALLEL:

# use HIDE to run commands invisibly, unless VERBOSE defined
HIDE:=$(if $(VERBOSE),,@)
UNAME := $(shell uname)

.PHONY: kat update reset up stop down clean fetch pull upgrade env-if-empty env build debian-build-image ubuntu-build-image docs upgraderequirements requirements

# Export Docker buildkit options
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# We can't really return an error here, so if settings-doc fails we delete the
# file which will result in sphinx-build returning an error later on
define build-settings-doc
	echo "# $(4)" > docs/source/installation-and-deployment/environment-settings/$(3).md
	DOCS=True PYTHONPATH=./$(1) settings-doc generate \
	-f markdown -m $(2) \
	--templates docs/settings-doc-templates \
	>> docs/source/installation-and-deployment/environment-settings/$(3).md || exit 1
endef


# Build and bring up all containers (default target)
kat: env-if-empty build up
	@echo
	@echo "The KAT frontend is running at http://localhost:8000,"
	@echo "An initial superuser has been created"
	@echo "The username is stored in DJANGO_SUPERUSER_EMAIL in the .env-default file."
	@echo "run 'grep 'DJANGO_SUPERUSER_EMAIL' .env-defaults' to find it."
	@echo "The related password can be found as DJANGO_SUPERUSER_PASSWORD in the .env file."
	@echo "run 'grep 'DJANGO_SUPERUSER_PASSWORD' .env' to find it."
	@echo
	@echo "WARNING: This is a development environment, do not use in production!"
	@echo "See https://docs.openkat.nl/installation-and-deployment/production-docker-environment.html for production"
	@echo "installation instructions."

# Remove containers, update using git pull and bring up containers
update: down pull kat

# Remove all containers and volumes, and bring containers up again (data loss!)
reset: clean kat

# Bring up containers
up:
	docker compose up --detach

# Stop containers
stop:
	-docker compose stop

# Remove containers but not volumes (no data loss)
down:
	-docker compose down

# Remove containers and all volumes (data loss!)
clean:
	-docker compose down --timeout 0 --volumes --remove-orphans
	-rm -Rf rocky/node_modules rocky/assets/dist rocky/.parcel-cache rocky/static

# Fetch the latest changes from the Git remote
fetch:
	git fetch --all --prune --tags

# Pull the latest changes from the default upstream
pull:
	git pull
	docker compose pull

# Upgrade to the latest release without losing persistent data. Usage: `make upgrade version=v1.5.0` (version is optional)
VERSION?=$(shell curl -sSf "https://api.github.com/repos/SSC-ICT-Innovatie/nl-kat-coordination/tags" | jq -r '[.[].name | select(. | contains("rc") | not)][0]')
upgrade: down fetch
	git checkout $(VERSION)
	make kat

# Create .env file only if it does not exist
env-if-empty:
ifeq ("$(wildcard .env)","")
	make env
endif

# Create .env file from the env-dist with randomly generated credentials from vars annotated by "{%EXAMPLE_VAR}"
env:
	cp .env-dist .env
	echo "Initializing .env with random credentials"
ifeq ($(UNAME), Darwin)  # Different sed on MacOS
	$(HIDE) grep -o "{%\([_A-Z]*\)}" .env-dist | sort -u | while read v; do sed -i '' "s/$$v/$$(openssl rand -hex 25)/g" .env; done
else
	$(HIDE) grep -o "{%\([_A-Z]*\)}" .env-dist | sort -u | while read v; do sed -i "s/$$v/$$(openssl rand -hex 25)/g" .env; done
endif

# Build will prepare all services: migrate them, seed them, etc.
build:
ifeq ($(UNAME),Darwin)
	docker compose build --pull --parallel --build-arg USER_UID="$$(id -u)"
else
	docker compose build --pull --parallel --build-arg USER_UID="$$(id -u)" --build-arg USER_GID="$$(id -g)"
endif
	make -C rocky build
	make -C boefjes build

# Build Debian 11 build image
debian12-build-image:
	docker build -t kat-debian12-build-image packaging/debian12

# Build Ubuntu 22.04 build image
ubuntu22.04-build-image:
	docker build -t kat-ubuntu22.04-build-image packaging/ubuntu22.04

CHECKSUM_CMD = $(if $(filter $(UNAME), Darwin), shasum -a 256, sha256sum --quiet)

docs:
	$(call build-settings-doc,octopoes,octopoes.config.settings,octopoes,Octopoes)
	$(call build-settings-doc,boefjes,boefjes.config,boefjes,Boefjes)
	$(call build-settings-doc,bytes,bytes.config,bytes,Bytes)
	$(call build-settings-doc,mula/scheduler,config.settings,mula,Mula)

	curl -sL -o - https://registry.npmjs.org/d3/-/d3-7.9.0.tgz | tar -Oxzf - package/dist/d3.min.js > docs/source/_static/d3.min.js
	curl -sL -o - https://registry.npmjs.org/mermaid/-/mermaid-11.3.0.tgz | tar -Oxzf - package/dist/mermaid.min.js > docs/source/_static/mermaid.min.js

	echo "f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539  docs/source/_static/d3.min.js" | $(CHECKSUM_CMD) --check || exit 1
	echo "0d2b6f2361e7e0ce466a6ed458e03daa5584b42ef6926c3beb62eb64670ca261  docs/source/_static/mermaid.min.js" | $(CHECKSUM_CMD) --check || exit 1

	PYTHONPATH=$(PYTHONPATH):boefjes/:bytes/:mula/:octopoes/ sphinx-build -b html --fail-on-warning docs/source docs/_build


upgraderequirements:
	@echo "Upgrading all required dependencies using uv..."
	files=$$(find . -name pyproject.toml -maxdepth 2); \
	for path in $$files; do \
		project_dir=$$(dirname $$path); \
		echo "Processing $$path..."; \
		uv lock --project $$project_dir --upgrade; \
		echo "New Lock file generated. Use \`make requirements\` to update requirements files..."
	done

requirements:
	@echo "Generating requirements.txt files for all projects using uv..."
	files=$$(find . -name pyproject.toml -maxdepth 2); \
	for path in $$files; do \
		project_dir=$$(dirname $$path); \
		echo "Processing $$path..."; \
		uv lock --project $$project_dir --check; \
		echo "Exporting main dependencies..."; \
		uv export --project $$project_dir --no-default-groups --format requirements-txt -o $$project_dir/requirements.txt; \
		if grep -q "\[dependency-groups\]" $$path && grep -q "dev =" $$path; then \
			echo "Exporting dev dependencies..."; \
			uv export --project $$project_dir --group dev --format requirements-txt -o $$project_dir/requirements-dev.txt; \
		else \
			echo "No dev group, skipping requirements-dev.txt..."; \
		fi; \
	done
