# Méthodologie de scoring Due Diligence — Phases d'implémentation

App : `due_diligence` | Site : `compliance` | Framework : Frappe v16

---

## Vue d'ensemble

Le moteur de scoring évalue chaque tiers sur une échelle **0 à 100** en combinant 7 axes de risque
pondérés. Le score détermine automatiquement une catégorie de risque qui conditionne le workflow
d'instruction du dossier.

### Formule générale (spec §14)

```
Score Brut = Σ (score_axe × poids_axe)
Score Pondéré = min(Score Brut + contribution_questionnaire, 100) − atténuants
Score Résiduel = Score Pondéré   (score de décision)
```

### 7 axes pondérés

| Axe | Poids spec | Description |
|---|---|---|
| Géographique | 20 % | Pays d'immatriculation — sanctions ONU/UE/OFAC, FATF |
| Corruption / Intégrité | 25 % | Type de tiers, PEP, offshore, listes sanctions |
| Financier | 15 % | Montant du contrat |
| Réputationnel | 15 % | Analyse IA presse / contentieux / scandales |
| Cybersécurité | 10 % | Accès SI, MFA, PRA/PCA, incidents |
| Données personnelles | 10 % | RGPD, biométriques, DPO |
| Documentaire | 5 % | Documents obligatoires manquants |

### 5 catégories de risque (spec §15)

| Score résiduel | Catégorie | Workflow déclenché |
|---|---|---|
| 0 – 20 | **Faible** | Revue standard |
| 21 – 40 | **Modéré** | Revue Compliance + screening |
| 41 – 60 | **Élevé** | DD renforcée + validation Manager |
| 61 – 80 | **Critique** | Validation CCO + revue juridique — **alerte email** |
| 81 – 100 | **Interdit** | Blocage automatique — **alerte email Direction** |

---

## Phase 1 — Moteur de scoring structurel

**Fichiers modifiés :** `dd_request.py`, `dd_request.json`

### Ce qui a été implémenté

- Architecture à **3 scores** distincts :
  - `score_brut` — profil structurel du tiers (axes pondérés, 0-100)
  - `score_pondere` — brut + contribution questionnaire
  - `score_residuel` — score de décision (= pondéré en Phase 1)
