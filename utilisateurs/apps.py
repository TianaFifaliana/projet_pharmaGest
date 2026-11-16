from django.apps import AppConfig


class UtilisateursConfig(AppConfig):
    name = "utilisateurs"

    def ready(self):
        from . import signals  # noqa: F401
