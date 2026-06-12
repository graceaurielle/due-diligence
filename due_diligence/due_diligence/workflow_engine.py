"""
Moteur de workflow dynamique — circuits, étapes, SLA, escalade.
App due_diligence | spec §§3-12
"""
import frappe
from frappe.utils import add_days, now_datetime

# ── Identifiants de circuits ──────────────────────────────────────────────────
CIRCUIT_FAIBLE   = "Faible"
CIRCUIT_MODERE   = "Modéré"
CIRCUIT_ELEVE    = "Élevé"
CIRCUIT_CRITIQUE = "Critique"
CIRCUIT_INTERDIT = "Interdit"

# ── Pays sensibles (miroir de dd_request.py — spec §1) ───────────────────────
_PAYS_SANCTIONS = frozenset({
	"North Korea", "Iran", "Syria", "Russia", "Belarus", "Cuba",
	"Venezuela", "Myanmar", "Sudan", "South Sudan", "Libya",
	"Yemen", "Somalia", "Central African Republic", "Mali",
	"Haiti", "Nicaragua", "Zimbabwe", "Eritrea",
	"Democratic Republic of the Congo",
})
_PAYS_CORRUPTION = frozenset({
	"Afghanistan", "Nigeria", "Iraq", "Pakistan", "Congo",
	"Guinea-Bissau", "Liberia", "Sierra Leone", "Togo", "Cameroon",
	"Ethiopia", "Kenya", "Guinea", "Lebanon", "Burkina Faso",
	"Uganda", "Tanzania", "Mozambique", "Morocco", "Vietnam",
	"Philippines", "Panama", "Jordan", "Albania", "Barbados",
	"Cayman Islands", "Gibraltar", "Jamaica", "Senegal", "Turkey",
})

# ── SLA par circuit (jours calendaires) ──────────────────────────────────────
_SLA_JOURS = {
	CIRCUIT_FAIBLE:   2,
	CIRCUIT_MODERE:   5,
	CIRCUIT_ELEVE:    10,
	CIRCUIT_CRITIQUE: 15,
	CIRCUIT_INTERDIT: 0,  # blocage immédiat
}

# ── Étapes de base par circuit — (ordre, libellé, rôle, obligatoire) ─────────
_ETAPES_BASE = {
	CIRCUIT_FAIBLE: [
		(1, "Vérification de complétude",        "DD Analyste",           True),
		(2, "Screening réglementaire standard",  "DD Analyste",           True),
		(3, "Validation manager métier",         "DD Manager Metier",     True),
		(4, "Validation Compliance simplifiée",  "DD Analyste",           True),
		(5, "Activation surveillance standard",  "DD Analyste",           True),
	],
	CIRCUIT_MODERE: [
		(1, "Préqualification automatique",      "DD Analyste",           True),
		(2, "Contrôle documentaire renforcé",    "DD Analyste",           True),
		(3, "Screening sanctions et PEP",        "DD Analyste",           True),
		(4, "Revue Compliance",                  "DD Analyste",           True),
		(5, "Validation manager métier",         "DD Manager Metier",     True),
		(6, "Validation Compliance",             "DD Manager Compliance", True),
		(7, "Contrôle financier",                "DD Financier",          True),
		(8, "Décision finale",                   "DD Manager Compliance", True),
	],
	CIRCUIT_ELEVE: [
		(1,  "Préqualification renforcée",       "DD Analyste",           True),
		(2,  "Screening sanctions approfondi",   "DD Analyste",           True),
		(3,  "Contrôle bénéficiaire effectif",   "DD Analyste",           True),
		(4,  "Revue anti-corruption",            "DD Analyste",           True),
		(5,  "Analyse réputationnelle IA",       "DD Analyste",           True),
		(6,  "Revue financière avancée",         "DD Financier",          True),
		(7,  "Revue cybersécurité",              "DD RSSI",               True),
		(8,  "Validation juridique",             "DD Juridique",          True),
		(9,  "Validation Compliance Manager",    "DD Manager Compliance", True),
		(10, "Validation CCO",                   "DD CCO",                True),
		(11, "Décision finale",                  "DD CCO",                True),
	],
	CIRCUIT_CRITIQUE: [
		(1,  "Escalade Compliance senior",       "DD Manager Compliance", True),
		(2,  "Screening sanctions avancé",       "DD Analyste",           True),
		(3,  "Revue juridique obligatoire",      "DD Juridique",          True),
		(4,  "Revue financière approfondie",     "DD Financier",          True),
		(5,  "Revue cybersécurité senior",       "DD RSSI",               True),
		(6,  "Revue DPO",                        "DD DPO",                True),
		(7,  "Comité conformité",                "DD Manager Compliance", True),
		(8,  "Validation CCO",                   "DD CCO",                True),
		(9,  "Validation Direction Générale",    "DD DG",                 True),
		(10, "Décision finale motivée",          "DD DG",                 True),
	],
	CIRCUIT_INTERDIT: [
		(1, "Blocage immédiat",                  "DD Manager Compliance", True),
		(2, "Alerte Compliance",                 "DD Manager Compliance", True),
		(3, "Notification Direction Juridique",  "DD Juridique",          True),
		(4, "Gel du dossier",                    "DD CCO",                True),
		(5, "Création rapport d'incident",       "DD Manager Compliance", True),
	],
}

