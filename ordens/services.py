from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from contas.models import Perfil

from .models import HistoricoStatus, OrdemServico, Prioridade, Status

# RN05: para cada status, os próximos status permitidos.
TRANSICOES = {
    Status.ABERTO: {Status.CLASSIFICADO, Status.CANCELADO},
    Status.CLASSIFICADO: {Status.ATRIBUIDO, Status.CANCELADO},
    # ATRIBUIDO → CLASSIFICADO é a volta para "Aguardando atribuição" (RN03, etapa 4)
    Status.ATRIBUIDO: {Status.EM_EXECUCAO, Status.CLASSIFICADO, Status.CANCELADO},
    Status.EM_EXECUCAO: {Status.CONCLUIDO, Status.CANCELADO},
    Status.CONCLUIDO: set(),
    Status.CANCELADO: set(),
}

ORDEM_PRIORIDADE = [Prioridade.URGENTE, Prioridade.ALTA, Prioridade.MEDIA, Prioridade.BAIXA]


def ordenar_por_prioridade(queryset):
    """RN07: urgentes no topo; dentro da mesma prioridade, as mais recentes primeiro."""
    peso = Case(
        *[When(prioridade=p, then=Value(i)) for i, p in enumerate(ORDEM_PRIORIDADE)],
        output_field=IntegerField(),
    )
    return queryset.annotate(peso_prioridade=peso).order_by("peso_prioridade", "-aberta_em")


def pode_mudar_para(ordem, novo_status):
    return novo_status in TRANSICOES[ordem.status]


def pode_gerir(usuario, ordem):
    if usuario.eh_admin:
        return True
    return usuario.eh_gestor and usuario.unidade_id == ordem.local.unidade_id


@transaction.atomic
def mudar_status(ordem, novo_status, usuario):
    """Único ponto do sistema que altera o status de uma OS."""
    if not pode_mudar_para(ordem, novo_status):
        raise ValidationError(
            f"Não é possível passar de “{ordem.get_status_display()}” "
            f"para “{Status(novo_status).label}”."
        )
    anterior = ordem.status
    ordem.status = novo_status
    agora = timezone.now()
    if novo_status == Status.EM_EXECUCAO:
        ordem.iniciada_em = agora
    elif novo_status == Status.CONCLUIDO:
        ordem.concluida_em = agora
    ordem.save()
    HistoricoStatus.objects.create(
        ordem=ordem, status_anterior=anterior, status_novo=novo_status, usuario=usuario
    )
    return ordem


@transaction.atomic
def abrir_ordem(solicitante, local, descricao, prioridade, equipamento=None):
    if equipamento and equipamento.local_id != local.pk:
        raise ValidationError("O equipamento escolhido não fica nesse local.")
    ordem = OrdemServico.objects.create(
        solicitante=solicitante, local=local, equipamento=equipamento,
        descricao=descricao, prioridade=prioridade,
    )
    HistoricoStatus.objects.create(ordem=ordem, status_novo=Status.ABERTO, usuario=solicitante)
    return ordem


def classificar(ordem, usuario, tipo_servico, riscos=""):
    if not pode_gerir(usuario, ordem):
        raise PermissionDenied("Só o gestor da unidade classifica chamados.")
    if tipo_servico is None:
        raise ValidationError("Informe o tipo de serviço.")
    ordem.tipo_servico = tipo_servico
    ordem.riscos = riscos
    return mudar_status(ordem, Status.CLASSIFICADO, usuario)


def atribuir(ordem, usuario, tecnico):
    if not pode_gerir(usuario, ordem):
        raise PermissionDenied("Só o gestor da unidade atribui técnicos.")
    if (
        tecnico.perfil != Perfil.TECNICO
        or not tecnico.is_active
        or tecnico.unidade_id != ordem.local.unidade_id
    ):
        raise ValidationError("Escolha um técnico ativo da unidade da OS.")
    # A checagem das NRs exigidas (RN01/RN04) entra aqui na etapa 4.
    ordem.tecnico = tecnico
    return mudar_status(ordem, Status.ATRIBUIDO, usuario)


def iniciar(ordem, usuario):
    if usuario.pk != ordem.tecnico_id:
        raise PermissionDenied("Só o técnico atribuído inicia o serviço.")
    # O checklist de segurança (RN02) passa a ser exigido aqui na etapa 4.
    return mudar_status(ordem, Status.EM_EXECUCAO, usuario)


def concluir(ordem, usuario):
    if usuario.pk != ordem.tecnico_id:
        raise PermissionDenied("Só o técnico atribuído conclui o serviço.")
    return mudar_status(ordem, Status.CONCLUIDO, usuario)


def pode_cancelar(usuario, ordem):
    return usuario.pk == ordem.solicitante_id or pode_gerir(usuario, ordem)


def cancelar(ordem, usuario, justificativa):
    """RN06: só o solicitante ou o gestor, sempre com justificativa."""
    if not pode_cancelar(usuario, ordem):
        raise PermissionDenied("Só o solicitante ou o gestor podem cancelar esta OS.")
    justificativa = (justificativa or "").strip()
    if not justificativa:
        raise ValidationError("A justificativa do cancelamento é obrigatória.")
    ordem.justificativa_cancelamento = justificativa
    return mudar_status(ordem, Status.CANCELADO, usuario)


def avaliar(ordem, usuario, nota):
    if usuario.pk != ordem.solicitante_id:
        raise PermissionDenied("Só quem abriu o chamado pode avaliá-lo.")
    if ordem.status != Status.CONCLUIDO:
        raise ValidationError("Só é possível avaliar um serviço concluído.")
    if ordem.avaliacao is not None:
        raise ValidationError("Este serviço já foi avaliado.")
    if nota not in range(1, 6):
        raise ValidationError("A nota deve ser de 1 a 5.")
    ordem.avaliacao = nota
    ordem.save(update_fields=["avaliacao"])
    return ordem
