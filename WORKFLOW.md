# Due Diligence — Workflow & Rôles

**Projet :** Application Frappe `due_diligence` — Cabinet AMOAMAN & ASSOCIÉS  
**Dernière mise à jour :** 2026-07-01

---

## Rôles du système

| Rôle Frappe | Qui | Accès desk |
|---|---|---|
| `DD Client` | Demandeur (client externe ou interne) | Non (portail uniquement) |
| `DD Analyste` | Analyste Compliance | Oui |
| `DD Financier` | Analyste financier | Oui |
| `DD RSSI` | Responsable Sécurité des Systèmes d'Information | Oui |
| `DD Juridique` | Juriste | Oui |
| `DD DPO` | Délégué à la Protection des Données | Oui |
| `DD Manager Metier` | Manager métier demandeur | Oui |
| `DD Manager Compliance` | Manager Compliance | Oui |
| `DD CCO` | Chief Compliance Officer | Oui |
| `DD DG` | Directeur Général | Oui |
| `System Manager` | Administrateur système | Oui |

---

## Circuits de traitement (`circuit_workflow`)

Le champ `circuit_workflow` sur `DD Request` détermine quel chemin le dossier emprunte. Il est calculé automatiquement à partir du score de risque lors de la préqualification.

| Circuit | Niveau de risque | Validations requises |
|---|---|---|
| `Faible` | Score bas, tiers standard | Analyste → Manager Métier |
| `Modéré` | Risque intermédiaire | Analyste → Financier → Manager Compliance |
| `Élevé` | Risque significatif | Analyste → Financier → RSSI → Juridique → Manager Compliance → CCO |
| `Critique` | Risque maximal | Analyste → Financier → RSSI → Juridique → DPO → Manager Compliance → CCO → DG |
| `Interdit` | Tiers sanctionné / listé | Rejet immédiat par Manager Compliance |

---

## États du workflow

| # | État | Rôle qui peut éditer | Signification |
|---|---|---|---|
| 1 | **Brouillon** | `DD Client` | Dossier en cours de saisie, non soumis |
| 2 | **Soumis** | `DD Analyste` | Dossier envoyé, en attente de prise en charge |
| 3 | **En préqualification** | `DD Analyste` | Premier examen : vérification identité, listes de sanctions |
| 4 | **En screening réglementaire** | `DD Analyste` | Vérification approfondie sur bases réglementaires (circuits Élevé/Critique) |
| 5 | **En analyse Compliance** | `DD Analyste` | Analyse principale : questionnaire, scoring, documents |
| 6 | **En attente de documents** | `DD Analyste` | Documents manquants demandés au client |
| 7 | **En analyse financière** | `DD Financier` | Revue des états financiers (circuits Modéré/Élevé/Critique) |
| 8 | **En revue cybersécurité** | `DD RSSI` | Audit des pratiques cyber (circuits Élevé/Critique) |
| 9 | **En revue juridique** | `DD Juridique` | Vérification contrats, statuts, litiges (circuits Élevé/Critique) |
| 10 | **En revue DPO** | `DD DPO` | Conformité RGPD / données personnelles (circuit Critique uniquement) |
| 11 | **En attente validation métier** | `DD Manager Metier` | Décision finale par le manager demandeur (circuit Faible) |
| 12 | **En attente validation Compliance** | `DD Manager Compliance` | Décision Compliance (circuits Modéré/Élevé/Critique) |
| 13 | **En attente validation CCO** | `DD CCO` | Validation CCO (circuits Élevé/Critique) |
| 14 | **En attente validation DG** | `DD DG` | Validation Direction Générale (circuit Critique uniquement) |
| 15 | **Suspendu** | `DD Manager Compliance` | Dossier mis en pause (peut reprendre) |
| 16 | **Clôturé — GO** | `System Manager` | Décision favorable, relation autorisée |
| 17 | **Clôturé — NO GO** | `System Manager` | Décision défavorable, relation interdite |
| 18 | **Clôturé — GO sous réserve** | `System Manager` | Autorisé avec conditions ou mesures atténuantes |
| 19 | **Rejeté** | `System Manager` | Tiers sanctionné, rejet immédiat |
| 20 | **Sous surveillance continue** | `System Manager` | Relation autorisée mais monitored en continu |

---

## Transitions par circuit

### Circuit Faible
```
[DD Client]
    Brouillon ──Soumettre──► Soumis

[DD Analyste]
    Soumis ──Prendre en préqualification──► En préqualification
    En préqualification ──Démarrer l'analyse──► En analyse Compliance
    En analyse Compliance ──Demander des documents──► En attente de documents
    En attente de documents ──Reprendre l'analyse──► En analyse Compliance
    En analyse Compliance ──Envoyer en validation métier──► En attente validation métier

[DD Manager Metier]
    En attente validation métier ──Valider GO──► Clôturé — GO
    En attente validation métier ──Valider NO GO──► Clôturé — NO GO
    En attente validation métier ──Valider GO sous réserve──► Clôturé — GO sous réserve
    En attente validation métier ──Mettre sous surveillance──► Sous surveillance continue
```

