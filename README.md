# PharmaGest

Application web de gestion de pharmacie (Django, Bootstrap 5, SQLite/PostgreSQL).

## Prérequis

- Python 3.12+
- Git

## Installation (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env   # puis renseigner SECRET_KEY et DEBUG
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Application disponible sur http://127.0.0.1:8000/ .

## Structure

```
config/            configuration du projet (settings, urls, wsgi)
utilisateurs/      comptes, rôles et permissions
medicaments/       catalogue des médicaments
fournisseurs/      fournisseurs
clients/           clients
achats/            commandes et réceptions fournisseurs
stock/             lots, mouvements de stock
ventes/            ventes et lignes de vente
rapports/          tableau de bord et états
templates/         gabarits HTML (base.html)
static/            css, js, images
media/             fichiers téléversés (non versionné)
```

## Règles métier

Le code applique les règles RG01 à RG12 (unicité des médicaments et codes-barres,
validation serveur des prix et quantités, stock jamais négatif, FEFO, traçabilité,
permissions par vue, transactions atomiques avec verrouillage).
