from django import forms

from medicaments.forms import FormulaireBootstrapMixin


class PeriodeDashboardForm(FormulaireBootstrapMixin, forms.Form):
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

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get("date_debut")
        fin = cleaned.get("date_fin")
        if debut and fin and debut > fin:
            self.add_error("date_fin", "La date de fin doit être postérieure ou égale à la date de début.")
        return cleaned
