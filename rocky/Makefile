.PHONY: build build-rocky build-rocky-frontend run test export_migrations debian clean


# Export Docker buildkit options
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Do not turn on OpenTelemetry when building Rocky
unexport SPAN_EXPORT_GRPC_ENDPOINT

build: build-rocky build-rocky-frontend

build-rocky:
# Set DATABASE_MIGRATION=false to prevent entrypoint from running migration
	docker compose run --rm -e DATABASE_MIGRATION=false rocky make build-rocky-native

dashboards:
	docker compose run --rm rocky python3 manage.py dashboards

build-rocky-native:
	while ! nc -vz $$ROCKY_DB_HOST $$ROCKY_DB_PORT; do sleep 0.1; done
	python3 manage.py migrate
	-python3 manage.py createsuperuser --no-input
	python3 manage.py loaddata OOI_database_seed.json
	python3 manage.py setup_dev_account
	python3 manage.py compilemessages

build-rocky-frontend:
	docker run --rm -v $$PWD:/app/rocky node:20-bookworm sh -c "cd /app/rocky && yarn --ignore-engine && yarn build && chown -R $$(id -u) .parcel-cache node_modules assets/dist"

almost-flush:
	docker compose run --rm rocky python manage.py almost_flush

run:
	python3 manage.py runserver

test:
	python3 manage.py test

testclean:
	docker compose -f .ci/docker-compose.yml kill
	docker compose -f .ci/docker-compose.yml down --remove-orphans
	docker compose -f .ci/docker-compose.yml build

utest: testclean ## Run the unit tests.
	docker compose -f .ci/docker-compose.yml run --rm rocky_tests

itest: testclean ## Run the integration tests.
	docker compose -f .ci/docker-compose.yml run --rm rocky_integration

bench: testclean ## Run the report benchmark.
	docker compose -f .ci/docker-compose.yml run --rm rocky_integration \
	python -m cProfile -o .ci/bench_$$(date +%Y_%m_%d-%H:%M:%S).pstat -m pytest -m slow --no-cov tests/integration

export_migrations:
	python3 manage.py export_migrations contenttypes 0001
	python3 manage.py export_migrations auth 0001
	python3 manage.py export_migrations admin 0001
	python3 manage.py export_migrations sessions 0001
	python3 manage.py export_migrations two_factor 0001
	python3 manage.py export_migrations otp_static 0001
	python3 manage.py export_migrations otp_totp 0001
	python3 manage.py export_migrations tools 0001
	python3 manage.py export_migrations fmea 0001
	python3 manage.py export_migrations accounts 0001
	python3 manage.py export_migrations crisis_room 0001

languages:
# Extracts strings to `.pot` file which should be translated
# Note that the creation of `.po` files is delegated to another tool (Weblate)
	python3 manage.py makemessages -i "venv/*" -i "build/*" -i "octopoes/*" -i "node_modules/*" --verbosity 2 --add-location file -a --keep-pot

lang: languages

debian12:
	mkdir -p build
	docker run --rm \
	--env PKG_NAME=kat-rocky \
	--env REPOSITORY=minvws/nl-kat-rocky \
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
	--env PKG_NAME=kat-rocky \
	--env REPOSITORY=minvws/nl-kat-rocky \
	--env RELEASE_VERSION=${RELEASE_VERSION} \
	--env RELEASE_TAG=${RELEASE_TAG} \
	--mount type=bind,src=${CURDIR},dst=/app \
	--mount type=bind,src=${CURDIR}/../octopoes,dst=/octopoes \
	--workdir /app \
	kat-ubuntu22.04-build-image \
	packaging/scripts/build-debian-package.sh

clean:
	rm -rf build
	rm -rf debian/kat-rocky/ debian/.debhelper debian/files static/ rocky.egg-info/ node_modules/ dist/
	rm -f debian/debhelper-build-stamp
	rm -f debian/kat-rocky.*.debhelper
	rm -f debian/kat-rocky.substvars
	rm -f debian/*.debhelper.log
	rm -f debian/changelog

check:
	pre-commit run --all-files --show-diff-on-failure --color always

test-prepare:
	python3 manage.py flush --no-input
	python3 manage.py migrate
	DJANGO_SUPERUSER_PASSWORD=robotpassword python3 manage.py createsuperuser --email robot@localhost --noinput
	python3 manage.py loaddata OOI_database_seed.json
	python3 manage.py setup_dev_account

test-rf: # Usage: `make test-rf headless=<bool>`
	pip3 install robotframework robotframework-browser robotframework-debuglibrary robotframework-otp robotframework-postgresqldb
	rfbrowser init

# Test fresh login while creating all users and running report generation as the superadmin
	docker exec -it nl-kat-coordination_rocky_1 make test-prepare
	robot -d tests/robot/results-complete_onboarding -v headless:$(headless) tests/robot/complete_onboarding

#test-rf-onboarding: # Usage: `make test-rf-onboarding headless=<bool>`
#	# Test fresh login while fully skipping onboarding
#	docker exec -it nl-kat_rocky_1 make test-prepare
#	robot -d tests/robot/results-skip_onboarding_no_report -v headless:$(headless) tests/robot/skip_onboarding_no_report
#
#	# Test fresh login while generating a report but not creating more user accounts
#	docker exec -it nl-kat_rocky_1 make test-prepare
#	robot -d tests/robot/results-skip_onboarding_with_report -v headless:$(headless) tests/robot/skip_onboarding_with_report
#
#	# Test fresh login while creating all users and running report generation as the redteamer
#	docker exec -it nl-kat_rocky_1 make test-prepare
#	robot -d tests/robot/results-complete_onboarding -v headless:$(headless) tests/robot/complete_onboarding
#
#	# You can run `make reset-database` manually after running tests to reset the database and create a new superuser account
#
#test-rf-functional: # Usage: `make test-rf-functional headless=<bool>`
#	# Test fresh login while fully skipping onboarding and running some functional tests
#	# These tests require clean databases
#	cd ../ && make kat
#	docker exec -it nl-kat_rocky_1 make test-prepare
#	robot -d tests/robot/results-skip_onboarding_with_functional_tests -v headless:$(headless) tests/robot/skip_onboarding_with_functional_tests
