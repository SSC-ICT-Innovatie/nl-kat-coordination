from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from bytes.database.db import SQL_BASE


class BoefjeMetaInDB(SQL_BASE):
    __tablename__ = "boefje_meta"

    id = Column(UUID, primary_key=True)
    boefje_id = Column(String(length=64), nullable=False)
    boefje_version = Column(String(length=16))
    organization = Column(String(length=32), nullable=False)
    input_ooi = Column(String(length=1024), nullable=True)
    arguments = Column(JSON, nullable=False, default=lambda: {})
    environment = Column(JSON, nullable=True, default=lambda: {})
    runnable_hash = Column(String(length=64), nullable=True)

    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))


Index("ix_boefje_meta_organization_boefje_id", BoefjeMetaInDB.organization, BoefjeMetaInDB.boefje_id)
Index(
    "ix_boefje_meta_lookup",
    BoefjeMetaInDB.organization,
    BoefjeMetaInDB.boefje_id,
    BoefjeMetaInDB.input_ooi,
    BoefjeMetaInDB.started_at.desc(),
)


class SigningProviderInDB(SQL_BASE):
    __tablename__ = "signing_provider"

    id = Column(Integer, primary_key=True, autoincrement=True)

    url = Column(String(length=256), nullable=False, unique=True)


class RawFileInDB(SQL_BASE):
    __tablename__ = "raw_file"

    id = Column(UUID, primary_key=True)

    secure_hash = Column(String(length=256), nullable=True)
    hash_retrieval_link = Column(String(length=2048), nullable=True)

    signing_provider_id = Column(
        Integer, ForeignKey("signing_provider.id", ondelete="CASCADE"), nullable=True, index=True
    )
    signing_provider = relationship("SigningProviderInDB")

    boefje_meta_id = Column(UUID, ForeignKey("boefje_meta.id", ondelete="CASCADE"), nullable=False, index=True)
    boefje_meta = relationship("BoefjeMetaInDB")

    mime_types = Column(ARRAY(String(length=64)), default=lambda: [])


class NormalizerMetaInDB(SQL_BASE):
    __tablename__ = "normalizer_meta"

    id = Column(UUID, primary_key=True)
    normalizer_id = Column(String(length=64), nullable=False)
    normalizer_version = Column(String(length=16))
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))

    raw_file_id = Column(UUID, ForeignKey("raw_file.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_file = relationship("RawFileInDB")
