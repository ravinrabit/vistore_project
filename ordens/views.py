from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView
from django.views.generic.detail import SingleObjectMixin

from contas.mixins import FiltroUnidadeMixin, GestaoMixin, PerfilRequeridoMixin
from estrutura.views import BuscaMixin, ExclusaoProtegidaMixin, UsuarioNoFormMixin
from seguranca import services as seguranca
from seguranca.forms import IncidenteForm

from . import forms, services
from .models import OrdemServico, Preventiva, Status


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
        if self.request.GET.get("revisao"):
            ordens = ordens.filter(requer_revisao_seguranca=True)
        return services.ordenar_por_prioridade(ordens)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        status = self.request.GET.get("status", "")
        contexto.update(
            status_escolhido=status if status in Status.values else "", opcoes_status=Status.choices,
            so_revisao=bool(self.request.GET.get("revisao")),
        )
        return contexto


class OrdemDetailView(OrdensDoUsuarioMixin, DetailView):
    model = OrdemServico
    context_object_name = "ordem"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["historico"] = self.object.historico.select_related("usuario")
        contexto["acoes"] = services.acoes_disponiveis(self.request.user, self.object)
        contexto["incidentes"] = self.object.incidentes.select_related("registrado_por")
        return contexto


class OrdemCreateView(PerfilRequeridoMixin, UsuarioNoFormMixin, CreateView):
    model = OrdemServico
    form_class = forms.AbrirOrdemForm
    template_name = "crud/form.html"
    perfis_permitidos = ["SOLICITANTE", "GESTOR"]
    success_url = reverse_lazy("ordens:lista")
    extra_context = {"titulo": "Abrir chamado"}

    def get_initial(self):
        # Vindo do QR Code do equipamento: /ordens/nova/?equipamento=<id>
        inicial = super().get_initial()
        pk = self.request.GET.get("equipamento", "")
        if not pk.isdigit():
            return inicial
        form = self.get_form_class()(usuario=self.request.user)
        equipamento = form.fields["equipamento"].queryset.filter(pk=pk).first()
        if equipamento:
            inicial.update(equipamento=equipamento, local=equipamento.local)
        return inicial

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
    template_name = "ordens/acao_form.html"
    context_object_name = "ordem"
    form_class = forms.ConfirmarForm
    acao = ""
    titulo = ""
    rotulo_botao = "Confirmar"
    classe_botao = "btn-vistore"
    aviso = ""
    mensagem_sucesso = ""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.object = self.get_object()
        if not services.acoes_disponiveis(request.user, self.object)[self.acao]:
            messages.error(
                request,
                f"Esta ação não está disponível para a OS #{self.object.pk}, "
                f"que está “{self.object.get_status_display()}”.",
            )
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    @property
    def success_url(self):
        return reverse("ordens:detalhe", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        kwargs.update(
            titulo=f"{self.titulo} — OS #{self.object.pk}", rotulo_botao=self.rotulo_botao,
            classe_botao=self.classe_botao, aviso=self.aviso,
        )
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        try:
            self.executar(form.cleaned_data)
        except ValidationError as erro:
            form.add_error(None, erro)
            return self.form_invalid(form)
        messages.success(self.request, self.mensagem_sucesso.format(ordem=self.object))
        return redirect(self.success_url)

    def executar(self, dados):
        raise NotImplementedError


class ClassificarView(AcaoOrdemView):
    acao = "classificar"
    form_class = forms.ClassificarForm
    titulo = "Classificar chamado"
    rotulo_botao = "Classificar"
    mensagem_sucesso = "OS #{ordem.pk} classificada. Agora atribua um técnico."

    def executar(self, dados):
        services.classificar(self.object, self.request.user, dados["tipo_servico"], dados["riscos"])


class AtribuirView(AcaoOrdemView):
    acao = "atribuir"
    form_class = forms.AtribuirForm
    titulo = "Atribuir técnico"
    rotulo_botao = "Atribuir"
    mensagem_sucesso = "{ordem.tecnico.nome} foi atribuído(a) à OS #{ordem.pk}."

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "ordem": self.object}

    def executar(self, dados):
        services.atribuir(self.object, self.request.user, dados["tecnico"])


