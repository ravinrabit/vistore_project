from django.urls import path

from . import views

app_name = "seguranca"

urlpatterns = [
    path("treinamentos/", views.TreinamentoListView.as_view(), name="treinamento_lista"),
    path("treinamentos/novo/", views.TreinamentoCreateView.as_view(), name="treinamento_novo"),
    path("treinamentos/<int:pk>/editar/", views.TreinamentoUpdateView.as_view(), name="treinamento_editar"),
    path("treinamentos/<int:pk>/excluir/", views.TreinamentoDeleteView.as_view(), name="treinamento_excluir"),

    path("tecnicos/", views.TreinamentoTecnicoListView.as_view(), name="realizacao_lista"),
    path("tecnicos/novo/", views.TreinamentoTecnicoCreateView.as_view(), name="realizacao_nova"),
    path("tecnicos/<int:pk>/editar/", views.TreinamentoTecnicoUpdateView.as_view(), name="realizacao_editar"),
    path("tecnicos/<int:pk>/excluir/", views.TreinamentoTecnicoDeleteView.as_view(), name="realizacao_excluir"),

    path("epis/", views.EPIListView.as_view(), name="epi_lista"),
    path("epis/novo/", views.EPICreateView.as_view(), name="epi_novo"),
    path("epis/<int:pk>/editar/", views.EPIUpdateView.as_view(), name="epi_editar"),
    path("epis/<int:pk>/excluir/", views.EPIDeleteView.as_view(), name="epi_excluir"),

    path("tipos/", views.TipoServicoListView.as_view(), name="tipo_lista"),
    path("tipos/novo/", views.TipoServicoCreateView.as_view(), name="tipo_novo"),
    path("tipos/<int:pk>/editar/", views.TipoServicoUpdateView.as_view(), name="tipo_editar"),
    path("tipos/<int:pk>/excluir/", views.TipoServicoDeleteView.as_view(), name="tipo_excluir"),
]
