# Due Diligence — Journal de progression

**Projet :** Application Frappe `due_diligence` — Cabinet AMOAMAN & ASSOCIÉS  
**Site cible :** `compliance`  
**Dernière mise à jour :** 2026-07-01

---

## État des phases

| Phase | Titre | Statut |
|-------|-------|--------|
| 1 | Modèle de données (DocTypes) | ✅ Terminé |
| 2 | Rôles & permissions | ✅ Terminé |
| 3 | Workflow de traitement | ✅ Terminé |
| 4 | Logique métier serveur (hooks) | ✅ Terminé |
| 5 | Portail client (web) | ✅ Terminé |
| 6 | Avis Compliance & impression | ✅ Terminé |
| 7 | Données de démo & tests | ✅ Terminé |
| 8 | Responsive design (toutes pages) | ✅ Terminé |
| 9 | Sidebar — widget utilisateur | ✅ Terminé |
| 10 | Conformité CSS (CSS custom properties) | ✅ Terminé |
| 11 | Bugs portail client — questions & documents | ✅ Terminé |
| 12 | Avis IA Gemini — intégration complète | ✅ Terminé |
| 13 | Champ `tiers_montant_contrat` — repositionnement & obligation | ✅ Terminé |
| 14 | Vérification IA des documents (Gemini Vision) | ✅ Terminé |
| 15 | Badge cloche + Circuit documents complémentaires | ✅ Terminé |

### À faire (backlog)
- [ ] Surveillance continue : logique de réévaluation périodique (`Sous surveillance continue`)
- [ ] Séparation des tâches : désactiver `allow_self_approval` en production sur certaines transitions
- [ ] Type DD **Sous-traitant** : aucune question définie — décider d'activer ou de désactiver
- [ ] Notifications email : configurer un compte SMTP sortant (Tools > Email Account) — voir warning "Please setup default outgoing Email Account"
- [ ] IA avis non visible par clients : `mes_avis.py` filtre `docstatus=1` mais les avis IA ont `docstatus=0`
- [ ] Administrator `isInterne=false` : Administrator a le rôle DD Client → apparaît comme non-interne dans le desk

---

## Phase 1 — Modèle de données

**Statut :** En cours  
**Date de démarrage :** 2026-06-04

### DocTypes à créer
- [x] `DD Type` — paramétrage des 13 types de DD
- [x] `DD Question` — banque de questions dynamiques
- [x] `DD Required Document` — child table documents
- [x] `DD Answer` — child table réponses questionnaire
- [x] `DD Request` — dossier central (is_submittable=1)

### Fixtures
- [x] 13 `DD Type` seeds (Fournisseur, Partenaire, Client, Sous-traitant, Intermédiaire commercial, Consultant, Fusion-Acquisition, Protection des données, Cybersécurité, ESG, Anticorruption, Financière, Réputationnelle)

### `bench migrate`
- [x] Migration exécutée et validée — 2026-06-04
  - 5 tables créées : tabDD Answer, tabDD Question, tabDD Request, tabDD Required Document, tabDD Type
  - 13 DD Type fixtures chargées en base

---

## Phase 2 — Rôles & permissions

### Rôles à créer
- `DD Client` (desk_access=0)
- `DD Analyste`
- `DD Manager Compliance`
- `DD Validateur`
- `DD Juridique`, `DD DPO`, `DD Cyber`, `DD Financier` (prévus, non câblés MVP)

### Permissions DD Request
- `DD Client` : create/read/write/submit (if_owner=1)
- `DD Analyste` : read/write
- `DD Manager Compliance` : read/write + workflow
- `DD Validateur` : read/write + décision finale

### Masquage v16
- `score_brut`, `score_pondere`, `commentaire_interne` → permlevel 1

---

## Phase 3 — Workflow

### États définis
1. Brouillon → 2. Soumis → 3. En préqualification → 4. En analyse Compliance
5. En attente de documents → 6. En validation Manager → 7. En validation Direction
8. Clôturé — GO / 9. Clôturé — NO GO / 10. Clôturé — GO sous réserve