### Circuit Modéré
```
[DD Analyste]
    ... → En analyse Compliance ──Envoyer en analyse financière──► En analyse financière

[DD Financier]
    En analyse financière ──Envoyer en validation Compliance──► En attente validation Compliance

[DD Manager Compliance]
    En attente validation Compliance ──Valider GO──► Clôturé — GO
    En attente validation Compliance ──Valider NO GO──► Clôturé — NO GO
    En attente validation Compliance ──Valider GO sous réserve──► Clôturé — GO sous réserve
    En attente validation Compliance ──Mettre sous surveillance──► Sous surveillance continue
```

### Circuit Élevé
```
[DD Analyste]
    En préqualification ──Démarrer le screening réglementaire──► En screening réglementaire
    En screening réglementaire ──Passer en analyse Compliance──► En analyse Compliance
    En analyse Compliance ──Envoyer en analyse financière──► En analyse financière

[DD Financier]
    En analyse financière ──Envoyer en revue cybersécurité──► En revue cybersécurité

[DD RSSI]
    En revue cybersécurité ──Envoyer en revue juridique──► En revue juridique

[DD Juridique]
    En revue juridique ──Envoyer en validation Compliance──► En attente validation Compliance

[DD Manager Compliance]
    En attente validation Compliance ──Envoyer en validation CCO──► En attente validation CCO

[DD CCO]
    En attente validation CCO ──Valider GO──► Clôturé — GO
    En attente validation CCO ──Valider NO GO──► Clôturé — NO GO
    En attente validation CCO ──Valider GO sous réserve──► Clôturé — GO sous réserve
    En attente validation CCO ──Mettre sous surveillance──► Sous surveillance continue
```

### Circuit Critique
```
[DD Analyste → DD Financier → DD RSSI → DD Juridique]
    (mêmes étapes que Élevé jusqu'à En revue juridique)

[DD Juridique]
    En revue juridique ──Envoyer en revue DPO──► En revue DPO

[DD DPO]
    En revue DPO ──Envoyer en validation Compliance──► En attente validation Compliance

[DD Manager Compliance]
    En attente validation Compliance ──Envoyer en validation CCO──► En attente validation CCO

[DD CCO]
    En attente validation CCO ──Envoyer en validation DG──► En attente validation DG

[DD DG]
    En attente validation DG ──Valider GO──► Clôturé — GO
    En attente validation DG ──Valider NO GO──► Clôturé — NO GO
    En attente validation DG ──Valider GO sous réserve──► Clôturé — GO sous réserve
    En attente validation DG ──Mettre sous surveillance──► Sous surveillance continue
```

### Circuit Interdit (tiers sanctionné)
```
[DD Manager Compliance]
    Soumis ──Bloquer — tiers sanctionné──► Rejeté
    En préqualification ──Bloquer — tiers sanctionné──► Rejeté
```

### Suspension (tous circuits)
```
[DD Manager Compliance]
    En préqualification / En screening réglementaire / En analyse Compliance
    / En analyse financière ──Suspendre le dossier──► Suspendu

    Suspendu ──Reprendre le dossier──► En analyse Compliance
```

---

## Vue synthétique : qui intervient à quel moment

```
ÉTAPE               FAIBLE    MODÉRÉ    ÉLEVÉ     CRITIQUE
──────────────────────────────────────────────────────────
Soumission          Client    Client    Client    Client
Préqualification    Analyste  Analyste  Analyste  Analyste
Screening réglem.   —         —         Analyste  Analyste
Analyse Compliance  Analyste  Analyste  Analyste  Analyste
Analyse financière  —         Financier Financier Financier
Revue cybersécurité —         —         RSSI      RSSI
Revue juridique     —         —         Juridique Juridique
Revue DPO           —         —         —         DPO
Validation          Mgr Métier Mgr Comp Mgr Comp  Mgr Comp
                               (clôture) → CCO    → CCO
                                                  → DG
```

---

## Points d'attention

- **`allow_self_approval: 1`** sur toutes les transitions → un analyste peut valider son propre travail (à revoir en production si séparation des tâches requise).
- **Champ `circuit_workflow`** doit être renseigné avant la préqualification pour que les transitions conditionnelles s'activent.
- **États clôturés** ne sont éditables que par `System Manager` → aucune modification post-décision sans droits admin.
- **`Sous surveillance continue`** n'est pas une clôture définitive : prévoir une logique de réévaluation périodique (non implémentée, voir PROGRESS.md).

