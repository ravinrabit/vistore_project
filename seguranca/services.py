from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from contas.models import Perfil, Usuario
from ordens.models import Status

from .models import Incidente, TreinamentoTecnico

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


def pode_registrar_incidente(usuario, ordem):
    if ordem.status not in (Status.ATRIBUIDO, Status.EM_EXECUCAO):
        return False
    if usuario.pk == ordem.tecnico_id or usuario.eh_admin:
        return True
    return usuario.eh_gestor and usuario.unidade_id == ordem.local.unidade_id


@transaction.atomic
def registrar_incidente(ordem, usuario, descricao, gravidade, houve_lesao=False, houve_afastamento=False):
    """RN08: incidente com lesão ou afastamento marca a OS para revisão do gestor."""
    if not pode_registrar_incidente(usuario, ordem):
        raise PermissionDenied("Só o técnico da OS ou o gestor registram incidentes durante o serviço.")
    incidente = Incidente.objects.create(
        ordem=ordem, descricao=descricao, gravidade=gravidade, houve_lesao=houve_lesao,
        houve_afastamento=houve_afastamento, registrado_por=usuario,
    )
    if houve_lesao or houve_afastamento:
        ordem.requer_revisao_seguranca = True
        ordem.save(update_fields=["requer_revisao_seguranca"])
    return incidente
