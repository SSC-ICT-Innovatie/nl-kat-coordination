from collections.abc import Iterator

import structlog
from sqlalchemy.orm import Session

from boefjes.config import Settings, settings
from boefjes.sql.db import ObjectNotFoundException, session_managed_iterator
from boefjes.sql.db_models import BoefjeInDB, NormalizerInDB, RunOnDB
from boefjes.sql.session import SessionMixin
from boefjes.storage.interfaces import NotAllowed, PluginNotFound, PluginStorage
from boefjes.worker.models import Boefje, Normalizer, PluginType

logger = structlog.get_logger(__name__)


class SQLPluginStorage(SessionMixin, PluginStorage):
    def __init__(self, session: Session, app_settings: Settings):
        self.app_settings = app_settings

        super().__init__(session)

    def get_all(self) -> list[PluginType]:
        boefjes = [self.to_boefje(boefje) for boefje in self.session.query(BoefjeInDB).all()]
        normalizers = [self.to_normalizer(normalizer) for normalizer in self.session.query(NormalizerInDB).all()]
        return boefjes + normalizers

    def boefje_by_id(self, boefje_id: str) -> Boefje:
        instance = self._db_boefje_instance_by_id(boefje_id)

        return self.to_boefje(instance)

    def normalizer_by_id(self, normalizer_id: str) -> Normalizer:
        instance = self._db_normalizer_instance_by_id(normalizer_id)

        return self.to_normalizer(instance)

    def create_boefje(self, boefje: Boefje) -> None:
        logger.info("Saving plugin: %s", boefje.model_dump_json())

        boefje_in_db = self.to_boefje_in_db(boefje)
        self.session.add(boefje_in_db)

    def update_boefje(self, boefje_id: str, data: dict) -> None:
        if not data:
            return

        instance = self._db_boefje_instance_by_id(boefje_id)

        if instance.static:
            raise NotAllowed(f"Plugin with id '{boefje_id}' is static, so updating it is not allowed")

        boefje = self.to_boefje(instance).copy(update=data)
        self.session.merge(self.to_boefje_in_db(boefje, instance.id))

    def create_normalizer(self, normalizer: Normalizer) -> None:
        logger.info("Saving plugin: %s", normalizer.model_dump_json())

        normalizer_in_db = self.to_normalizer_in_db(normalizer)
        self.session.add(normalizer_in_db)

    def update_normalizer(self, normalizer_id: str, data: dict) -> None:
        if not data:
            return

        instance = self._db_normalizer_instance_by_id(normalizer_id)

        if instance.static:
            raise NotAllowed(f"Plugin with id '{normalizer_id}' is static, so updating it is not allowed")

        normalizer = self.to_normalizer(instance).copy(update=data)
        self.session.merge(self.to_normalizer_in_db(normalizer, instance.id))

    def delete_boefje_by_id(self, boefje_id: str) -> None:
        instance = self._db_boefje_instance_by_id(boefje_id)

        self.session.delete(instance)

    def delete_normalizer_by_id(self, normalizer_id: str) -> None:
        instance = self._db_normalizer_instance_by_id(normalizer_id)

        self.session.delete(instance)

    def _db_boefje_instance_by_id(self, boefje_id: str) -> BoefjeInDB:
        instance = self.session.query(BoefjeInDB).filter(BoefjeInDB.plugin_id == boefje_id).first()

        if instance is None:
            raise PluginNotFound(boefje_id) from ObjectNotFoundException(BoefjeInDB, id=boefje_id)

        return instance

    def _db_normalizer_instance_by_id(self, normalizer_id: str) -> NormalizerInDB:
        instance = self.session.query(NormalizerInDB).filter(NormalizerInDB.plugin_id == normalizer_id).first()

        if instance is None:
            raise PluginNotFound(normalizer_id) from ObjectNotFoundException(NormalizerInDB, id=normalizer_id)

        return instance

    @staticmethod
    def to_boefje_in_db(boefje: Boefje, pk: int | None = None) -> BoefjeInDB:
        run_on_db = RunOnDB.from_run_ons(boefje.run_on)
        boefje = BoefjeInDB(
            plugin_id=boefje.id,
            created=boefje.created,
            name=boefje.name,
            description=boefje.description,
            scan_level=str(boefje.scan_level),
            consumes=boefje.consumes,
            produces=boefje.produces,
            schema=boefje.boefje_schema,
            cron=boefje.cron,
            interval=boefje.interval,
            run_on=run_on_db.value if run_on_db is not None else None,
            oci_image=boefje.oci_image,
            oci_arguments=boefje.oci_arguments,
            version=boefje.version,
            static=boefje.static,
            deduplicate=boefje.deduplicate,
        )

        if pk is not None:
            boefje.id = pk

        return boefje

    @staticmethod
    def to_normalizer_in_db(normalizer: Normalizer, pk: int | None = None) -> NormalizerInDB:
        normalizer = NormalizerInDB(
            plugin_id=normalizer.id,
            created=normalizer.created,
            name=normalizer.name,
            description=normalizer.description,
            consumes=normalizer.consumes,
            produces=normalizer.produces,
            version=normalizer.version,
            static=normalizer.static,
        )

        if pk is not None:
            normalizer.id = pk

        return normalizer

    @staticmethod
    def to_boefje(boefje_in_db: BoefjeInDB) -> Boefje:
        return Boefje(
            id=boefje_in_db.plugin_id,
            name=boefje_in_db.name,
            plugin_id=boefje_in_db.id,
            created=boefje_in_db.created,
            description=boefje_in_db.description,
            scan_level=int(boefje_in_db.scan_level),
            consumes=boefje_in_db.consumes,
            produces=boefje_in_db.produces,
            boefje_schema=boefje_in_db.schema,
            cron=boefje_in_db.cron,
            interval=boefje_in_db.interval,
            run_on=RunOnDB(boefje_in_db.run_on).to_run_ons() if boefje_in_db.run_on else None,
            oci_image=boefje_in_db.oci_image,
            oci_arguments=boefje_in_db.oci_arguments,
            version=boefje_in_db.version,
            static=boefje_in_db.static,
            deduplicate=boefje_in_db.deduplicate,
        )

    @staticmethod
    def to_normalizer(normalizer_in_db: NormalizerInDB) -> Normalizer:
        return Normalizer(
            id=normalizer_in_db.plugin_id,
            name=normalizer_in_db.name,
            plugin_id=normalizer_in_db.id,
            created=normalizer_in_db.created,
            description=normalizer_in_db.description,
            consumes=normalizer_in_db.consumes,
            produces=normalizer_in_db.produces,
            version=normalizer_in_db.version,
            static=normalizer_in_db.static,
        )


def create_plugin_storage(session) -> SQLPluginStorage:
    return SQLPluginStorage(session, settings)


def get_plugin_storage() -> Iterator[PluginStorage]:
    yield from session_managed_iterator(create_plugin_storage)
