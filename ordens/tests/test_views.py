"""Testes das telas de ordens: quem vê o quê, quem pode cada ação e a ordem das listas (RN07)."""

from django.urls import reverse

from ordens import services
from ordens.models import OrdemServico, Prioridade, Status

from .base import DadosOrdensTestCase


class ListaEDetalheTests(DadosOrdensTestCase):
    def lista(self, usuario, **params):
        self.client.force_login(usuario)
        return list(self.client.get(reverse("ordens:lista"), params).context["object_list"])

    def test_cada_perfil_ve_so_as_suas_ordens(self):
        minha = self.nova_ordem()
        de_outro = self.nova_ordem(solicitante=self.outro_solicitante)
        da_outra_unidade = self.nova_ordem(local=self.local_enn)
        atribuida = self.ordem_atribuida()

        self.assertCountEqual(self.lista(self.solicitante), [minha, da_outra_unidade, atribuida])
        self.assertCountEqual(self.lista(self.gestor), [minha, de_outro, atribuida])
        self.assertEqual(self.lista(self.tecnico), [atribuida])
        self.assertEqual(len(self.lista(self.admin)), 4)

    def test_lista_mostra_urgentes_no_topo(self):
        baixa = self.nova_ordem(Prioridade.BAIXA)
        urgente = self.nova_ordem(Prioridade.URGENTE)
        alta = self.nova_ordem(Prioridade.ALTA)
        self.assertEqual(self.lista(self.gestor), [urgente, alta, baixa])

    def test_filtro_por_status(self):
        aberta = self.nova_ordem()
        self.ordem_atribuida()
        self.assertEqual(self.lista(self.gestor, status=Status.ABERTO), [aberta])

    def test_detalhe_de_ordem_alheia_da_404(self):
        ordem = self.nova_ordem()
        url = reverse("ordens:detalhe", args=[ordem.pk])
        for usuario in [self.outro_solicitante, self.gestor_enn, self.tecnico]:
            with self.subTest(usuario=usuario.email):
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_paginas_de_erro_amigaveis(self):
        ordem = self.nova_ordem()
        self.client.force_login(self.gestor_enn)
        resposta = self.client.get(reverse("ordens:detalhe", args=[ordem.pk]))
        self.assertTemplateUsed(resposta, "404.html")
        self.client.force_login(self.tecnico)
        resposta = self.client.get(reverse("estrutura:local_lista"))
        self.assertEqual(resposta.status_code, 403)
        self.assertTemplateUsed(resposta, "403.html")

    def test_detalhe_mostra_linha_do_tempo(self):
        ordem = self.ordem_atribuida()
        self.client.force_login(self.solicitante)
        resposta = self.client.get(reverse("ordens:detalhe", args=[ordem.pk]))
        self.assertEqual(len(resposta.context["historico"]), 3)
        self.assertContains(resposta, "Linha do tempo")


class AberturaTests(DadosOrdensTestCase):
    def test_solicitante_abre_chamado(self):
        self.client.force_login(self.solicitante)
        resposta = self.client.post(reverse("ordens:nova"), {
            "local": self.local.pk, "equipamento": self.equipamento.pk,
            "prioridade": Prioridade.URGENTE, "descricao": "Ar não liga",
        })
        ordem = OrdemServico.objects.get()
        self.assertRedirects(resposta, reverse("ordens:detalhe", args=[ordem.pk]))
        self.assertEqual(ordem.solicitante, self.solicitante)
        self.assertEqual(ordem.historico.count(), 1)

    def test_nao_abre_chamado_em_local_de_outra_unidade(self):
        self.client.force_login(self.solicitante)
        resposta = self.client.post(reverse("ordens:nova"), {
            "local": self.local_enn.pk, "prioridade": Prioridade.MEDIA, "descricao": "Teste",
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(OrdemServico.objects.exists())

    def test_tecnico_nao_abre_chamado(self):
        self.client.force_login(self.tecnico)
        self.assertEqual(self.client.get(reverse("ordens:nova")).status_code, 403)

    def test_anonimo_vai_para_o_login(self):
        resposta = self.client.get(reverse("ordens:lista"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("contas:login"), resposta["Location"])


class AcoesTests(DadosOrdensTestCase):
    def post(self, usuario, nome, ordem, dados=None):
        self.client.force_login(usuario)
        return self.client.post(reverse(f"ordens:{nome}", args=[ordem.pk]), dados or {})

    def test_fluxo_completo_pelas_telas(self):
        ordem = self.nova_ordem()
        self.post(self.gestor, "classificar", ordem, {"tipo_servico": self.tipo.pk, "riscos": "Piso molhado"})
        self.post(self.gestor, "atribuir", ordem, {"tecnico": self.tecnico.pk})
        self.post(self.tecnico, "checklist", ordem, {"area_isolada": "on"})
        self.post(self.tecnico, "iniciar", ordem)
        self.post(self.tecnico, "concluir", ordem)
        self.post(self.solicitante, "avaliar", ordem, {"nota": 4})
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, Status.CONCLUIDO)
        self.assertEqual(ordem.riscos, "Piso molhado")
        self.assertEqual(ordem.avaliacao, 4)

    def test_solicitante_nao_classifica(self):
        ordem = self.nova_ordem()
        self.post(self.solicitante, "classificar", ordem, {"tipo_servico": self.tipo.pk})
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, Status.ABERTO)

    def test_select_de_tecnicos_mostra_so_os_da_unidade(self):
        ordem = self.nova_ordem()
        services.classificar(ordem, self.gestor, self.tipo)
        self.client.force_login(self.gestor)
        resposta = self.client.get(reverse("ordens:atribuir", args=[ordem.pk]))
        self.assertEqual(list(resposta.context["form"].fields["tecnico"].queryset), [self.tecnico])

    def test_cancelamento_sem_justificativa_volta_com_erro(self):
        ordem = self.nova_ordem()
        resposta = self.post(self.solicitante, "cancelar", ordem, {"justificativa": ""})
        self.assertEqual(resposta.status_code, 200)
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, Status.ABERTO)

    def test_tecnico_nao_cancela(self):
        ordem = self.ordem_atribuida()
        self.post(self.tecnico, "cancelar", ordem, {"justificativa": "Não quero"})
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, Status.ATRIBUIDO)

    def test_gestor_de_outra_unidade_recebe_404(self):
        ordem = self.nova_ordem()
        resposta = self.post(self.gestor_enn, "classificar", ordem, {"tipo_servico": self.tipo.pk})
        self.assertEqual(resposta.status_code, 404)
