from django.urls import path

from . import views

app_name = "ordens"

urlpatterns = [
    path("", views.OrdemListView.as_view(), name="lista"),
    path("nova/", views.OrdemCreateView.as_view(), name="nova"),
    path("<int:pk>/", views.OrdemDetailView.as_view(), name="detalhe"),
    path("<int:pk>/classificar/", views.ClassificarView.as_view(), name="classificar"),
    path("<int:pk>/atribuir/", views.AtribuirView.as_view(), name="atribuir"),
    path("<int:pk>/checklist/", views.ChecklistView.as_view(), name="checklist"),
    path("<int:pk>/iniciar/", views.IniciarView.as_view(), name="iniciar"),
    path("<int:pk>/concluir/", views.ConcluirView.as_view(), name="concluir"),
    path("<int:pk>/cancelar/", views.CancelarView.as_view(), name="cancelar"),
    path("<int:pk>/avaliar/", views.AvaliarView.as_view(), name="avaliar"),
]
