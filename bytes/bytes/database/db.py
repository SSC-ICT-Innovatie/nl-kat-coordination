from functools import cache

import structlog
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import declarative_base

logger = structlog.get_logger(__name__)

SQL_BASE = declarative_base()


@cache
def get_engine(db_uri: str, pool_size: int) -> Engine:
    """Returns database engine according to config settings."""
    db_uri_redacted = make_url(name_or_url=str(db_uri)).render_as_string(hide_password=True)
    logger.info("Connecting to database %s with pool size %s...", db_uri_redacted, pool_size)

    engine = create_engine(db_uri, pool_pre_ping=True, pool_size=pool_size, connect_args={"options": "-c timezone=utc"})

    logger.info("Connected to database %s.", db_uri_redacted)

    return engine
