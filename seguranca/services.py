from django.utils import timezone

from contas.models import Perfil, Usuario

from .models import TreinamentoTecnico

CODIGO_NR10 = "NR-10"
CODIGO_NR35 = "NR-35"


def codigos_exigidos(tipo_servico):
    """RN04: além dos treinamentos ligados ao tipo, elétrico exige NR-10 e altura exige NR-35."""
    codigos = set(tipo_servico.treinamentos_exigidos.values_list("codigo", flat=True))
    if tipo_servico.eletrico:
        codigos.add(CODIGO_NR10)
    if tipo_servico.trabalho_em_altura:
        codigos.add(CODIGO_NR35)
    return codigos


def treinamentos_pendentes(tecnico, tipo_servico, data=None):
    """Códigos exigidos que o técnico não tem válidos na data (hoje, se não informada)."""
    data = data or timezone.localdate()
    realizados = TreinamentoTecnico.objects.filter(tecnico=tecnico).select_related("treinamento")
    validos = {r.treinamento.codigo for r in realizados if r.valido_em(data)}
    return sorted(codigos_exigidos(tipo_servico) - validos)


def tecnico_apto(tecnico, tipo_servico, data=None):
    """RN01: apto só com TODOS os treinamentos exigidos válidos na data."""
    return not treinamentos_pendentes(tecnico, tipo_servico, data)


def tecnicos_aptos(unidade_id, tipo_servico, data=None):
    candidatos = Usuario.objects.filter(perfil=Perfil.TECNICO, is_active=True, unidade=unidade_id)
    aptos = [t.pk for t in candidatos if tecnico_apto(t, tipo_servico, data)]
    return candidatos.filter(pk__in=aptos)
