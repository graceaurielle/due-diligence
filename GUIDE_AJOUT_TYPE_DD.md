# Guide : Ajouter un nouveau type de Due Diligence

Ce guide explique comment ajouter les questions, sections, documents requis et demandes
pour un nouveau type de DD (ex : Partenaire, Client, Sous-traitant...).

---

## Architecture en 3 couches

```
DD Type          ← définit le type (ex : "Partenaire") et ses documents requis
 └── DD Section  ← définit les sections du questionnaire (ex : "A — Informations générales")
      └── DD Question  ← définit chaque question, liée à une section
```

Les 3 couches sont dans des fichiers JSON de fixtures et sont importées via `bench migrate`.

---

## Étape 1 — Vérifier que le DD Type existe

Le type doit exister dans `fixtures/dd_type.json`.
Tous les types sont déjà créés (Fournisseur, Partenaire, Client, Sous-traitant, etc.).

Si tu veux ajouter les documents requis à un type, modifie son entrée dans `dd_type.json` :

```json
{
  "doctype": "DD Type",
  "name": "Partenaire",
  "type_name": "Partenaire",
  "documents_requis_template": [
    {"nom_document": "Accord de partenariat", "obligatoire": 1},
    {"nom_document": "Statuts", "obligatoire": 1},
    {"nom_document": "Rapport annuel", "obligatoire": 0}
  ]
}
```

**`obligatoire: 1`** = document obligatoire dans la checklist  
**`obligatoire: 0`** = document optionnel

---

## Étape 2 — Créer les sections dans `dd_section.json`

Fichier : `apps/due_diligence/due_diligence/fixtures/dd_section.json`

Chaque section a un `name` unique (clé primaire), un `dd_type`, un `section_label` et un `ordre`.

**Convention de nommage des `name` :** `ABREV-SEC-X`
- `ABREV` = abréviation du type (ex : PART pour Partenaire, CLI pour Client)
- `SEC` = toujours SEC
- `X` = lettre de la section (A, B, C...)

**L'`ordre` détermine l'ordre d'affichage.** Utiliser des multiples de 10 pour laisser de la place.

```json
[
  {
    "doctype": "DD Section",
    "name": "PART-SEC-A",
    "dd_type": "Partenaire",
    "section_label": "A — Informations générales",
    "ordre": 10
  },
  {
    "doctype": "DD Section",
    "name": "PART-SEC-B",
    "dd_type": "Partenaire",
    "section_label": "B — Gouvernance",
    "ordre": 20
  },
  {
    "doctype": "DD Section",
    "name": "PART-SEC-C",
    "dd_type": "Partenaire",
    "section_label": "C — Conformité",
    "ordre": 30
  }
]
```

Ajouter ces entrées à la fin du tableau JSON existant dans `dd_section.json`
(après les entrées Fournisseur).

---

## Étape 3 — Créer les questions dans `dd_question.json`

Fichier : `apps/due_diligence/due_diligence/fixtures/dd_question.json`

**Convention de nommage des `name` :** `ABREV-SEC-NNN` ou `ABREV-SEC-NNN-SUB`
- `ABREV` = même abréviation que pour les sections
- `SEC` = lettre de la section (A, B, C...)
- `NNN` = numéro sur 3 chiffres (001, 002, 003...)
- `-SUB` = pour une sous-question conditionnelle

### Question simple (champ texte)

```json
{
  "doctype": "DD Question",
  "name": "PART-A-001",
  "dd_type": "Partenaire",
  "etape": "PART-SEC-A",
  "question_label": "Raison sociale du partenaire",
  "field_type": "Data",
  "obligatoire": 1,
  "poids_risque": 0,
  "demander_document": 0
}
```

### Question oui/non (case à cocher)

```json
{
  "doctype": "DD Question",
  "name": "PART-B-001",
  "dd_type": "Partenaire",
  "etape": "PART-SEC-B",
  "question_label": "Existe-t-il des liens avec des responsables publics ?",
  "field_type": "Check",
  "obligatoire": 1,
  "poids_risque": 25,
  "demander_document": 0
}
```

### Question avec demande de document

Cocher `demander_document: 1` et renseigner `label_document`.
Le document apparaîtra dans la checklist finale (étape 5 du wizard).

```json
{
  "doctype": "DD Question",
  "name": "PART-A-002",
  "dd_type": "Partenaire",
  "etape": "PART-SEC-A",
  "question_label": "L'entité dispose-t-elle d'un rapport annuel ?",
  "field_type": "Check",
  "obligatoire": 0,
  "poids_risque": 0,
  "demander_document": 1,
  "label_document": "Rapport annuel d'activité"
}
```

### Sous-question conditionnelle

Une sous-question n'apparaît que si la question parente a une certaine valeur.
Elle doit avoir `question_parente` (le `name` de la question parente) et `valeur_declenchante`.

**Pour une case à cocher (Check) : `valeur_declenchante` = `"Oui"`**

