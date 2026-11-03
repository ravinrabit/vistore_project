from django.core.management.base import BaseCommand

from ordens.services import gerar_preventivas


class Command(BaseCommand):
    help = (
        "RN09: gera a OS das preventivas ativas 7 dias antes da data prevista e agenda a próxima. "
        "Pode ser agendado para rodar todo dia."
    )

    def handle(self, *args, **options):
        geradas = gerar_preventivas()
        for ordem in geradas:
            self.stdout.write(f"  OS #{ordem.pk} gerada: {ordem.equipamento} ({ordem.tipo_servico}).")
        self.stdout.write(self.style.SUCCESS(f"{len(geradas)} OS preventiva(s) gerada(s)."))
