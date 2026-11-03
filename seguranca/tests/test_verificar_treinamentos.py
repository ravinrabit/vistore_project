"""Testes da RN03: treinamento vencido com o serviço ainda não iniciado devolve a OS para atribuição."""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone

from ordens import services
from ordens.models import ChecklistSeguranca, Status
from ordens.tests.base import DadosOrdensTestCase
from seguranca.models import TipoServico, Treinamento, TreinamentoTecnico


class VerificarTreinamentosTests(DadosOrdensTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.nr10 = Treinamento.objects.create(codigo="NR-10", nome="Eletricidade", validade_meses=24)
        cls.eletrico = TipoServico.objects.create(nome="Elétrica", eletrico=True)

    def setUp(self):
        hoje = timezone.localdate()
        self.realizacao = TreinamentoTecnico.objects.create(
            tecnico=self.tecnico, treinamento=self.nr10,
            data_realizacao=hoje - timedelta(days=700), data_validade=hoje + timedelta(days=5),
        )
        self.ordem = self.nova_ordem()
        services.classificar(self.ordem, self.gestor, self.eletrico)
        services.atribuir(self.ordem, self.gestor, self.tecnico)

    def vencer_treinamento(self):
        self.realizacao.data_validade = timezone.localdate() - timedelta(days=1)
        self.realizacao.save()

    def test_treinamento_em_dia_mantem_a_atribuicao(self):
        self.assertEqual(services.verificar_treinamentos(), [])
        self.ordem.refresh_from_db()
        self.assertEqual(self.ordem.status, Status.ATRIBUIDO)

    def test_treinamento_vencido_devolve_a_os(self):
        services.confirmar_checklist(self.ordem, self.tecnico, [], area_isolada=True)
        self.vencer_treinamento()
        self.assertEqual(services.verificar_treinamentos(), [self.ordem])
        self.ordem.refresh_from_db()
        self.assertEqual(self.ordem.status, Status.CLASSIFICADO)
        self.assertIsNone(self.ordem.tecnico)
        self.assertFalse(ChecklistSeguranca.objects.filter(ordem=self.ordem).exists())
        ultimo = self.ordem.historico.last()
        self.assertEqual(ultimo.status_anterior, Status.ATRIBUIDO)
        self.assertIsNone(ultimo.usuario)  # mudança feita pelo sistema

    def test_os_ja_iniciada_nao_e_afetada(self):
        services.confirmar_checklist(self.ordem, self.tecnico, [], area_isolada=True)
        services.iniciar(self.ordem, self.tecnico)
        self.vencer_treinamento()
        self.assertEqual(services.verificar_treinamentos(), [])

    def test_vencimento_futuro_e_verificado_na_data_informada(self):
        daqui_10_dias = timezone.localdate() + timedelta(days=10)
        self.assertEqual(services.verificar_treinamentos(daqui_10_dias), [self.ordem])

    def test_comando(self):
        self.vencer_treinamento()
        saida = StringIO()
        call_command("verificar_treinamentos", stdout=saida)
        self.assertIn(f"OS #{self.ordem.pk}", saida.getvalue())
