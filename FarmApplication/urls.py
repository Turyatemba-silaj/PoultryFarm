from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("<str:record_type>/", views.record_list, name="record_list"),
    path("<str:record_type>/add/", views.record_create, name="record_create"),
    path("<str:record_type>/<int:pk>/edit/", views.record_update, name="record_update"),
    path("<str:record_type>/<int:pk>/delete/", views.record_delete, name="record_delete"),
]



