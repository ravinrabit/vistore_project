"""Testes dos alertas por e-mail (no teste o Django guarda os e-mails em mail.outbox)."""

from datetime import date, timedelta

from django.core import mail
from django.utils import timezone

from ordens import notificacoes, services
from seguranca import services as seguranca
from seguranca.models import Gravidade, TipoServico, Treinamento, TreinamentoTecnico

from .base import DadosOrdensTestCase


class NotificacoesTests(DadosOrdensTestCase):
    def test_tecnico_recebe_aviso_de_atribuicao(self):
        with self.captureOnCommitCallbacks(execute=True):
            ordem = self.ordem_atribuida()
        [email] = mail.outbox
        self.assertEqual(email.to, [self.tecnico.email])
        self.assertIn(f"OS #{ordem.pk}", email.subject)
        self.assertIn(f"/ordens/{ordem.pk}/", email.body)

    def test_solicitante_recebe_aviso_de_conclusao(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.ordem_concluida()
        self.assertEqual(mail.outbox[-1].to, [self.solicitante.email])
        self.assertIn("concluído", mail.outbox[-1].subject)

    def test_gestores_recebem_aviso_de_incidente_com_lesao(self):
        ordem = self.ordem_atribuida()
        with self.captureOnCommitCallbacks(execute=True):
            seguranca.registrar_incidente(ordem, self.tecnico, "Leve", Gravidade.LEVE)
        self.assertEqual(mail.outbox, [])
        with self.captureOnCommitCallbacks(execute=True):
            seguranca.registrar_incidente(ordem, self.tecnico, "Corte", Gravidade.MODERADA, houve_lesao=True)
        [email] = mail.outbox
        self.assertEqual(email.to, [self.gestor.email])  # só o gestor da unidade da OS

    def test_devolucao_da_rn03_avisa_gestor_e_tecnico(self):
        nr10 = Treinamento.objects.create(codigo="NR-10", nome="Eletricidade", validade_meses=24)
        realizacao = TreinamentoTecnico.objects.create(
            tecnico=self.tecnico, treinamento=nr10, data_realizacao=date(2025, 1, 1),
            data_validade=timezone.localdate() + timedelta(days=1),
        )
        ordem = self.nova_ordem()
        services.classificar(ordem, self.gestor, TipoServico.objects.create(nome="Elétrica", eletrico=True))
        services.atribuir(ordem, self.gestor, self.tecnico)
        realizacao.data_validade = timezone.localdate() - timedelta(days=1)
        realizacao.save()
        with self.captureOnCommitCallbacks(execute=True):
            services.verificar_treinamentos()
        self.assertCountEqual(mail.outbox[-1].to, [self.gestor.email, self.tecnico.email])

    def test_usuario_desativado_nao_recebe(self):
        self.tecnico.is_active = False
        self.tecnico.save()
        with self.captureOnCommitCallbacks(execute=True):
            ordem = self.nova_ordem()
            ordem.tecnico = self.tecnico
            notificacoes.avisar_atribuicao(ordem)
        self.assertEqual(mail.outbox, [])
