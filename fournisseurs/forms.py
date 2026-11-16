from django import forms
from django.core.exceptions import ValidationError

from utilisateurs.forms import FormulaireBootstrapMixin

from .models import Fournisseur


class FormulaireFournisseur(FormulaireBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Fournisseur
        fields = (
            "nom",
            "contact",
            "telephone",
            "email",
            "adresse",
            "ville",
            "actif",
        )
        error_messages = {
            "nom": {
                "unique": "Un fournisseur portant ce nom existe déjà.",
            },
        }

    def clean_nom(self):
        nom = (self.cleaned_data.get("nom") or "").strip()
        if not nom:
            raise ValidationError("Le nom du fournisseur est obligatoire.")
        return nom

    def clean_telephone(self):
        return (self.cleaned_data.get("telephone") or "").strip()

    def clean_contact(self):
        return (self.cleaned_data.get("contact") or "").strip()

    def clean_ville(self):
        return (self.cleaned_data.get("ville") or "").strip()
