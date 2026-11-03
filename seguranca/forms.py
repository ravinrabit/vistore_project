from django import forms

from contas.forms import EstiloBootstrapMixin

from .models import Incidente


class IncidenteForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Incidente
        fields = ["gravidade", "descricao", "houve_lesao", "houve_afastamento"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 4, "placeholder": "O que aconteceu?"})}
        help_texts = {
            "houve_afastamento": "Lesão ou afastamento colocam a OS em revisão de segurança (RN08).",
        }