class ChecklistView(AcaoOrdemView):
    acao = "checklist"
    form_class = forms.ChecklistForm
    titulo = "Checklist de segurança"
    rotulo_botao = "Confirmar checklist"
    aviso = "Nenhum serviço começa sem segurança: o serviço só pode ser iniciado depois deste checklist."
    mensagem_sucesso = "Checklist da OS #{ordem.pk} confirmado. Você já pode iniciar o serviço."

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "ordem": self.object}

    def executar(self, dados):
        services.confirmar_checklist(
            self.object, self.request.user, dados.get("epis", []), dados["area_isolada"]
        )


class IniciarView(AcaoOrdemView):
    acao = "iniciar"
    titulo = "Iniciar serviço"
    rotulo_botao = "Iniciar"
    mensagem_sucesso = "Serviço da OS #{ordem.pk} iniciado."

    def executar(self, dados):
        services.iniciar(self.object, self.request.user)


class ConcluirView(AcaoOrdemView):
    acao = "concluir"
    titulo = "Concluir serviço"
    rotulo_botao = "Concluir serviço"
    classe_botao = "btn-success"
    aviso = "Depois de concluída, a OS não pode voltar atrás. Confirme só se o serviço terminou."
    mensagem_sucesso = "OS #{ordem.pk} concluída. O solicitante já pode avaliar."

    def executar(self, dados):
        services.concluir(self.object, self.request.user)


class CancelarView(AcaoOrdemView):
    acao = "cancelar"
    form_class = forms.CancelarForm
    titulo = "Cancelar OS"
    rotulo_botao = "Confirmar cancelamento"
    classe_botao = "btn-danger"
    mensagem_sucesso = "OS #{ordem.pk} cancelada."

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


class IncidenteView(AcaoOrdemView):
    acao = "incidente"
    form_class = IncidenteForm
    titulo = "Registrar incidente"
    rotulo_botao = "Registrar incidente"
    classe_botao = "btn-danger"
    mensagem_sucesso = "Incidente registrado na OS #{ordem.pk}."

    def executar(self, dados):
        incidente = seguranca.registrar_incidente(self.object, self.request.user, **dados)
        if incidente.houve_lesao or incidente.houve_afastamento:
            messages.warning(
                self.request,
                "A OS entrou em revisão de segurança e só pode ser concluída depois da liberação do gestor.",
            )


class RevisaoView(AcaoOrdemView):
    acao = "revisar"
    titulo = "Concluir revisão de segurança"
    rotulo_botao = "Liberar a OS"
    aviso = "Confirme que o incidente foi analisado e que o serviço pode seguir com segurança."
    mensagem_sucesso = "Revisão de segurança da OS #{ordem.pk} concluída."

    def executar(self, dados):
        services.concluir_revisao(self.object, self.request.user)


# --- Preventivas (RN09) ----------------------------------------------------

class PreventivaListView(GestaoMixin, FiltroUnidadeMixin, BuscaMixin, ListView):
    model = Preventiva
    campo_unidade = "equipamento__local__unidade"
    campos_busca = ["equipamento__nome", "equipamento__patrimonio", "tipo_servico__nome"]
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().select_related("equipamento__local__unidade", "tipo_servico")


class PreventivaCreateView(GestaoMixin, UsuarioNoFormMixin, SuccessMessageMixin, CreateView):
    model = Preventiva
    form_class = forms.PreventivaForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("ordens:preventiva_lista")
    success_message = "Preventiva cadastrada."
    extra_context = {"titulo": "Nova preventiva"}

    def form_valid(self, form):
        form.instance.responsavel = self.request.user
        return super().form_valid(form)


class PreventivaUpdateView(GestaoMixin, FiltroUnidadeMixin, UsuarioNoFormMixin, SuccessMessageMixin, UpdateView):
    model = Preventiva
    form_class = forms.PreventivaForm
    template_name = "crud/form.html"
    campo_unidade = "equipamento__local__unidade"
    success_url = reverse_lazy("ordens:preventiva_lista")
    success_message = "Preventiva atualizada."
    extra_context = {"titulo": "Editar preventiva"}


class PreventivaDeleteView(GestaoMixin, FiltroUnidadeMixin, ExclusaoProtegidaMixin, DeleteView):
    model = Preventiva
    template_name = "crud/confirmar_exclusao.html"
    campo_unidade = "equipamento__local__unidade"
    success_url = reverse_lazy("ordens:preventiva_lista")
    mensagem_protegido = "Esta preventiva já gerou ordens de serviço. Desative-a em vez de excluir."
