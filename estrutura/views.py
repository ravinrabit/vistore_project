

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import ProtectedError, Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from contas.mixins import FiltroUnidadeMixin, GestaoMixin, SomenteAdminMixin

from .forms import EquipamentoForm, LocalForm, UnidadeForm
from .models import Equipamento, Local, Unidade


class BuscaMixin:

    campos_busca = []

    def get_queryset(self):
        queryset = super().get_queryset()
        termo = self.request.GET.get("q", "").strip()
        if termo:
            filtro = Q()
            for campo in self.campos_busca:
                filtro |= Q(**{f"{campo}__icontains": termo})
            queryset = queryset.filter(filtro)
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "")
        return contexto


class UsuarioNoFormMixin:

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs


class ExclusaoProtegidaMixin:

    mensagem_protegido = "Não é possível excluir: existem registros ligados a este item."

    def form_valid(self, form):
        try:
            resposta = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, self.mensagem_protegido)
            return redirect(self.success_url)
        messages.success(self.request, "Registro excluído com sucesso.")
        return resposta


# --- Unidade ---------------------------------------------------------------

class UnidadeListView(GestaoMixin, FiltroUnidadeMixin, BuscaMixin, ListView):
    model = Unidade
    campo_unidade = "pk"  # o Gestor enxerga apenas a própria unidade
    campos_busca = ["nome", "endereco"]
    paginate_by = 20


class UnidadeCreateView(SomenteAdminMixin, SuccessMessageMixin, CreateView):
    model = Unidade
    template_name = "crud/form.html"
    form_class = UnidadeForm
    success_url = reverse_lazy("estrutura:unidade_lista")
    success_message = "Unidade “%(nome)s” cadastrada."
    extra_context = {"titulo": "Nova unidade"}


class UnidadeUpdateView(GestaoMixin, FiltroUnidadeMixin, SuccessMessageMixin, UpdateView):
    model = Unidade
    template_name = "crud/form.html"
    campo_unidade = "pk"
    form_class = UnidadeForm
    success_url = reverse_lazy("estrutura:unidade_lista")
    success_message = "Unidade “%(nome)s” atualizada."
    extra_context = {"titulo": "Editar unidade"}

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if not self.request.user.eh_admin:
            del form.fields["ativa"]
        return form


class UnidadeDeleteView(SomenteAdminMixin, ExclusaoProtegidaMixin, DeleteView):
    model = Unidade
    template_name = "crud/confirmar_exclusao.html"
    success_url = reverse_lazy("estrutura:unidade_lista")
    mensagem_protegido = "Esta unidade tem usuários ou locais. Desative-a em vez de excluir."


# --- Local -----------------------------------------------------------------

class LocalListView(GestaoMixin, FiltroUnidadeMixin, BuscaMixin, ListView):
    model = Local
    campos_busca = ["bloco", "andar", "sala", "unidade__nome"]
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().select_related("unidade")


class LocalCreateView(GestaoMixin, UsuarioNoFormMixin, SuccessMessageMixin, CreateView):
    model = Local
    template_name = "crud/form.html"
    form_class = LocalForm
    success_url = reverse_lazy("estrutura:local_lista")
    success_message = "Local cadastrado."
    extra_context = {"titulo": "Novo local"}


class LocalUpdateView(GestaoMixin, FiltroUnidadeMixin, UsuarioNoFormMixin, SuccessMessageMixin, UpdateView):
    model = Local
    template_name = "crud/form.html"
    form_class = LocalForm
    success_url = reverse_lazy("estrutura:local_lista")
    success_message = "Local atualizado."
    extra_context = {"titulo": "Editar local"}


class LocalDeleteView(GestaoMixin, FiltroUnidadeMixin, ExclusaoProtegidaMixin, DeleteView):
    model = Local
    template_name = "crud/confirmar_exclusao.html"
    success_url = reverse_lazy("estrutura:local_lista")
    mensagem_protegido = "Este local tem equipamentos ou ordens de serviço e não pode ser excluído."


# --- Equipamento -----------------------------------------------------------

class EquipamentoListView(GestaoMixin, FiltroUnidadeMixin, BuscaMixin, ListView):
    model = Equipamento
    campo_unidade = "local__unidade"
    campos_busca = ["nome", "patrimonio", "local__sala", "local__bloco"]
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().select_related("local__unidade")


class EquipamentoCreateView(GestaoMixin, UsuarioNoFormMixin, SuccessMessageMixin, CreateView):
    model = Equipamento
    template_name = "crud/form.html"
    form_class = EquipamentoForm
    success_url = reverse_lazy("estrutura:equipamento_lista")
    success_message = "Equipamento “%(nome)s” cadastrado."
    extra_context = {"titulo": "Novo equipamento"}


class EquipamentoUpdateView(
    GestaoMixin, FiltroUnidadeMixin, UsuarioNoFormMixin, SuccessMessageMixin, UpdateView
):
    model = Equipamento
    template_name = "crud/form.html"
    form_class = EquipamentoForm
    campo_unidade = "local__unidade"
    success_url = reverse_lazy("estrutura:equipamento_lista")
    success_message = "Equipamento “%(nome)s” atualizado."
    extra_context = {"titulo": "Editar equipamento"}


class EquipamentoDeleteView(GestaoMixin, FiltroUnidadeMixin, ExclusaoProtegidaMixin, DeleteView):
    model = Equipamento
    template_name = "crud/confirmar_exclusao.html"
    campo_unidade = "local__unidade"
    success_url = reverse_lazy("estrutura:equipamento_lista")
    mensagem_protegido = "Este equipamento tem ordens de serviço ou preventivas e não pode ser excluído."


class EquipamentoQRCodeView(GestaoMixin, FiltroUnidadeMixin, DetailView):
    """Etiqueta para imprimir e colar no equipamento: o QR abre o chamado já preenchido."""

    model = Equipamento
    campo_unidade = "local__unidade"
    template_name = "estrutura/equipamento_qrcode.html"

    def get_context_data(self, **kwargs):
        url = reverse("ordens:nova") + f"?equipamento={self.object.pk}"
        return super().get_context_data(url_chamado=self.request.build_absolute_uri(url), **kwargs)
