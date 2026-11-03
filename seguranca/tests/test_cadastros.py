"""Testes dos cadastros de segurança: quem acessa e o filtro por unidade."""

from datetime import date

from django.urls import reverse

from ordens.tests.base import DadosOrdensTestCase
from seguranca.models import TipoServico, Treinamento, TreinamentoTecnico


class CadastrosTests(DadosOrdensTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.nr10 = Treinamento.objects.create(codigo="NR-10", nome="Eletricidade", validade_meses=24)
        cls.realizacao = TreinamentoTecnico.objects.create(
            tecnico=cls.tecnico, treinamento=cls.nr10, data_realizacao=date(2026, 1, 10)
        )
        cls.realizacao_enn = TreinamentoTecnico.objects.create(
            tecnico=cls.tecnico_enn, treinamento=cls.nr10, data_realizacao=date(2026, 1, 10)
        )

    def test_tecnico_e_solicitante_nao_acessam(self):
        rotas = ["seguranca:treinamento_lista", "seguranca:realizacao_lista", "seguranca:epi_lista", "seguranca:tipo_lista"]
        for usuario in [self.tecnico, self.solicitante]:
            self.client.force_login(usuario)
            for rota in rotas:
                with self.subTest(usuario=usuario.email, rota=rota):
                    self.assertEqual(self.client.get(reverse(rota)).status_code, 403)

    def test_gestor_ve_so_treinamentos_dos_tecnicos_da_unidade(self):
        self.client.force_login(self.gestor)
        resposta = self.client.get(reverse("seguranca:realizacao_lista"))
        self.assertEqual(list(resposta.context["object_list"]), [self.realizacao])
        url = reverse("seguranca:realizacao_editar", args=[self.realizacao_enn.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_gestor_registra_treinamento_e_validade_e_calculada(self):
        self.client.force_login(self.gestor)
        nr35 = Treinamento.objects.create(codigo="NR-35", nome="Altura", validade_meses=24)
        self.client.post(reverse("seguranca:realizacao_nova"), {
            "tecnico": self.tecnico.pk, "treinamento": nr35.pk, "data_realizacao": "2026-03-31",
        })
        realizacao = TreinamentoTecnico.objects.get(treinamento=nr35)
        self.assertEqual(realizacao.data_validade, date(2028, 3, 31))

    def test_gestor_nao_registra_treinamento_de_tecnico_de_outra_unidade(self):
        self.client.force_login(self.gestor)
        resposta = self.client.post(reverse("seguranca:realizacao_nova"), {
            "tecnico": self.tecnico_enn.pk, "treinamento": self.nr10.pk, "data_realizacao": "2026-03-01",
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(TreinamentoTecnico.objects.filter(tecnico=self.tecnico_enn).count(), 1)

    def test_so_admin_altera_tipos_de_servico(self):
        self.client.force_login(self.gestor)
        self.assertEqual(self.client.get(reverse("seguranca:tipo_lista")).status_code, 200)
        self.assertEqual(self.client.get(reverse("seguranca:tipo_novo")).status_code, 403)
        self.client.force_login(self.admin)
        self.client.post(reverse("seguranca:tipo_novo"), {
            "nome": "Elétrica predial", "eletrico": "on", "treinamentos_exigidos": [self.nr10.pk],
        })
        self.assertTrue(TipoServico.objects.get(nome="Elétrica predial").eletrico)

    def test_treinamento_em_uso_nao_e_excluido(self):
        self.client.force_login(self.gestor)
        resposta = self.client.post(reverse("seguranca:treinamento_excluir", args=[self.nr10.pk]), follow=True)
        self.assertTrue(Treinamento.objects.filter(pk=self.nr10.pk).exists())
        self.assertContains(resposta, "não pode ser excluído")
