from django_downloadview import ObjectDownloadView
from rest_framework import mixins, viewsets
from structlog import get_logger

from files.models import File
from files.serializers import FileSerializer
from tasks.models import TaskResult
from tasks.tasks import process_raw_file

logger = get_logger(__name__)


class FileViewSet(viewsets.ModelViewSet):
    serializer_class = FileSerializer
    queryset = File.objects.all()
    search_fields = ["file"]

    def get_queryset(self):
        qs = super().get_queryset()

        if "type" in self.request.GET:
            qs = qs.filter(type=self.request.GET["type"])

        return qs

    def perform_create(self, serializer):
        file = serializer.save()

        if "task_id" in self.request.GET:
            TaskResult.objects.create(file=file, task_id=self.request.GET["task_id"])

        process_raw_file(file)


class FileDownloadView(viewsets.GenericViewSet, mixins.RetrieveModelMixin, ObjectDownloadView):
    queryset = File.objects.all()
    permission_required = ("files.view_file", "files.download_file")
