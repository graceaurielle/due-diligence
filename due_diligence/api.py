import json

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow


@frappe.whitelist()
def get_dd_types():
    """Types de DD actifs pour le wizard — étape 1."""
    return frappe.get_all(
        "DD Type",
        filters={"actif": 1},
        fields=["name", "type_name", "criticite_moyenne", "description_metier"],
        order_by="type_name asc",
    )


@frappe.whitelist()
def get_questions(dd_type):
    """Questions du questionnaire pour un type de DD donné, avec hiérarchie et section label."""
    sections_raw = frappe.get_all(
        "DD Section",
        filters={"dd_type": dd_type},
        fields=["name", "section_label", "ordre"],
    )
    section_map = {s.name: s for s in sections_raw}

    questions = frappe.get_all(
        "DD Question",
        filters={"dd_type": dd_type},
        fields=[
            "name", "question_label", "etape", "field_type",
            "obligatoire", "options", "poids_risque", "valeur_declenchante",
            "question_parente", "demander_document", "label_document",
        ],
        order_by="idx asc",
    )
    for q in questions:
        sec = section_map.get(q.get("etape") or "")
        q["section_label"] = sec.section_label if sec else (q.get("etape") or "Général")
        q["section_ordre"] = int(sec.ordre) if sec and sec.ordre else 0

    return sorted(questions, key=lambda x: (x.get("section_ordre") or 0, x.get("idx") or 0))


@frappe.whitelist()
def get_required_documents(dd_type):
    """Retourne la liste des documents requis pour un type de DD."""
    docs = frappe.get_all(
        "DD Document Requis Template",
        filters={"parent": dd_type, "parenttype": "DD Type"},
        fields=["nom_document", "obligatoire"],
        order_by="idx asc",
    )
    return docs


@frappe.whitelist()
def check_country_risk(country):
    """Évalue le niveau de risque géopolitique/sanctions d'un pays."""
    if not country:
        return {"risk_level": "faible", "reason": ""}

    SANCTIONS_CRITIQUES = {
        "North Korea", "Iran", "Syria", "Russia", "Belarus", "Cuba",
        "Venezuela", "Myanmar", "Sudan", "South Sudan", "Libya",
        "Yemen", "Somalia", "Central African Republic", "Mali",
        "Haiti", "Nicaragua", "Zimbabwe", "Eritrea",
        "Democratic Republic of the Congo",
    }

    FATF_RISQUE_ELEVE = {
        "Afghanistan", "Albania", "Barbados", "Burkina Faso", "Cameroon",
        "Cayman Islands", "Gibraltar", "Jamaica", "Jordan", "Morocco",
        "Mozambique", "Nigeria", "Panama", "Philippines", "Senegal",
        "Tanzania", "Turkey", "Uganda", "Vietnam", "Pakistan",
        "Iraq", "Lebanon", "Ethiopia", "Kenya", "Guinea",
        "Congo", "Guinea-Bissau", "Liberia", "Sierra Leone", "Togo",
    }

    if country in SANCTIONS_CRITIQUES:
        return {
            "risk_level": "critique",
            "reason": f"{country} est soumis à des sanctions internationales critiques (ONU/UE/OFAC).",
            "mesures": [
                "Due Diligence renforcée obligatoire",
                "Validation Compliance senior requise",
                "Revue juridique obligatoire",
                "Validation Direction Générale au-delà des seuils critiques",
                "Screening sanctions approfondi",
                "Documents additionnels exigés",
            ],
        }

    if country in FATF_RISQUE_ELEVE:
        return {
            "risk_level": "eleve",
            "reason": f"{country} figure sur les listes de surveillance FATF ou présente des indicateurs AML/CTF élevés.",
            "mesures": [
                "Due Diligence approfondie requise",
                "Validation Compliance requise",
                "Screening sanctions standard",
            ],
        }

    # Analyse contextuelle via IA pour les pays non couverts par les listes statiques
    try:
        import anthropic
        api_key = frappe.conf.get("anthropic_api_key", "")
        if not api_key:
            return {"risk_level": "faible", "reason": ""}
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    f'Évalue le risque compliance/AML/sanctions du pays "{country}" pour une entreprise africaine.\n'
                    "Réponds UNIQUEMENT avec un JSON valide (pas de markdown) :\n"
                    '{"risk_level":"faible"|"modere"|"eleve"|"critique",'
                    '"reason":"explication max 80 mots en français",'
                    '"mesures":["mesure1","mesure2"]}'
                ),
            }],
        )
        import json as _json
        return _json.loads(message.content[0].text.strip())
    except Exception:
        return {"risk_level": "faible", "reason": ""}


