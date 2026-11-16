# Guide d'utilisation - PharmaGest

## Rôles
- **ADMINISTRATEUR** : gestion complète (utilisateurs, paramètres, données).
- **PHARMACIEN_RESPONSABLE** : supervision, validations sensibles, retours/annulations ventes, blocage lots, statistiques globales.
- **GESTIONNAIRE_STOCK** : achats, réceptions, inventaires, alertes/stock.
- **CAISSIER** : ventes/caisse, consultation de ses propres ventes/encaissements.
- **RESPONSABLE_GESTION** : consultation et tableaux de bord globaux.

## Connexion
- Accès via `/` → écran de connexion. Déconnexion et changement de mot de passe disponibles dans le menu utilisateur.
- Les connexions/déconnexions et opérations sensibles sont tracées dans le journal d'audit (`rapports.JournalAudit`).

## Modules principaux
- **Médicaments & catégories** : création/modification, archivage si historique (stock/achats/ventes) pour préserver la traçabilité.
- **Fournisseurs / Clients** : fiches, activation/désactivation, suppression limitée si historique.
- **Achats** : commande → réception. Le stock n'est modifié qu'à la réception validée (RG04). Une réception ne peut être validée qu'une fois (anti double validation, RG05). PDFs : bon de commande, bon de réception.
- **Stock** : lots FEFO (premier périmé, premier sorti), mouvements, alertes (rupture, seuil, péremption/proche péremption), inventaire/corrections (motif obligatoire), blocage/déblocage lot (pharmacien responsable). PDFs : état du stock, alertes, produits proches péremption.
- **Ventes (caisse)** : panier/confirmation atomique avec re-vérification serveur (stock, lot non périmé/non bloqué), prix appliqué figé (RG06-RG08/RG12), reçu/facture PDF.
- **Retours & annulations** (pharmacien responsable/admin) : retour de ligne avec motif (réintégration stock optionnelle) ou annulation compensatoire d'une vente (sans suppression de l'original, compensations par ligne + paiements annulés).
- **Rapports / Tableau de bord** : indicateurs par période (CA, encaissements/paiements valides, marge commerciale estimée = CA − coût d'achat estimé), graphiques, exports PDF. Portée par rôle : caissier = ses données ; rôles gestion = global.

## Paramètres de la pharmacie
- Configurables dans l'administration Django (`Parametres`, singleton) : nom, adresse, téléphone, email, NIF, STAT, mentions légales. Utilisés sur les documents PDF.

## Sauvegarde / restauration
```powershell
python manage.py sauvegarde_db --output-dir backups
# SQLite: restaure un .sqlite3 ; JSON: restaure un dumpdata (.json)
python manage.py restauration_db backups\<fichier> --yes
```
> La restauration est destructive : exécuter avec prudence et hors production active.
