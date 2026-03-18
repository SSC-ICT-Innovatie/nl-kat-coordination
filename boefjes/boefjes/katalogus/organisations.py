from fastapi import APIRouter, Depends, HTTPException, status

from boefjes.sql.db import ObjectNotFoundException
from boefjes.sql.organisation_storage import get_organisations_store
from boefjes.storage.interfaces import OrganisationStorage
from boefjes.worker.models import Organisation

router = APIRouter(prefix="/organisations", tags=["organisations"])


@router.get("", response_model=dict[str, Organisation])
def list_organisations(storage: OrganisationStorage = Depends(get_organisations_store)):
    with storage as store:
        return store.get_all()


@router.get("/{organisation_id}", response_model=Organisation)
def get_organisation(organisation_id: str, storage: OrganisationStorage = Depends(get_organisations_store)):
    try:
        with storage as store:
            return store.get_by_id(organisation_id)
    except (KeyError, ObjectNotFoundException):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown organisation")


@router.post("/", status_code=status.HTTP_201_CREATED)
def add_organisation(organisation: Organisation, storage: OrganisationStorage = Depends(get_organisations_store)):
    with storage as store:
        store.create(organisation)


@router.put("/")
def upsert_organisation(organisation: Organisation, storage: OrganisationStorage = Depends(get_organisations_store)):
    with storage as store:
        store.update(organisation)


@router.delete("/{organisation_id}")
def remove_organisation(organisation_id: str, storage: OrganisationStorage = Depends(get_organisations_store)):
    with storage as store:
        store.delete_by_id(organisation_id)
