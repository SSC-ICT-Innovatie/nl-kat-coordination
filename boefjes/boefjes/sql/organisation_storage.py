from collections.abc import Iterator

import structlog
from sqlalchemy.orm import Session

from boefjes.config import Settings, settings
from boefjes.sql.db import ObjectNotFoundException, session_managed_iterator
from boefjes.sql.db_models import OrganisationInDB
from boefjes.sql.session import SessionMixin
from boefjes.storage.interfaces import OrganisationNotFound, OrganisationStorage
from boefjes.worker.models import Organisation

logger = structlog.get_logger(__name__)


class SQLOrganisationStorage(SessionMixin, OrganisationStorage):
    def __init__(self, session: Session, app_settings: Settings):
        self.app_settings = app_settings

        super().__init__(session)

    def get_by_id(self, organisation_id: str) -> Organisation:
        instance = self._db_instance_by_id(organisation_id)

        return self.to_organisation(instance)

    def get_all(self) -> dict[str, Organisation]:
        query = self.session.query(OrganisationInDB)

        return {organisation.id: self.to_organisation(organisation) for organisation in query.all()}

    def create(self, organisation: Organisation) -> None:
        logger.info("Saving organisation: %s", organisation.model_dump_json())

        organisation_in_db = self.to_organisation_in_db(organisation)
        self.session.add(organisation_in_db)

    def update(self, organisation: Organisation) -> None:
        instance = self._db_instance_by_id(organisation.id)
        instance.name = organisation.name
        instance.deduplicate = organisation.deduplicate

    def delete_by_id(self, organisation_id: str) -> None:
        instance = self._db_instance_by_id(organisation_id)

        self.session.delete(instance)

    def _db_instance_by_id(self, organisation_id: str) -> OrganisationInDB:
        instance = self.session.query(OrganisationInDB).filter(OrganisationInDB.id == organisation_id).first()

        if instance is None:
            raise OrganisationNotFound(organisation_id) from ObjectNotFoundException(
                OrganisationInDB, id=organisation_id
            )

        return instance

    @staticmethod
    def to_organisation_in_db(organisation: Organisation) -> OrganisationInDB:
        return OrganisationInDB(id=organisation.id, name=organisation.name, deduplicate=organisation.deduplicate)

    @staticmethod
    def to_organisation(organisation_in_db: OrganisationInDB) -> Organisation:
        return Organisation(
            id=organisation_in_db.id, name=organisation_in_db.name, deduplicate=organisation_in_db.deduplicate
        )


def create_organisation_storage(session: Session) -> SQLOrganisationStorage:
    return SQLOrganisationStorage(session, settings)


def get_organisations_store() -> Iterator[OrganisationStorage]:
    yield from session_managed_iterator(create_organisation_storage)