# ── Étapes supplémentaires par type de tiers — (ordre float, …) ───────────────
# La clé est une sous-chaîne (insensible à la casse) du label du DD Type.
_ETAPES_TYPE = {
	"sous-traitant si": [
		(2.1, "Revue RSSI",              "DD RSSI",    True),
		(2.2, "Audit cybersécurité",     "DD RSSI",    True),
		(2.3, "Revue IAM",               "DD RSSI",    True),
		(2.4, "Validation IT",           "DD RSSI",    True),
	],
	"intermédiaire": [
		(2.1, "Revue anticorruption",    "DD Analyste",           True),
		(2.2, "Screening PEP",           "DD Analyste",           True),
		(5.1, "Validation CCO",          "DD CCO",                True),
	],
	"consultant gouvernemental": [
		(3.1, "Validation juridique",    "DD Juridique",          True),
		(8.1, "Validation DG",           "DD DG",                 True),
	],
	"partenaire cloud": [
		(2.1, "Revue DPO",               "DD DPO",                True),
		(2.2, "Revue RSSI",              "DD RSSI",               True),
		(2.3, "Validation architecture", "DD RSSI",               True),
	],
	"cible m&a": [
		(3.1, "Audit financier",         "DD Financier",          True),
		(4.1, "Audit juridique",         "DD Juridique",          True),
		(5.1, "Audit cybersécurité",     "DD RSSI",               True),
		(5.2, "Audit ESG",               "DD Analyste",           True),
		(5.3, "Audit réputationnel",     "DD Analyste",           True),
	],
}

# ── Documents obligatoires par circuit (spec §11) ─────────────────────────────
_DOCS_CIRCUIT = {
	CIRCUIT_MODERE: [
		"Attestation fiscale", "États financiers",
		"Références commerciales", "Attestation bancaire",
	],
	CIRCUIT_ELEVE: [
		"Politique anticorruption", "Registre UBO",
		"Organigramme capitalistique", "Audit cybersécurité",
		"ISO 27001", "DPA", "PRA/PCA", "États financiers certifiés",
	],
	CIRCUIT_CRITIQUE: [
		"Politique anticorruption", "Registre UBO",
		"Organigramme capitalistique", "Audit cybersécurité",
		"ISO 27001", "DPA", "PRA/PCA", "États financiers certifiés",
		"Rapport d'audit senior", "Déclaration bénéficiaires effectifs",
	],
}

# ── Rôles d'escalade par niveau (0 = base, 3 = DG) ───────────────────────────
_ROLES_ESCALADE = [
	"DD Manager Metier",     # niveau 1
	"DD Manager Compliance", # niveau 2
	"DD CCO",                # niveau 3
	"DD DG",                 # niveau 4
]

# ── Statuts terminaux (pas d'escalade SLA) ────────────────────────────────────
_STATUTS_CLOS = frozenset({
	"Clôturé — GO", "Clôturé — NO GO", "Clôturé — GO sous réserve",
	"Rejeté", "Accepté", "Accepté sous réserve", "Clôturé",
	"Sous surveillance continue",
})


# ── API publique ──────────────────────────────────────────────────────────────

def determiner_circuit(doc):
	"""Retourne le circuit de traitement adapté au profil du dossier (spec §§3-7)."""
	from frappe.utils import flt
	score   = int(doc.score_residuel or 0)
	pays    = doc.tiers_pays or ""
	montant = flt(doc.tiers_montant_contrat or 0)

	# Interdit — blocage absolu
	if (
		getattr(doc, "tiers_figure_listes_sanctions", "") == "Oui"
		or pays in _PAYS_SANCTIONS
		or score >= 81
	):
		return CIRCUIT_INTERDIT

	# Critique
	if (
		score >= 61
		or (getattr(doc, "tiers_actionnaires_pep", "") == "Oui" and pays in _PAYS_CORRUPTION)
		or (getattr(doc, "tiers_incident_cyber", False) and getattr(doc, "acces_si", False))
		or (getattr(doc, "tiers_donnees_biometriques", False) and getattr(doc, "donnees_personnelles", False))
		or montant >= 100_000_000
	):
		return CIRCUIT_CRITIQUE

	# Élevé
	if (
		score >= 41
		or pays in _PAYS_CORRUPTION
		or getattr(doc, "acces_si", False)
		or montant >= 25_000_000
		or getattr(doc, "tiers_structures_offshore", "") == "Oui"
		or getattr(doc, "interaction_publique", False)
	):
		return CIRCUIT_ELEVE

	# Modéré
	if (
		score >= 21
		or montant >= 5_000_000
		or getattr(doc, "tiers_paiements_offshore", "") == "Oui"
		or getattr(doc, "donnees_personnelles", False)
	):
		return CIRCUIT_MODERE

	return CIRCUIT_FAIBLE


