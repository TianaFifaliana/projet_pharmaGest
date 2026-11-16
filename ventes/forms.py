import json

from django import forms

from clients.models import Client
from medicaments.forms import FormulaireBootstrapMixin

from .models import Paiement, Vente


class CaisseVenteForm(FormulaireBootstrapMixin, forms.Form):
    client = forms.ModelChoiceField(
        label="Client",
        queryset=Client.objects.filter(actif=True).order_by("nom", "prenom"),
        required=False,
        empty_label="Client comptoir",
    )
    mode_paiement = forms.ChoiceField(
        label="Mode de paiement",
        choices=Paiement.Mode.choices,
    )
    commentaire = forms.CharField(
        label="Commentaire",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    lignes_json = forms.CharField(widget=forms.HiddenInput(), required=False)

    def clean_lignes_json(self):
        raw = self.cleaned_data.get("lignes_json") or ""
        if not raw.strip():
            raise forms.ValidationError("Ajoutez au moins un médicament au panier.")
        try:
            data = json.loads(raw)
        except ValueError:
            raise forms.ValidationError("Données du panier invalides.")
        if not isinstance(data, list) or not data:
            raise forms.ValidationError("Ajoutez au moins un médicament au panier.")
        return raw

    def clean_mode_paiement(self):
        mode = self.cleaned_data.get("mode_paiement")
        if mode not in Paiement.Mode.values:
            raise forms.ValidationError("Mode de paiement invalide.")
        return mode


class FiltreVenteForm(FormulaireBootstrapMixin, forms.Form):
    q = forms.CharField(label="N° vente", required=False)
    statut = forms.ChoiceField(
        label="Statut",
        choices=[("", "Tous")] + list(Vente.Statut.choices),
        required=False,
    )
    date_debut = forms.DateField(
        label="Du", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    date_fin = forms.DateField(
        label="Au", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    client = forms.ModelChoiceField(
        label="Client",
        queryset=Client.objects.order_by("nom", "prenom"),
        required=False,
        empty_label="Tous",
    )


class RetourLigneForm(FormulaireBootstrapMixin, forms.Form):
    quantite = forms.IntegerField(label="Quantité à retourner", min_value=1)
    reintegrable = forms.BooleanField(
        label="Produit réintégrable en stock",
        required=False,
        initial=False,
    )
    motif = forms.CharField(
        label="Motif du retour",
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, ligne=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ligne = ligne
        if ligne is not None:
            self.fields["quantite"].widget.attrs["max"] = ligne.quantite_retournable
            self.fields["quantite"].help_text = f"Maximum retournable : {ligne.quantite_retournable}."

    def clean_quantite(self):
        qte = self.cleaned_data.get("quantite")
        if self.ligne is not None and qte and qte > self.ligne.quantite_retournable:
            raise forms.ValidationError("Quantité supérieure à la quantité retournable.")
        return qte

    def clean_motif(self):
        motif = (self.cleaned_data.get("motif") or "").strip()
        if not motif:
            raise forms.ValidationError("Le motif est obligatoire.")
        return motif


class AnnulationVenteForm(FormulaireBootstrapMixin, forms.Form):
    motif = forms.CharField(
        label="Motif de l'annulation",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def clean_motif(self):
        motif = (self.cleaned_data.get("motif") or "").strip()
        if not motif:
            raise forms.ValidationError("Le motif est obligatoire.")
        return motif
