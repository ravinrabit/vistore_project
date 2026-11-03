from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Status(models.TextChoices):
    """RN05: Aberto → Classificado → Atribuído → Em execução → Concluído (ou Cancelado)."""

    ABERTO = "ABERTO", "Aberto"
    CLASSIFICADO = "CLASSIFICADO", "Aguardando atribuição"
    ATRIBUIDO = "ATRIBUIDO", "Atribuído"
    EM_EXECUCAO = "EM_EXECUCAO", "Em execução"
    CONCLUIDO = "CONCLUIDO", "Concluído"
    CANCELADO = "CANCELADO", "Cancelado"


class Prioridade(models.TextChoices):
    BAIXA = "BAIXA", "Baixa"
    MEDIA = "MEDIA", "Média"
    ALTA = "ALTA", "Alta"
    URGENTE = "URGENTE", "Urgente"


class OrdemServico(models.Model):
    """Chamado de manutenção. As regras do fluxo (RN01, RN02, RN05) entram na etapa 3."""

    descricao = models.TextField("descrição")
    prioridade = models.CharField(
        "prioridade", max_length=10, choices=Prioridade.choices, default=Prioridade.MEDIA
    )
    status = models.CharField("status", max_length=15, choices=Status.choices, default=Status.ABERTO)
    riscos = models.TextField("riscos identificados", blank=True)

    local = models.ForeignKey(
        "estrutura.Local", verbose_name="local", on_delete=models.PROTECT, related_name="ordens"
    )
    equipamento = models.ForeignKey(
        "estrutura.Equipamento", verbose_name="equipamento", on_delete=models.PROTECT,
        related_name="ordens", null=True, blank=True,
    )
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="solicitante", on_delete=models.PROTECT,
        related_name="ordens_solicitadas",
    )
    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="técnico", on_delete=models.PROTECT,
        related_name="ordens_atribuidas", null=True, blank=True,
        limit_choices_to={"perfil": "TECNICO"},
    )
    tipo_servico = models.ForeignKey(
        "seguranca.TipoServico", verbose_name="tipo de serviço", on_delete=models.PROTECT,
        related_name="ordens", null=True, blank=True,
    )
    preventiva = models.ForeignKey(
        "Preventiva", verbose_name="preventiva de origem", on_delete=models.PROTECT,
        related_name="ordens", null=True, blank=True,
    )

    aberta_em = models.DateTimeField("aberta em", auto_now_add=True)
    iniciada_em = models.DateTimeField("iniciada em", null=True, blank=True)
    concluida_em = models.DateTimeField("concluída em", null=True, blank=True)

    avaliacao = models.PositiveSmallIntegerField(
        "avaliação", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)], help_text="Nota de 1 a 5.",
    )
    justificativa_cancelamento = models.TextField("justificativa do cancelamento", blank=True)
    requer_revisao_seguranca = models.BooleanField("requer revisão de segurança", default=False)

    class Meta:
        verbose_name = "ordem de serviço"
        verbose_name_plural = "ordens de serviço"
        ordering = ["-aberta_em"]

    def __str__(self):
        return f"OS #{self.pk} — {self.get_status_display()}"


class HistoricoStatus(models.Model):
    """Registro de cada mudança de status de uma ordem (auditoria)."""

    ordem = models.ForeignKey(
        OrdemServico, verbose_name="ordem de serviço", on_delete=models.CASCADE, related_name="historico"
    )
    status_anterior = models.CharField(
        "status anterior", max_length=15, choices=Status.choices, blank=True
    )
    status_novo = models.CharField("status novo", max_length=15, choices=Status.choices)
    # Vazio quando a mudança é automática (ex.: comando verificar_treinamentos, RN03)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="usuário", on_delete=models.PROTECT,
        related_name="mudancas_status", null=True, blank=True,
    )
    data_hora = models.DateTimeField("data e hora", auto_now_add=True)

    class Meta:
        verbose_name = "histórico de status"
        verbose_name_plural = "históricos de status"
        ordering = ["data_hora", "id"]  # o id desempata mudanças gravadas no mesmo instante

    def __str__(self):
        anterior = self.get_status_anterior_display() or "—"
        return f"OS #{self.ordem_id}: {anterior} → {self.get_status_novo_display()}"


class ChecklistSeguranca(models.Model):

    ordem = models.OneToOneField(
        OrdemServico, verbose_name="ordem de serviço", on_delete=models.CASCADE, related_name="checklist"
    )
    epis_confirmados = models.ManyToManyField(
        "seguranca.EPI", verbose_name="EPIs confirmados", blank=True, related_name="checklists"
    )
    area_isolada = models.BooleanField("área isolada/sinalizada", default=False)
    confirmado_em = models.DateTimeField("confirmado em", null=True, blank=True)

    class Meta:
        verbose_name = "checklist de segurança"
        verbose_name_plural = "checklists de segurança"

    def __str__(self):
        return f"Checklist da OS #{self.ordem_id}"


class Preventiva(models.Model):

    equipamento = models.ForeignKey(
        "estrutura.Equipamento", verbose_name="equipamento", on_delete=models.PROTECT,
        related_name="preventivas",
    )
    tipo_servico = models.ForeignKey(
        "seguranca.TipoServico", verbose_name="tipo de serviço", on_delete=models.PROTECT,
        related_name="preventivas",
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="responsável", on_delete=models.PROTECT,
        related_name="preventivas", null=True, blank=True,
        help_text="Aparece como solicitante das OS geradas.",
    )
    periodicidade_dias = models.PositiveIntegerField("periodicidade (dias)")
    proxima_data = models.DateField("próxima data")
    ativa = models.BooleanField("ativa", default=True)

    class Meta:
        verbose_name = "preventiva"
        verbose_name_plural = "preventivas"
        ordering = ["proxima_data"]

    def __str__(self):
        return f"{self.tipo_servico} em {self.equipamento} (a cada {self.periodicidade_dias} dias)"