def generer_etapes(circuit, type_tiers_label=None):
	"""Retourne la liste triée des dicts d'étapes pour un circuit + type de tiers."""
	base = list(_ETAPES_BASE.get(circuit, []))

	# Étapes spécifiques au type de tiers (lookup insensible à la casse)
	label_lower = (type_tiers_label or "").lower()
	for cle, etapes_sup in _ETAPES_TYPE.items():
		if cle in label_lower:
			base.extend(etapes_sup)
			break

	base.sort(key=lambda x: x[0])

	return [
		{
			"ordre":           i + 1,
			"etape":           x[1],
			"role_validateur": x[2],
			"obligatoire":     1 if x[3] else 0,
			"statut":          "En attente",
		}
		for i, x in enumerate(base)
	]


def calculer_date_sla(circuit):
	"""Retourne la date d'échéance SLA (maintenant + N jours)."""
	jours = _SLA_JOURS.get(circuit, 5)
	if jours == 0:
		return now_datetime()
	return add_days(now_datetime(), jours)


def get_docs_requis_circuit(circuit):
	"""Documents obligatoires pour ce circuit (spec §11)."""
	return _DOCS_CIRCUIT.get(circuit, [])


def escalader(dd_request_name):
	"""Monte d'un niveau d'escalade, notifie le responsable et journalise."""
	doc = frappe.get_doc("DD Request", dd_request_name)
	niveau_actuel = int(doc.niveau_escalade or 0)

	if niveau_actuel >= len(_ROLES_ESCALADE):
		return  # niveau max atteint

	nouveau_niveau = niveau_actuel + 1
	role_cible = _ROLES_ESCALADE[nouveau_niveau - 1]

	frappe.db.set_value("DD Request", dd_request_name, {
		"niveau_escalade": nouveau_niveau,
		"sla_depasse": 1,
	})

	# Notification email
	destinataires = _emails_role(role_cible)
	if destinataires:
		try:
			frappe.sendmail(
				recipients=destinataires,
				subject=f"[ESCALADE DD N{nouveau_niveau}] {dd_request_name} — SLA dépassé",
				message=(
					f"<p>Le dossier <b>{dd_request_name}</b> dépasse son délai de traitement.</p>"
					f"<table style='border-collapse:collapse;width:100%;margin:12px 0;'>"
					f"<tr><td style='padding:6px 10px;font-weight:600;color:#64748b;width:35%;'>Tiers</td>"
					f"<td style='padding:6px 10px;'>{doc.tiers_nom or '—'}</td></tr>"
					f"<tr><td style='padding:6px 10px;font-weight:600;color:#64748b;'>Circuit</td>"
					f"<td style='padding:6px 10px;'>{doc.circuit_workflow or '—'}</td></tr>"
					f"<tr><td style='padding:6px 10px;font-weight:600;color:#64748b;'>Score résiduel</td>"
					f"<td style='padding:6px 10px;font-weight:700;'>{doc.score_residuel or 0} / 100</td></tr>"
					f"<tr><td style='padding:6px 10px;font-weight:600;color:#64748b;'>Niveau escalade</td>"
					f"<td style='padding:6px 10px;'>{nouveau_niveau} / {len(_ROLES_ESCALADE)}</td></tr>"
					f"</table>"
					f"<p><a href='{frappe.utils.get_url()}/app/dd-request/{dd_request_name}' "
					f"style='background:#0d1b2a;color:#fff;padding:10px 20px;border-radius:6px;"
					f"text-decoration:none;font-weight:600;'>Ouvrir le dossier</a></p>"
				),
				now=True,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"DD — escalade notification {dd_request_name}")

	# Journalisation
	_journaliser(
		dd_request_name,
		f"Escalade N{nouveau_niveau}",
		f"SLA dépassé — escalade automatique vers rôle : {role_cible}",
		declencheur="Planificateur SLA",
	)
	frappe.db.commit()


def _journaliser(dd_request_name, type_evenement, description, ancien_statut="", nouveau_statut="", declencheur=""):
	"""Insère un événement dans le journal du dossier (safe hors transaction principale)."""
	try:
		frappe.get_doc({
			"doctype": "DD Workflow Event",
			"parent": dd_request_name,
			"parenttype": "DD Request",
			"parentfield": "workflow_events",
			"date_evenement": now_datetime(),
			"type_evenement": type_evenement,
			"description": (description or "")[:500],
			"utilisateur": frappe.session.user,
			"ancien_statut": ancien_statut or "",
			"nouveau_statut": nouveau_statut or "",
			"declencheur": declencheur or "",
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "DD — journalisation workflow")


def _emails_role(role):
	users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
	if not users:
		return []
	return frappe.get_all("User", filters={"name": ["in", users], "enabled": 1}, pluck="email")
