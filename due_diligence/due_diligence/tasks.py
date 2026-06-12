"""Tâches planifiées Due Diligence."""
import frappe
from frappe.utils import now_datetime

from due_diligence.due_diligence.workflow_engine import _STATUTS_CLOS, escalader


def verifier_sla_workflows():
	"""Vérifie les SLA dépassés et déclenche les escalades (toutes les 4h)."""
	dossiers = frappe.get_all(
		"DD Request",
		filters={
			"docstatus": 1,
			"date_echeance_sla": ["<", now_datetime()],
			"sla_depasse": 0,
			"circuit_workflow": ["not in", ["Interdit", ""]],
			"workflow_state": ["not in", list(_STATUTS_CLOS)],
		},
		pluck="name",
	)

	for name in dossiers:
		try:
			escalader(name)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"DD — escalade SLA {name}")
