import shutil
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Restaure une sauvegarde (SQLite: copie de fichier .sqlite3, PostgreSQL/JSON: loaddata). ATTENTION: opération destructive."

    def add_arguments(self, parser):
        parser.add_argument("fichier", help="Chemin du fichier de sauvegarde (.sqlite3 ou .json)")
        parser.add_argument("--yes", action="store_true", help="Confirmer la restauration sans invite interactive")

    def handle(self, *args, **options):
        src = Path(options["fichier"])
        if not src.is_absolute():
            src = Path(settings.BASE_DIR) / src
        if not src.exists():
            raise CommandError(f"Fichier introuvable: {src}")
        if not options["yes"]:
            raise CommandError("Restauration annulée: ajoutez --yes pour confirmer (opération potentiellement destructive).")

        db = settings.DATABASES["default"]
        engine = db.get("ENGINE", "")
        if src.suffix == ".sqlite3":
            if "sqlite3" not in engine:
                raise CommandError("La restauration d'un fichier .sqlite3 nécessite DB_ENGINE=sqlite.")
            dst = Path(db["NAME"])
            shutil.copy2(src, dst)
            self.stdout.write(self.style.SUCCESS(f"Base SQLite restaurée depuis: {src}"))
            return
        if src.suffix == ".json":
            call_command("loaddata", str(src), verbosity=1)
            self.stdout.write(self.style.SUCCESS(f"Données JSON restaurées depuis: {src}"))
            return
        raise CommandError("Format non supporté. Utilisez un fichier .sqlite3 ou .json (dumpdata).")
