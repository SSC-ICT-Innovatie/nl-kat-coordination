from django.urls import path, re_path

from katalogus.views.boefje_setup import AddBoefjeVariantView, AddBoefjeView, EditBoefjeView
from katalogus.views.change_clearance_level import ChangeClearanceLevel
from katalogus.views.katalogus import (
    AboutPluginsView,
    BoefjeListView,
    KATalogusLandingView,
    KATalogusView,
    NormalizerListView,
)
from katalogus.views.katalogus_settings import ConfirmCloneSettingsView, KATalogusSettingsView
from katalogus.views.nibbles import NibblesToggleView, NibblesView
from katalogus.views.plugin_detail import BoefjeDetailView, NormalizerDetailView, PluginCoverImgView
from katalogus.views.plugin_enable_disable import PluginEnableDisableView
from katalogus.views.plugin_settings_add import PluginSettingsAddView
from katalogus.views.plugin_settings_delete import PluginSettingsDeleteView

urlpatterns = [
    path("", KATalogusLandingView.as_view(), name="katalogus"),
    path("settings/", KATalogusSettingsView.as_view(), name="katalogus_settings"),
    path("settings/migrate/", KATalogusSettingsView.as_view(), name="katalogus_clone_settings"),
    path(
        "settings/migrate/confirmation/<to_organization>/",
        ConfirmCloneSettingsView.as_view(),
        name="confirm_clone_settings",
    ),
    path("plugins/boefjes/add/", AddBoefjeView.as_view(), name="boefje_setup"),
    path("plugins/boefjes/add-variant/<plugin_id>/", AddBoefjeVariantView.as_view(), name="boefje_variant_setup"),
    re_path(r"^plugins/boefjes/(?P<view_type>(grid|table))/$", BoefjeListView.as_view(), name="boefjes_list"),
    path("plugins/normalizers/<view_type>/", NormalizerListView.as_view(), name="normalizers_list"),
    path("plugins/all/<view_type>/", KATalogusView.as_view(), name="all_plugins_list"),
    path("plugins/about-plugins/", AboutPluginsView.as_view(), name="about_plugins"),
    path("plugins/nibbles/<view_type>/", NibblesView.as_view(), name="nibbles_list"),
    path("plugins/nibbles/<nibble_id>/<state>/", NibblesToggleView.as_view(), name="nibbles_toggle"),
    path("plugins/boefje/<plugin_id>/", BoefjeDetailView.as_view(), name="boefje_detail"),
    path("plugins/boefje/<plugin_id>/edit/", EditBoefjeView.as_view(), name="edit_boefje"),
    path("plugins/normalizer/<plugin_id>/", NormalizerDetailView.as_view(), name="normalizer_detail"),
    path(
        "plugins/<plugin_type>/<plugin_id>/<plugin_state>/",
        PluginEnableDisableView.as_view(),
        name="plugin_enable_disable",
    ),
    path("plugins/<plugin_id>/cover.jpg", PluginCoverImgView.as_view(), name="plugin_cover"),
    path(
        "plugins/<plugin_type>/<plugin_id>/change-clearance-level/<scan_level>/",
        ChangeClearanceLevel.as_view(),
        name="change_clearance_level",
    ),
    path(
        "plugins/<plugin_type>/<plugin_id>/settings/add/", PluginSettingsAddView.as_view(), name="plugin_settings_add"
    ),
    path(
        "plugins/<plugin_type>/<plugin_id>/settings/delete/",
        PluginSettingsDeleteView.as_view(),
        name="plugin_settings_delete",
    ),
]
