"""Alertas por e-mail. São enviados só depois que a transação é gravada no banco."""

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse

from contas.models import Perfil, Usuario


def _enviar(assunto, mensagem, destinatarios, ordem):
    emails = [u.email for u in destinatarios if u and u.is_active and u.email]
    if not emails:
        return
    link = settings.SITE_URL.rstrip("/") + reverse("ordens:detalhe", args=[ordem.pk])
    corpo = f"{mensagem}\n\nAbrir a OS: {link}\n\n— Vistore · SENAC-DF"
    # Falha no envio não pode desfazer a mudança da OS
    transaction.on_commit(
        lambda: send_mail(f"[Vistore] {assunto}", corpo, None, emails, fail_silently=True)
    )


def gestores_da_unidade(ordem):
    return Usuario.objects.filter(perfil=Perfil.GESTOR, is_active=True, unidade=ordem.local.unidade_id)


def avisar_atribuicao(ordem):
    _enviar(
        f"OS #{ordem.pk} atribuída a você",
        f"Você recebeu a OS #{ordem.pk} ({ordem.get_prioridade_display()}): {ordem.descricao}\n"
        f"Local: {ordem.local}\nLembre-se: preencha o checklist de segurança antes de iniciar.",
        [ordem.tecnico], ordem,
    )


def avisar_conclusao(ordem):
    _enviar(
        f"Seu chamado #{ordem.pk} foi concluído",
        f"O serviço do chamado #{ordem.pk} foi concluído. Avalie o atendimento de 1 a 5.",
        [ordem.solicitante], ordem,
    )


def avisar_revisao_seguranca(ordem, incidente):
    _enviar(
        f"Incidente na OS #{ordem.pk}: revisão de segurança",
        f"Foi registrado um incidente {incidente.get_gravidade_display().lower()} na OS #{ordem.pk} "
        f"com lesão ou afastamento. A OS aguarda a sua revisão.\n\n{incidente.descricao}",
        gestores_da_unidade(ordem), ordem,
    )


def avisar_devolucao(ordem, tecnico_anterior):
    _enviar(
        f"OS #{ordem.pk} voltou para atribuição",
        f"{tecnico_anterior.nome} não tem mais em dia os treinamentos exigidos (ou foi desativado). "
        f"A OS #{ordem.pk} voltou para 'Aguardando atribuição' e precisa de outro técnico.",
        list(gestores_da_unidade(ordem)) + [tecnico_anterior], ordem,
    )
