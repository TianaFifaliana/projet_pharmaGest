import os
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crée une sauvegarde de la base de données (SQLite: copie, PostgreSQL: dumpdata json; option pg_dump si disponible)."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", default="backups", help="Dossier de sortie des sauvegardes")
        parser.add_argument("--pg-dump", action="store_true", help="Utiliser pg_dump si PostgreSQL est configuré et pg_dump disponible")

    def handle(self, *args, **options):
        out_dir = Path(options["output_dir"])
        if not out_dir.is_absolute():
            out_dir = Path(settings.BASE_DIR) / out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        db = settings.DATABASES["default"]
        engine = db.get("ENGINE", "")

        if "sqlite3" in engine:
            src = Path(db["NAME"])
            if not src.exists():
                raise CommandError(f"Base SQLite introuvable: {src}")
            dst = out_dir / f"sqlite_backup_{ts}.sqlite3"
            import shutil
            shutil.copy2(src, dst)
            self.stdout.write(self.style.SUCCESS(f"Sauvegarde SQLite créée: {dst}"))
            return

        if "postgresql" in engine and options.get("pg_dump"):
            dst = out_dir / f"pg_dump_{ts}.sql"
            env = os.environ.copy()
            if db.get("PASSWORD"):
                env["PGPASSWORD"] = str(db["PASSWORD"])
            cmd = [
                "pg_dump", "-h", db.get("HOST") or "localhost", "-p", str(db.get("PORT") or 5432),
                "-U", db.get("USER") or "", "-d", db.get("NAME") or "", "-f", str(dst),
            ]
            try:
                subprocess.run(cmd, check=True, env=env)
                self.stdout.write(self.style.SUCCESS(f"Sauvegarde pg_dump créée: {dst}"))
                return
            except Exception as e:
                raise CommandError(f"pg_dump a échoué ({e}). Réessayez sans --pg-dump pour un export dumpdata.")

        if "postgresql" in engine:
            dst = out_dir / f"dumpdata_{ts}.json"
            with open(dst, "w", encoding="utf-8") as f:
                call_command("dumpdata", exclude=["contenttypes", "auth.permission", "sessions.session", "admin.logentry"], natural_foreign=True, natural_primary=True, indent=2, stdout=f)
            self.stdout.write(self.style.SUCCESS(f"Export JSON (dumpdata) créé: {dst}"))
            return

        raise CommandError(f"Moteur de base non supporté: {engine}")
