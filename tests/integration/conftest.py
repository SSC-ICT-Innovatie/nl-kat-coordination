from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from django.conf import settings
from django.core.management import call_command
from pytest_django import DjangoDbBlocker
from pytest_django.fixtures import _disable_migrations, _get_databases_for_setup


@pytest.fixture
def valid_time():
    return datetime.now(UTC)


@pytest.fixture(autouse=True)
def flush_db():
    """We use the same database as a test mirror in the integration tests. This makes sure the database gets cleaned
    between tests in spite of the @pytest.mark.django_db(transaction=True)."""

    yield
    call_command("flush", verbosity=0, interactive=False)


@pytest.fixture(scope="session")
def django_db_setup(
    request: pytest.FixtureRequest,
    django_test_environment: None,  # noqa: ARG001
    django_db_blocker: DjangoDbBlocker,
    django_db_use_migrations: bool,
    django_db_keepdb: bool,
    django_db_createdb: bool,
    django_db_modify_db_settings: None,  # noqa: ARG001
) -> Generator[None]:
    """
    Make sure openkat-test-api and openkat_integration in .ci/docker-compose.yml use the same database:
    Since openkat_integration calls pytest, it creates a test database by default within ci_postgres, where the
    openkat-test-api will use the regular database. This will result in the API not knowing about plugins, users or
    Authtokens created during the test, but we need this since plugins created during the test have openkat-test-api
    as a callback service.
    """
    settings.DATABASES["default"]["TEST"]["MIRROR"] = "default"

    # Original fixture code:
    """Top level fixture to ensure test databases are available"""
    from django.test.utils import setup_databases, teardown_databases  # noqa: PLC0415

    setup_databases_args = {}

    if not django_db_use_migrations:
        _disable_migrations()

    if django_db_keepdb and not django_db_createdb:
        setup_databases_args["keepdb"] = True

    aliases, serialized_aliases = _get_databases_for_setup(request.session.items)

    with django_db_blocker.unblock():
        db_cfg = setup_databases(
            verbosity=request.config.option.verbose,
            interactive=False,
            aliases=aliases,
            serialized_aliases=serialized_aliases,
            **setup_databases_args,
        )

    yield

    if not django_db_keepdb:
        with django_db_blocker.unblock():
            try:
                teardown_databases(db_cfg, verbosity=request.config.option.verbose)
            except Exception as exc:  # noqa: BLE001
                request.node.warn(pytest.PytestWarning(f"Error when trying to teardown test databases: {exc!r}"))