@frappe.whitelist()
def get_dd_draft(dd_name):
    """Charge les données nécessaires au wizard pour compléter un DD existant."""
    doc = frappe.get_doc("DD Request", dd_name)
    if doc.client_user != frappe.session.user:
        frappe.throw(_("Accès non autorisé."), frappe.PermissionError)
    return {
        "dd_type": doc.dd_type or "",
        "tiers_montant_contrat": doc.tiers_montant_contrat or 0,
        "workflow_state": doc.workflow_state or "",
    }


@frappe.whitelist()
def complete_dd_request(dd_name, data):
    """Met à jour un DD existant (partie client : tiers, questionnaire, documents)."""
    if isinstance(data, str):
        data = json.loads(data)

    doc = frappe.get_doc("DD Request", dd_name)
    if doc.client_user != frappe.session.user:
        frappe.throw(_("Accès non autorisé."), frappe.PermissionError)

    tiers_fields = [
        "tiers_nom", "tiers_nom_commercial", "tiers_rccm", "tiers_nif",
        "tiers_forme_juridique", "tiers_date_creation", "tiers_pays",
        "tiers_adresse_siege", "tiers_filiales_internationales", "tiers_appartient_groupe",
        "tiers_secteur", "tiers_description_activites", "tiers_nb_employes",
        "tiers_principaux_clients", "tiers_marches_geographiques", "tiers_secteurs_reglementes",
        "tiers_actionnaires_principaux", "tiers_beneficiaires_effectifs",
        "tiers_beneficiaires_detail", "tiers_structure_actionnariat", "tiers_actionnaires_pep",
        "tiers_pep_detail", "tiers_responsables_publics_participations", "tiers_detenu_etat",
        "tiers_structures_offshore", "tiers_trusts_holdings", "tiers_nature_operations_pays_risque",
        "tiers_flux_financiers_internationaux", "tiers_licences_reglementaires",
        "tiers_relations_entites_publiques_locales", "tiers_risques_sanctions_secondaires",
        "tiers_figure_listes_sanctions", "tiers_paiements_offshore",
    ]
    for field in tiers_fields:
        if field in data:
            setattr(doc, field, data[field])

    doc.tiers_pays_activites = []
    for p in json.loads(data.get("tiers_pays_activites", "[]") or "[]"):
        if p:
            doc.append("tiers_pays_activites", {"pays": p})

    doc.tiers_pays_risque_detecte = int(data.get("tiers_pays_risque_detecte", 0))
    doc.interaction_publique = int(data.get("interaction_publique", 0))
    doc.donnees_personnelles = int(data.get("donnees_personnelles", 0))
    doc.acces_si = int(data.get("acces_si", 0))

    doc.answers = []
    for ans in data.get("answers", []):
        doc.append("answers", {
            "question": ans.get("question"),
            "question_label": ans.get("question_label"),
            "reponse": ans.get("reponse"),
            "poids_applique": int(ans.get("poids_applique", 0)),
        })

    doc.required_documents = []
    for req in data.get("required_documents", []):
        doc.append("required_documents", {
            "nom_document": req.get("nom_document"),
            "obligatoire": int(req.get("obligatoire", 0)),
            "fichier": req.get("fichier", ""),
            "statut": "Reçu" if req.get("fichier") else "Attendu",
        })

    doc.save(ignore_permissions=True)
    apply_workflow(doc, "Soumettre le dossier")
    return {"name": doc.name}


