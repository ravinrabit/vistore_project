from django.test import TestCase

from contas.models import Perfil, Usuario
from estrutura.models import Equipamento, Local, Unidade
from ordens import services
from ordens.models import Prioridade
from seguranca.models import TipoServico


class DadosOrdensTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.taguatinga = Unidade.objects.create(nome="Taguatinga")
        cls.ennius = Unidade.objects.create(nome="Ennius Muniz")
        cls.local = Local.objects.create(unidade=cls.taguatinga, bloco="A", andar="Térreo", sala="101")
        cls.local_enn = Local.objects.create(unidade=cls.ennius, bloco="B", andar="1º", sala="201")
        cls.equipamento = Equipamento.objects.create(local=cls.local, nome="Ar-condicionado", patrimonio="T-001")
        cls.tipo = TipoServico.objects.create(nome="Manutenção de ar-condicionado")

        def criar(email, perfil, unidade=None):
            return Usuario.objects.create_user(email=email, password="x", nome=email, perfil=perfil, unidade=unidade)

        cls.admin = criar("admin@t.com", Perfil.ADMIN)
        cls.gestor = criar("gestor@t.com", Perfil.GESTOR, cls.taguatinga)
        cls.gestor_enn = criar("gestor.enn@t.com", Perfil.GESTOR, cls.ennius)
        cls.tecnico = criar("tecnico@t.com", Perfil.TECNICO, cls.taguatinga)
        cls.tecnico_enn = criar("tecnico.enn@t.com", Perfil.TECNICO, cls.ennius)
        cls.solicitante = criar("solic@t.com", Perfil.SOLICITANTE, cls.taguatinga)
        cls.outro_solicitante = criar("outro@t.com", Perfil.SOLICITANTE, cls.taguatinga)

    def nova_ordem(self, prioridade=Prioridade.MEDIA, local=None, solicitante=None):
        return services.abrir_ordem(
            solicitante=solicitante or self.solicitante, local=local or self.local,
            descricao="Ar pingando", prioridade=prioridade,
        )

    def ordem_atribuida(self):
        ordem = self.nova_ordem()
        services.classificar(ordem, self.gestor, self.tipo)
        return services.atribuir(ordem, self.gestor, self.tecnico)

    def ordem_concluida(self):
        ordem = self.ordem_atribuida()
        services.iniciar(ordem, self.tecnico)
        return services.concluir(ordem, self.tecnico)
