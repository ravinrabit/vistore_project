"""Testes da RN08: incidente com lesão ou afastamento coloca a OS em revisão de segurança."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from ordens import services
from ordens.models import Status
from ordens.tests.base import DadosOrdensTestCase
from seguranca import services as seguranca
from seguranca.models import Gravidade


class IncidenteTests(DadosOrdensTestCase):
    def ordem_em_execucao(self):
        ordem = self.ordem_atribuida()
        services.confirmar_checklist(ordem, self.tecnico, [], area_isolada=True)
        return services.iniciar(ordem, self.tecnico)

    def test_incidente_leve_nao_marca_revisao(self):
        ordem = self.ordem_em_execucao()
        seguranca.registrar_incidente(ordem, self.tecnico, "Escorregou sem se machucar", Gravidade.LEVE)
        self.assertFalse(ordem.requer_revisao_seguranca)

    def test_lesao_ou_afastamento_marcam_revisao(self):
        for campo in ["houve_lesao", "houve_afastamento"]:
            with self.subTest(campo=campo):
                ordem = self.ordem_em_execucao()
                seguranca.registrar_incidente(ordem, self.tecnico, "Corte na mão", Gravidade.MODERADA, **{campo: True})
                ordem.refresh_from_db()
                self.assertTrue(ordem.requer_revisao_seguranca)

    def test_os_em_revisao_so_conclui_depois_da_liberacao(self):
        ordem = self.ordem_em_execucao()
        seguranca.registrar_incidente(ordem, self.tecnico, "Choque", Gravidade.GRAVE, houve_afastamento=True)
        with self.assertRaisesMessage(ValidationError, "RN08"):
            services.concluir(ordem, self.tecnico)
        with self.assertRaises(PermissionDenied):
            services.concluir_revisao(ordem, self.tecnico)
        services.concluir_revisao(ordem, self.gestor)
        self.assertEqual(services.concluir(ordem, self.tecnico).status, Status.CONCLUIDO)

    def test_quem_pode_registrar(self):
        ordem = self.ordem_em_execucao()
        for usuario in [self.solicitante, self.gestor_enn, self.tecnico_enn]:
            with self.subTest(usuario=usuario.email), self.assertRaises(PermissionDenied):
                seguranca.registrar_incidente(ordem, usuario, "Teste", Gravidade.LEVE)
        seguranca.registrar_incidente(ordem, self.gestor, "Registrado pelo gestor", Gravidade.LEVE)

    def test_nao_registra_fora_do_servico(self):
        with self.assertRaises(PermissionDenied):
            seguranca.registrar_incidente(self.nova_ordem(), self.gestor, "Antes de atribuir", Gravidade.LEVE)

    def test_tela_de_incidente(self):
        ordem = self.ordem_em_execucao()
        self.client.force_login(self.tecnico)
        resposta = self.client.post(reverse("ordens:incidente", args=[ordem.pk]), {
            "gravidade": Gravidade.MODERADA, "descricao": "Queda da escada", "houve_lesao": "on",
        }, follow=True)
        self.assertContains(resposta, "OS em revisão de segurança")
        self.assertFalse(resposta.context["acoes"]["concluir"])
