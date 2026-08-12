from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import TemplateView
from reports.viewsets import ReportRecipeViewSet, ReportViewSet
from rest_framework import routers
from tools.viewsets import OrganizationViewSet
from two_factor.urls import urlpatterns as tf_urls

from rocky.views.bytes_raw import BytesRawView
from rocky.views.finding_add import FindingAddView
from rocky.views.finding_list import FindingListView
from rocky.views.finding_type_add import FindingTypeAddView
from rocky.views.health import Health, HealthChecks
from rocky.views.indemnification_add import IndemnificationAddView
from rocky.views.landing_page import LandingPageView
from rocky.views.ooi_add import OOIAddTypeSelectView, OOIAddView
from rocky.views.ooi_delete import OOIDeleteView
from rocky.views.ooi_detail import OOIDetailView
from rocky.views.ooi_detail_related_object import OOIRelatedObjectAddView
from rocky.views.ooi_edit import OOIEditView
from rocky.views.ooi_findings import OOIFindingListView
from rocky.views.ooi_list import OOIListExportView, OOIListView
from rocky.views.ooi_mute import MuteFindingsBulkView, MuteFindingView
from rocky.views.ooi_tree import OOIGraphView, OOISummaryView, OOITreeView
from rocky.views.organization_add import OrganizationAddView
from rocky.views.organization_edit import OrganizationEditView
from rocky.views.organization_list import OrganizationListView
from rocky.views.organization_member_add import (
    DownloadMembersTemplateView,
    MembersUploadView,
    OrganizationMemberAddAccountTypeView,
    OrganizationMemberAddView,
)
from rocky.views.organization_member_edit import OrganizationMemberEditView
from rocky.views.organization_member_list import OrganizationMemberListView
from rocky.views.organization_settings import OrganizationSettingsView
from rocky.views.privacy_statement import PrivacyStatementView
from rocky.views.scan_profile import ScanProfileDetailView
from rocky.views.scans import ScanListView
from rocky.views.task_detail import BoefjeTaskDetailView, DownloadTaskDetail, NormalizerTaskJSONView
from rocky.views.tasks import (
    AllBoefjesTaskListView,
    AllNormalizersTaskListView,
    AllReportsTaskListView,
    BoefjesTaskListView,
    NormalizersTaskListView,
    ReportsTaskListView,
)
from rocky.views.upload_csv import UploadCSV
from rocky.views.upload_raw import UploadRaw

handler404 = "rocky.views.handler404.handler404"
handler403 = "rocky.views.handler403.handler403"


