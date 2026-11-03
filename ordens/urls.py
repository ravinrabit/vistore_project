from django.urls import path

from . import views

app_name = "ordens"

urlpatterns = [
    path("", views.OrdemListView.as_view(), name="lista"),
    path("nova/", views.OrdemCreateView.as_view(), name="nova"),
]
