# Checklist de déploiement - PharmaGest (production)

## 1. Configuration applicative
- [ ] `DJANGO_ENV=prod`, `DEBUG=False`, `SECRET_KEY` forte et unique.
- [ ] `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` (HTTPS) renseignés.
- [ ] `DB_ENGINE=postgresql` + `DB_NAME/USER/PASSWORD/HOST/PORT` configurés.
- [ ] Backend email réel configuré (`EMAIL_BACKEND`, SMTP si besoin).
- [ ] Cookies/HTTPS activés : `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `SECURE_SSL_REDIRECT=True`, HSTS selon politique (`SECURE_HSTS_SECONDS`).
- [ ] Derrière reverse-proxy TLS : `USE_X_FORWARDED_PROTO=True` et proxy transmet `X-Forwarded-Proto`.

## 2. Préparation
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt  # inclure gunicorn, psycopg[binary]
python manage.py migrate --settings=config.settings.prod
python manage.py creer_groupes --settings=config.settings.prod
python manage.py collectstatic --noinput --settings=config.settings.prod
python manage.py check --deploy --settings=config.settings.prod
python manage.py createsuperuser --settings=config.settings.prod
```

## 3. Serveur d'application (gunicorn)
Exemple (adapter workers/chemins) :
```bash
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 60 \
  --env DJANGO_SETTINGS_MODULE=config.settings.prod
```
- Exécuter via `systemd` (restart=on-failure), utilisateur dédié non-root, répertoire de travail projet.

## 4. Reverse proxy (Nginx, exemple)
```nginx
server {
  listen 80; server_name pharma.exemple.mg; return 301 https://$host$request_uri;
}
server {
  listen 443 ssl http2; server_name pharma.exemple.mg;
  # ssl_certificate / ssl_certificate_key ...
  client_max_body_size 20M;
  location /static/ { alias /srv/pharmagest/staticfiles/; }
  location /media/  { alias /srv/pharmagest/media/; }
  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

## 5. Sauvegarde & exploitation
- [ ] Sauvegardes planifiées : `python manage.py sauvegarde_db` (ou `pg_dump` natif en PostgreSQL) + test de restauration sur environnement de recette.
- [ ] Journaux applicatifs/proxy supervisés ; rotation des logs.
- [ ] Comptes nominatifs, moindre privilège, mots de passe forts ; `seed_data` réservé dev/démo.

## 6. Recette finale
- [ ] `manage.py check --deploy` sans avertissements bloquants.
- [ ] Parcours critiques validés : auth, achat→réception→stock, vente, retour/annulation, PDFs, dashboard par rôle.
- [ ] Sauvegarde/restauration testée sur copie de la base.
