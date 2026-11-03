"""Testes da RN02: o serviço só inicia depois do checklist de segurança confirmado."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from ordens import services
from ordens.models import Status
from ordens.tests.base import DadosOrdensTestCase
from seguranca.models import EPI


class ChecklistTests(DadosOrdensTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.luvas = EPI.objects.create(nome="Luvas isolantes", numero_ca="1")
        cls.oculos = EPI.objects.create(nome="Óculos", numero_ca="2")
        cls.tipo.epis_exigidos.set([cls.luvas, cls.oculos])

    def test_nao_inicia_sem_checklist(self):
        ordem = self.ordem_atribuida()
        with self.assertRaisesMessage(ValidationError, "checklist"):
            services.iniciar(ordem, self.tecnico)
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, Status.ATRIBUIDO)

    def test_todos_os_epis_exigidos_precisam_ser_confirmados(self):
        ordem = self.ordem_atribuida()
        with self.assertRaisesMessage(ValidationError, "Óculos"):
            services.confirmar_checklist(ordem, self.tecnico, [self.luvas], area_isolada=True)
        self.assertFalse(services.checklist_confirmado(ordem))

    def test_area_isolada_e_obrigatoria(self):
        ordem = self.ordem_atribuida()
        with self.assertRaises(ValidationError):
            services.confirmar_checklist(ordem, self.tecnico, [self.luvas, self.oculos], area_isolada=False)

    def test_so_o_tecnico_atribuido_preenche(self):
        ordem = self.ordem_atribuida()
        with self.assertRaises(PermissionDenied):
            services.confirmar_checklist(ordem, self.gestor, [self.luvas, self.oculos], area_isolada=True)

    def test_checklist_completo_libera_o_inicio(self):
        ordem = self.ordem_atribuida()
        checklist = services.confirmar_checklist(ordem, self.tecnico, [self.luvas, self.oculos], area_isolada=True)
        self.assertIsNotNone(checklist.confirmado_em)
        self.assertCountEqual(checklist.epis_confirmados.all(), [self.luvas, self.oculos])
        self.assertEqual(services.iniciar(ordem, self.tecnico).status, Status.EM_EXECUCAO)

    def test_tela_mostra_checklist_antes_de_iniciar(self):
        ordem = self.ordem_atribuida()
        self.client.force_login(self.tecnico)
        url = reverse("ordens:detalhe", args=[ordem.pk])
        acoes = self.client.get(url).context["acoes"]
        self.assertTrue(acoes["checklist"])
        self.assertFalse(acoes["iniciar"])

        self.client.post(reverse("ordens:checklist", args=[ordem.pk]), {
            "epis": [self.luvas.pk, self.oculos.pk], "area_isolada": "on",
        })
        acoes = self.client.get(url).context["acoes"]
        self.assertFalse(acoes["checklist"])
        self.assertTrue(acoes["iniciar"])
