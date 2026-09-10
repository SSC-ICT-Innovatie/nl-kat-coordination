from django.urls import path

from . import views

# Crisis room overview (non-org-scope) urls
urlpatterns = [
    path("", views.CrisisRoomView.as_view(), name="crisis_room"),
    path("auditlog/", views.AuditLogView.as_view(), name="crisis_room_audit_log"),
]
