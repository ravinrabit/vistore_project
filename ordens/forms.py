from django import forms

from contas.forms import EstiloBootstrapMixin
from contas.models import Usuario
from estrutura.models import Equipamento, Local
from seguranca.models import EPI, TipoServico
from seguranca.services import codigos_exigidos, tecnicos_aptos

from .models import OrdemServico, Preventiva


class AbrirOrdemForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = OrdemServico
        fields = ["local", "equipamento", "prioridade", "descricao"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 4, "placeholder": "Descreva o problema"})}

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        locais = Local.objects.select_related("unidade")
        equipamentos = Equipamento.objects.select_related("local")
        if not usuario.eh_admin:
            locais = locais.filter(unidade=usuario.unidade)
            equipamentos = equipamentos.filter(local__unidade=usuario.unidade)
        self.fields["local"].queryset = locais
        self.fields["equipamento"].queryset = equipamentos
        self.fields["equipamento"].label_from_instance = lambda e: f"{e} · {e.local.sala}"
        self.fields["equipamento"].help_text = "Opcional. Deve ficar no local escolhido."

    def clean(self):
        dados = super().clean()
        local, equipamento = dados.get("local"), dados.get("equipamento")
        if local and equipamento and equipamento.local_id != local.pk:
            self.add_error("equipamento", "Este equipamento não fica no local escolhido.")
        return dados


class ClassificarForm(EstiloBootstrapMixin, forms.Form):
    tipo_servico = forms.ModelChoiceField(label="Tipo de serviço", queryset=TipoServico.objects.all())
    riscos = forms.CharField(
        label="Riscos identificados", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )


class AtribuirForm(EstiloBootstrapMixin, forms.Form):
    tecnico = forms.ModelChoiceField(label="Técnico", queryset=Usuario.objects.none())

    def __init__(self, *args, ordem, **kwargs):
        super().__init__(*args, **kwargs)
        campo = self.fields["tecnico"]
        campo.queryset = tecnicos_aptos(ordem.local.unidade_id, ordem.tipo_servico)
        exigidos = ", ".join(sorted(codigos_exigidos(ordem.tipo_servico))) or "nenhum"
        campo.help_text = f"Só aparecem técnicos com os treinamentos exigidos em dia. Exigidos: {exigidos}."
        if not campo.queryset.exists():
            campo.help_text = (
                f"Nenhum técnico da unidade tem em dia os treinamentos exigidos ({exigidos}). "
                "Atualize os treinamentos antes de atribuir."
            )


class CancelarForm(EstiloBootstrapMixin, forms.Form):
    justificativa = forms.CharField(
        label="Justificativa", widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Obrigatória. Explique por que a OS está sendo cancelada.",
    )


class AvaliarForm(EstiloBootstrapMixin, forms.Form):
    nota = forms.TypedChoiceField(
        label="Nota", coerce=int,
        choices=[(5, "5 — Excelente"), (4, "4 — Bom"), (3, "3 — Regular"), (2, "2 — Ruim"), (1, "1 — Péssimo")],
    )


class ChecklistForm(EstiloBootstrapMixin, forms.Form):
    epis = forms.ModelMultipleChoiceField(
        label="EPIs em uso", queryset=EPI.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    area_isolada = forms.BooleanField(label="A área está isolada e sinalizada", required=False)

    def __init__(self, *args, ordem, **kwargs):
        super().__init__(*args, **kwargs)
        campo = self.fields["epis"]
        campo.queryset = ordem.tipo_servico.epis_exigidos.all()
        if campo.queryset.exists():
            campo.help_text = "Marque cada EPI exigido pelo tipo de serviço que você está usando agora."
        else:
            del self.fields["epis"]

    def clean_epis(self):
        return list(self.cleaned_data["epis"])


class ConfirmarForm(forms.Form):
    pass


class PreventivaForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Preventiva
        fields = ["equipamento", "tipo_servico", "periodicidade_dias", "proxima_data", "ativa"]
        widgets = {"proxima_data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
        help_texts = {"proxima_data": "A OS é gerada automaticamente 7 dias antes desta data (RN09)."}

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        equipamentos = Equipamento.objects.select_related("local")
        if not usuario.eh_admin:
            equipamentos = equipamentos.filter(local__unidade=usuario.unidade_id)
        self.fields["equipamento"].queryset = equipamentos
        self.fields["periodicidade_dias"].min_value = 1