---

## Phase 4 — Logique métier

- `validate` : verrou soumission unique côté portail
- `calculer_score` : scoring MVP (règles + poids)
- `on_update` / hook File : SHA-256 hash documentaire
- `on_submit` : assignation analyste, notifications email
- Décision finale : horodatage `date_decision`, notification client

---

## Phase 5 — Portail client

- `/mes-demandes` : tableau de bord client
- `/nouvelle-demande` : wizard multi-étapes
- `/suivi/<name>` : suivi lecture seule
- `/connexion` : page d'authentification custom (split layout navy/blanc)

### Bug résolu
- Fichiers `.py` avec tirets (`mes-demandes.py`) non détectés par Frappe → renommés en underscores (`mes_demandes.py`, `nouvelle_demande.py`, `dd_confirmation.py`)

---

## Phase 6 — Print Format

- « Avis Compliance » : PDF A4 style bleu institutionnel AMOAMAN — ✅ livré 2026-06-05
- Moteur Jinja natif Frappe v16
- Fixture : `fixtures/print_format.json` → importée via `bench migrate`
- 5 sections : Infos générales, Facteurs de risque + scores, Questionnaire, Documents, Avis Compliance
- Bandeau décision coloré (GO / NO GO / GO sous réserve), zone signatures, pied de page CONFIDENTIEL

---

## Phase 7 — Démo & tests

### Données démo — livré 2026-06-05
- Script : `bench --site compliance execute due_diligence.demo.seed`
- Utilisateur : `demo.client@amoaman.ci` / `Demo@2026!` (rôle DD Client)
- DD-2026-00001 — TechnoSoft SARL → En analyse Compliance
- DD-2026-00002 — BTP Groupe Ivoire → Clôturé — GO
- DD-2026-00003 — Conseil & Stratégie CI → En attente de documents
- Suppression : `bench --site compliance execute due_diligence.demo.teardown`

### Tests automatisés — 12/12 ✅
- `bench --site compliance run-tests --app due_diligence`
- **TestScoring** (9 tests) : score zéro, bonus contexte, cumuls, seuils exacts (Faible/Modéré/Élevé/Critique)
- **TestVerrouPortail** (3 tests) : blocage DD Client sur dossier soumis, passage analyste, brouillon libre
- **TestIsolation** (1 test) : filtre owner= exclusif

---

## Phase 8 — Responsive design

**Statut :** Terminé — 2026-06-11

### Pages traitées
- [x] `connexion.html` — split layout 50/50, collapse mobile
- [x] `tableau-de-bord.html` — KPI 4→2 cols, charts 3→1 col, donut vertical sur mobile
- [x] `mes-demandes.html` — header flex-wrap, tableau scroll horizontal, KPI 3→2 cols
- [x] `mes-suivis.html` — header flex-wrap, btn-label masqué ≤520px, suivi-card min-width:0
- [x] `nouvelle-demande.html` — stepper collapse, type-grid 3→2→1 cols
- [x] `suivi.html` — page-title 18px, status-pill white-space:normal, word-break
- [x] `mes-avis.html` — avis-grid 2→1 col, overflow-wrap sur noms longs
- [x] `dd-confirmation.html` — confirm-card centré, padding réduit

### Règles appliquées
- `_sidebar.html` : sidebar en drawer ≤1024px, `.dd-mobile-bar` sticky, `word-break:break-word` global sur `.dd-main`
- Breakpoints : 1024px (tablette), 800px (moyen), 767px (mobile), 520px (petit téléphone), 420px (très petit)
- Pattern `btn-label` : `<span class="btn-label">` masqué ≤520px pour garder l'icône seule
- `height:auto; min-height:60px; flex-wrap:wrap` sur `.dd-header` pour éviter le clipping

---

## Phase 9 — Sidebar widget utilisateur

**Statut :** Terminé — 2026-06-11

