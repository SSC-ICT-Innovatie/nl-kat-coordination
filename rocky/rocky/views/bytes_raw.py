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


class BytesRawView(OrganizationView):
    def get(self, request, **kwargs):
        boefje_meta_id = kwargs["boefje_meta_id"]
        try:
            raw_metas = self.bytes_client.get_raw_metas(boefje_meta_id, self.organization.code)
            _strip_environment_secrets(raw_metas, self.katalogus_client)
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


def _strip_environment_secrets(raw_metas: list[dict], katalogus_client) -> None:
    """Strip only secret-marked fields from the boefje environment, not the entire
    environment (#4508). If the schema can't be retrieved, strip everything as a
    fail-safe."""
    if not raw_metas:
        return
    boefje_id = raw_metas[0]["boefje_meta"]["boefje"]["id"]
    try:
        plugin = katalogus_client.get_plugin(boefje_id)
        secret_fields = (getattr(plugin, "boefje_schema", None) or {}).get("secret", [])
    except Exception:
        logger.exception("Could not retrieve boefje schema; stripping entire environment")
        for raw_meta in raw_metas:
            raw_meta["boefje_meta"].pop("environment", None)
        return
    for raw_meta in raw_metas:
        env = raw_meta["boefje_meta"].get("environment")
        if env:
            for key in secret_fields:
                env.pop(key, None)


def zip_data(raws: dict[str, bytes], raw_metas: list[dict]) -> BytesIO:
    zf_buffer = BytesIO()

    with zipfile.ZipFile(zf_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for raw_meta in raw_metas:
            zf.writestr(raw_meta["id"], raws[raw_meta["id"]])
            zf.writestr(f"raw_meta_{raw_meta['id']}.json", json.dumps(raw_meta))

    zf_buffer.seek(0)

    return zf_buffer
