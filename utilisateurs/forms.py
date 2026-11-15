from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.contrib.auth.models import Group

from .models import User
from .roles import ADMINISTRATEUR, ROLES


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
            if hasattr(widget, "input_type") and widget.input_type in {"text", "email", "tel"}:
                widget.attrs.setdefault("autocomplete", "off")


class FormulaireConnexion(FormulaireBootstrapMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Nom d'utilisateur"
        self.fields["password"].label = "Mot de passe"
        self.fields["username"].widget.attrs.update(
            {"autofocus": True, "autocomplete": "username"}
        )
        self.fields["password"].widget.attrs.update({"autocomplete": "current-password"})


class FormulaireChangementMotDePasse(FormulaireBootstrapMixin, PasswordChangeForm):
    pass


class FormulaireReinitialisationMotDePasse(FormulaireBootstrapMixin, PasswordResetForm):
    pass


class FormulaireConfirmationReinitialisation(FormulaireBootstrapMixin, SetPasswordForm):
    pass


def champ_roles():
    return forms.ModelMultipleChoiceField(
        label="Rôles",
        queryset=Group.objects.none(),
        required=False,
        help_text=(
            "Un utilisateur peut cumuler plusieurs rôles. L'attribution des rôles "
            "est réservée aux administrateurs."
        ),
    )


class FormulaireRolesMixin:
    def __init__(self, *args, **kwargs):
        self.utilisateur_courant = kwargs.pop("utilisateur_courant", None)
        super().__init__(*args, **kwargs)
        self.fields["groups"].queryset = Group.objects.filter(name__in=ROLES).order_by("name")

    def clean_groups(self):
        groupes = self.cleaned_data.get("groups")
        if not groupes:
            return groupes

        autres_administrateurs = (
            User.objects.filter(is_active=True, groups__name=ADMINISTRATEUR)
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if self.instance.pk and self.instance.a_un_role(ADMINISTRATEUR):
            if ADMINISTRATEUR not in [g.name for g in groupes] and not autres_administrateurs:
                raise forms.ValidationError(
                    "Impossible de retirer le rôle Administrateur au dernier "
                    "administrateur actif du site."
                )
        return groupes


class FormulaireCreationUtilisateur(
    FormulaireRolesMixin, FormulaireBootstrapMixin, UserCreationForm
):
    groups = champ_roles()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "is_active",
            "groups",
        )
        labels = {
            "username": "Nom d'utilisateur",
            "first_name": "Prénom",
            "last_name": "Nom",
            "email": "Adresse e-mail",
            "telephone": "Téléphone",
            "is_active": "Compte actif",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Mot de passe"
        self.fields["password2"].label = "Confirmation du mot de passe"
        self.fields["is_active"].initial = True


class FormulaireModificationUtilisateur(
    FormulaireRolesMixin, FormulaireBootstrapMixin, forms.ModelForm
):
    groups = champ_roles()

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "is_active",
            "groups",
        )
        labels = {
            "username": "Nom d'utilisateur",
            "first_name": "Prénom",
            "last_name": "Nom",
            "email": "Adresse e-mail",
            "telephone": "Téléphone",
            "is_active": "Compte actif",
        }

    def clean_is_active(self):
        actif = self.cleaned_data.get("is_active")
        if self.instance.pk == getattr(self.utilisateur_courant, "pk", None) and not actif:
            raise forms.ValidationError("Vous ne pouvez pas désactiver votre propre compte.")
        if (
            self.instance.pk
            and not actif
            and self.instance.is_active
            and self.instance.a_un_role(ADMINISTRATEUR)
            and not User.objects.filter(is_active=True, groups__name=ADMINISTRATEUR)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError(
                "Impossible de désactiver le dernier administrateur actif du site."
            )
        return actif
