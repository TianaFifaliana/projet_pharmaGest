"""Définition des rôles PharmaGest et des permissions associées.

Chaque rôle correspond à un groupe Django. Les permissions sont décrites par
application et par mode, ce qui permet à la commande ``creer_groupes`` de
fonctionner même lorsque les modèles d'une application n'existent pas encore.
"""

ADMINISTRATEUR = "Administrateur"
PHARMACIEN_RESPONSABLE = "Pharmacien responsable"
GESTIONNAIRE_STOCK = "Gestionnaire de stock"
CAISSIER = "Caissier"
RESPONSABLE_GESTION = "Responsable de gestion"

ROLES = (
    ADMINISTRATEUR,
    PHARMACIEN_RESPONSABLE,
    GESTIONNAIRE_STOCK,
    CAISSIER,
    RESPONSABLE_GESTION,
)

LECTURE = "lecture"
SAISIE = "saisie"
GESTION = "gestion"
COMPLET = "complet"
TOUS = "tous"

MODES = {
    LECTURE: ("view",),
    SAISIE: ("view", "add"),
    GESTION: ("view", "add", "change"),
    COMPLET: ("view", "add", "change", "delete"),
}

ROLE_DESCRIPTIONS = {
    ADMINISTRATEUR: "Accès total à l'application, gestion des comptes et des rôles.",
    PHARMACIEN_RESPONSABLE: (
        "Supervise le catalogue, le stock, les achats et les ventes ; valide les "
        "réceptions et consulte les rapports."
    ),
    GESTIONNAIRE_STOCK: (
        "Gère les médicaments, les lots et les commandes fournisseurs ; consulte "
        "les rapports de stock."
    ),
    CAISSIER: "Saisit les ventes et encaisse les clients ; consultation du catalogue.",
    RESPONSABLE_GESTION: (
        "Gère les clients et les fournisseurs ; consulte les achats, ventes, stocks "
        "et rapports."
    ),
}

ROLE_PERMISSIONS = {
    ADMINISTRATEUR: TOUS,
    PHARMACIEN_RESPONSABLE: {
        "medicaments": GESTION,
        "stock": GESTION,
        "achats": GESTION,
        "ventes": GESTION,
        "clients": LECTURE,
        "fournisseurs": LECTURE,
        "rapports": LECTURE,
        "utilisateurs": LECTURE,
    },
    GESTIONNAIRE_STOCK: {
        "medicaments": GESTION,
        "stock": GESTION,
        "achats": GESTION,
        "fournisseurs": LECTURE,
        "rapports": LECTURE,
    },
    CAISSIER: {
        "ventes": SAISIE,
        "clients": SAISIE,
        "medicaments": LECTURE,
        "stock": LECTURE,
    },
    RESPONSABLE_GESTION: {
        "clients": GESTION,
        "fournisseurs": GESTION,
        "achats": LECTURE,
        "ventes": LECTURE,
        "stock": LECTURE,
        "medicaments": LECTURE,
        "rapports": LECTURE,
        "utilisateurs": LECTURE,
    },
}
