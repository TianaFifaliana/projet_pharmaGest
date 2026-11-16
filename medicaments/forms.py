from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

from .models import Categorie, Medicament

TAILLE_MAX_PHOTO = 2 * 1024 * 1024
FORMATS_PHOTO = {"JPEG", "PNG", "WEBP"}


def valider_photo(fichier):
    """Vérifie le format réel (JPEG/PNG/WebP) et la taille maximale (2 Mo)."""
    if not fichier:
        return fichier

    if fichier.size > TAILLE_MAX_PHOTO:
        raise ValidationError("La photo ne doit pas dépasser 2 Mo.")

    try:
        image = Image.open(fichier)
        format_image = image.format
        image.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("Le fichier fourni n'est pas une image valide.")
    finally:
        fichier.seek(0)

    if format_image not in FORMATS_PHOTO:
        raise ValidationError(
            "Format non pris en charge. Utilisez une image JPEG, PNG ou WebP."
        )
    return fichier


class FormulaireBootstrapMixin:
    """Applique les classes Bootstrap 5 aux widgets d'un formulaire."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.appliquer_styles()

    def appliquer_styles(self):
        for champ in self.fields.values():
            widget = champ.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"
                continue
            if isinstance(widget, forms.Select):
                widget.attrs["class"] = "form-select"
            else:
                widget.attrs["class"] = "form-control"
            if hasattr(widget, "input_type") and widget.input_type in {
                "text",
                "email",
                "tel",
                "number",
            }:
                widget.attrs.setdefault("autocomplete", "off")


class FormulaireCategorie(FormulaireBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ("nom", "description")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_nom(self):
        nom = (self.cleaned_data.get("nom") or "").strip()
        if not nom:
            raise ValidationError("Le nom de la catégorie est obligatoire.")
        return nom


class FormulaireMedicament(FormulaireBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Medicament
        fields = (
            "nom_commercial",
            "nom_generique",
            "categorie",
            "forme",
            "dosage",
            "laboratoire",
            "code_barres",
            "photo",
            "prix_achat",
            "prix_vente",
            "seuil_alerte",
            "statut",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categorie"].empty_label = "Sélectionnez une catégorie"
        self.fields["photo"].widget.attrs.update(
            {"accept": "image/jpeg,image/png,image/webp"}
        )
        self.fields["code_barres"].widget.attrs.update({"autocomplete": "off"})

    def clean_code_barres(self):
        code = (self.cleaned_data.get("code_barres") or "").strip()
        if not code:
            return None
        return code

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if not photo or (self.instance.pk and photo == self.instance.photo):
            return photo
        return valider_photo(photo)

    def clean_prix_achat(self):
        prix = self.cleaned_data.get("prix_achat")
        if prix is not None and prix <= Decimal("0"):
            raise ValidationError("Le prix d'achat doit être strictement positif.")
        return prix

    def clean_prix_vente(self):
        prix = self.cleaned_data.get("prix_vente")
        if prix is not None and prix <= Decimal("0"):
            raise ValidationError("Le prix de vente doit être strictement positif.")
        return prix

    def clean_nom_commercial(self):
        nom = (self.cleaned_data.get("nom_commercial") or "").strip()
        if not nom:
            raise ValidationError("Le nom commercial est obligatoire.")
        return nom
