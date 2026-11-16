from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from rapports.models import JournalAudit

from .models import User


def _ip_client(request):
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@receiver(user_logged_in)
def journaliser_connexion(sender, request, user, **kwargs):
    if not user or not getattr(user, "pk", None):
        return
    JournalAudit.objects.create(
        utilisateur=user,
        action=JournalAudit.Action.CONNEXION,
        modele=User.__name__,
        objet_id=str(user.pk),
        description=f"Connexion de {user.get_username()}",
        adresse_ip=_ip_client(request),
    )


@receiver(user_logged_out)
def journaliser_deconnexion(sender, request, user, **kwargs):
    if not user or not getattr(user, "pk", None):
        return
    JournalAudit.objects.create(
        utilisateur=user,
        action=JournalAudit.Action.DECONNEXION,
        modele=User.__name__,
        objet_id=str(user.pk),
        description=f"Déconnexion de {user.get_username()}",
        adresse_ip=_ip_client(request),
    )
