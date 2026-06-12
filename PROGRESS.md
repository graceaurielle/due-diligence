# Due Diligence — Journal de progression

**Projet :** Application Frappe `due_diligence` — Cabinet AMOAMAN & ASSOCIÉS  
**Site cible :** `compliance`  
**Dernière mise à jour :** 2026-06-11

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

### À faire (backlog)
- [ ] Surveillance continue : logique de réévaluation périodique (`Sous surveillance continue`)
- [ ] Séparation des tâches : désactiver `allow_self_approval` en production sur certaines transitions
- [ ] Type DD **Sous-traitant** : aucune question définie — décider d'activer ou de désactiver
- [ ] Notifications email : câbler sur toutes les transitions (actuellement `send_email_alert: 0`)

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

## Notes techniques

- `is_submittable = 1` sur DD Request → verrouillage natif post-submit
- `allow_on_submit = 1` sur champs équipe (évaluation + décision)
- `has_website_permission` → filtre owner-only côté portail
- Points d'extension commentés pour : screening externe, IA/NLP, OCR, e-signature