@frappe.whitelist()
def create_dd_request(data):
    """Crée un DD Request depuis le wizard portail et renvoie son nom."""
    if isinstance(data, str):
        data = json.loads(data)

    doc = frappe.new_doc("DD Request")
    doc.update({
        "client_user": frappe.session.user,
        "demandeur_nom": data.get("demandeur_nom", ""),
        "demandeur_fonction": data.get("demandeur_fonction", ""),
        "matricule_interne": data.get("matricule_interne", ""),
        "departement": data.get("departement", ""),
        "pays_rattachement": data.get("pays_rattachement", ""),
        "responsable_hierarchique": data.get("responsable_hierarchique", ""),
        "direction_metier": data.get("direction_metier", ""),
        "email_contact": data.get("email_contact", ""),
        "telephone_professionnel": data.get("telephone_professionnel", ""),
        "niveau_hierarchique": data.get("niveau_hierarchique", ""),
        "dd_type": data.get("dd_type", ""),
        "tiers_nom": data.get("tiers_nom", ""),
        "tiers_nom_commercial": data.get("tiers_nom_commercial", ""),
        "tiers_rccm": data.get("tiers_rccm", ""),
        "tiers_nif": data.get("tiers_nif", ""),
        "tiers_forme_juridique": data.get("tiers_forme_juridique", ""),
        "tiers_date_creation": data.get("tiers_date_creation", ""),
        "tiers_pays": data.get("tiers_pays", ""),
        "tiers_adresse_siege": data.get("tiers_adresse_siege", ""),
        "tiers_pays_activites": [{"pays": p} for p in json.loads(data.get("tiers_pays_activites", "[]") or "[]") if p],
        "tiers_filiales_internationales": data.get("tiers_filiales_internationales", ""),
        "tiers_appartient_groupe": data.get("tiers_appartient_groupe", ""),
        "tiers_secteur": data.get("tiers_secteur", ""),
        "tiers_description_activites": data.get("tiers_description_activites", ""),
        "tiers_nb_employes": data.get("tiers_nb_employes", ""),
        "tiers_montant_contrat": data.get("tiers_montant_contrat") or 0,
        "tiers_principaux_clients": data.get("tiers_principaux_clients", ""),
        "tiers_marches_geographiques": data.get("tiers_marches_geographiques", ""),
        "tiers_secteurs_reglementes": data.get("tiers_secteurs_reglementes", ""),
        "interaction_publique": int(data.get("interaction_publique", 0)),
        "donnees_personnelles": int(data.get("donnees_personnelles", 0)),
        "acces_si": int(data.get("acces_si", 0)),
        "tiers_actionnaires_principaux": data.get("tiers_actionnaires_principaux", ""),
        "tiers_beneficiaires_effectifs": data.get("tiers_beneficiaires_effectifs", ""),
        "tiers_structure_actionnariat": data.get("tiers_structure_actionnariat", ""),
        "tiers_actionnaires_pep": data.get("tiers_actionnaires_pep", ""),
        "tiers_responsables_publics_participations": data.get("tiers_responsables_publics_participations", ""),
        "tiers_detenu_etat": data.get("tiers_detenu_etat", ""),
        "tiers_structures_offshore": data.get("tiers_structures_offshore", ""),
        "tiers_trusts_holdings": data.get("tiers_trusts_holdings", ""),
        "tiers_pays_risque_detecte": int(data.get("tiers_pays_risque_detecte", 0)),
        "tiers_nature_operations_pays_risque": data.get("tiers_nature_operations_pays_risque", ""),
        "tiers_flux_financiers_internationaux": data.get("tiers_flux_financiers_internationaux", ""),
        "tiers_licences_reglementaires": data.get("tiers_licences_reglementaires", ""),
        "tiers_relations_entites_publiques_locales": data.get("tiers_relations_entites_publiques_locales", ""),
        "tiers_risques_sanctions_secondaires": data.get("tiers_risques_sanctions_secondaires", ""),
        "tiers_figure_listes_sanctions": data.get("tiers_figure_listes_sanctions", ""),
        "tiers_paiements_offshore": data.get("tiers_paiements_offshore", ""),
        "relation_description": data.get("relation_description", ""),
        "relation_objectif_metier": data.get("relation_objectif_metier", ""),
        "relation_justification_choix": data.get("relation_justification_choix", ""),
        "relation_strategique": data.get("relation_strategique", ""),
        "relation_strategique_explication": data.get("relation_strategique_explication", ""),
        "relation_strategique_impact": data.get("relation_strategique_impact", ""),
        "relation_dependance_critique": data.get("relation_dependance_critique", ""),
        "relation_urgence": data.get("relation_urgence", ""),
        "relation_urgence_justification": data.get("relation_urgence_justification", ""),
        "relation_urgence_impact_retard": data.get("relation_urgence_impact_retard", ""),
        "relation_procedure_exceptionnelle": data.get("relation_procedure_exceptionnelle", ""),
    })

    for ans in data.get("answers", []):
        doc.append("answers", {
            "question": ans.get("question"),
            "question_label": ans.get("question_label"),
            "reponse": ans.get("reponse"),
            "poids_applique": int(ans.get("poids_applique", 0)),
        })

    for req in data.get("required_documents", []):
        doc.append("required_documents", {
            "nom_document": req.get("nom_document"),
            "obligatoire": int(req.get("obligatoire", 0)),
            "fichier": req.get("fichier", ""),
            "statut": "Reçu" if req.get("fichier") else "Attendu",
        })

    doc.insert(ignore_permissions=True)
    apply_workflow(doc, "Soumettre le dossier")
    return {"name": doc.name}


