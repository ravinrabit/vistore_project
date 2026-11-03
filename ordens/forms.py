from django import forms

from contas.forms import EstiloBootstrapMixin
from estrutura.models import Equipamento, Local

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
