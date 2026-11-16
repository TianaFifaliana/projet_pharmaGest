# Installation - PharmaGest

## Prérequis
- Python 3.12+ (testé avec Django 6.1.3)
- pip, venv
- (Production) PostgreSQL 14+ et client/driver `psycopg` si `DB_ENGINE=postgresql`

## Installation (développement)
```powershell
git clone <depot> pharmaGest
cd pharmaGest
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt  # ou: pip install django python-decouple reportlab coverage psycopg[binary]
Copy-Item .env.example .env
# éditer .env: SECRET_KEY, DJANGO_ENV=dev, DB_ENGINE=sqlite
python manage.py migrate
python manage.py creer_groupes
python manage.py seed_data        # optionnel: données de démo
python manage.py createsuperuser   # optionnel
python manage.py runserver
```

## Variables d'environnement (.env)
- `DJANGO_ENV`: `dev` ou `prod` (sélectionne `config.settings.dev|prod`)
- `SECRET_KEY`: clé secrète Django (obligatoire, unique en prod)
- `DEBUG`: `True/False` (ignoré en prod, forcé à False)
- `ALLOWED_HOSTS`: hôtes autorisés (CSV)
- `CSRF_TRUSTED_ORIGINS`: origines CSRF de confiance en HTTPS (CSV, ex. `https://pharma.exemple.mg`)
- `DB_ENGINE`: `sqlite` ou `postgresql`
- SQLite: `SQLITE_NAME=db.sqlite3`
- PostgreSQL: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- Email: `DEFAULT_FROM_EMAIL`, `EMAIL_BACKEND`
- Sécurité HTTPS/proxy: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, `USE_X_FORWARDED_PROTO`

## Vérifications
```powershell
python manage.py check
python manage.py test
```