@frappe.whitelist()
def save_dd_draft(data):
    """Sauvegarde partielle (brouillon) depuis le wizard — sans validation obligatoire."""
    if isinstance(data, str):
        data = json.loads(data)

    doc = frappe.new_doc("DD Request")
    doc.flags.ignore_mandatory = True
    doc.flags.ignore_validate = True

    fields = [
        "dd_type", "demandeur_nom", "demandeur_fonction", "matricule_interne",
        "departement", "pays_rattachement", "responsable_hierarchique",
        "direction_metier", "email_contact", "telephone_professionnel",
        "niveau_hierarchique", "tiers_nom", "tiers_nom_commercial", "tiers_rccm",
        "tiers_nif", "tiers_forme_juridique", "tiers_date_creation", "tiers_pays",
        "tiers_adresse_siege", "tiers_filiales_internationales",
        "tiers_appartient_groupe", "tiers_secteur", "tiers_description_activites",
        "tiers_nb_employes", "tiers_principaux_clients", "tiers_marches_geographiques",
        "tiers_secteurs_reglementes", "tiers_actionnaires_principaux",
        "tiers_beneficiaires_effectifs", "tiers_beneficiaires_detail",
        "tiers_structure_actionnariat", "tiers_actionnaires_pep", "tiers_pep_detail",
        "tiers_responsables_publics_participations", "tiers_detenu_etat",
        "tiers_structures_offshore", "tiers_trusts_holdings",
        "relation_description", "relation_objectif_metier", "relation_justification_choix",
        "relation_strategique", "relation_urgence",
    ]
    for f in fields:
        if data.get(f):
            doc.set(f, data[f])

    doc.set("client_user", frappe.session.user)
    if data.get("tiers_montant_contrat"):
        doc.set("tiers_montant_contrat", data["tiers_montant_contrat"] or 0)
    if data.get("tiers_pays_activites"):
        for p in json.loads(data["tiers_pays_activites"] or "[]"):
            if p:
                doc.append("tiers_pays_activites", {"pays": p})

    doc.insert(ignore_permissions=True)
    return {"name": doc.name}
