from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, FormView, ListView
from django.views.generic.detail import SingleObjectMixin

from contas.mixins import PerfilRequeridoMixin
from estrutura.views import BuscaMixin, UsuarioNoFormMixin

from . import forms, services
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
        contexto["acoes"] = services.acoes_disponiveis(self.request.user, self.object)
        return contexto


class OrdemCreateView(PerfilRequeridoMixin, UsuarioNoFormMixin, CreateView):
    model = OrdemServico
    form_class = forms.AbrirOrdemForm
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


class AcaoOrdemView(OrdensDoUsuarioMixin, SingleObjectMixin, FormView):
    """Base das ações sobre uma OS. A regra fica no services; a view só chama."""

    model = OrdemServico
    template_name = "crud/form.html"
    form_class = forms.ConfirmarForm
    acao = ""
    titulo = ""
    rotulo_botao = "Confirmar"
    mensagem_sucesso = ""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.object = self.get_object()
        if not services.acoes_disponiveis(request.user, self.object)[self.acao]:
            messages.error(request, "Esta ação não está disponível para esta OS.")
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    @property
    def success_url(self):
        return reverse("ordens:detalhe", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        kwargs.update(titulo=f"{self.titulo} — OS #{self.object.pk}", rotulo_botao=self.rotulo_botao)
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        try:
            self.executar(form.cleaned_data)
        except ValidationError as erro:
            form.add_error(None, erro)
            return self.form_invalid(form)
        messages.success(self.request, self.mensagem_sucesso)
        return redirect(self.success_url)

    def executar(self, dados):
        raise NotImplementedError


class ClassificarView(AcaoOrdemView):
    acao = "classificar"
    form_class = forms.ClassificarForm
    titulo = "Classificar chamado"
    rotulo_botao = "Classificar"
    mensagem_sucesso = "Chamado classificado. Agora atribua um técnico."

    def executar(self, dados):
        services.classificar(self.object, self.request.user, dados["tipo_servico"], dados["riscos"])


class AtribuirView(AcaoOrdemView):
    acao = "atribuir"
    form_class = forms.AtribuirForm
    titulo = "Atribuir técnico"
    rotulo_botao = "Atribuir"
    mensagem_sucesso = "Técnico atribuído."

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "ordem": self.object}

    def executar(self, dados):
        services.atribuir(self.object, self.request.user, dados["tecnico"])


class IniciarView(AcaoOrdemView):
    acao = "iniciar"
    titulo = "Iniciar serviço"
    rotulo_botao = "Iniciar"
    mensagem_sucesso = "Serviço iniciado."

    def executar(self, dados):
        services.iniciar(self.object, self.request.user)


class ConcluirView(AcaoOrdemView):
    acao = "concluir"
    titulo = "Concluir serviço"
    rotulo_botao = "Concluir"
    mensagem_sucesso = "Serviço concluído."

    def executar(self, dados):
        services.concluir(self.object, self.request.user)


class CancelarView(AcaoOrdemView):
    acao = "cancelar"
    form_class = forms.CancelarForm
    titulo = "Cancelar OS"
    rotulo_botao = "Cancelar OS"
    mensagem_sucesso = "OS cancelada."

    def executar(self, dados):
        services.cancelar(self.object, self.request.user, dados["justificativa"])


class AvaliarView(AcaoOrdemView):
    acao = "avaliar"
    form_class = forms.AvaliarForm
    titulo = "Avaliar serviço"
    rotulo_botao = "Enviar avaliação"
    mensagem_sucesso = "Obrigado pela avaliação!"

    def executar(self, dados):
        services.avaliar(self.object, self.request.user, dados["nota"])
