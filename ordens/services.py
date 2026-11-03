from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from contas.models import Perfil
from seguranca.services import pode_registrar_incidente, tecnico_apto, treinamentos_pendentes

from . import notificacoes
from .models import ChecklistSeguranca, HistoricoStatus, OrdemServico, Preventiva, Prioridade, Status

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
    pendentes = treinamentos_pendentes(tecnico, ordem.tipo_servico)
    if pendentes:
        raise ValidationError(
            f"{tecnico.nome} não tem treinamento válido em: {', '.join(pendentes)} (RN01)."
        )
    ordem.tecnico = tecnico
    mudar_status(ordem, Status.ATRIBUIDO, usuario)
    notificacoes.avisar_atribuicao(ordem)
    return ordem


@transaction.atomic
def devolver_para_atribuicao(ordem, usuario=None):
    """Volta a OS para "Aguardando atribuição": tira o técnico e descarta o checklist."""
    ChecklistSeguranca.objects.filter(ordem=ordem).delete()
    ordem.tecnico = None
    return mudar_status(ordem, Status.CLASSIFICADO, usuario)


def verificar_treinamentos(data=None):
    """RN03: OS atribuída cujo técnico ficou sem algum treinamento exigido volta para atribuição."""
    devolvidas = []
    atribuidas = OrdemServico.objects.filter(status=Status.ATRIBUIDO).select_related("tecnico", "tipo_servico")
    for ordem in atribuidas:
        tecnico = ordem.tecnico
        if not tecnico.is_active or not tecnico_apto(tecnico, ordem.tipo_servico, data):
            devolvidas.append(devolver_para_atribuicao(ordem))
            notificacoes.avisar_devolucao(ordem, tecnico)
    return devolvidas


def checklist_confirmado(ordem):
    return ChecklistSeguranca.objects.filter(ordem=ordem, confirmado_em__isnull=False).exists()


@transaction.atomic
def confirmar_checklist(ordem, usuario, epis, area_isolada):
    """RN02: o técnico confirma cada EPI exigido pelo tipo de serviço e o isolamento da área."""
    if usuario.pk != ordem.tecnico_id:
        raise PermissionDenied("Só o técnico atribuído preenche o checklist.")
    if ordem.status != Status.ATRIBUIDO:
        raise ValidationError("O checklist é preenchido antes de iniciar o serviço.")
    exigidos = ordem.tipo_servico.epis_exigidos.all()
    faltando = [epi.nome for epi in exigidos if epi not in epis]
    if faltando:
        raise ValidationError(f"Confirme todos os EPIs exigidos. Faltam: {', '.join(faltando)}.")
    if not area_isolada:
        raise ValidationError("Confirme que a área está isolada e sinalizada.")
    checklist, _ = ChecklistSeguranca.objects.get_or_create(ordem=ordem)
    checklist.area_isolada = True
    checklist.confirmado_em = timezone.now()
    checklist.save()
    checklist.epis_confirmados.set(epis)
    return checklist


def iniciar(ordem, usuario):
    if usuario.pk != ordem.tecnico_id:
        raise PermissionDenied("Só o técnico atribuído inicia o serviço.")
    if not checklist_confirmado(ordem):
        raise ValidationError("Preencha o checklist de segurança antes de iniciar (RN02).")
    return mudar_status(ordem, Status.EM_EXECUCAO, usuario)


def concluir(ordem, usuario):
    if usuario.pk != ordem.tecnico_id:
        raise PermissionDenied("Só o técnico atribuído conclui o serviço.")
    if ordem.requer_revisao_seguranca:
        raise ValidationError(
            "Esta OS teve incidente com lesão ou afastamento e aguarda a revisão do gestor (RN08)."
        )
    mudar_status(ordem, Status.CONCLUIDO, usuario)
    notificacoes.avisar_conclusao(ordem)
    return ordem


def concluir_revisao(ordem, usuario):
    if not pode_gerir(usuario, ordem):
        raise PermissionDenied("Só o gestor da unidade conclui a revisão de segurança.")
    if not ordem.requer_revisao_seguranca:
        raise ValidationError("Esta OS não está em revisão de segurança.")
    ordem.requer_revisao_seguranca = False
    ordem.save(update_fields=["requer_revisao_seguranca"])
    return ordem


def pode_cancelar(usuario, ordem):
    return usuario.pk == ordem.solicitante_id or pode_gerir(usuario, ordem)


def acoes_disponiveis(usuario, ordem):
    """Usado pelas telas para decidir quais botões mostrar e quais ações liberar."""
    gestor = pode_gerir(usuario, ordem)
    eh_tecnico_da_os = usuario.pk == ordem.tecnico_id
    confirmado = eh_tecnico_da_os and ordem.status == Status.ATRIBUIDO and checklist_confirmado(ordem)
    return {
        "classificar": gestor and ordem.status == Status.ABERTO,
        "atribuir": gestor and ordem.status == Status.CLASSIFICADO,
        "checklist": eh_tecnico_da_os and ordem.status == Status.ATRIBUIDO and not confirmado,
        "iniciar": eh_tecnico_da_os and ordem.status == Status.ATRIBUIDO and confirmado,
        "concluir": (
            eh_tecnico_da_os and ordem.status == Status.EM_EXECUCAO and not ordem.requer_revisao_seguranca
        ),
        "incidente": pode_registrar_incidente(usuario, ordem),
        "revisar": gestor and ordem.requer_revisao_seguranca,
        "cancelar": pode_cancelar(usuario, ordem) and pode_mudar_para(ordem, Status.CANCELADO),
        "avaliar": (
            usuario.pk == ordem.solicitante_id
            and ordem.status == Status.CONCLUIDO
            and ordem.avaliacao is None
        ),
    }


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


DIAS_ANTECEDENCIA_PREVENTIVA = 7


@transaction.atomic
def gerar_ordem_preventiva(preventiva):
    """Cria a OS já classificada (o tipo de serviço é conhecido) e agenda a próxima data."""
    equipamento = preventiva.equipamento
    ordem = abrir_ordem(
        solicitante=preventiva.responsavel, local=equipamento.local, equipamento=equipamento,
        descricao=f"Manutenção preventiva: {preventiva.tipo_servico} em {equipamento} "
                  f"(prevista para {preventiva.proxima_data:%d/%m/%Y}).",
        prioridade=Prioridade.MEDIA,
    )
    ordem.preventiva = preventiva
    ordem.tipo_servico = preventiva.tipo_servico
    mudar_status(ordem, Status.CLASSIFICADO, None)
    preventiva.proxima_data += timedelta(days=preventiva.periodicidade_dias)
    preventiva.save(update_fields=["proxima_data"])
    return ordem


def gerar_preventivas(hoje=None):
    """RN09: gera a OS das preventivas ativas cuja data prevista está a 7 dias ou menos."""
    hoje = hoje or timezone.localdate()
    limite = hoje + timedelta(days=DIAS_ANTECEDENCIA_PREVENTIVA)
    pendentes = Preventiva.objects.filter(ativa=True, proxima_data__lte=limite, responsavel__isnull=False)
    return [gerar_ordem_preventiva(p) for p in pendentes.select_related("equipamento__local", "tipo_servico")]
