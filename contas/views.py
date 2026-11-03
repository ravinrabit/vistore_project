from datetime import timedelta

from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView

from estrutura.models import Equipamento, Local, Unidade
from ordens import relatorios
from ordens.models import OrdemServico, Prioridade, Status
from ordens.services import ordenar_por_prioridade
from seguranca.models import TreinamentoTecnico

from .forms import LoginForm
from .models import Perfil, Usuario


class LoginView(auth_views.LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class PainelView(LoginRequiredMixin, TemplateView):

    def get_template_names(self):
        usuario = self.request.user
        perfil = Perfil.ADMIN if usuario.eh_admin else usuario.perfil
        return [f"contas/painel/{perfil.lower()}.html"]

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        usuario = self.request.user
        ordens = OrdemServico.objects.select_related("local")
        finalizados = [Status.CONCLUIDO, Status.CANCELADO]

        if usuario.eh_admin:
            contexto.update(
                total_unidades=Unidade.objects.filter(ativa=True).count(),
                total_usuarios=Usuario.objects.filter(is_active=True).count(),
                total_locais=Local.objects.count(),
                total_equipamentos=Equipamento.objects.count(),
                por_status=relatorios.ordens_por_status(ordens),
                por_semana=relatorios.chamados_por_semana(ordens),
            )
        elif usuario.eh_gestor:
            daqui_30_dias = timezone.localdate() + timedelta(days=30)
            da_unidade = ordens.filter(local__unidade=usuario.unidade)
            contexto.update(
                total_locais=Local.objects.filter(unidade=usuario.unidade).count(),
                total_equipamentos=Equipamento.objects.filter(local__unidade=usuario.unidade).count(),
                ordens_abertas=da_unidade.filter(status=Status.ABERTO).count(),
                aguardando_atribuicao=da_unidade.filter(status=Status.CLASSIFICADO).count(),
                em_revisao=da_unidade.filter(requer_revisao_seguranca=True).count(),
                urgentes_pendentes=da_unidade.filter(prioridade=Prioridade.URGENTE)
                .exclude(status__in=finalizados).count(),
                pendencias=ordenar_por_prioridade(
                    da_unidade.filter(status__in=[Status.ABERTO, Status.CLASSIFICADO])
                )[:5],
                por_status=relatorios.ordens_por_status(da_unidade),
                por_semana=relatorios.chamados_por_semana(da_unidade),
                treinamentos_vencendo=TreinamentoTecnico.objects.filter(
                    tecnico__unidade=usuario.unidade,
                    data_validade__range=(timezone.localdate(), daqui_30_dias),
                ).count(),
            )
        elif usuario.eh_tecnico:
            meus_servicos = ordens.filter(tecnico=usuario).exclude(status__in=finalizados)
            contexto.update(
                ordens_atribuidas=meus_servicos.count(),
                meus_servicos=ordenar_por_prioridade(meus_servicos)[:10],
                meus_treinamentos=usuario.treinamentos.select_related("treinamento"),
                hoje=timezone.localdate(),
                limite_alerta=timezone.localdate() + timedelta(days=30),
            )
        else:
            minhas = ordens.filter(solicitante=usuario)
            contexto.update(
                minhas_abertas=minhas.exclude(status__in=finalizados).count(),
                minhas_concluidas=minhas.filter(status=Status.CONCLUIDO).count(),
                para_avaliar=minhas.filter(status=Status.CONCLUIDO, avaliacao__isnull=True).count(),
                ultimas=minhas.order_by("-aberta_em")[:5],
            )
        return contexto
