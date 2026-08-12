import json
from functools import partial

import sqlalchemy
import structlog

from scheduler.config import settings
from scheduler.storage.errors import StorageError


class DBConn:
    def __init__(self, dsn: str, pool_size: int = 25):
        self.logger: structlog.BoundLogger = structlog.getLogger(__name__)

        self.dsn = dsn
        self.pool_size = pool_size

    def connect(self) -> None:
        db_uri_redacted = sqlalchemy.engine.make_url(name_or_url=self.dsn).render_as_string(hide_password=True)

        pool_size = settings.Settings().db_connection_pool_size

        self.logger.debug(
            "Connecting to database %s with pool size %s...",
            self.dsn,
            pool_size,
            dsn=db_uri_redacted,
            pool_size=pool_size,
        )

        try:
            serializer = partial(json.dumps, default=str)
            self.engine = sqlalchemy.create_engine(
                self.dsn,
                pool_pre_ping=True,
                pool_size=pool_size,
                pool_recycle=300,
                json_serializer=serializer,
                connect_args={"options": "-c timezone=utc"},
            )
        except sqlalchemy.exc.SQLAlchemyError as e:
            self.logger.error("Failed to connect to database %s: %s", self.dsn, e, dsn=db_uri_redacted)
            raise StorageError("Failed to connect to database.")

        self.logger.debug("Connected to database %s.", db_uri_redacted, dsn=db_uri_redacted)

        try:
            self.session = sqlalchemy.orm.sessionmaker(bind=self.engine)
        except sqlalchemy.exc.SQLAlchemyError as e:
            self.logger.error("Failed to create session: %s", e)
            raise StorageError("Failed to create session.")
