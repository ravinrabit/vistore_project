"""Testes da RN01 (técnico com todos os treinamentos válidos) e da RN04 (NR-10 e NR-35)."""

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from contas.models import Perfil, Usuario
from ordens import services
from ordens.models import Status
from ordens.tests.base import DadosOrdensTestCase
from seguranca import services as seguranca
from seguranca.models import TipoServico, Treinamento, TreinamentoTecnico


class TreinamentosTestCase(DadosOrdensTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.nr10 = Treinamento.objects.create(codigo="NR-10", nome="Eletricidade", validade_meses=24)
        cls.nr35 = Treinamento.objects.create(codigo="NR-35", nome="Altura", validade_meses=24)
        cls.nr33 = Treinamento.objects.create(codigo="NR-33", nome="Espaço confinado", validade_meses=12)
        cls.eletrico = TipoServico.objects.create(nome="Elétrica", eletrico=True)
        cls.altura = TipoServico.objects.create(nome="Telhado", trabalho_em_altura=True)
        cls.luminaria = TipoServico.objects.create(nome="Luminária alta", eletrico=True, trabalho_em_altura=True)
        cls.confinado = TipoServico.objects.create(nome="Caixa d'água")
        cls.confinado.treinamentos_exigidos.add(cls.nr33)

    def dar_treinamento(self, treinamento, tecnico=None, realizado_ha=30, validade=None):
        return TreinamentoTecnico.objects.create(
            tecnico=tecnico or self.tecnico, treinamento=treinamento,
            data_realizacao=timezone.localdate() - timedelta(days=realizado_ha), data_validade=validade,
        )

    def ordem_classificada(self, tipo):
        ordem = self.nova_ordem()
        return services.classificar(ordem, self.gestor, tipo)


class ExigenciasTests(TreinamentosTestCase):
    def test_rn04_eletrico_exige_nr10_e_altura_exige_nr35(self):
        self.assertEqual(seguranca.codigos_exigidos(self.eletrico), {"NR-10"})
        self.assertEqual(seguranca.codigos_exigidos(self.altura), {"NR-35"})
        self.assertEqual(seguranca.codigos_exigidos(self.luminaria), {"NR-10", "NR-35"})

    def test_treinamentos_ligados_ao_tipo_tambem_sao_exigidos(self):
        self.assertEqual(seguranca.codigos_exigidos(self.confinado), {"NR-33"})

    def test_precisa_de_todos_os_treinamentos(self):
        self.dar_treinamento(self.nr10)
        self.assertFalse(seguranca.tecnico_apto(self.tecnico, self.luminaria))
        self.dar_treinamento(self.nr35)
        self.assertTrue(seguranca.tecnico_apto(self.tecnico, self.luminaria))

    def test_treinamento_vencido_nao_vale(self):
        self.dar_treinamento(self.nr10, realizado_ha=800, validade=timezone.localdate() - timedelta(days=1))
        self.assertEqual(seguranca.treinamentos_pendentes(self.tecnico, self.eletrico), ["NR-10"])

    def test_validade_e_conferida_na_data_informada(self):
        self.dar_treinamento(self.nr10, validade=date.today() + timedelta(days=10))
        self.assertTrue(seguranca.tecnico_apto(self.tecnico, self.eletrico))
        self.assertFalse(seguranca.tecnico_apto(self.tecnico, self.eletrico, date.today() + timedelta(days=11)))


class AtribuicaoTests(TreinamentosTestCase):
    def test_rn01_nao_atribui_tecnico_sem_nr(self):
        ordem = self.ordem_classificada(self.eletrico)
        with self.assertRaisesMessage(ValidationError, "NR-10"):
            services.atribuir(ordem, self.gestor, self.tecnico)
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, Status.CLASSIFICADO)

    def test_atribui_tecnico_apto(self):
        self.dar_treinamento(self.nr10)
        ordem = services.atribuir(self.ordem_classificada(self.eletrico), self.gestor, self.tecnico)
        self.assertEqual(ordem.status, Status.ATRIBUIDO)

    def test_select_mostra_so_tecnicos_aptos(self):
        apto = Usuario.objects.create_user(
            email="apto@t.com", password="x", nome="Apto", perfil=Perfil.TECNICO, unidade=self.taguatinga
        )
        self.dar_treinamento(self.nr35, tecnico=apto)
        ordem = self.ordem_classificada(self.altura)
        self.client.force_login(self.gestor)
        resposta = self.client.get(reverse("ordens:atribuir", args=[ordem.pk]))
        self.assertEqual(list(resposta.context["form"].fields["tecnico"].queryset), [apto])
