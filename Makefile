.PHONY: build run test export_migrations debian clean plugins up
HIDE:=$(if $(VERBOSE),,@)

UNAME := $(shell uname)

# Export Docker buildkit options
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

run := docker compose run --rm -e DATABASE_MIGRATION=false openkat
exec := docker compose exec -T openkat


kat:
	make kat_parallel -j 4

up: build
	docker compose up -d
	sleep 2
	-$(exec) python manage.py createsuperuser --no-input || (sleep 2 && $(exec) python manage.py createsuperuser --no-input)
	make init
	make seed

kat_parallel: frontend up images
init: messages static

clean: .env
	docker compose down --timeout 0 --volumes --remove-orphans
	-rm -Rf node_modules assets/dist .parcel-cache static media *.egg-info

object-clean: .env
	docker compose down --volumes xtdb
	docker compose up -d
	sleep 5
	make seed

build: .env
ifeq ($(UNAME),Darwin)
	docker compose build --pull --build-arg USER_UID="$$(id -u)"
else
	docker compose build --pull --build-arg USER_UID="$$(id -u)" --build-arg USER_GID="$$(id -g)"
endif

reset:
	make clean
	make kat

login:
	@OPENKAT_DB_HOST=localhost python manage.py login

user:
	-$(exec) python manage.py createsuperuser --no-input

seed:
	$(exec) python manage.py seed

messages:
	$(exec) python manage.py compilemessages

static:
	-$(exec) python manage.py collectstatic

frontend:
	docker run --rm -v $$PWD:/app/openkat node:20-bookworm sh -c "cd /app/openkat && yarn --ignore-engine && yarn build && chown -R $$(id -u) .parcel-cache node_modules assets/dist"

export REGISTRY=ghcr.io/minvws/openkat

images: plugins

plugins:
	docker build -f plugins/plugins/plugins.Dockerfile -t $(REGISTRY)/plugins:0.1.0 -t $(REGISTRY)/plugins:latest -t openkat/plugins .

testclean:
	docker compose -f .ci/docker-compose.yml down --timeout 0 --remove-orphans --volumes
ifeq ($(UNAME),Darwin)
	docker compose -f .ci/docker-compose.yml build --pull --build-arg USER_UID="$$(id -u)"
else
	docker compose -f .ci/docker-compose.yml build --pull --build-arg USER_UID="$$(id -u)" --build-arg USER_GID="$$(id -g)"
endif

utest: testclean ## Run the unit tests.
	docker compose -f .ci/docker-compose.yml run --rm openkat_tests

itest: testclean ## Run the integration tests.
	docker compose -f .ci/docker-compose.yml run --rm openkat_integration

bench:
	pytest -n 0 --benchmark-only tests/objects/test_bench.py

languages:
# Extracts strings to `.pot` file which should be translated
# Note that the creation of `.po` files is delegated to another tool (Weblate)
	python manage.py makemessages -i "venv/*" -i "build/*" -i "node_modules/*" --verbosity 2 --add-location file -a --keep-pot --no-obsolete

lang: languages

check:
	pre-commit run --all-files --show-diff-on-failure --color always

# Create .env file from the env-dist with randomly generated credentials from vars annotated by "{%EXAMPLE_VAR}"
.env:
	cp .env-dist .env
	echo "Initializing .env with random credentials"
ifeq ($(UNAME), Darwin)  # Different sed on MacOS
	$(HIDE) grep -o "{%\([_A-Z]*\)}" .env-dist | sort -u | while read v; do sed -i '' "s/$$v/$$(openssl rand -hex 25)/g" .env; done
else
	$(HIDE) grep -o "{%\([_A-Z]*\)}" .env-dist | sort -u | while read v; do sed -i "s/$$v/$$(openssl rand -hex 25)/g" .env; done
endif
