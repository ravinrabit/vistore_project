from django import template

from ordens.models import Prioridade, Status

register = template.Library()

CORES_STATUS = {
    Status.ABERTO: "secondary",
    Status.CLASSIFICADO: "info",
    Status.ATRIBUIDO: "primary",
    Status.EM_EXECUCAO: "warning",
    Status.CONCLUIDO: "success",
    Status.CANCELADO: "dark",
}

CORES_PRIORIDADE = {
    Prioridade.BAIXA: "light",
    Prioridade.MEDIA: "secondary",
    Prioridade.ALTA: "warning",
    Prioridade.URGENTE: "danger",
}


@register.filter
def cor_status(status):
    return CORES_STATUS.get(status, "secondary")


@register.filter
def cor_prioridade(prioridade):
    return CORES_PRIORIDADE.get(prioridade, "secondary")
