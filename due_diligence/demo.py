"""
Données de démonstration — AMOAMAN & ASSOCIÉS Due Diligence
Usage : bench --site compliance execute due_diligence.demo.seed
"""
import frappe
from frappe.utils import now_datetime


DEMO_EMAIL = "demo.client@amoaman.ci"
DEMO_PASSWORD = "Demo@2026!"


def seed():
    frappe.set_user("Administrator")
    _create_demo_user()
    _create_requests()
    frappe.db.commit()
    print("✓ Données démo créées avec succès.")
    print(f"  Connexion : {DEMO_EMAIL} / {DEMO_PASSWORD}")


def _create_demo_user():
    if frappe.db.exists("User", DEMO_EMAIL):
        return
    user = frappe.get_doc({
        "doctype": "User",
        "email": DEMO_EMAIL,
        "first_name": "Marie",
        "last_name": "Kouassi",
        "full_name": "Marie Kouassi",
        "enabled": 1,
        "new_password": DEMO_PASSWORD,
        "send_welcome_email": 0,
        "roles": [{"role": "DD Client"}],
    })
    user.insert(ignore_permissions=True)
    print(f"  ✓ Utilisateur démo créé : {DEMO_EMAIL}")


def _make_request(data):
    if frappe.db.exists("DD Request", {"tiers_nom": data["tiers_nom"], "owner": DEMO_EMAIL}):
        print(f"  – DD Request '{data['tiers_nom']}' déjà existant, ignoré.")
        return
    doc = frappe.get_doc({"doctype": "DD Request", **data})
    doc.owner = DEMO_EMAIL
    doc.insert(ignore_permissions=True)
    if data.get("_workflow_state"):
        doc.db_set("workflow_state", data["_workflow_state"], update_modified=False)
    if data.get("_decision"):
        doc.db_set("decision_finale", data["_decision"], update_modified=False)
        doc.db_set("date_decision", now_datetime(), update_modified=False)
    if data.get("_docstatus"):
        doc.db_set("docstatus", data["_docstatus"], update_modified=False)
    print(f"  ✓ DD Request créé : {doc.name} — {data['tiers_nom']}")


def _create_requests():
    _make_request({
        "tiers_nom": "TechnoSoft SARL",
        "dd_type": "Fournisseur",
        "tiers_pays": "Ivory Coast",
        "tiers_secteur": "Technologies de l'information",
        "tiers_montant_contrat": 45000000,
        "demandeur_nom": "Marie Kouassi",
        "demandeur_fonction": "Responsable Achats",
        "direction_metier": "Direction des Systèmes d'Information",
        "email_contact": DEMO_EMAIL,
        "interaction_publique": 0,
        "donnees_personnelles": 1,
        "acces_si": 1,
        "_workflow_state": "En analyse Compliance",
        "_docstatus": 1,
    })

    _make_request({
        "tiers_nom": "BTP Groupe Ivoire",
        "dd_type": "Sous-traitant",
        "tiers_pays": "Ivory Coast",
        "tiers_secteur": "BTP / Construction",
        "tiers_montant_contrat": 120000000,
        "demandeur_nom": "Marie Kouassi",
        "demandeur_fonction": "Responsable Achats",
        "direction_metier": "Direction Immobilière",
        "email_contact": DEMO_EMAIL,
        "interaction_publique": 1,
        "donnees_personnelles": 0,
        "acces_si": 0,
        "_workflow_state": "Clôturé — GO",
        "_decision": "GO",
        "_docstatus": 1,
    })

    _make_request({
        "tiers_nom": "Conseil & Stratégie CI",
        "dd_type": "Consultant",
        "tiers_pays": "France",
        "tiers_secteur": "Conseil / Management",
        "tiers_montant_contrat": 18000000,
        "demandeur_nom": "Marie Kouassi",
        "demandeur_fonction": "Responsable Achats",
        "direction_metier": "Direction Générale",
        "email_contact": DEMO_EMAIL,
        "interaction_publique": 1,
        "donnees_personnelles": 1,
        "acces_si": 0,
        "_workflow_state": "En attente de documents",
        "_docstatus": 1,
    })


def teardown():
    """Supprime toutes les données démo — usage tests CI uniquement."""
    frappe.set_user("Administrator")
    docs = frappe.get_all("DD Request", filters={"owner": DEMO_EMAIL}, pluck="name")
    for name in docs:
        frappe.db.set_value("DD Request", name, "docstatus", 2)
        frappe.delete_doc("DD Request", name, ignore_permissions=True, force=True)
    if frappe.db.exists("User", DEMO_EMAIL):
        frappe.delete_doc("User", DEMO_EMAIL, ignore_permissions=True)
    frappe.db.commit()
    print("✓ Données démo supprimées.")
