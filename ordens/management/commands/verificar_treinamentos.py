from django.core.management.base import BaseCommand

from ordens.services import verificar_treinamentos


class Command(BaseCommand):
    help = (
        "RN03: devolve para 'Aguardando atribuição' as OS atribuídas cujo técnico ficou "
        "sem algum treinamento exigido. Pode ser agendado para rodar todo dia."
    )

    def handle(self, *args, **options):
        devolvidas = verificar_treinamentos()
        for ordem in devolvidas:
            self.stdout.write(f"  OS #{ordem.pk} voltou para 'Aguardando atribuição'.")
        self.stdout.write(self.style.SUCCESS(f"{len(devolvidas)} OS devolvida(s) para atribuição."))
