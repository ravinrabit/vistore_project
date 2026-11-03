from django import template

from ordens.models import Prioridade, Status

register = template.Library()

# Sufixo da classe CSS badge-os--<valor> (ver static/css/vistore.css)
CORES_STATUS = {
    Status.ABERTO: "aberto",
    Status.CLASSIFICADO: "classificado",
    Status.ATRIBUIDO: "atribuido",
    Status.EM_EXECUCAO: "execucao",
    Status.CONCLUIDO: "concluido",
    Status.CANCELADO: "cancelado",
}

CORES_PRIORIDADE = {
    Prioridade.BAIXA: "baixa",
    Prioridade.MEDIA: "media",
    Prioridade.ALTA: "alta",
    Prioridade.URGENTE: "urgente",
}


@register.filter
def cor_status(status):
    return CORES_STATUS.get(status, "aberto")


@register.filter
def cor_prioridade(prioridade):
    return CORES_PRIORIDADE.get(prioridade, "media")
