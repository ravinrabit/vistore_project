
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from contas.models import Perfil, Usuario
from estrutura.models import Equipamento, Local, TipoAmbiente, Unidade
from ordens.models import Preventiva
from seguranca.models import EPI, TipoServico, Treinamento, TreinamentoTecnico

SENHA_PADRAO = "vistore123"

UNIDADES = {
    "Taguatinga": "QSD 1, Área Especial, Taguatinga Sul — DF",
    "Ennius Muniz": "SCS Quadra 6, Asa Sul — Brasília/DF",
}

LOCAIS = [
    ("Taguatinga", "A", "Térreo", "Sala 101", TipoAmbiente.SALA_AULA,
     [("Ar-condicionado Split 18.000 BTUs", "TAG-0001"), ("Projetor multimídia", "TAG-0002")]),
    ("Taguatinga", "A", "1º andar", "Laboratório de Informática 1", TipoAmbiente.LABORATORIO,
     [("Ar-condicionado Split 24.000 BTUs", "TAG-0003")]),
    ("Taguatinga", "B", "Térreo", "Casa de máquinas", TipoAmbiente.TECNICO,
     [("Quadro de distribuição elétrica QD-01", "TAG-0004"), ("Bomba d'água", "TAG-0005")]),
    ("Taguatinga", "B", "Térreo", "Cozinha pedagógica", TipoAmbiente.COZINHA,
     [("Coifa industrial", "TAG-0006")]),
    ("Ennius Muniz", "Principal", "2º andar", "Auditório", TipoAmbiente.AUDITORIO,
     [("Sistema de som", "ENM-0001"), ("Luminárias do palco (6 m)", "ENM-0002")]),
    ("Ennius Muniz", "Principal", "Térreo", "Secretaria", TipoAmbiente.ADMINISTRATIVO,
     [("Ar-condicionado Split 12.000 BTUs", "ENM-0003")]),
    ("Ennius Muniz", "Anexo", "Cobertura", "Telhado", TipoAmbiente.AREA_EXTERNA,
     [("Calhas e rufos", "ENM-0004")]),
]

TREINAMENTOS = [
    ("NR-10", "Segurança em Instalações e Serviços em Eletricidade", 24),
    ("NR-35", "Trabalho em Altura", 24),
]

EPIS = [
    ("Capacete de segurança classe B", "10001", "Proteção contra impacto e choque elétrico."),
    ("Luvas isolantes de borracha", "10002", "Classe 0, para baixa tensão."),
    ("Óculos de proteção", "10003", "Proteção contra partículas."),
    ("Botina de segurança sem biqueira metálica", "10004", "Indicada para eletricistas."),
    ("Cinturão de segurança tipo paraquedista", "10005", "Obrigatório em trabalho em altura."),
    ("Talabarte duplo com absorvedor de energia", "10006", "Usado com o cinturão paraquedista."),
]

TIPOS_SERVICO = {
    "Manutenção elétrica": (
        "Tomadas, disjuntores, quadros e circuitos.", True, False,
        ["NR-10"], ["10001", "10002", "10003", "10004"],
    ),
    "Troca de luminárias em altura": (
        "Troca de lâmpadas e luminárias acima de 2 m.", True, True,
        ["NR-10", "NR-35"], ["10001", "10002", "10005", "10006"],
    ),
    "Limpeza de calhas e telhado": (
        "Serviços na cobertura das edificações.", False, True,
        ["NR-35"], ["10001", "10005", "10006"],
    ),
    "Manutenção de ar-condicionado": (
        "Limpeza de filtros e manutenção preventiva.", False, False,
        [], ["10003"],
    ),
    "Pintura e pequenos reparos": ("Pintura de paredes e reparos gerais.", False, False, [], ["10003"]),
}


