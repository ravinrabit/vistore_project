from datetime import timedelta

from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from contas.mixins import FiltroUnidadeMixin, GestaoMixin, SomenteAdminMixin
from estrutura.views import BuscaMixin, ExclusaoProtegidaMixin, UsuarioNoFormMixin

from .forms import EPIForm, TipoServicoForm, TreinamentoForm, TreinamentoTecnicoForm
from .models import EPI, TipoServico, Treinamento, TreinamentoTecnico


class CrudMixin(SuccessMessageMixin):
    """Configuração comum dos cadastros de segurança (templates genéricos de crud/)."""

    template_name = "crud/form.html"


# --- Treinamento (NRs) -----------------------------------------------------

class TreinamentoListView(GestaoMixin, BuscaMixin, ListView):
    model = Treinamento
    campos_busca = ["codigo", "nome"]
    paginate_by = 20


class TreinamentoCreateView(GestaoMixin, CrudMixin, CreateView):
    model = Treinamento
    form_class = TreinamentoForm
    success_url = reverse_lazy("seguranca:treinamento_lista")
    success_message = "Treinamento “%(codigo)s” cadastrado."
    extra_context = {"titulo": "Novo treinamento"}


class TreinamentoUpdateView(GestaoMixin, CrudMixin, UpdateView):
    model = Treinamento
    form_class = TreinamentoForm
    success_url = reverse_lazy("seguranca:treinamento_lista")
    success_message = "Treinamento “%(codigo)s” atualizado."
    extra_context = {"titulo": "Editar treinamento"}


class TreinamentoDeleteView(GestaoMixin, ExclusaoProtegidaMixin, DeleteView):
    model = Treinamento
    template_name = "crud/confirmar_exclusao.html"
    success_url = reverse_lazy("seguranca:treinamento_lista")
    mensagem_protegido = "Este treinamento já foi realizado por técnicos e não pode ser excluído."


# --- Treinamentos dos técnicos ---------------------------------------------

class TreinamentoTecnicoListView(GestaoMixin, FiltroUnidadeMixin, BuscaMixin, ListView):
    model = TreinamentoTecnico
    campo_unidade = "tecnico__unidade"
    campos_busca = ["tecnico__nome", "treinamento__codigo"]
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().select_related("tecnico__unidade", "treinamento").order_by("data_validade")

    def get_context_data(self, **kwargs):
        hoje = timezone.localdate()
        return super().get_context_data(hoje=hoje, limite_alerta=hoje + timedelta(days=30), **kwargs)


class TreinamentoTecnicoCreateView(GestaoMixin, UsuarioNoFormMixin, CrudMixin, CreateView):
    model = TreinamentoTecnico
    form_class = TreinamentoTecnicoForm
    success_url = reverse_lazy("seguranca:realizacao_lista")
    success_message = "Treinamento registrado."
    extra_context = {"titulo": "Registrar treinamento de técnico"}


class TreinamentoTecnicoUpdateView(GestaoMixin, FiltroUnidadeMixin, UsuarioNoFormMixin, CrudMixin, UpdateView):
    model = TreinamentoTecnico
    form_class = TreinamentoTecnicoForm
    campo_unidade = "tecnico__unidade"
    success_url = reverse_lazy("seguranca:realizacao_lista")
    success_message = "Treinamento atualizado."
    extra_context = {"titulo": "Editar treinamento de técnico"}


class TreinamentoTecnicoDeleteView(GestaoMixin, FiltroUnidadeMixin, ExclusaoProtegidaMixin, DeleteView):
    model = TreinamentoTecnico
    template_name = "crud/confirmar_exclusao.html"
    campo_unidade = "tecnico__unidade"
    success_url = reverse_lazy("seguranca:realizacao_lista")


# --- EPI -------------------------------------------------------------------

class EPIListView(GestaoMixin, BuscaMixin, ListView):
    model = EPI
    campos_busca = ["nome", "numero_ca"]
    paginate_by = 20


class EPICreateView(GestaoMixin, CrudMixin, CreateView):
    model = EPI
    form_class = EPIForm
    success_url = reverse_lazy("seguranca:epi_lista")
    success_message = "EPI “%(nome)s” cadastrado."
    extra_context = {"titulo": "Novo EPI"}


class EPIUpdateView(GestaoMixin, CrudMixin, UpdateView):
    model = EPI
    form_class = EPIForm
    success_url = reverse_lazy("seguranca:epi_lista")
    success_message = "EPI “%(nome)s” atualizado."
    extra_context = {"titulo": "Editar EPI"}


class EPIDeleteView(GestaoMixin, ExclusaoProtegidaMixin, DeleteView):
    model = EPI
    template_name = "crud/confirmar_exclusao.html"
    success_url = reverse_lazy("seguranca:epi_lista")


# --- Tipo de serviço (só o Administrador altera) ---------------------------

class TipoServicoListView(GestaoMixin, BuscaMixin, ListView):
    model = TipoServico
    campos_busca = ["nome"]
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().prefetch_related("treinamentos_exigidos", "epis_exigidos")


class TipoServicoCreateView(SomenteAdminMixin, CrudMixin, CreateView):
    model = TipoServico
    form_class = TipoServicoForm
    success_url = reverse_lazy("seguranca:tipo_lista")
    success_message = "Tipo de serviço “%(nome)s” cadastrado."
    extra_context = {"titulo": "Novo tipo de serviço"}


class TipoServicoUpdateView(SomenteAdminMixin, CrudMixin, UpdateView):
    model = TipoServico
    form_class = TipoServicoForm
    success_url = reverse_lazy("seguranca:tipo_lista")
    success_message = "Tipo de serviço “%(nome)s” atualizado."
    extra_context = {"titulo": "Editar tipo de serviço"}


class TipoServicoDeleteView(SomenteAdminMixin, ExclusaoProtegidaMixin, DeleteView):
    model = TipoServico
    template_name = "crud/confirmar_exclusao.html"
    success_url = reverse_lazy("seguranca:tipo_lista")
    mensagem_protegido = "Este tipo de serviço está em uso por ordens ou preventivas e não pode ser excluído."
