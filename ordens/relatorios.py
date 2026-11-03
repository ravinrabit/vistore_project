"""Números dos gráficos dos painéis. Recebe as OS já filtradas pelo perfil/unidade."""

from datetime import datetime, time, timedelta

from django.db.models import Count
from django.utils import timezone

from .models import Status

SEMANAS_NO_GRAFICO = 8


def ordens_por_status(ordens):
    contagem = dict(ordens.values_list("status").annotate(total=Count("id")).order_by())
    return [{"rotulo": rotulo, "valor": contagem.get(valor, 0)} for valor, rotulo in Status.choices]


def chamados_por_semana(ordens, hoje=None):
    """Chamados abertos em cada uma das últimas 8 semanas (segunda a domingo)."""
    hoje = hoje or timezone.localdate()
    segunda_atual = hoje - timedelta(days=hoje.weekday())
    semanas = []
    for i in range(SEMANAS_NO_GRAFICO - 1, -1, -1):
        inicio = segunda_atual - timedelta(weeks=i)
        # Intervalo de data e hora em vez de aberta_em__date: o __date no MariaDB depende das
        # tabelas de fuso horário do servidor, que o MariaDB portátil não traz.
        de = timezone.make_aware(datetime.combine(inicio, time.min))
        semanas.append({
            "rotulo": f"{inicio:%d/%m}",
            "valor": ordens.filter(aberta_em__gte=de, aberta_em__lt=de + timedelta(weeks=1)).count(),
        })
    return semanas
