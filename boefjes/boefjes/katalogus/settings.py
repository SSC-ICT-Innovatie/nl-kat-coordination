from fastapi import APIRouter, Depends

from boefjes.dependencies.plugins import PluginService, get_plugin_service

router = APIRouter(prefix="/organisations/{organisation_id}/{plugin_id}/settings", tags=["settings"])


@router.get("", response_model=dict)
def list_settings(
    organisation_id: str, plugin_id: str, plugin_service: PluginService = Depends(get_plugin_service)
) -> dict[str, str]:
    with plugin_service as p:
        return p.get_all_settings(organisation_id, plugin_id)


@router.put("")
def upsert_settings(
    organisation_id: str, plugin_id: str, values: dict, plugin_service: PluginService = Depends(get_plugin_service)
) -> None:
    with plugin_service as p:
        p.upsert_settings(values, organisation_id, plugin_id)


@router.delete("")
def remove_settings(
    organisation_id: str, plugin_id: str, plugin_service: PluginService = Depends(get_plugin_service)
) -> None:
    with plugin_service as p:
        p.delete_settings(organisation_id, plugin_id)