---

## Actions disponibles dans le desk (DD Request)

### Boutons du groupe « Compliance »

| Bouton | Rôles | Disponibilité | Comportement |
|---|---|---|---|
| **Générer l'avis** | DD Analyste, DD Manager Compliance, DD Validateur, System Manager | États : En validation Manager, En validation Direction, Clôturé | Crée un `DD Avis Compliance` humain lié au dossier, ou ouvre le document existant |
| **Générer l'avis IA** | DD Analyste, DD Manager Compliance, DD Validateur, System Manager | Tous états (rôles autorisés) | Appelle l'API Gemini, crée/met à jour un `DD Avis Compliance` avec `is_ia_avis = 1`, puis redirige vers ce document |
| **Rédiger mon avis** | DD Analyste, DD Manager Compliance, DD Validateur, System Manager | Tous états (rôles autorisés) | Ouvre un nouveau formulaire `DD Avis Compliance` pré-rempli (dd_request, tiers, type, date) sans sauvegarder — l'utilisateur complète la décision et enregistre |

### Génération automatique de l'avis IA

À chaque soumission de dossier par le client (`on_submit`), l'avis IA est généré automatiquement et silencieusement :
- Un document `DD Avis Compliance` avec `is_ia_avis = 1` est créé
- La décision (GO / NO GO / GO sous réserve) est extraite automatiquement du texte Gemini
- Si Gemini est indisponible → échec silencieux (la soumission n'est pas bloquée)
- Visible dans la liste `DD Avis Compliance` du dossier

---

## Système de notifications (Notification Log + realtime)

### Principe technique

Toutes les notifications passent par deux canaux combinés :
1. **`Notification Log`** (DocType Frappe) : persisté en base, visible dans la cloche du desk
2. **`frappe.publish_realtime("notification", after_commit=True, user=...)`** : incrémente le badge numérique sur la cloche en temps réel

> **Important :** Le payload doit être absent (pas de dict message). Le format correct est `frappe.publish_realtime("notification", after_commit=True, user=user)` — c'est le seul format que le client JS Frappe v16 reconnaît pour incrémenter le badge.

### Événements notifiés

| Événement | Destinataire | Canal |
|---|---|---|
| Dossier soumis par le client | Analyste assigné (`analyste_assigne`) | Notification Log + realtime + email |
| Dossier passe à l'étape suivante | Prochain acteur désigné | Notification Log + realtime + email |
| État → "En attente de documents" | Client (`doc.owner`) | Notification Log + realtime + email (liste des docs demandés + lien `/suivi`) |
| Client dépose un document | Analyste assigné | Notification Log + realtime + email |
| Tous les docs obligatoires fournis | Analyste assigné + tous DD Manager Compliance | Notification Log + realtime + email (bouton "Reprendre l'analyse →") |

### Méthodes clés (`dd_request.py`)

| Méthode | Rôle |
|---|---|
| `_notifier_prochain_acteur()` | Appelé sur `on_update` — identifie le destinataire selon `workflow_state` et crée le Notification Log |
| `_notifier_client_docs_manquants()` | Appelé quand état → "En attente de documents" — notifie l'owner du dossier |
| `_notifier_analyste_doc_fourni(doc, nom_document, tous_fournis)` | Module-level helper — notifie après chaque dépôt client ; notifie les managers si tous les obligatoires sont fournis |

### Circuit "Documents complémentaires"

```
[DD Analyste — desk]
    Remplit le tableau "Documents complémentaires" (child table DD Document Complementaire)
    → déclenche "Demander des documents complémentaires"
    → État : En analyse Compliance ──► En attente de documents

[Système]
    → Notification Log + email au client avec liste des docs + lien /suivi?name=...

[DD Client — portail /suivi]
    Voit la section "Documents complémentaires requis" (orange si en attente)
    → Clique "Déposer" sur chaque ligne
    → Upload via POST /api/method/upload_file (fichier privé)
    → Appel POST fournir_document_complementaire → ligne marquée "Fourni"

[Système]
    → Notification Log + email à l'analyste ("document déposé")
    → Si tous obligatoires fournis : notifie aussi les DD Manager Compliance
    → Bouton "Reprendre l'analyse →" dans la notification

[DD Analyste — desk]
    Déclenche "Reprendre l'analyse"
    → État : En attente de documents ──► En analyse Compliance
```

### Nota : email SMTP

Les notifications email (`frappe.sendmail`) nécessitent un compte SMTP configuré dans **Tools > Email Account**. Sans configuration, chaque envoi génère un warning "Please setup default outgoing Email Account" visible dans le desk. Les `Notification Log` (cloche) fonctionnent indépendamment du SMTP.
