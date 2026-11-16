# Dossier de conception - PharmaGest

## 1. Modèle conceptuel de données (MCD, Mermaid ER)

```mermaid
erDiagram
  UTILISATEUR ||--o{ COMMANDE_ACHAT : cree
  UTILISATEUR ||--o{ RECEPTION_ACHAT : valide
  UTILISATEUR ||--o{ VENTE : effectue
  UTILISATEUR ||--o{ PAIEMENT : encaisse
  UTILISATEUR ||--o{ MOUVEMENT_STOCK : realise
  UTILISATEUR ||--o{ JOURNAL_AUDIT : trace

  FOURNISSEUR ||--o{ COMMANDE_ACHAT : fournit
  COMMANDE_ACHAT ||--|{ LIGNE_ACHAT : contient
  COMMANDE_ACHAT ||--o{ RECEPTION_ACHAT : recoit
  RECEPTION_ACHAT ||--|{ LIGNE_RECEPTION : detaille
  LIGNE_ACHAT ||--o{ LIGNE_RECEPTION : concerne

  CATEGORIE ||--o{ MEDICAMENT : classe
  MEDICAMENT ||--o{ LOT_STOCK : stocke
  LIGNE_RECEPTION ||--o| LOT_STOCK : cree
  LOT_STOCK ||--o{ MOUVEMENT_STOCK : historise
  LOT_STOCK ||--o{ LIGNE_VENTE : alimente

  CLIENT ||--o{ VENTE : achete
  VENTE ||--|{ LIGNE_VENTE : contient
  VENTE ||--o{ PAIEMENT : reglee_par
  VENTE ||--o{ RETOUR_VENTE : compensee_par
  LIGNE_VENTE ||--o{ RETOUR_VENTE : retournee

  UTILISATEUR {
    int id PK
    string username
    string role_groupe
  }
  CATEGORIE { int id PK string nom }
  MEDICAMENT { int id PK string nom_commercial decimal prix_achat decimal prix_vente int seuil_alerte string statut }
  LOT_STOCK { int id PK string numero_lot int quantite_recue int quantite_disponible date date_peremption bool bloque }
  FOURNISSEUR { int id PK string nom bool actif }
  COMMANDE_ACHAT { int id PK string reference string statut date date_commande }
  LIGNE_ACHAT { int id PK int quantite decimal prix_unitaire }
  RECEPTION_ACHAT { int id PK string reference bool est_validee date date_reception }
  LIGNE_RECEPTION { int id PK int quantite string numero_lot date date_peremption }
  CLIENT { int id PK string nom string prenom bool actif }
  VENTE { int id PK string numero string statut datetime date_creation }
  LIGNE_VENTE { int id PK int quantite decimal prix_applique }
  PAIEMENT { int id PK decimal montant string mode string statut }
  RETOUR_VENTE { int id PK string type_retour int quantite bool reintegrable decimal montant }
  MOUVEMENT_STOCK { int id PK string type_mouvement int quantite string reference }
  JOURNAL_AUDIT { int id PK string action string modele string objet_id datetime date_action }
  PARAMETRES { int id PK string nom_pharmacie string nif string stat }
```