```json
{
  "doctype": "DD Question",
  "name": "PART-B-001-SUB",
  "dd_type": "Partenaire",
  "etape": "PART-SEC-B",
  "question_label": "Précisez la nature de ces liens",
  "field_type": "Small Text",
  "obligatoire": 1,
  "poids_risque": 0,
  "question_parente": "PART-B-001",
  "valeur_declenchante": "Oui",
  "demander_document": 1,
  "label_document": "Déclaration de liens d'intérêts"
}
```

---

## Référence des `field_type`

| field_type   | Rendu dans le wizard       | Usage typique                         |
|--------------|----------------------------|---------------------------------------|
| `Data`       | Champ texte court          | Noms, numéros, codes                  |
| `Small Text` | Zone de texte multiligne   | Descriptions, précisions              |
| `Check`      | Bouton Oui / Non           | Questions fermées (oui/non)           |
| `Int`        | Champ numérique entier     | Effectifs, quantités                  |
| `Currency`   | Champ montant              | Chiffre d'affaires, budgets           |
| `Date`       | Sélecteur de date          | Dates de création, échéances          |
| `Select`     | Liste déroulante           | Choix parmi des options (voir options)|

Pour `Select`, ajouter un champ `options` avec les valeurs séparées par `\n` :

```json
{
  "field_type": "Select",
  "options": "Faible\nModéré\nÉlevé\nCritique"
}
```

---

## Référence des champs `poids_risque`

Le `poids_risque` contribue au score de risque global calculé pour la demande DD.
Utiliser des valeurs cohérentes :

| Niveau de risque         | Valeur suggérée |
|--------------------------|-----------------|
| Aucun impact             | 0               |
| Risque faible            | 5 à 10          |
| Risque modéré            | 15 à 25         |
| Risque élevé             | 30 à 50         |
| Risque critique / bloquant | 75 à 100      |

---

## Étape 4 — Appliquer les changements

Après avoir modifié les fichiers JSON :

```bash
bench --site compliance migrate
bench --site compliance clear-cache
```

Les nouvelles sections et questions seront importées dans la DB.
Tu peux ensuite les modifier depuis l'interface Frappe desk :
- **Due Diligence → Sections** pour modifier les sections
- **Due Diligence → Questions** pour modifier les questions

---

## Exemple complet : type "Partenaire"

### `dd_section.json` — ajouter à la fin du tableau

```json
  {"doctype": "DD Section", "name": "PART-SEC-A", "dd_type": "Partenaire", "section_label": "A — Informations générales", "ordre": 10},
  {"doctype": "DD Section", "name": "PART-SEC-B", "dd_type": "Partenaire", "section_label": "B — Gouvernance", "ordre": 20},
  {"doctype": "DD Section", "name": "PART-SEC-C", "dd_type": "Partenaire", "section_label": "C — Conformité", "ordre": 30}
```

### `dd_question.json` — ajouter à la fin du tableau

```json
  {"doctype": "DD Question", "name": "PART-A-001", "dd_type": "Partenaire", "etape": "PART-SEC-A", "question_label": "Raison sociale", "field_type": "Data", "obligatoire": 1, "poids_risque": 0, "demander_document": 0},
  {"doctype": "DD Question", "name": "PART-A-002", "dd_type": "Partenaire", "etape": "PART-SEC-A", "question_label": "Pays d'immatriculation", "field_type": "Data", "obligatoire": 1, "poids_risque": 0, "demander_document": 0},
  {"doctype": "DD Question", "name": "PART-B-001", "dd_type": "Partenaire", "etape": "PART-SEC-B", "question_label": "Liens avec responsables publics ?", "field_type": "Check", "obligatoire": 1, "poids_risque": 25, "demander_document": 0},
  {"doctype": "DD Question", "name": "PART-B-001-SUB", "dd_type": "Partenaire", "etape": "PART-SEC-B", "question_label": "Précisez la nature de ces liens", "field_type": "Small Text", "obligatoire": 1, "poids_risque": 0, "question_parente": "PART-B-001", "valeur_declenchante": "Oui", "demander_document": 1, "label_document": "Déclaration de liens d'intérêts"}
```

### `dd_type.json` — documents requis pour Partenaire

```json
  "documents_requis_template": [
    {"nom_document": "Statuts", "obligatoire": 1},
    {"nom_document": "Rapport annuel", "obligatoire": 0},
    {"nom_document": "RCCM ou équivalent", "obligatoire": 1}
  ]
```

---

## Conventions à respecter

- Le champ `name` dans chaque entrée JSON est la **clé primaire** — ne pas le changer après création (il sert à identifier le record lors de `bench migrate`)
- Toujours utiliser le même préfixe d'abréviation pour un type donné (PART, CLI, SOUS, INT...)
- L'`etape` d'une question doit être le `name` d'une section existante du même `dd_type`
- La `question_parente` d'une sous-question doit être le `name` d'une question existante
- Après `bench migrate`, les records peuvent être modifiés depuis l'interface sans toucher aux fichiers JSON (les modifications de l'interface sont prioritaires)