- **Axe Géographique** : liste FATF/ONU/OFAC — 3 niveaux (sanctions critiques 100, corruption élevée 60, surveillance 30)
- **Axe Corruption** : type de tiers (criticité DD Type) + 10 flags structurels (PEP +25, offshore +35, sanctions +40, etc.)
- **Axe Financier** : 4 paliers de montant (≥50M=100, ≥10M=60, ≥1M=40, ≥100K=20)
- **Axe Cybersécurité** (partiel) : accès SI uniquement (+25)
- **Axe Données** (partiel) : traitement de données personnelles (+40)
- **Axe Documentaire** (partiel) : documents obligatoires manquants (+15 par document)
- **Contribution questionnaire** : +1 pt par tranche de 10 pts de poids questionnaire, plafonnée à +20
- **5 catégories** dont "Interdit" (ajout de l'option dans le champ `categorie_risque`)
- **Explicabilité JSON** (`detail_scoring`) : snapshot complet axes/aggravants/scores
- **Redistribution Phase 1** : l'axe réputationnel (15%) non calculé → poids redistribués proportionnellement sur les 6 axes (`_POIDS_P1`) pour maintenir l'échelle 0-100
- **Override manuel** : analyste peut forcer `categorie_risque` mais doit renseigner `justification_score_manuel`

### Nouveaux champs DocType

| Champ | Type | Visibilité |
|---|---|---|
| `score_residuel` | Int | Analyste+ (permlevel 1) |
| `detail_scoring` | Long Text JSON | Analyste+ (permlevel 1) |
| Option "Interdit" dans `categorie_risque` | Select | Analyste+ |

### Impact métier

- Chaque dossier reçoit un score calculé automatiquement dès la soumission
- Catégorisation cohérente et traçable, indépendante de l'appréciation individuelle
- Le questionnaire Compliance enrichit le scoring structurel
- L'analyste garde la main via l'override manuel justifié

---

## Phase 2 — Axes complets, atténuants, IA réputationnelle

**Fichiers modifiés :** `dd_request.py`, `dd_request.json`

### Ce qui a été implémenté

#### Axe Cybersécurité — complété (spec §10)

| Critère | Points | Champ |
|---|---|---|
| Accès administration SI | +25 | `acces_si` (existant) |
| Absence MFA | +20 | `tiers_sans_mfa` |
| Absence PRA / PCA | +15 | `tiers_sans_pra_pca` |
| Incident cybersécurité majeur (12 mois) | +30 | `tiers_incident_cyber` |

Max brut calibré : 90 pts (normalisation → 0-100)

#### Axe Données personnelles — complété (spec §11)

| Critère | Points | Champ |
|---|---|---|
| Traitement de données personnelles | +40 | `donnees_personnelles` (existant) |
| Données biométriques | +25 | `tiers_donnees_biometriques` |
| Violation RGPD documentée | +30 | `tiers_violation_rgpd` |
| Absence de DPO | +15 | `tiers_dpo_absent` |

Max brut calibré : 110 pts (normalisation → 0-100)

#### Atténuants (spec §14)

Soustraits du `score_pondere` après contribution questionnaire :

| Atténuant | Réduction | Champ |
|---|---|---|
| Certification ISO 27001 | −15 pts | `tiers_certif_iso27001` |
| Certification ISO 37001 | −20 pts | `tiers_certif_iso37001` |
| Audit Big Four récent | −10 pts | `tiers_audit_big4` |
| Garantie bancaire | −10 pts | `tiers_garantie_bancaire` |
| États financiers certifiés | −15 pts | `tiers_etats_certifies` |
| Solvabilité forte documentée | −20 pts | `tiers_solvabilite_forte` |

Cumul max théorique : −90 pts. Le score pondéré ne peut pas descendre en dessous de 0.

#### Axe Réputationnel — IA (spec §12, §18)

- Appel **Gemini** via API REST Google (`X-goog-api-key`, modèle `gemini-flash-latest`)
- Clé configurée dans `frappe.conf["gemini_api_key"]` (`sites/compliance/site_config.json`)
- Analyse : presse négative, scandales financiers, corruption, contentieux, sanctions
- Score 0-100 stocké dans `score_reputationnel`, résumé textuel dans `resume_reputationnel`
- **Cache** : l'IA n'est appelée qu'une fois (si `resume_reputationnel` est vide)
- **Recalcul forcé** : vider `resume_reputationnel` pour relancer l'analyse
- **Switch formule** : si `ax_reput > 0` → utilise `_POIDS_AXES` (7 axes, somme = 1.0) ; sinon `_POIDS_P1` (6 axes redistribués)

### Nouveaux champs DocType (permlevel 1 — analyste uniquement)

Section **Cybersécurité & Données** : `tiers_sans_mfa`, `tiers_sans_pra_pca`, `tiers_incident_cyber`, `tiers_donnees_biometriques`, `tiers_violation_rgpd`, `tiers_dpo_absent`

Section **Atténuants** : `tiers_certif_iso27001`, `tiers_certif_iso37001`, `tiers_audit_big4`, `tiers_garantie_bancaire`, `tiers_etats_certifies`, `tiers_solvabilite_forte`

Champs IA : `score_reputationnel` (Int), `resume_reputationnel` (Small Text)

> **Note :** L'axe réputationnel utilise l'API Gemini (`check_country_risk` dans `api.py`). Aucune dépendance Anthropic dans l'application.

### Impact métier

- L'analyste Compliance peut saisir les résultats de son investigation technique (Cyber, Données) directement dans le dossier — ils impactent automatiquement le score
- Les certifications et garanties du tiers allègent le score pondéré de façon transparente et auditée
- Un tiers ISO 37001 + audit Big4 voit son score réduit de 30 pts — différenciation significative
- L'IA réputationnelle enrichit le score d'une dimension que les flags structurels ne capturent pas (scandales, condamnations, presse négative)

---

## Phase 3 — Gouvernance, Traçabilité, Configurabilité

**Fichiers modifiés :** `dd_request.py`, `dd_request.json`
**Nouveaux DocTypes :** `DD Score History`, `DD Scoring Config`

### Ce qui a été implémenté

#### Historique des scores — `DD Score History` (spec §17)

Table enfant de `DD Request`. Chaque fois que le `score_residuel` change lors d'une sauvegarde,
une ligne est automatiquement ajoutée avec :

| Colonne | Contenu |
|---|---|
| `date_calcul` | Horodatage précis (datetime) |
| `calcule_par` | Utilisateur ayant déclenché la sauvegarde |
| `score_brut` / `score_pondere` / `score_residuel` | Snapshot des 3 scores |
| `categorie` | Catégorie calculée automatiquement |
| `delta_categorie` | Évolution ex. "Modéré → Critique" |
| `declencheur` | Contexte du recalcul |

L'historique est visible uniquement par l'équipe Compliance (permlevel 1). Il fournit la piste d'audit
réglementaire sur toute la vie du dossier.

#### Moteur de règles configurable — `DD Scoring Config` (spec §14)

Nouveau DocType accessible aux rôles **DD Manager Compliance** et **System Manager**.

Permet de configurer sans toucher au code :
- Les **7 poids des axes** (en %, somme forcée à 100 %)
- Les **4 seuils de catégorie** (Faible / Modéré / Élevé / Critique — Interdit = reste)
- **Une seule config active** à la fois (désactivation automatique de la précédente)

Si aucune config active n'existe → les constantes module (`_POIDS_AXES`, `_SEUILS_RISQUE`) s'appliquent
comme valeurs par défaut.

#### Alertes catégorie Critique / Interdit (spec §16)

Quand `categorie_risque` passe à **Critique** ou **Interdit** lors d'une mise à jour :

- Email automatique envoyé aux rôles **DD Validateur** et **DD Manager Compliance**
- Contient : référence dossier, nom du tiers, score résiduel, demandeur, lien direct
- Couleur rouge pour Interdit, orange pour Critique
- Pas d'alerte si la catégorie ne change pas (évite les doublons sur chaque sauvegarde)

### Architecture globale après Phase 3

```
DD Request (validate)
  └─ calculer_score()
       ├─ _charger_config_scoring()   ← DD Scoring Config actif ou constantes module
       ├─ [calcul 7 axes]
       ├─ [formule pondérée]
       ├─ [atténuants]
       ├─ _score_reputationnel_ia()   ← Gemini REST (cache)
       └─ _enregistrer_historique_score()   ← DD Score History (si changement)

DD Request (on_update)
  └─ _alerter_categorie_critique()   ← email Validateur + Manager si Critique/Interdit
```

### Impact métier

- **Auditabilité complète** : toute modification de score est horodatée et attribuée → traçabilité réglementaire (SAPIN II, Loi Duhot)
- **Adaptabilité** : l'équipe Compliance peut repondérer les axes en réponse à un changement réglementaire (ex. hausse du poids cyber après une directive NIS2) sans intervention dev
- **Réactivité opérationnelle** : les validateurs et managers sont alertés en temps réel dès qu'un dossier atteint un niveau critique — pas de risque de dossiers "Interdit" passés inaperçus

---

## Récapitulatif technique

| Composant | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|---|---|---|---|---|
| Axes actifs | 6 (réput. = 0) | 7 (réput. IA) | 7 | 7 |
| Atténuants | — | 6 (−90 pts max) | configurables | + docs optionnels conformes (−8/doc, max −20) |
| Catégories | 5 | 5 | seuils configurables | seuils configurables |
| Historique | — | — | DD Score History | DD Score History |
| Config dynamique | — | — | DD Scoring Config | DD Scoring Config |
| Alertes | — | — | email Critique/Interdit | email Critique/Interdit |
| IA | — | Gemini (réputation) | Gemini (réputation + avis compliance) | Gemini Vision (vérif docs) |
| Axe Documentaire | docs manquants | docs manquants | docs manquants | docs manquants OU non conformes IA | Gemini Vision (vérif docs) |

## Variables d'environnement

| Clé `frappe.conf` | Rôle | Requis |
|---|---|---|
| `gemini_api_key` | Clé API Google Gemini — axe réputationnel + génération avis IA | Non (fallback = 0 / avis non générés) |

## Phase 4 — Vérification documentaire IA (Gemini Vision)

**Fichiers modifiés :** `dd_request.py`, `dd_required_document.json`

### Ce qui a été implémenté

#### Champs IA sur `DD Required Document`

| Champ | Type | Rôle |
|---|---|---|
| `ia_verification` | Select | Non vérifié / Conforme / Non conforme / Incertain |
| `ia_confiance` | Int | Score de confiance 0-100% |
| `ia_motif` | Small Text | Explication décision IA |
| `ia_infos_extraites` | Long Text | JSON : dates, noms, numéros, autres |

#### Déclenchement automatique

`on_update()` → `_analyser_documents_ia()` → `_verifier_document_ia(row, api_key)` pour chaque fichier nouvellement uploadé (ia_verification vide ou "Non vérifié").

#### Gemini Vision

- Formats : image/jpeg, png, webp, heic, heif, application/pdf (limite 5 Mo)
- Prompt JSON structuré : vérification type document + extraction infos clés
- Fallback chain : `gemini-2.5-flash-lite` → `gemini-2.0-flash-lite` → `gemini-2.5-flash` → `gemini-2.0-flash`
- Seuil "Incertain" : `confiance >= 40` mais non conforme

#### Impact scoring

- **Axe Documentaire** : doc uploadé mais `ia_verification="Non conforme"` → pénalisé comme manquant (+15 pts)
- **Atténuants** : doc optionnel `ia_verification="Conforme"` → −8 pts, max −20 pts au total

---

## Prochaines évolutions possibles

- **Questionnaire par axe** : mapper chaque question DD au bon axe (cyber → ax_cyber, anticorruption → ax_corr) plutôt que contribution flat +20 max
- **Axe Documentaire Phase 5** : document expiré (utiliser `ia_infos_extraites.dates`), incohérence (+25), falsification suspectée (+50)
- **Score résiduel décorrélé** : mesures de maîtrise post-DD (plan d'action, suivi périodique) réduisant le score résiduel indépendamment du score pondéré
- **Screening automatique** : intégration APIs World-Check / Dow Jones Risk & Compliance pour l'axe Corruption
- **Tableau de bord Compliance** : évolution des scores par portefeuille, alertes expirations, suivi des atténuants
