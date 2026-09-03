from django.urls import path

from . import views

# Crisis room overview (non-org-scope) url
urlpatterns = [path("", views.CrisisRoomView.as_view(), name="crisis_room")]
