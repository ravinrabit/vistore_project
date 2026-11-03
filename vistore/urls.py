from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Vistore — Administração"
admin.site.site_title = "Vistore"
admin.site.index_title = "Painel administrativo"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("contas.urls")),
    path("estrutura/", include("estrutura.urls")),
    path("ordens/", include("ordens.urls")),
]
