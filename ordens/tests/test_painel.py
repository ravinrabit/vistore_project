"""Testes dos painéis: cada perfil vê as próprias pendências, nunca as de outra unidade."""

from django.urls import reverse

from ordens import services
from ordens.models import Prioridade

from .base import DadosOrdensTestCase


class PainelTests(DadosOrdensTestCase):
    def contexto(self, usuario):
        self.client.force_login(usuario)
        return self.client.get(reverse("contas:painel")).context

    def test_tecnico_ve_so_os_proprios_servicos_em_aberto(self):
        em_aberto = self.ordem_atribuida()
        self.ordem_concluida()
        self.nova_ordem()
        contexto = self.contexto(self.tecnico)
        self.assertEqual(list(contexto["meus_servicos"]), [em_aberto])
        self.assertEqual(contexto["ordens_atribuidas"], 1)

    def test_gestor_ve_pendencias_so_da_sua_unidade_com_urgentes_no_topo(self):
        media = self.nova_ordem(Prioridade.MEDIA)
        urgente = self.nova_ordem(Prioridade.URGENTE)
        classificada = self.nova_ordem(Prioridade.BAIXA)
        services.classificar(classificada, self.gestor, self.tipo)
        self.nova_ordem(Prioridade.URGENTE, local=self.local_enn)
        self.ordem_atribuida()

        contexto = self.contexto(self.gestor)
        self.assertEqual(list(contexto["pendencias"]), [urgente, media, classificada])
        self.assertEqual(contexto["ordens_abertas"], 2)
        self.assertEqual(contexto["aguardando_atribuicao"], 1)
        self.assertEqual(contexto["urgentes_pendentes"], 1)

    def test_solicitante_ve_servicos_para_avaliar(self):
        concluida = self.ordem_concluida()
        self.nova_ordem(solicitante=self.outro_solicitante)
        contexto = self.contexto(self.solicitante)
        self.assertEqual(contexto["para_avaliar"], 1)
        self.assertEqual(list(contexto["ultimas"]), [concluida])

    def test_graficos_do_gestor_contam_so_a_unidade(self):
        self.nova_ordem()
        self.ordem_atribuida()
        self.nova_ordem(local=self.local_enn)
        contexto = self.contexto(self.gestor)
        por_status = {item["rotulo"]: item["valor"] for item in contexto["por_status"]}
        self.assertEqual(por_status["Aberto"], 1)
        self.assertEqual(por_status["Atribuído"], 1)
        self.assertEqual(len(contexto["por_semana"]), 8)
        self.assertEqual(contexto["por_semana"][-1]["valor"], 2)  # as 2 OS desta semana