class Command(BaseCommand):
    help = "Cria dados de exemplo: unidades, locais, equipamentos, usuários, NRs, EPIs e tipos de serviço."

    @transaction.atomic  # se algo falhar no meio, nada é gravado
    def handle(self, *args, **options):
        unidades = self._criar_unidades()
        self._criar_locais_e_equipamentos(unidades)
        treinamentos = self._criar_treinamentos()
        epis = self._criar_epis()
        self._criar_tipos_servico(treinamentos, epis)
        self._criar_usuarios(unidades, treinamentos)
        self._criar_preventivas()
        self.stdout.write(self.style.SUCCESS("Dados de exemplo criados com sucesso!"))

    def _criar_unidades(self):
        unidades = {}
        for nome, endereco in UNIDADES.items():
            unidades[nome], _ = Unidade.objects.update_or_create(nome=nome, defaults={"endereco": endereco})
        self.stdout.write(f"  {len(unidades)} unidades")
        return unidades

    def _criar_locais_e_equipamentos(self, unidades):
        total_equip = 0
        for unidade, bloco, andar, sala, tipo, equipamentos in LOCAIS:
            local, _ = Local.objects.update_or_create(
                unidade=unidades[unidade], bloco=bloco, andar=andar, sala=sala,
                defaults={"tipo_ambiente": tipo},
            )
            for nome, patrimonio in equipamentos:
                Equipamento.objects.update_or_create(
                    patrimonio=patrimonio, defaults={"nome": nome, "local": local}
                )
                total_equip += 1
        self.stdout.write(f"  {len(LOCAIS)} locais e {total_equip} equipamentos")

    def _criar_treinamentos(self):
        treinamentos = {}
        for codigo, nome, meses in TREINAMENTOS:
            treinamentos[codigo], _ = Treinamento.objects.update_or_create(
                codigo=codigo, defaults={"nome": nome, "validade_meses": meses}
            )
        self.stdout.write(f"  {len(treinamentos)} treinamentos (NRs)")
        return treinamentos

    def _criar_epis(self):
        epis = {}
        for nome, ca, descricao in EPIS:
            epis[ca], _ = EPI.objects.update_or_create(numero_ca=ca, defaults={"nome": nome, "descricao": descricao})
        self.stdout.write(f"  {len(epis)} EPIs")
        return epis

    def _criar_tipos_servico(self, treinamentos, epis):
        for nome, (descricao, eletrico, altura, nrs, cas) in TIPOS_SERVICO.items():
            tipo, _ = TipoServico.objects.update_or_create(
                nome=nome,
                defaults={"descricao": descricao, "eletrico": eletrico, "trabalho_em_altura": altura},
            )
            tipo.treinamentos_exigidos.set([treinamentos[c] for c in nrs])
            tipo.epis_exigidos.set([epis[ca] for ca in cas])
        self.stdout.write(f"  {len(TIPOS_SERVICO)} tipos de serviço")

    def _criar_usuarios(self, unidades, treinamentos):
        taguatinga = unidades["Taguatinga"]
        dados = [
            ("admin@vistore.test", "Administrador do Sistema", Perfil.ADMIN, None),
            ("gestor@vistore.test", "Gabriela Gestora", Perfil.GESTOR, taguatinga),
            ("tecnico@vistore.test", "Tiago Técnico", Perfil.TECNICO, taguatinga),
            ("solicitante@vistore.test", "Sofia Solicitante", Perfil.SOLICITANTE, taguatinga),
        ]
        for email, nome, perfil, unidade in dados:
            usuario, criado = Usuario.objects.get_or_create(
                email=email, defaults={"nome": nome, "perfil": perfil, "unidade": unidade}
            )
            if criado:
                usuario.set_password(SENHA_PADRAO)
                # O Administrador também acessa o Django Admin
                usuario.is_staff = usuario.is_superuser = perfil == Perfil.ADMIN
                usuario.save()

            if perfil == Perfil.TECNICO:
                # NR-10 em dia; NR-35 vencendo em 20 dias (bom para demonstrar alertas)
                hoje = timezone.localdate()
                TreinamentoTecnico.objects.get_or_create(
                    tecnico=usuario, treinamento=treinamentos["NR-10"],
                    defaults={"data_realizacao": hoje - timedelta(days=180)},
                )
                TreinamentoTecnico.objects.get_or_create(
                    tecnico=usuario, treinamento=treinamentos["NR-35"],
                    defaults={"data_realizacao": hoje - timedelta(days=700),
                              "data_validade": hoje + timedelta(days=20)},
                )

        self.stdout.write(f"  {len(dados)} usuários (senha: {SENHA_PADRAO})")
        for email, _, perfil, _ in dados:
            self.stdout.write(f"    {perfil.label:<20} {email}")

    def _criar_preventivas(self):
        # Limpeza do ar a cada 90 dias, vencendo em 5 dias: o gerar_preventivas já cria a OS
        Preventiva.objects.get_or_create(
            equipamento=Equipamento.objects.get(patrimonio="TAG-0001"),
            tipo_servico=TipoServico.objects.get(nome="Manutenção de ar-condicionado"),
            defaults={
                "responsavel": Usuario.objects.get(email="gestor@vistore.test"),
                "periodicidade_dias": 90,
                "proxima_data": timezone.localdate() + timedelta(days=5),
            },
        )
        self.stdout.write("  1 preventiva (rode: python manage.py gerar_preventivas)")
