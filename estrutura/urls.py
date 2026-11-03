from django.urls import path

from . import views

app_name = "estrutura"

urlpatterns = [
    path("unidades/", views.UnidadeListView.as_view(), name="unidade_lista"),
    path("unidades/nova/", views.UnidadeCreateView.as_view(), name="unidade_nova"),
    path("unidades/<int:pk>/editar/", views.UnidadeUpdateView.as_view(), name="unidade_editar"),
    path("unidades/<int:pk>/excluir/", views.UnidadeDeleteView.as_view(), name="unidade_excluir"),

    path("locais/", views.LocalListView.as_view(), name="local_lista"),
    path("locais/novo/", views.LocalCreateView.as_view(), name="local_novo"),
    path("locais/<int:pk>/editar/", views.LocalUpdateView.as_view(), name="local_editar"),
    path("locais/<int:pk>/excluir/", views.LocalDeleteView.as_view(), name="local_excluir"),

    path("equipamentos/", views.EquipamentoListView.as_view(), name="equipamento_lista"),
    path("equipamentos/novo/", views.EquipamentoCreateView.as_view(), name="equipamento_novo"),
    path("equipamentos/<int:pk>/editar/", views.EquipamentoUpdateView.as_view(), name="equipamento_editar"),
    path("equipamentos/<int:pk>/qrcode/", views.EquipamentoQRCodeView.as_view(), name="equipamento_qrcode"),
    path("equipamentos/<int:pk>/excluir/", views.EquipamentoDeleteView.as_view(), name="equipamento_excluir"),
]
