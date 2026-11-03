"""Testes da RN09: a preventiva gera a OS 7 dias antes da data prevista."""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from ordens import services
from ordens.models import OrdemServico, Preventiva, Status

from .base import DadosOrdensTestCase


class PreventivaTests(DadosOrdensTestCase):
    def criar(self, dias_ate_a_data, ativa=True):
        return Preventiva.objects.create(
            equipamento=self.equipamento, tipo_servico=self.tipo, responsavel=self.gestor,
            periodicidade_dias=90, proxima_data=timezone.localdate() + timedelta(days=dias_ate_a_data),
            ativa=ativa,
        )

    def test_gera_os_classificada_ate_7_dias_antes(self):
        preventiva = self.criar(7)
        data_prevista = preventiva.proxima_data
        [ordem] = services.gerar_preventivas()
        self.assertEqual(ordem.status, Status.CLASSIFICADO)
        self.assertEqual(ordem.tipo_servico, self.tipo)
        self.assertEqual(ordem.preventiva, preventiva)
        self.assertEqual(ordem.solicitante, self.gestor)
        self.assertEqual(ordem.historico.last().usuario, None)
        preventiva.refresh_from_db()
        self.assertEqual(preventiva.proxima_data, data_prevista + timedelta(days=90))

    def test_nao_gera_antes_da_hora_nem_inativa(self):
        self.criar(8)
        self.criar(3, ativa=False)
        self.assertEqual(services.gerar_preventivas(), [])

    def test_rodar_de_novo_nao_duplica(self):
        self.criar(2)
        services.gerar_preventivas()
        services.gerar_preventivas()
        self.assertEqual(OrdemServico.objects.count(), 1)

    def test_comando(self):
        self.criar(0)
        saida = StringIO()
        call_command("gerar_preventivas", stdout=saida)
        self.assertIn("1 OS preventiva", saida.getvalue())

    def test_gestor_cadastra_e_vira_responsavel(self):
        self.client.force_login(self.gestor)
        self.client.post(reverse("ordens:preventiva_nova"), {
            "equipamento": self.equipamento.pk, "tipo_servico": self.tipo.pk,
            "periodicidade_dias": 30, "proxima_data": "2026-12-01", "ativa": "on",
        })
        self.assertEqual(Preventiva.objects.get().responsavel, self.gestor)

    def test_gestor_de_outra_unidade_nao_ve(self):
        preventiva = self.criar(30)
        self.client.force_login(self.gestor_enn)
        self.assertEqual(list(self.client.get(reverse("ordens:preventiva_lista")).context["object_list"]), [])
        url = reverse("ordens:preventiva_editar", args=[preventiva.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
