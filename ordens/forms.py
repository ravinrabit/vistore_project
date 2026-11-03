from django import forms

from contas.forms import EstiloBootstrapMixin
from contas.models import Perfil, Usuario
from estrutura.models import Equipamento, Local
from seguranca.models import TipoServico

from .models import OrdemServico


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
        self.fields["tecnico"].queryset = Usuario.objects.filter(
            perfil=Perfil.TECNICO, is_active=True, unidade=ordem.local.unidade_id
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


class ConfirmarForm(forms.Form):
    pass