## 2. Modèle logique de données (MLD, relationnel simplifié)
- `utilisateurs_user(id PK, username, email, is_active, ...)` + groupes Django (`auth_group`, `auth_user_groups`)
- `medicaments_categorie(id PK, nom UNIQUE, description)`
- `medicaments_medicament(id PK, categorie_id FK→categorie, nom_commercial, nom_generique, forme, dosage, prix_achat, prix_vente, seuil_alerte, statut, code_barres UNIQUE NULL)`
- `stock_lotstock(id PK, medicament_id FK, reception_ligne_id FK NULL, numero_lot, quantite_recue, quantite_disponible, date_peremption, date_reception, bloque)`
- `stock_mouvementstock(id PK, lot_id FK, auteur_id FK NULL, type_mouvement, quantite, reference, commentaire, date_mouvement)`
- `fournisseurs_fournisseur(id PK, nom, telephone, contact, email, adresse, ville, actif)`
- `achats_commandeachat(id PK, fournisseur_id FK, cree_par_id FK, reference UNIQUE, statut, date_commande, notes)`
- `achats_ligneachat(id PK, commande_id FK, medicament_id FK, quantite, prix_unitaire)`
- `achats_receptionachat(id PK, commande_id FK, validee_par_id FK, reference UNIQUE, est_validee, date_reception, commentaire)`
- `achats_lignereception(id PK, reception_id FK, ligne_achat_id FK, quantite, numero_lot, date_peremption)`
- `clients_client(id PK, nom, prenom, telephone, email, adresse, date_naissance, actif)`
- `ventes_vente(id PK, client_id FK NULL, caissier_id FK, numero UNIQUE, statut, date_creation)`
- `ventes_lignevente(id PK, vente_id FK, lot_id FK, quantite, prix_applique)`
- `ventes_paiement(id PK, vente_id FK, caissier_id FK, montant, mode, statut, reference, date_paiement)`
- `ventes_retourvente(id PK, vente_id FK, ligne_vente_id FK NULL, lot_id FK NULL, auteur_id FK, type_retour, quantite, reintegrable, montant, motif)`
- `rapports_journalaudit(id PK, utilisateur_id FK NULL, action, modele, objet_id, description, adresse_ip, date_action)`
- `rapports_parametres(id PK singleton, nom_pharmacie, adresse, telephone, email, nif, stat, mentions_legales)`

## 3. UML - cas d'utilisation (Mermaid)

```mermaid
flowchart LR
  subgraph Acteurs
    Admin[Administrateur]
    Pharma[Pharmacien responsable]
    Stock[Gestionnaire stock]
    Caissier[Caissier]
    Gest[Resp. gestion]
  end
  subgraph PharmaGest
    UC1((Gérer utilisateurs/rôles))
    UC2((Gérer référentiels))
    UC3((Commander & réceptionner))
    UC4((Gérer stock/inventaire/alertes))
    UC5((Vendre / encaisser))
    UC6((Retourner / annuler vente))
    UC7((Consulter dashboard & PDF))
    UC8((Paramètres & audit))
  end
  Admin --> UC1 & UC2 & UC8 & UC7
  Pharma --> UC2 & UC4 & UC6 & UC7 & UC8
  Stock --> UC3 & UC4
  Caissier --> UC5 & UC7
  Gest --> UC7
```

## 4. UML - séquence (vente validée, simplifié)

```mermaid
sequenceDiagram
  actor C as Caissier
  participant V as Vue Caisse
  participant S as ventes.services
  participant DB as BD (transaction)
  C->>V: Confirmer panier
  V->>S: valider_vente(token, lignes)
  S->>DB: atomic + select_for_update(lots/vente)
  S->>S: Vérifier token, stock, FEFO, lot non périmé/bloqué
  S->>DB: Créer Vente/Lignes/Paiement, décrémenter lots, Mouvements SORTIE
  S->>DB: JournalAudit(VALIDATION)
  DB-->>V: Commit (OK) / Rollback (erreur)
  V-->>C: Reçu / message d'erreur
```

## 5. Règles de gestion clés
- RG04 : commande ≠ stock ; entrée stock uniquement à réception validée.
- RG05 : anti double validation réception (verrouillage/transaction).
- RG06-RG08/RG12 : vente atomique, re-vérification serveur, lot valide (non périmé/bloqué), qté ≤ stock, prix appliqué figé.
- FEFO : allocation par date de péremption croissante.
- Retours/annulations : compensatoires, sans suppression de la vente d'origine, audit.
- Traçabilité : `JournalAudit` sur opérations sensibles (auth, CRUD sensibles, validations, mouvements/ajustements, PDFs selon vues).
