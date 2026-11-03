from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView

from contas.mixins import PerfilRequeridoMixin
from estrutura.views import BuscaMixin, UsuarioNoFormMixin

from . import services
from .forms import AbrirOrdemForm
from .models import OrdemServico, Status


class OrdensDoUsuarioMixin(LoginRequiredMixin):
    """Cada perfil só enxerga as próprias OS; as demais dão 404."""

    def get_queryset(self):
        usuario = self.request.user
        ordens = OrdemServico.objects.select_related(
            "local__unidade", "equipamento", "solicitante", "tecnico", "tipo_servico"
        )
        if usuario.eh_admin:
            return ordens
        if usuario.eh_gestor:
            return ordens.filter(local__unidade=usuario.unidade_id)
        if usuario.eh_tecnico:
            return ordens.filter(tecnico=usuario)
        return ordens.filter(solicitante=usuario)


class OrdemListView(OrdensDoUsuarioMixin, BuscaMixin, ListView):
    model = OrdemServico
    campos_busca = ["descricao", "local__sala", "equipamento__nome"]
    paginate_by = 20

    def get_queryset(self):
        ordens = super().get_queryset()
        status = self.request.GET.get("status")
        if status in Status.values:
            ordens = ordens.filter(status=status)
        return services.ordenar_por_prioridade(ordens)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(status_escolhido=self.request.GET.get("status", ""), opcoes_status=Status.choices)
        return contexto


class OrdemDetailView(OrdensDoUsuarioMixin, DetailView):
    model = OrdemServico
    context_object_name = "ordem"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["historico"] = self.object.historico.select_related("usuario")
        return contexto


class OrdemCreateView(PerfilRequeridoMixin, UsuarioNoFormMixin, CreateView):
    model = OrdemServico
    form_class = AbrirOrdemForm
    template_name = "crud/form.html"
    perfis_permitidos = ["SOLICITANTE", "GESTOR"]
    success_url = reverse_lazy("ordens:lista")
    extra_context = {"titulo": "Abrir chamado"}

    def form_valid(self, form):
        dados = form.cleaned_data
        self.object = services.abrir_ordem(
            solicitante=self.request.user, local=dados["local"], equipamento=dados["equipamento"],
            descricao=dados["descricao"], prioridade=dados["prioridade"],
        )
        messages.success(self.request, f"Chamado #{self.object.pk} aberto.")
        return redirect("ordens:detalhe", pk=self.object.pk)
