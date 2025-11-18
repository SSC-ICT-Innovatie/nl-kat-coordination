import datetime
import uuid
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import models


def raw_file_name(instance: "File", path: str) -> str:
    return f"files/{datetime.date.today()}/{instance.type}/{path}"


class File(models.Model):
    file = models.FileField(upload_to=raw_file_name)  # the name kwarg will determine the rest of the path
    type = models.CharField(max_length=128, blank=True)
    organizations = models.ManyToManyField("openkat.organization", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def path(self):
        return Path(self.file.name)

    def save(self, *args, **kwargs):
        if not self.type:
            self.type = self.path().suffix.lstrip(".")

        return super().save(*args, **kwargs)

    class Meta:
        permissions = (("download_file", "Can download files"),)


class GenericContent(ContentFile):
    def __init__(self, content: str | bytes):
        super().__init__(content, name=f"data/{uuid.uuid4()}")


class TemporaryContent(ContentFile):
    def __init__(self, content: str | bytes):
        super().__init__(content, name=f"tmp/{uuid.uuid4()}")


class PluginContent(ContentFile):
    def __init__(self, content: str | bytes, plugin_id: str):
        super().__init__(content, name=f"{plugin_id}/{uuid.uuid4()}")


class ReportContent(ContentFile):
    def __init__(self, content: str | bytes, name: str):
        super().__init__(content, name=f"reports/{name}.pdf")
