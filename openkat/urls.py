from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import TemplateView
from django.views.i18n import JavaScriptCatalog
from rest_framework import routers
from two_factor.urls import urlpatterns as tf_urls

from files.viewsets import FileDownloadView, FileViewSet
from objects.urls import object_router
from openkat.views.account import AccountView
from openkat.views.landing_page import LandingPageView
from openkat.views.login import LoginOpenKATView, LogoutOpenKATView, SetupOpenKATView
from openkat.views.organization_add import OrganizationAddView
from openkat.views.organization_edit import OrganizationEditView
from openkat.views.organization_list import OrganizationListView
from openkat.views.organization_member_add import (
    DownloadMembersTemplateView,
    MembersUploadView,
    OrganizationMemberAddAccountTypeView,
    OrganizationMemberAddView,
)
from openkat.views.organization_member_edit import OrganizationMemberEditView
from openkat.views.organization_member_list import OrganizationMemberListView
from openkat.views.organization_settings import OrganizationSettingsView
from openkat.views.password_reset import PasswordResetConfirmView, PasswordResetView
from openkat.views.recover_email import RecoverEmailView
from openkat.viewsets import OrganizationViewSet
from tasks.viewsets import TaskViewSet

handler404 = "openkat.views.handler404.handler404"
handler403 = "openkat.views.handler403.handler403"

router = routers.SimpleRouter(use_regex_path=False)
router.register(r"organization", OrganizationViewSet)
router.register(r"task", TaskViewSet, basename="task")
router.register(r"file", FileViewSet, basename="file")


urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("api/v1/", include(router.urls)),
    path("api/v1/objects/", include(object_router.urls)),
    path("", include(tf_urls)),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path("api/v1/file/<slug:pk>/download/", FileDownloadView.as_view(actions={"get": "get"}), name="download"),
]
urlpatterns += i18n_patterns(
    path("<int:organization_id>/account/", AccountView.as_view(), name="account_detail"),
    path("login/", LoginOpenKATView.as_view(), name="login"),
    path("logout/", LogoutOpenKATView.as_view(), name="logout"),
    path("two_factor/setup/", SetupOpenKATView.as_view(), name="setup"),
    path("recover-email/", RecoverEmailView.as_view(), name="recover_email"),
    path("password_reset/", PasswordResetView.as_view(), name="password_reset"),
    path("reset/<uidb64>/<token>/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("admin/", admin.site.urls),
    path("", LandingPageView.as_view(), name="landing_page"),
    # New view:
    path("", include("plugins.urls"), name="plugins"),
    path("", include("tasks.urls"), name="tasks"),
    path("", include("files.urls"), name="files"),
    path("", include("objects.urls"), name="objects"),
    path("reports/", include("reports.urls"), name="reports"),
    path("organizations/", OrganizationListView.as_view(), name="organization_list"),
    path("organizations/add/", OrganizationAddView.as_view(), name="organization_add"),
    path("<int:organization_id>/settings/edit/", OrganizationEditView.as_view(), name="organization_edit"),
    path(
        "<int:organization_id>/members/add/",
        OrganizationMemberAddAccountTypeView.as_view(),
        name="organization_member_add_account_type",
    ),
    path(
        "<int:organization_id>/members/add/<account_type>/",
        OrganizationMemberAddView.as_view(),
        name="organization_member_add",
    ),
    path(
        "<int:organization_id>/members/upload/member_template",
        DownloadMembersTemplateView.as_view(),
        name="download_organization_member_template",
    ),
    path("<int:organization_id>/members/upload/", MembersUploadView.as_view(), name="organization_member_upload"),
    path("<int:organization_id>/settings", OrganizationSettingsView.as_view(), name="organization_settings"),
    path("<int:organization_id>/members", OrganizationMemberListView.as_view(), name="organization_member_list"),
    path(
        "<int:organization_id>/members/edit/<int:pk>/",
        OrganizationMemberEditView.as_view(),
        name="organization_member_edit",
    ),
)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# used by recurrence
urlpatterns += [path("jsi18n.js", JavaScriptCatalog.as_view(packages=["recurrence"]), name="jsi18n")]

if settings.DEBUG_TOOLBAR:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()
