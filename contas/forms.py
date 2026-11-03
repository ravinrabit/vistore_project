from django import forms
from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):

    username = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"class": "form-control", "autofocus": True, "placeholder": "seu.email@senacdf.edu.br"}),
    )
    password = forms.CharField(
        label="Senha",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}),
    )

    error_messages = {
        "invalid_login": "E-mail ou senha incorretos.",
        # RN10: o Django bloqueia usuários com is_active=False
        "inactive": "Este usuário está desativado. Procure o administrador.",
    }


class EstiloBootstrapMixin:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")

    def full_clean(self):
        super().full_clean()
        # Marca os campos com erro para o Bootstrap e para leitores de tela
        for nome in self.errors:
            if nome in self.fields:
                attrs = self.fields[nome].widget.attrs
                attrs["class"] = f"{attrs.get('class', '')} is-invalid".strip()
                attrs["aria-invalid"] = "true"
                attrs["aria-describedby"] = f"{self[nome].auto_id}-erro"
