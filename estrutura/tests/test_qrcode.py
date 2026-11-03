"""Testes do QR Code: a etiqueta aponta para o chamado já preenchido com o equipamento."""

from django.urls import reverse

from ordens.tests.base import DadosOrdensTestCase


class QRCodeTests(DadosOrdensTestCase):
    def test_etiqueta_aponta_para_chamado_do_equipamento(self):
        self.client.force_login(self.gestor)
        resposta = self.client.get(reverse("estrutura:equipamento_qrcode", args=[self.equipamento.pk]))
        self.assertTrue(resposta.context["url_chamado"].endswith(f"/ordens/nova/?equipamento={self.equipamento.pk}"))

    def test_chamado_vem_preenchido(self):
        self.client.force_login(self.solicitante)
        resposta = self.client.get(reverse("ordens:nova"), {"equipamento": self.equipamento.pk})
        form = resposta.context["form"]
        self.assertEqual(form.initial["equipamento"], self.equipamento)
        self.assertEqual(form.initial["local"], self.local)

    def test_equipamento_de_outra_unidade_e_ignorado(self):
        self.client.force_login(self.gestor_enn)
        resposta = self.client.get(reverse("ordens:nova"), {"equipamento": self.equipamento.pk})
        self.assertNotIn("equipamento", resposta.context["form"].initial)

    def test_parametro_invalido_nao_quebra(self):
        self.client.force_login(self.solicitante)
        self.assertEqual(self.client.get(reverse("ordens:nova"), {"equipamento": "abc"}).status_code, 200)

    def test_qrcode_de_outra_unidade_da_404(self):
        self.client.force_login(self.gestor_enn)
        url = reverse("estrutura:equipamento_qrcode", args=[self.equipamento.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
