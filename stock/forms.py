from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from medicaments.forms import FormulaireBootstrapMixin
from medicaments.models import Medicament

from .models import MouvementStock
from .services import DEFAULT_JOURS_ALERTE_PEREMPTION

User = get_user_model()


class FiltreMouvementStockForm(FormulaireBootstrapMixin, forms.Form):
    medicament = forms.ModelChoiceField(
        label="Médicament",
        queryset=Medicament.objects.order_by("nom_commercial"),
        required=False,
        empty_label="Tous les médicaments",
    )
    type_mouvement = forms.ChoiceField(
        label="Type",
        choices=[("", "Tous les types")] + list(MouvementStock.TypeMouvement.choices),
        required=False,
    )
    date_debut = forms.DateField(
        label="Du",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_fin = forms.DateField(
        label="Au",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    utilisateur = forms.ModelChoiceField(
        label="Utilisateur",
        queryset=User.objects.filter(is_active=True).order_by("username"),
        required=False,
        empty_label="Tous les utilisateurs",
    )


class InventaireLotForm(FormulaireBootstrapMixin, forms.Form):
    stock_compte = forms.IntegerField(
        label="Stock compté (physique)",
        min_value=0,
        widget=forms.NumberInput(attrs={"min": 0}),
    )
    motif = forms.CharField(
        label="Motif de la correction",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Expliquez l'écart constaté (obligatoire)"}),
    )

    def clean_motif(self):
        motif = (self.cleaned_data.get("motif") or "").strip()
        if not motif:
            raise forms.ValidationError("Le motif de la correction est obligatoire.")
        return motif


class AlertePeremptionForm(FormulaireBootstrapMixin, forms.Form):
    jours = forms.IntegerField(
        label="Péremption proche (jours)",
        min_value=1,
        max_value=3650,
        initial=DEFAULT_JOURS_ALERTE_PEREMPTION,
        required=False,
    )

    def clean_jours(self):
        val = self.cleaned_data.get("jours")
        return val if val else DEFAULT_JOURS_ALERTE_PEREMPTION