- Widget avatar + nom + email en bas de sidebar (données depuis `frappe.db.get_value` côté Jinja)
- Initiales calculées côté serveur (ex. "JD" pour Jean Dupont)
- Dropdown "Déconnexion" au clic, fermeture au clic extérieur
- Remplace l'ancien lien de déconnexion simple

---

## Phase 10 — Conformité CSS

**Statut :** Terminé — 2026-06-11

- Suppression de toutes les valeurs Jinja `{{ }}` dans les attributs `style=""`
- Remplacement par **CSS Custom Properties** : `style="--dot-color: {{ val }}"` + `background: var(--dot-color)` en CSS
- Classes sémantiques `.risk-faible / .risk-modere / .risk-eleve / .risk-critique` pour couleurs
- Classe `.risk-dot` pour l'indicateur de risque dans les tableaux
- Fichier concerné : `tableau-de-bord.html`

---

## Phase 11 — Bugs portail client (questions & documents)

**Statut :** Terminé — 2026-06-24

### Contexte
Flux : utilisateur interne (desk) crée le DD Request, choisit le type et assigne un client.
Le client reçoit un lien `/nouvelle-demande?dd_name=XXX` et doit remplir le questionnaire (étape 2) et les documents (étape 3).
Les questions et les documents n'apparaissaient pas, quelle que soit le type de DD.

### Bugs identifiés et corrigés

#### Bug 1 — `frappe.call is not a function` (cause racine principale)
- **Fichier :** `www/nouvelle-demande.html`
- **Cause :** L'IIFE d'initialisation `(function(){...})()` s'exécutait immédiatement au parsing du `<script>`, avant que Frappe JS ait fini de s'initialiser. `frappe.call` n'existait donc pas encore → `wizard.ddType` restait vide → aucune question chargée.
- **Correction :** Remplacement de l'IIFE par `frappe.ready(function() { ... })` qui attend l'initialisation complète de Frappe JS.

