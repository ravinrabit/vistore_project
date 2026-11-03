"""Testes das regras do fluxo da OS: RN05 (transições), RN06 (cancelamento) e RN07 (prioridade)."""

from django.core.exceptions import PermissionDenied, ValidationError

from ordens import services
from ordens.models import OrdemServico, Prioridade, Status

from .base import DadosOrdensTestCase


class TransicoesTests(DadosOrdensTestCase):
    def test_abrir_ordem_comeca_aberta_e_registra_historico(self):
        ordem = self.nova_ordem()
        self.assertEqual(ordem.status, Status.ABERTO)
        historico = ordem.historico.get()
        self.assertEqual(historico.status_anterior, "")
        self.assertEqual(historico.status_novo, Status.ABERTO)

    def test_fluxo_completo_grava_historico_e_datas(self):
        ordem = self.ordem_concluida()
        self.assertEqual(ordem.status, Status.CONCLUIDO)
        self.assertIsNotNone(ordem.iniciada_em)
        self.assertIsNotNone(ordem.concluida_em)
        self.assertEqual(
            list(ordem.historico.values_list("status_novo", flat=True)),
            [Status.ABERTO, Status.CLASSIFICADO, Status.ATRIBUIDO, Status.EM_EXECUCAO, Status.CONCLUIDO],
        )

    def test_nao_pula_etapas(self):
        ordem = self.nova_ordem()
        for status in [Status.ATRIBUIDO, Status.EM_EXECUCAO, Status.CONCLUIDO]:
            with self.subTest(status=status), self.assertRaises(ValidationError):
                services.mudar_status(ordem, status, self.gestor)
        self.assertEqual(ordem.historico.count(), 1)

    def test_concluida_e_cancelada_sao_finais(self):
        concluida = self.ordem_concluida()
        cancelada = services.cancelar(self.nova_ordem(), self.solicitante, "Aberto por engano")
        for ordem in [concluida, cancelada]:
            for status in Status.values:
                with self.subTest(ordem=ordem.status, status=status):
                    self.assertFalse(services.pode_mudar_para(ordem, status))

    def test_qualquer_status_antes_de_concluido_pode_ser_cancelado(self):
        for status in [Status.ABERTO, Status.CLASSIFICADO, Status.ATRIBUIDO, Status.EM_EXECUCAO]:
            with self.subTest(status=status):
                self.assertIn(Status.CANCELADO, services.TRANSICOES[status])

    def test_equipamento_precisa_ser_do_local(self):
        with self.assertRaises(ValidationError):
            services.abrir_ordem(
                self.solicitante, self.local_enn, "Teste", Prioridade.BAIXA, equipamento=self.equipamento
            )

    def test_gestor_de_outra_unidade_nao_classifica(self):
        with self.assertRaises(PermissionDenied):
            services.classificar(self.nova_ordem(), self.gestor_enn, self.tipo)

    def test_atribuir_exige_tecnico_da_unidade(self):
        ordem = self.nova_ordem()
        services.classificar(ordem, self.gestor, self.tipo)
        for usuario in [self.tecnico_enn, self.solicitante]:
            with self.subTest(usuario=usuario.email), self.assertRaises(ValidationError):
                services.atribuir(ordem, self.gestor, usuario)

    def test_so_o_tecnico_atribuido_inicia(self):
        ordem = self.ordem_atribuida()
        with self.assertRaises(PermissionDenied):
            services.iniciar(ordem, self.tecnico_enn)


class CancelamentoTests(DadosOrdensTestCase):
    def test_solicitante_cancela_com_justificativa(self):
        ordem = services.cancelar(self.nova_ordem(), self.solicitante, "Problema resolvido")
        self.assertEqual(ordem.status, Status.CANCELADO)
        self.assertEqual(ordem.justificativa_cancelamento, "Problema resolvido")

    def test_gestor_cancela_ordem_atribuida(self):
        ordem = services.cancelar(self.ordem_atribuida(), self.gestor, "Serviço terceirizado")
        self.assertEqual(ordem.status, Status.CANCELADO)

    def test_justificativa_e_obrigatoria(self):
        ordem = self.nova_ordem()
        for justificativa in ["", "   ", None]:
            with self.subTest(justificativa=justificativa), self.assertRaises(ValidationError):
                services.cancelar(ordem, self.solicitante, justificativa)
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, Status.ABERTO)

    def test_tecnico_e_outros_nao_cancelam(self):
        ordem = self.ordem_atribuida()
        for usuario in [self.tecnico, self.outro_solicitante, self.gestor_enn]:
            with self.subTest(usuario=usuario.email), self.assertRaises(PermissionDenied):
                services.cancelar(ordem, usuario, "Quero cancelar")

    def test_concluida_nao_pode_ser_cancelada(self):
        with self.assertRaises(ValidationError):
            services.cancelar(self.ordem_concluida(), self.gestor, "Tarde demais")


class AvaliacaoTests(DadosOrdensTestCase):
    def test_solicitante_avalia_servico_concluido(self):
        ordem = services.avaliar(self.ordem_concluida(), self.solicitante, 5)
        self.assertEqual(ordem.avaliacao, 5)

    def test_nao_avalia_antes_de_concluir(self):
        with self.assertRaises(ValidationError):
            services.avaliar(self.ordem_atribuida(), self.solicitante, 4)

    def test_nota_fora_da_faixa_e_recusada(self):
        ordem = self.ordem_concluida()
        for nota in [0, 6]:
            with self.subTest(nota=nota), self.assertRaises(ValidationError):
                services.avaliar(ordem, self.solicitante, nota)

    def test_so_avalia_uma_vez_e_so_o_solicitante(self):
        ordem = self.ordem_concluida()
        with self.assertRaises(PermissionDenied):
            services.avaliar(ordem, self.outro_solicitante, 3)
        services.avaliar(ordem, self.solicitante, 4)
        with self.assertRaises(ValidationError):
            services.avaliar(ordem, self.solicitante, 1)


class PrioridadeTests(DadosOrdensTestCase):
    def test_urgentes_aparecem_primeiro(self):
        baixa = self.nova_ordem(Prioridade.BAIXA)
        urgente = self.nova_ordem(Prioridade.URGENTE)
        media = self.nova_ordem(Prioridade.MEDIA)
        alta = self.nova_ordem(Prioridade.ALTA)
        ordenadas = list(services.ordenar_por_prioridade(OrdemServico.objects.all()))
        self.assertEqual(ordenadas, [urgente, alta, media, baixa])
