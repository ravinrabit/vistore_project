from django import forms

from contas.forms import EstiloBootstrapMixin
from contas.models import Perfil, Usuario

from .models import EPI, Incidente, TipoServico, Treinamento, TreinamentoTecnico


class IncidenteForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Incidente
        fields = ["gravidade", "descricao", "houve_lesao", "houve_afastamento"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 4, "placeholder": "O que aconteceu?"})}
        help_texts = {
            "houve_afastamento": "Lesão ou afastamento colocam a OS em revisão de segurança (RN08).",
        }


class TreinamentoForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Treinamento
        fields = ["codigo", "nome", "validade_meses"]


class TreinamentoTecnicoForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = TreinamentoTecnico
        fields = ["tecnico", "treinamento", "data_realizacao", "data_validade"]
        widgets = {
            "data_realizacao": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_validade": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        tecnicos = Usuario.objects.filter(perfil=Perfil.TECNICO, is_active=True)
        if not usuario.eh_admin:
            tecnicos = tecnicos.filter(unidade=usuario.unidade_id)
        self.fields["tecnico"].queryset = tecnicos
        self.fields["data_validade"].required = False

    def clean(self):
        dados = super().clean()
        realizacao, validade = dados.get("data_realizacao"), dados.get("data_validade")
        if realizacao and validade and validade < realizacao:
            self.add_error("data_validade", "A validade não pode ser anterior à realização.")
        return dados


class EPIForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = EPI
        fields = ["nome", "numero_ca", "descricao"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 3})}


class TipoServicoForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = TipoServico
        fields = ["nome", "descricao", "eletrico", "trabalho_em_altura", "treinamentos_exigidos", "epis_exigidos"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "treinamentos_exigidos": forms.CheckboxSelectMultiple,
            "epis_exigidos": forms.CheckboxSelectMultiple,
        }
        help_texts = {
            "treinamentos_exigidos": "NR-10 e NR-35 já são exigidas automaticamente pelos campos acima (RN04).",
        }
