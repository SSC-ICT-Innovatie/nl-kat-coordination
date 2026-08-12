from django.urls import path

from . import views

# Crisis room overview urls
urlpatterns = [
    path("", views.CrisisRoomView.as_view(), name="crisis_room"),
    path("<organization_code>/<int:id>/", views.OrganizationsCrisisRoomView.as_view(), name="organization_crisis_room"),
    path(
        "<organization_code>/",
        views.OrganizationsCrisisRoomLandingView.as_view(),
        name="organization_crisis_room_landing",
    ),
    path("<organization_code>/add/", views.AddDashboardView.as_view(), name="add_dashboard"),
    path("<organization_code>/update-item/", views.UpdateDashboardItemView.as_view(), name="update_dashboard_item"),
    path("<organization_code>/delete/", views.DeleteDashboardView.as_view(), name="delete_dashboard"),
    path("<organization_code>/delete-item/", views.DeleteDashboardItemView.as_view(), name="delete_dashboard_item"),
]
