from django import forms
from django.core.exceptions import ValidationError

from utilisateurs.forms import FormulaireBootstrapMixin

from .models import Client


class FormulaireClient(FormulaireBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Client
        fields = (
            "nom",
            "prenom",
            "telephone",
            "email",
            "adresse",
            "actif",
        )

    def clean_nom(self):
        nom = (self.cleaned_data.get("nom") or "").strip()
        if not nom:
            raise ValidationError("Le nom du client est obligatoire.")
        return nom

    def clean_prenom(self):
        return (self.cleaned_data.get("prenom") or "").strip()

    def clean_telephone(self):
        return (self.cleaned_data.get("telephone") or "").strip()
