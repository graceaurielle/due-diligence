import frappe
from frappe.model.document import Document
from frappe.utils import add_months


class DDAvisCompliance(Document):

	def validate(self):
		self._remplir_depuis_dossier()
		self._calculer_expiration()

	def _remplir_depuis_dossier(self):
		if not self.dd_request:
			return
		dossier = frappe.get_doc("DD Request", self.dd_request, ignore_permissions=True)
		self.score_final = dossier.score_pondere or dossier.score_brut or 0
		self.categorie_risque = dossier.categorie_risque
		self.date_soumission = dossier.creation.date() if dossier.creation else None

	def _calculer_expiration(self):
		if self.date_decision and self.validite_avis:
			self.date_expiration = add_months(self.date_decision, self.validite_avis)

	def on_submit(self):
		self.db_set("date_validation", frappe.utils.now(), update_modified=False)
		self._mettre_a_jour_dossier()
		self._notifier_client()

	def _mettre_a_jour_dossier(self):
		frappe.db.set_value("DD Request", self.dd_request, {
			"decision_finale": self.decision,
			"reserves": self.reserves or "",
			"date_decision": self.date_decision,
		})

	def _notifier_client(self):
		dossier = frappe.get_doc("DD Request", self.dd_request, ignore_permissions=True)
		destinataire = dossier.email_contact or (
			frappe.db.get_value("User", dossier.client_user, "email")
			if dossier.client_user else None
		)
		if not destinataire:
			return
		try:
			frappe.sendmail(
				recipients=[destinataire],
				subject=f"[AMOAMAN] Avis Due Diligence disponible — {self.dd_request}",
				message=(
					f"Madame, Monsieur,<br><br>"
					f"L'avis de Due Diligence concernant <strong>{self.tiers_nom}</strong> "
					f"est désormais disponible sur votre espace client.<br><br>"
					f"Décision : <strong>{self.decision}</strong><br><br>"
					f"Vous pouvez consulter l'avis complet en vous connectant à votre espace : "
					f'<a href="/suivi?name={self.dd_request}">Accéder à mon dossier</a><br><br>'
					f"Cabinet AMOAMAN &amp; Associés"
				),
				now=True,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "DD Avis Compliance — erreur notification client")
