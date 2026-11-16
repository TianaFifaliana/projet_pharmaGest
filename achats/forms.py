from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from fournisseurs.models import Fournisseur
from medicaments.forms import FormulaireBootstrapMixin
from medicaments.models import Medicament

from .models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat


class FormulaireCommandeAchat(FormulaireBootstrapMixin, forms.ModelForm):
    class Meta:
        model = CommandeAchat
        fields = ("fournisseur", "commentaire")
        widgets = {
            "commentaire": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fournisseurs = Fournisseur.objects.filter(actif=True).order_by("nom")
        if self.instance and self.instance.pk_id and self.instance.fournisseur_id:
            fournisseurs = (fournisseurs | Fournisseur.objects.filter(pk=self.instance.fournisseur_id)).distinct()
        self.fields["fournisseur"].queryset = fournisseurs
        self.fields["fournisseur"].empty_label = "Sélectionnez un fournisseur"


class FormulaireLigneAchat(FormulaireBootstrapMixin, forms.ModelForm):
    class Meta:
        model = LigneAchat
        fields = ("medicament", "quantite", "prix_unitaire")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        medicaments = Medicament.objects.filter(statut=Medicament.Statut.ACTIF).order_by("nom_commercial")
        if self.instance and self.instance.pk_id and self.instance.medicament_id:
            medicaments = (medicaments | Medicament.objects.filter(pk=self.instance.medicament_id)).distinct()
        self.fields["medicament"].queryset = medicaments
        self.fields["medicament"].empty_label = "Sélectionnez un médicament"
        self.fields["quantite"].widget.attrs.update({"min": 1, "class": "form-control quantite-input"})
        self.fields["prix_unitaire"].widget.attrs.update(
            {"min": "0.01", "step": "0.01", "class": "form-control prix-input"}
        )


class BaseLigneAchatFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        lignes_valides = 0
        medicaments = []
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE") and form.instance.pk:
                continue
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            medicament = form.cleaned_data.get("medicament")
            quantite = form.cleaned_data.get("quantite")
            prix_unitaire = form.cleaned_data.get("prix_unitaire")
            if not medicament and not quantite and not prix_unitaire:
                continue
            if not medicament or not quantite or prix_unitaire in (None, ""):
                raise ValidationError("Chaque ligne doit contenir un médicament, une quantité et un prix unitaire.")
            if quantite <= 0:
                raise ValidationError("La quantité de chaque ligne doit être strictement positive.")
            if prix_unitaire <= 0:
                raise ValidationError("Le prix unitaire de chaque ligne doit être strictement positif.")
            if medicament.pk in medicaments:
                raise ValidationError("Un même médicament ne peut apparaître qu'une seule fois dans la commande.")
            medicaments.append(medicament.pk)
            lignes_valides += 1
        if lignes_valides == 0:
            raise ValidationError("Ajoutez au moins une ligne de commande.")


LigneAchatFormSet = inlineformset_factory(
    CommandeAchat,
    LigneAchat,
    form=FormulaireLigneAchat,
    formset=BaseLigneAchatFormSet,
    fields=("medicament", "quantite", "prix_unitaire"),
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class FormulaireReceptionAchat(FormulaireBootstrapMixin, forms.ModelForm):
    class Meta:
        model = ReceptionAchat
        fields = ("commentaire",)
        widgets = {
            "commentaire": forms.Textarea(attrs={"rows": 3}),
        }


class FormulaireLigneReception(FormulaireBootstrapMixin, forms.ModelForm):
    class Meta:
        model = LigneReception
        fields = ("quantite", "numero_lot", "date_peremption")

    def __init__(self, *args, ligne_achat=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ligne_achat = ligne_achat or getattr(self.instance, "ligne_achat", None)
        self.fields["quantite"].required = False
        self.fields["numero_lot"].required = False
        self.fields["date_peremption"].required = False
        self.fields["quantite"].widget.attrs.update({"min": 0, "class": "form-control"})
        self.fields["date_peremption"].widget = forms.DateInput(
            attrs={"type": "date", "class": "form-control"}
        )
        if self.ligne_achat:
            restante = self.ligne_achat.quantite_restante
            self.fields["quantite"].widget.attrs["max"] = restante
            self.fields["quantite"].help_text = f"Restant à recevoir : {restante}"

    def clean(self):
        cleaned = super().clean()
        quantite = cleaned.get("quantite") or 0
        numero_lot = (cleaned.get("numero_lot") or "").strip()
        date_peremption = cleaned.get("date_peremption")
        cleaned["numero_lot"] = numero_lot

        if quantite == 0 and not numero_lot and not date_peremption:
            cleaned["quantite"] = 0
            return cleaned

        if quantite <= 0:
            raise ValidationError("La quantité reçue doit être strictement positive.")
        if not numero_lot:
            raise ValidationError("Le numéro de lot est obligatoire lorsqu'une quantité est reçue.")
        if not date_peremption:
            raise ValidationError("La date de péremption est obligatoire lorsqu'une quantité est reçue.")
        if date_peremption < timezone.localdate():
            raise ValidationError("La date de péremption ne peut pas être dans le passé.")
        if self.ligne_achat and quantite > self.ligne_achat.quantite_restante:
            raise ValidationError(
                f"La quantité reçue dépasse la quantité restante ({self.ligne_achat.quantite_restante})."
            )
        cleaned["quantite"] = quantite
        return cleaned
