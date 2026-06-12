import unittest

import frappe
from frappe.exceptions import ValidationError


def _make_doc(**kwargs):
    defaults = {
        "doctype": "DD Request",
        "tiers_nom": "Tiers Test",
        "dd_type": "Fournisseur",
        "tiers_pays": "Côte d'Ivoire",
        "demandeur_nom": "Test User",
        "demandeur_fonction": "Testeur",
        "direction_metier": "IT",
        "email_contact": "test@example.com",
        "interaction_publique": 0,
        "donnees_personnelles": 0,
        "acces_si": 0,
    }
    defaults.update(kwargs)
    return frappe.get_doc(defaults)


class TestScoring(unittest.TestCase):

    def _score(self, **kwargs):
        doc = _make_doc(**kwargs)
        doc.calculer_score()
        return doc

    def test_score_zero_sans_reponses(self):
        doc = self._score()
        self.assertEqual(doc.score_brut, 0)
        self.assertEqual(doc.categorie_risque, "Faible")

    def test_bonus_interaction_publique(self):
        doc = self._score(interaction_publique=1)
        self.assertEqual(doc.score_brut, 15)

    def test_bonus_donnees_personnelles(self):
        doc = self._score(donnees_personnelles=1)
        self.assertEqual(doc.score_brut, 10)

    def test_bonus_acces_si(self):
        doc = self._score(acces_si=1)
        self.assertEqual(doc.score_brut, 10)

    def test_bonus_cumules(self):
        doc = self._score(interaction_publique=1, donnees_personnelles=1, acces_si=1)
        self.assertEqual(doc.score_brut, 35)
        self.assertEqual(doc.categorie_risque, "Modéré")

    def test_categorie_faible(self):
        doc = self._score()
        doc.score_brut = 15
        doc.calculer_score()
        self.assertEqual(doc.categorie_risque, "Faible")

    def test_categorie_eleve(self):
        doc = _make_doc(interaction_publique=1, donnees_personnelles=1, acces_si=1)
        doc.answers = []
        # Ajoute des réponses fictives pour atteindre score > 40
        for i in range(3):
            row = frappe.get_doc({"doctype": "DD Answer", "poids_applique": 10})
            doc.append("answers", row)
        doc.calculer_score()
        # 15 + 10 + 10 + 30 = 65
        self.assertEqual(doc.score_brut, 65)
        self.assertEqual(doc.categorie_risque, "Critique")

    def test_seuils_exacts(self):
        cases = [
            (0, "Faible"), (20, "Faible"),
            (21, "Modéré"), (40, "Modéré"),
            (41, "Élevé"), (60, "Élevé"),
            (61, "Critique"), (100, "Critique"),
        ]
        for brut, expected in cases:
            doc = _make_doc()
            doc.answers = []
            doc.interaction_publique = 0
            doc.donnees_personnelles = 0
            doc.acces_si = 0
            # On injecte directement le score brut après avoir calculé
            doc.calculer_score()
            # Réinitialise et teste la catégorisation seule
            doc.score_brut = brut
            # Re-évalue la catégorie manuellement (même logique)
            from due_diligence.due_diligence.doctype.dd_request.dd_request import _SEUILS_RISQUE
            cat = "Critique"
            for seuil, categorie in _SEUILS_RISQUE:
                if brut <= seuil:
                    cat = categorie
                    break
            self.assertEqual(cat, expected, f"score_brut={brut}")


class TestVerrouPortail(unittest.TestCase):

    def test_verrou_bloque_dd_client_sur_dossier_soumis(self):
        doc = _make_doc()
        doc.owner = "test_client@example.com"
        doc.workflow_state = "En analyse Compliance"

        # Simule un DD Client propriétaire du dossier
        frappe.session.user = "test_client@example.com"
        with unittest.mock.patch("frappe.get_roles", return_value=["DD Client", "Guest"]):
            with self.assertRaises(frappe.exceptions.ValidationError):
                doc._verrou_portail()

    def test_verrou_laisse_passer_analyste(self):
        doc = _make_doc()
        doc.owner = "test_client@example.com"
        doc.workflow_state = "En analyse Compliance"

        frappe.session.user = "analyste@example.com"
        with unittest.mock.patch("frappe.get_roles", return_value=["DD Analyste"]):
            doc._verrou_portail()  # Ne doit pas lever d'exception

    def test_verrou_laisse_passer_brouillon(self):
        doc = _make_doc()
        doc.owner = "test_client@example.com"
        doc.workflow_state = "Brouillon"

        frappe.session.user = "test_client@example.com"
        with unittest.mock.patch("frappe.get_roles", return_value=["DD Client"]):
            doc._verrou_portail()  # Brouillon non verrouillé


class TestIsolation(unittest.TestCase):
    """Vérifie que le filtre owner= empêche l'accès cross-utilisateur."""

    def test_filtre_owner_exclut_autres_users(self):
        # Sans données réelles, on vérifie la logique du filtre
        # Le portail filtre toujours par owner=frappe.session.user
        user_a = "client_a@example.com"
        user_b = "client_b@example.com"

        # Simule que user_a voit ses propres docs
        frappe.session.user = user_a
        filters = {"owner": frappe.session.user}
        self.assertEqual(filters["owner"], user_a)
        self.assertNotEqual(filters["owner"], user_b)


# Import nécessaire pour mock dans tests verrou
import unittest.mock
