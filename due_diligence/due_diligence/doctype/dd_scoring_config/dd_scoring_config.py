import frappe
from frappe import _
from frappe.model.document import Document


class DDScoringConfig(Document):

    def validate(self):
        self._verifier_poids()
        self._verifier_seuils()
        self._calculer_total()

    def _verifier_poids(self):
        total = (
            (self.poids_geo or 0) + (self.poids_corruption or 0) +
            (self.poids_financier or 0) + (self.poids_reputationnel or 0) +
            (self.poids_cyber or 0) + (self.poids_donnees or 0) +
            (self.poids_documentaire or 0)
        )
        if abs(total - 100) > 0.01:
            frappe.throw(
                _("La somme des poids doit être égale à 100 %. Valeur actuelle : {0:.2f} %").format(total),
                title=_("Poids invalides"),
            )

    def _verifier_seuils(self):
        seuils = [self.seuil_faible, self.seuil_modere, self.seuil_eleve, self.seuil_critique]
        for i in range(len(seuils) - 1):
            if seuils[i] >= seuils[i + 1]:
                frappe.throw(
                    _("Les seuils doivent être strictement croissants."),
                    title=_("Seuils invalides"),
                )
        if self.seuil_critique >= 100:
            frappe.throw(
                _("Le seuil Critique doit être inférieur à 100 (la catégorie Interdit couvre le reste)."),
                title=_("Seuils invalides"),
            )

    def _calculer_total(self):
        self.total_poids = round(
            (self.poids_geo or 0) + (self.poids_corruption or 0) +
            (self.poids_financier or 0) + (self.poids_reputationnel or 0) +
            (self.poids_cyber or 0) + (self.poids_donnees or 0) +
            (self.poids_documentaire or 0), 2
        )
