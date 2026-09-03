import base64
import json
import zipfile
from http import HTTPStatus
from io import BytesIO

import structlog
from account.mixins import OrganizationView
from django.contrib import messages
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from httpx import HTTPError

logger = structlog.get_logger(__name__)

RAW_FILE_LIMIT = 1024 * 1024

_HASH_NOTE = (
    "Secret fields have been removed from the boefje metadata in this download.\n"
    "As a result, the hash of the metadata JSON will not match the hash stored\n"
    "in Bytes. The raw file data itself is unmodified and its hash is intact.\n"
)


def _strip_secret_fields(raw_metas: list[dict], katalogus_client) -> None:
    """Remove secret fields from boefje_meta.environment using the boefje
    schema's ``secret`` list, so they are not leaked via raw meta downloads
    (#4508). Falls back to removing the entire environment if the schema
    cannot be fetched — fail-closed for security."""
    schema_cache: dict[str, set[str] | None] = {}

    for raw_meta in raw_metas:
        boefje_meta = raw_meta.get("boefje_meta")
        if not isinstance(boefje_meta, dict):
            continue
        environment = boefje_meta.get("environment")
        if not isinstance(environment, dict) or not environment:
            continue

        boefje_id = boefje_meta.get("boefje", {}).get("id", "")
        if boefje_id not in schema_cache:
            try:
                plugin = katalogus_client.get_plugin(boefje_id)
                schema = getattr(plugin, "boefje_schema", None) or {}
                schema_cache[boefje_id] = set(schema.get("secret", []))
            except Exception:
                logger.exception("Failed to fetch boefje schema, stripping entire environment")
                schema_cache[boefje_id] = None  # fail closed

        secrets = schema_cache[boefje_id]
        if secrets is None:
            boefje_meta.pop("environment", None)
        else:
            for key in secrets:
                environment.pop(key, None)


class BytesRawView(OrganizationView):
    def get(self, request, **kwargs):
        boefje_meta_id = kwargs["boefje_meta_id"]
        try:
            raw_metas = self.bytes_client.get_raw_metas(boefje_meta_id, self.organization.code)
            _strip_secret_fields(raw_metas, self.katalogus_client)
            is_json_format = request.GET.get("format") == "json"
            if is_json_format:
                size_limit = int(request.GET.get("size_limit", RAW_FILE_LIMIT))
                for raw_meta in raw_metas:
                    raw_meta["raw_file"] = base64.b64encode(
                        self.bytes_client.get_raw(raw_meta["id"])[:size_limit]
                    ).decode("ascii")
                return JsonResponse(raw_metas, safe=False)
        except Http404:
            msg = _("Getting raw data failed, No such meta.")
            logger.exception("Getting raw data failed, No such meta")
            messages.add_message(request, messages.ERROR, msg)

            if request.GET.get("format", False) != "json":
                messages.add_message(request, messages.ERROR, msg)

                return redirect(reverse("task_list", kwargs={"organization_code": self.organization.code}))
            return JsonResponse({"error": msg}, status=HTTPStatus.NOT_FOUND)
        except HTTPError:
            msg = _("Getting raw data failed.")
            logger.exception("Getting raw data failed")
            messages.add_message(request, messages.ERROR, msg)
            return redirect(reverse("task_list", kwargs={"organization_code": self.organization.code}))

        if not raw_metas:
            msg = _("The task does not have any raw data.")
            messages.add_message(request, messages.ERROR, msg)
            return redirect(reverse("task_list", kwargs={"organization_code": self.organization.code}))

        raws = {raw_meta["id"]: self.bytes_client.get_raw(raw_meta["id"]) for raw_meta in raw_metas}
        response = FileResponse(zip_data(raws, raw_metas), filename=f"{boefje_meta_id}.zip")
        logger.info("Raw files have been downloaded", boefje_meta_id=boefje_meta_id, event_code="700001")

        return response


def zip_data(raws: dict[str, bytes], raw_metas: list[dict]) -> BytesIO:
    zf_buffer = BytesIO()

    with zipfile.ZipFile(zf_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("NOTE.txt", _HASH_NOTE)
        for raw_meta in raw_metas:
            zf.writestr(raw_meta["id"], raws[raw_meta["id"]])
            zf.writestr(f"raw_meta_{raw_meta['id']}.json", json.dumps(raw_meta))

    zf_buffer.seek(0)

    return zf_buffer
