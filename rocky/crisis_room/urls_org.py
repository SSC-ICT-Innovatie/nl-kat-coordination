from django.urls import path

from . import views

# Crisis room urls scoped to an organization. Included under
# <organization_code>/crisis-room/ in rocky/urls.py, so organization_code
# is provided by the mount point and does not need to be captured here.
urlpatterns = [
    path("", views.OrganizationsCrisisRoomLandingView.as_view(), name="organization_crisis_room_landing"),
    path("logs/", views.OrganizationAuditLogView.as_view(), name="organization_crisis_room_audit_log"),
    path("<int:id>/", views.OrganizationsCrisisRoomView.as_view(), name="organization_crisis_room"),
    path("add/", views.AddDashboardView.as_view(), name="add_dashboard"),
    path("update-item/", views.UpdateDashboardItemView.as_view(), name="update_dashboard_item"),
    path("delete/", views.DeleteDashboardView.as_view(), name="delete_dashboard"),
    path("delete-item/", views.DeleteDashboardItemView.as_view(), name="delete_dashboard_item"),
]
