from functools import wraps

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

URL_CONNEXION = "utilisateurs:connexion"


class ConnexionRequiseMixin(LoginRequiredMixin):
    login_url = URL_CONNEXION
    redirect_field_name = "suivant"


class PermissionRequiseMixin(ConnexionRequiseMixin, PermissionRequiredMixin):
    permission_denied_message = (
        "Vous n'avez pas les droits nécessaires pour accéder à cette page."
    )


def permission_requise(*permissions):
    """Décorateur : connexion obligatoire puis vérification des permissions."""

    def decorateur(vue):
        vue_protegee = permission_required(permissions, raise_exception=True)(vue)
        vue_protegee = login_required(vue_protegee, login_url=URL_CONNEXION)

        @wraps(vue)
        def enveloppe(request, *args, **kwargs):
            return vue_protegee(request, *args, **kwargs)

        return enveloppe

    return decorateur
