import json
import zipfile
from io import BytesIO

import structlog
from account.mixins import OrganizationView
from django.contrib import messages
from django.http import FileResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from httpx import HTTPError

logger = structlog.get_logger(__name__)


class BytesRawView(OrganizationView):
    def get(self, request, **kwargs):
        self.bytes_client.login()
        boefje_meta_id = kwargs["boefje_meta_id"]
        try:
            raw_metas = self.bytes_client.get_raw_metas(boefje_meta_id, self.organization.code)
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
        for raw_meta in raw_metas:
            zf.writestr(raw_meta["id"], raws[raw_meta["id"]])
            zf.writestr(f"raw_meta_{raw_meta['id']}.json", json.dumps(raw_meta))

    zf_buffer.seek(0)

    return zf_buffer