#### Bug 2 — Permission refusée sur `frappe.get_doc("DD Request", ...)` pour les portal users
- **Fichier :** `due_diligence/api.py` — fonctions `get_dd_draft` et `complete_dd_request`
- **Cause :** `frappe.get_doc` applique les permissions standard Frappe. Le rôle "DD Client" est un Website User (desk_access=0) sans permission standard de lecture sur "DD Request" (seul `has_website_permission` est défini, qui ne s'applique pas aux appels whitelist). Résultat : exception silencieuse, `dd_type` jamais retourné.
- **Correction :**
  - `get_dd_draft` : remplacé par `frappe.db.get_value(...)` (bypass permissions, vérification manuelle du `client_user`)
  - `complete_dd_request` : vérification du `client_user` via `frappe.db.get_value`, puis `frappe.flags.ignore_permissions = True` avant `frappe.get_doc`

#### Bug 3 — `frappe.get_all` retourne vide pour les Website Users sans `ignore_permissions=True`
- **Fichier :** `due_diligence/api.py` — fonctions `get_dd_types`, `get_questions`, `get_required_documents`
- **Cause :** `frappe.get_all` sur des doctypes internes (`DD Question`, `DD Section`, `DD Document Requis Template`) retourne silencieusement une liste vide pour les Website Users, même si le rôle `All` a `read=1`.
- **Correction :** Ajout de `ignore_permissions=True` sur tous les `frappe.get_all` de ces fonctions.

#### Bug 4 — `loadQuestions()` early-exit sans appeler les sections DPD/Cyber/Financière
- **Fichier :** `www/nouvelle-demande.html` — fonction `loadQuestions()`
- **Cause :** Le branch `if (wizard.questions.length > 0)` appelait uniquement `renderQuestions()` et retournait, sautant `renderDpdSection()`, `renderCyberSection()`, etc. De plus, `renderQuestions()` remplace tout le `innerHTML` du container, effaçant les sections précédemment injectées.
- **Correction :** L'early-exit appelle maintenant toutes les fonctions render. Gardes anti-double-injection ajoutées (`if (document.getElementById('dpd-gateway-card')) return;`).

### Fichiers modifiés
- `apps/due_diligence/due_diligence/api.py`
- `apps/due_diligence/due_diligence/www/nouvelle-demande.html`

---

## Phase 12 — Avis IA Gemini (intégration complète)

**Statut :** Terminé — 2026-06-24

### Contexte
Remplacement complet d'Anthropic/Claude par l'API Gemini (Google). L'avis IA n'est plus stocké dans un champ `avis_ia` sur le DD Request, mais crée un document `DD Avis Compliance` dédié (marqué `is_ia_avis = 1`), cohérent avec les avis humains.

### Ce qui a été implémenté

#### Migration Anthropic → Gemini
- **`api.py`** `check_country_risk` : remplacé `import anthropic` + `anthropic_api_key` par appel REST Gemini (`X-goog-api-key`, modèle `gemini-flash-latest`)
- **`site_config.json`** : clé `gemini_api_key` configurée
- Paquet `anthropic` non installé sur ce serveur → Gemini REST via `requests` (toujours disponible)

#### Stratégie multi-modèles avec fallback
Ordre de tentative (lite d'abord = quota gratuit plus élevé) :
1. `gemini-flash-lite-latest`
2. `gemini-2.0-flash-lite`
3. `gemini-2.5-flash-lite`
4. `gemini-flash-latest`
5. `gemini-2.0-flash`
6. `gemini-2.5-flash` (génération manuelle uniquement)

Gestion erreurs : 429 (quota) → retry avec backoff, 503 (indispo) → retry, 404 (modèle absent) → skip immédiat.

#### Architecture DD Avis Compliance pour l'IA
- Suppression du champ `avis_ia` (Long Text) et `avis_analyste` sur `DD Request`
- Suppression de la section `sb_avis` sur `DD Request`
- Nouveau champ `is_ia_avis` (Check, read_only) sur `DD Avis Compliance`
- L'avis IA est créé comme un `DD Avis Compliance` standard avec `is_ia_avis = 1`
- Les champs `decision` (GO/NO GO/GO sous réserve) et `motif_decision` sont remplis automatiquement
- Le modèle IA est guidé pour commencer par `DECISION: GO` / `DECISION: NO GO` / `DECISION: GO sous réserve` pour parsing fiable

#### Génération automatique à la soumission
- `DD Request.on_submit` → `_generer_avis_ia_auto(self)` (méthode de classe, `dd_request.py`)
- `api.py` `complete_dd_request` et `create_dd_request` → `_generer_avis_ia_auto(dd_request_name)` (fonction standalone)
- Les deux fonctions vérifient l'existence d'un avis IA non soumis avant de créer (pas de doublons)
- Silencieuses en cas d'échec (ne bloquent pas la soumission)

#### Bouton "Générer l'avis IA" (desk)
- Visible pour : `DD Analyste`, `DD Manager Compliance`, `DD Validateur`, `System Manager`
- Crée ou met à jour le `DD Avis Compliance` IA non soumis existant
- Après génération → redirige directement vers le document créé

#### Bouton "Rédiger mon avis" (desk)
- Ouvre un nouveau formulaire `DD Avis Compliance` pré-rempli (sans insert serveur) via `frappe.new_doc()`
- Champs pré-remplis : `dd_request`, `tiers_nom`, `dd_type`, `redige_par`, `date_decision`
- Aucune validation de champs obligatoires (l'utilisateur les saisit lui-même)

### Fichiers modifiés
- `apps/due_diligence/due_diligence/due_diligence/doctype/dd_request/dd_request.py`
- `apps/due_diligence/due_diligence/due_diligence/doctype/dd_request/dd_request.json`
- `apps/due_diligence/due_diligence/due_diligence/doctype/dd_request/dd_request.js`
- `apps/due_diligence/due_diligence/due_diligence/doctype/dd_avis_compliance/dd_avis_compliance.json`
- `apps/due_diligence/due_diligence/api.py`
- `sites/compliance/site_config.json`

---

## Phase 13 — Champ `tiers_montant_contrat` : repositionnement & obligation

**Statut :** Terminé — 2026-06-30

### Contexte
Le champ "Montant du contrat (FCFA)" était dans la section "Demandeur" (rempli par le client). Il doit être dans la section "Nature de votre relation avec nous" car c'est l'interne qui le renseigne, et il doit être obligatoire.

### Ce qui a été fait

- **`dd_request.json`** : champ `tiers_montant_contrat` déplacé après `sb_relation`, `"reqd": 1` ajouté
- **`tabDocField` SQL** : réordonnage `idx` via `bench execute` (eval one-liner) :
  - `UPDATE tabDocField SET idx=idx+1 WHERE parent='DD Request' AND idx >= 17 AND idx < 46`
  - `UPDATE tabDocField SET idx=17 WHERE parent='DD Request' AND fieldname='tiers_montant_contrat'`
  - `UPDATE tabDocField SET reqd=1 WHERE parent='DD Request' AND fieldname='tiers_montant_contrat'`
- Ordre final : `sb_relation(16)` → `tiers_montant_contrat(17)` → `relation_description(18)` → `relation_objectif_metier(19)`

### Note technique
`bench migrate` / `bench reload-doc` ne réordonnent pas les `idx` existants — toujours passer par SQL direct.

---

## Phase 14 — Vérification IA des documents (Gemini Vision)

**Statut :** Terminé — 2026-06-30

### Contexte
Les documents joints à un dossier DD doivent être vérifiés automatiquement : est-ce bien le bon type de document ? Un RCCM uploadé à la place d'une photo d'identité doit être détecté et pénalisé. Les docs optionnels conformes doivent réduire le score.

### Nouveaux champs `DD Required Document`

| Champ | Type | Description |
|---|---|---|
| `ia_verification` | Select | Non vérifié / Conforme / Non conforme / Incertain |
| `ia_confiance` | Int | Score de confiance IA 0-100% |
| `ia_motif` | Small Text | Explication de la décision IA (max 80 mots) |
| `ia_infos_extraites` | Long Text | JSON avec dates, noms, numéros extraits |

Migration : `bench --site compliance migrate` → 4 colonnes `ia_*` créées dans `tabDD Required Document`.

### Logique implémentée (`dd_request.py`)

1. **`on_update()`** → appelle `_analyser_documents_ia()`
2. **`_analyser_documents_ia()`** : itère les lignes de `required_documents`, skip si pas de fichier ou déjà vérifié, appelle `_verifier_document_ia(row, api_key)` puis `db_set` les résultats
3. **`_verifier_document_ia(row, api_key)`** :
   - Lit le fichier via `frappe.get_doc("File", {"file_url": row.fichier})`
   - Vérifie la taille (limite 5 Mo) et le MIME (image/jpeg, png, webp, heic, heif, application/pdf)
   - Encode en base64 et envoie à Gemini Vision avec prompt structuré JSON
   - Fallback chain : `gemini-2.5-flash-lite` → `gemini-2.0-flash-lite` → `gemini-2.5-flash` → `gemini-2.0-flash`
   - Parse la réponse JSON : `conforme`, `confiance`, `motif`, `infos` (dates/noms/numeros/autres)
   - Seuil "Incertain" si `confiance >= 40` mais non conforme

### Impact sur le scoring (`calculer_score()`)

**Axe Documentaire [5%] :**
- Doc obligatoire `statut="Attendu"` OU doc uploadé mais `ia_verification="Non conforme"` → pénalisé (+15 pts)
- Traite les mauvais documents uploadés comme des documents manquants

**Atténuants :**
- Doc optionnel avec fichier ET `ia_verification="Conforme"` → −8 pts par doc, max −20 pts au total

### Fichiers modifiés
- `apps/due_diligence/due_diligence/due_diligence/doctype/dd_required_document/dd_required_document.json`
- `apps/due_diligence/due_diligence/due_diligence/doctype/dd_request/dd_request.py`

---

---

## Phase 15 — Badge cloche + Circuit documents complémentaires

**Statut :** Terminé — 2026-07-01

### 15.1 — Badge cloche Frappe (compteur notifications)

**Problème :** Le badge numérique sur la cloche de notifications ne s'incrémentait jamais, bien que les `Notification Log` étaient créés correctement.

**Cause racine :** Les appels `frappe.publish_realtime("notification", {"doctype": "Notification Log"}, user=user)` passaient un dict comme payload. Or Frappe v16 (`notification_log.py`) appelle `frappe.publish_realtime("notification", after_commit=True, user=...)` sans payload — le client JS côté bureau n'incrémente le badge que sur ce format exact.

**Correction dans `dd_request.py` :** Suppression du dict dans les 3 occurrences de `publish_realtime` :
```python
# Avant (badge cassé) :
frappe.publish_realtime("notification", {"doctype": "Notification Log"}, user=user, after_commit=True)

# Après (correct) :
frappe.publish_realtime("notification", after_commit=True, user=user)
```

### 15.2 — Circuit documents complémentaires

**Objectif :** Permettre à l'analyste de lister des documents manquants, notifier le client, et que le client les dépose depuis le portail `/suivi`.

#### Nouveau DocType `DD Document Complementaire` (child table)

| Champ | Type | Description |
|---|---|---|
| `nom_document` | Data (reqd) | Nom du document demandé |
| `obligatoire` | Check (défaut=1) | Si obligatoire pour la reprise |
| `statut` | Select (En attente/Fourni) | Statut du dépôt |
| `description` | Small Text | Instructions/précisions |
| `commentaire_analyste` | Small Text | Note interne |
| `fichier` | Attach | Fichier déposé par le client |
| `date_fourni` | Datetime (read_only) | Horodatage du dépôt |

Child table `documents_complementaires` ajoutée à `DD Request` (section collapsible).

#### Flux complet

1. **Analyste** renseigne le tableau `Documents complémentaires` dans le desk, puis déclenche "Demander des documents complémentaires" → état "En attente de documents"
2. **`_notifier_client_docs_manquants()`** : crée un `Notification Log` + realtime pour le client (owner du dossier), envoie un email avec liste des docs + lien `/suivi?name=...`
3. **Portail `/suivi`** : section orange "Documents complémentaires requis" visible, avec badge "N en attente" et un bouton **Déposer** par ligne
4. **`uploadDoc(input)`** JS :
   - `POST /api/method/upload_file` (Frappe standard, fichier privé)
   - `POST /api/method/due_diligence...fournir_document_complementaire` → marque la ligne `Fourni` + date
5. **`_notifier_analyste_doc_fourni()`** :
   - Notifie toujours l'analyste assigné
   - Si tous les docs obligatoires sont fournis → notifie aussi tous les `DD Manager Compliance` avec bouton vert "Reprendre l'analyse →"

#### API whitelistée `fournir_document_complementaire`
- Vérification : `session.user == doc.owner` OU permission write sur "DD Request"
- Met à jour `row.fichier`, `row.statut = "Fourni"`, `row.date_fourni`
- Retourne `{"tous_fournis": bool}`

### Fichiers modifiés / créés
- `due_diligence/doctype/dd_document_complementaire/dd_document_complementaire.json` (nouveau)
- `due_diligence/doctype/dd_document_complementaire/dd_document_complementaire.py` (nouveau)
- `due_diligence/doctype/dd_request/dd_request.json` — champ `documents_complementaires` ajouté
- `due_diligence/doctype/dd_request/dd_request.py` — fix `publish_realtime` + `_notifier_client_docs_manquants` + `fournir_document_complementaire` + `_notifier_analyste_doc_fourni`
- `www/suivi.py` — `docs_comp` passé au contexte
- `www/suivi.html` — section upload + JS `uploadDoc()`

---

## Notes techniques

- `is_submittable = 1` sur DD Request → verrouillage natif post-submit
- `allow_on_submit = 1` sur champs équipe (évaluation + décision)
- `has_website_permission` → filtre owner-only côté portail
- Points d'extension commentés pour : screening externe, IA/NLP, OCR, e-signature