router = routers.SimpleRouter()
router.register(r"organization", OrganizationViewSet)
router.register(r"report", ReportViewSet, basename="report")
router.register(r"report-recipe", ReportRecipeViewSet, basename="report-recipe")

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("api/v1/", include(router.urls)),
    path("<organization_code>/health/", Health.as_view(), name="health"),
    path("", include(tf_urls)),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
]
urlpatterns += i18n_patterns(
    path("", include("account.urls"), name="account"),
    path("admin/", admin.site.urls),
    path("", LandingPageView.as_view(), name="landing_page"),
    path("onboarding/", include("onboarding.urls"), name="onboarding"),
    path("crisis-room/", include("crisis_room.urls"), name="crisis_room"),
    path("privacy-statement/", PrivacyStatementView.as_view(), name="privacy_statement"),
    path("tasks/", AllBoefjesTaskListView.as_view(), name="all_task_list"),
    path("tasks/boefjes", AllBoefjesTaskListView.as_view(), name="all_boefjes_task_list"),
    path("tasks/normalizers", AllNormalizersTaskListView.as_view(), name="all_normalizers_task_list"),
    path("tasks/reports", AllReportsTaskListView.as_view(), name="all_reports_task_list"),
    path(
        "<organization_code>/settings/indemnifications/", IndemnificationAddView.as_view(), name="indemnification_add"
    ),
    path("<organization_code>/findings/", FindingListView.as_view(), name="finding_list"),
    path("<organization_code>/findings/add/", FindingAddView.as_view(), name="finding_add"),
    path("<organization_code>/findings/mute/", MuteFindingView.as_view(), name="finding_mute"),
    path("<organization_code>/findings/mute/bulk/", MuteFindingsBulkView.as_view(), name="finding_mute_bulk"),
    path("<organization_code>/findings/finding_type/add/", FindingTypeAddView.as_view(), name="finding_type_add"),
    path("<organization_code>/objects/graph/", OOIGraphView.as_view(), name="ooi_graph"),
    path("<organization_code>/objects/summary/", OOISummaryView.as_view(), name="ooi_summary"),
    path("<organization_code>/objects/tree/", OOITreeView.as_view(), name="ooi_tree"),
    path("<organization_code>/objects/findings/", OOIFindingListView.as_view(), name="ooi_findings"),
    path("organizations/", OrganizationListView.as_view(), name="organization_list"),
    path("organizations/add/", OrganizationAddView.as_view(), name="organization_add"),
    path("<organization_code>/settings/edit/", OrganizationEditView.as_view(), name="organization_edit"),
    path(
        "<organization_code>/members/add/",
        OrganizationMemberAddAccountTypeView.as_view(),
        name="organization_member_add_account_type",
    ),
    path(
        "<organization_code>/members/add/<account_type>/",
        OrganizationMemberAddView.as_view(),
        name="organization_member_add",
    ),
    path(
        "<organization_code>/members/upload/member_template",
        DownloadMembersTemplateView.as_view(),
        name="download_organization_member_template",
    ),
    path("<organization_code>/members/upload/", MembersUploadView.as_view(), name="organization_member_upload"),
    path("<organization_code>/settings", OrganizationSettingsView.as_view(), name="organization_settings"),
    path("<organization_code>/members", OrganizationMemberListView.as_view(), name="organization_member_list"),
    path(
        "<organization_code>/members/edit/<int:pk>/",
        OrganizationMemberEditView.as_view(),
        name="organization_member_edit",
    ),
    path("<organization_code>/health/v1/", HealthChecks.as_view(), name="health_beautified"),
    path("<organization_code>/objects/", OOIListView.as_view(), name="ooi_list"),
    path("<organization_code>/objects/add/", OOIAddTypeSelectView.as_view(), name="ooi_add_type_select"),
    path("<organization_code>/objects/add-related/", OOIRelatedObjectAddView.as_view(), name="ooi_add_related"),
    path("<organization_code>/objects/add/<ooi_type>/", OOIAddView.as_view(), name="ooi_add"),
    path("<organization_code>/objects/edit/", OOIEditView.as_view(), name="ooi_edit"),
    path("<organization_code>/objects/delete/", OOIDeleteView.as_view(), name="ooi_delete"),
    path("<organization_code>/objects/detail/", OOIDetailView.as_view(), name="ooi_detail"),
    path("<organization_code>/objects/export", OOIListExportView.as_view(), name="ooi_list_export"),
    path("<organization_code>/objects/scan-profile/", ScanProfileDetailView.as_view(), name="scan_profile_detail"),
    path("<organization_code>/objects/scans/", ScanListView.as_view(), name="scan_list"),
    path("<organization_code>/objects/upload/csv/", UploadCSV.as_view(), name="upload_csv"),
    path("<organization_code>/objects/upload/raw/", UploadRaw.as_view(), name="upload_raw"),
    path("<organization_code>/objects/upload/raw/<mime_type>", UploadRaw.as_view(), name="upload_raw_typed"),
    path("<organization_code>/tasks/", BoefjesTaskListView.as_view(), name="task_list"),
    path("<organization_code>/tasks/boefjes", BoefjesTaskListView.as_view(), name="boefjes_task_list"),
    path("<organization_code>/tasks/boefjes/<task_id>", BoefjeTaskDetailView.as_view(), name="boefje_task_view"),
    path("<organization_code>/tasks/normalizers", NormalizersTaskListView.as_view(), name="normalizers_task_list"),
    path("<organization_code>/tasks/reports", ReportsTaskListView.as_view(), name="reports_task_list"),
    path(
        "<organization_code>/tasks/normalizers/<task_id>", NormalizerTaskJSONView.as_view(), name="normalizer_task_view"
    ),
    path("<organization_code>/tasks/<task_id>/download/", DownloadTaskDetail.as_view(), name="download_task_meta"),
    path("<organization_code>/bytes/<boefje_meta_id>/raw", BytesRawView.as_view(), name="bytes_raw"),
    path("<organization_code>/kat-alogus/", include("katalogus.urls"), name="katalogus"),
    path("<organization_code>/reports/", include("reports.urls"), name="reports"),
)
