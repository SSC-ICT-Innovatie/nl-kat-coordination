from django.urls import path

from plugins.views import (
    BusinessRuleCreateView,
    BusinessRuleDeleteView,
    BusinessRuleDetailView,
    BusinessRuleListView,
    BusinessRuleToggleView,
    BusinessRuleUpdateView,
    PluginCreateView,
    PluginDeleteView,
    PluginDetailView,
    PluginIdDetailView,
    PluginListView,
    PluginScansDetailView,
    PluginScheduleView,
    PluginUpdateView,
    PluginVariantsDetailView,
)

urlpatterns = [
    path("plugins/", PluginListView.as_view(), name="plugin_list"),
    path("plugins/add", PluginCreateView.as_view(), name="add_plugin"),
    path("plugins/<int:pk>/", PluginDetailView.as_view(), name="plugin_detail"),
    path("plugins/<slug:plugin_id>/", PluginIdDetailView.as_view(), name="plugin_id_detail"),
    path("plugins/<int:pk>/edit", PluginUpdateView.as_view(), name="update_plugin"),
    path("plugins/<int:pk>/scans", PluginScansDetailView.as_view(), name="plugin_detail_scans"),
    path("plugins/<int:pk>/variants", PluginVariantsDetailView.as_view(), name="plugin_detail_variants"),
    path("plugins/<int:pk>/schedule/", PluginScheduleView.as_view(), name="schedule_plugin"),
    path("plugins/<slug:pk>/delete", PluginDeleteView.as_view(), name="delete_plugin"),
    # Business Rule views
    path("business-rules/", BusinessRuleListView.as_view(), name="business_rule_list"),
    path("business-rules/add/", BusinessRuleCreateView.as_view(), name="add_business_rule"),
    path("business-rules/<int:pk>/", BusinessRuleDetailView.as_view(), name="business_rule_detail"),
    path("business-rules/<int:pk>/edit/", BusinessRuleUpdateView.as_view(), name="edit_business_rule"),
    path("business-rules/<int:pk>/delete/", BusinessRuleDeleteView.as_view(), name="delete_business_rule"),
    path("business-rules/<int:pk>/toggle/", BusinessRuleToggleView.as_view(), name="toggle_business_rule"),
]
