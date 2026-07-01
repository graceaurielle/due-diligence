import hashlib

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

# États dans lesquels le demandeur ne peut plus modifier son dossier
_ETATS_VERROUS = frozenset({
	"Soumis", "En préqualification", "En screening réglementaire",
	"En analyse Compliance", "En analyse financière",
	"En revue juridique", "En revue cybersécurité", "En revue DPO",
	"En attente de documents", "En attente validation métier",
	"En attente validation Manager", "En attente validation Compliance",
	"En attente validation CCO", "En attente validation DG",
	"En validation Manager", "En validation Direction",
	"Escaladé", "Suspendu",
	"Clôturé — GO", "Clôturé — NO GO", "Clôturé — GO sous réserve",
	"Rejeté", "Accepté", "Accepté sous réserve",
	"Clôturé", "Sous surveillance continue",
})

# ── Axe géographique ──────────────────────────────────────────────────────────
# Synchroniser avec SANCTIONS_CRITIQUES / FATF_RISQUE_ELEVE dans api.py

_PAYS_SANCTIONS_CRITIQUES = frozenset({
	"North Korea", "Iran", "Syria", "Russia", "Belarus", "Cuba",
	"Venezuela", "Myanmar", "Sudan", "South Sudan", "Libya",
	"Yemen", "Somalia", "Central African Republic", "Mali",
	"Haiti", "Nicaragua", "Zimbabwe", "Eritrea",
	"Democratic Republic of the Congo",
})  # → ax_geo = 100

_PAYS_CORRUPTION_ELEVE = frozenset({
	"Afghanistan", "Nigeria", "Iraq", "Pakistan", "Congo",
	"Guinea-Bissau", "Liberia", "Sierra Leone", "Togo", "Cameroon",
	"Ethiopia", "Kenya", "Guinea", "Lebanon", "Burkina Faso",
	"Uganda", "Tanzania", "Mozambique", "Morocco", "Vietnam",
	"Philippines", "Panama", "Jordan", "Albania", "Barbados",
	"Cayman Islands", "Gibraltar", "Jamaica", "Senegal", "Turkey",
})  # → ax_geo = 60

_PAYS_SURVEILLANCE = frozenset({
	"Chad", "Niger", "Rwanda", "Bangladesh", "Indonesia",
	"Guatemala", "Honduras", "El Salvador", "Bolivia", "Ivory Coast",
})  # → ax_geo = 30

# ── Axe type de tiers (inclus dans axe corruption) ────────────────────────────
_SCORE_TYPE_TIERS = {"Faible": 5, "Modéré": 20, "Élevé": 35, "Critique": 50}

# ── Poids de la formule finale — spec §14 ─────────────────────────────────────
# Pays 20% | Corruption 25% | Financier 15% | Réputation 15%
# Cyber 10% | Données 10% | Documentaire 5%
_POIDS_AXES = {
	"geo":           0.20,
	"corruption":    0.25,
	"financier":     0.15,
	"reputationnel": 0.15,
	"cyber":         0.10,
	"donnees":       0.10,
	"documentaire":  0.05,
}

# Maxima bruts par axe (normalisation 0-100)
_MAX_CORRUPTION   = 120  # calibré "3 flags graves + type élevé"
_MAX_CYBER        = 90   # SI(25) + MFA(20) + PRA(15) + incident(30)
_MAX_DONNEES      = 110  # perso(40) + bio(25) + RGPD(30) + DPO(15)
_MAX_DOCUMENTAIRE = 60   # 4 docs manquants × 15

# Poids redistribués quand l'axe réputationnel n'est pas encore calculé
# (somme des 6 autres axes = 0.85 → chaque poids divisé par 0.85 → somme = 1.0)
_POIDS_P1 = {k: v / 0.85 for k, v in _POIDS_AXES.items() if k != "reputationnel"}

# ── Seuils score résiduel 0-100 → catégorie (spec §15) ────────────────────────
_SEUILS_RISQUE = [(20, "Faible"), (40, "Modéré"), (60, "Élevé"), (80, "Critique")]
# > 80 → "Interdit"

# ── Atténuants (spec §14) ─────────────────────────────────────────────────────
_ATTENUANTS = [
	("tiers_certif_iso27001",  15, "ISO 27001"),
	("tiers_certif_iso37001",  20, "ISO 37001"),
	("tiers_audit_big4",       10, "Audit Big Four"),
	("tiers_garantie_bancaire", 10, "Garantie bancaire"),
	("tiers_etats_certifies",  15, "États financiers certifiés"),
	("tiers_solvabilite_forte", 20, "Solvabilité forte"),
]


class DDRequest(Document):

	def before_insert(self):
		if not self.client_user and "DD Client" in frappe.get_roles():
			self.client_user = frappe.session.user

	def before_submit(self):
		self._valider_champs_client()

	def _valider_champs_client(self):
		champs_requis = [
			("tiers_nom",                              "Raison sociale complète"),
			("tiers_rccm",                             "RCCM / Registre de commerce"),
			("tiers_nif",                              "Numéro d'identification fiscale (NIF)"),
			("tiers_forme_juridique",                  "Forme juridique"),
			("tiers_adresse_siege",                    "Adresse du siège social"),
			("tiers_filiales_internationales",         "Le tiers dispose-t-il de filiales internationales ?"),
			("tiers_appartient_groupe",                "Le tiers appartient-il à un groupe international ?"),
			("tiers_description_activites",            "Description des activités opérationnelles"),
			("tiers_secteurs_reglementes",             "Le tiers intervient-il dans des secteurs réglementés ?"),
			("tiers_actionnaires_principaux",          "Actionnaires principaux"),
			("tiers_beneficiaires_effectifs",          "Bénéficiaires effectifs identifiés"),
			("tiers_actionnaires_pep",                 "Actionnaires politiquement exposés (PEP) ?"),
			("tiers_responsables_publics_participations", "Des responsables publics détiennent-ils des participations ?"),
			("tiers_detenu_etat",                      "Le tiers est-il détenu partiellement ou totalement par un État ?"),
			("tiers_structures_offshore",              "Structures offshore dans l'actionnariat ?"),
			("tiers_trusts_holdings",                  "Trusts, holdings ou structures complexes ?"),
		]
		manquants = [label for field, label in champs_requis if not self.get(field)]
		if manquants:
			frappe.throw(
				_("Le client n'a pas encore rempli tous les champs obligatoires :<br>")
				+ "<br>".join(f"• {l}" for l in manquants),
				title=_("Dossier incomplet"),
			)

	def validate(self):
		self._verrou_portail()
		self.calculer_score()

	def on_update(self):
		self._hash_documents()
		self._analyser_documents_ia()
		self._horodater_decision()
		self._alerter_categorie_critique()
		self._recalculer_circuit_si_changement()
		self._alerter_ecart_score()
		self._notifier_prochain_acteur()

	def on_submit(self):
		self._assigner_analyste()
		self._notifier_soumission()
		self._initialiser_workflow()
		self._generer_avis_ia_auto()

	# ------------------------------------------------------------------
	# 4.8d  Contrôle séquentiel des étapes workflow
	# ------------------------------------------------------------------
	def before_workflow_action(self, action):
		"""Bloque l'action si l'étape précédente n'est pas encore complétée par le bon rôle,
		puis valide automatiquement la première étape disponible pour le rôle courant."""
		_ACTIONS_LIBRES = {"Soumettre le dossier", "Suspendre le dossier", "Reprendre le dossier"}
		if action in _ACTIONS_LIBRES:
			return

		steps = frappe.get_all(
			"DD Workflow Step",
			filters={"parent": self.name, "parenttype": "DD Request"},
			fields=["name", "ordre", "etape", "role_validateur", "statut", "obligatoire"],
			order_by="ordre asc",
		)
		if not steps:
			return

		roles_courants = set(frappe.get_roles())
		if "System Manager" in roles_courants:
			return

		etapes_obligatoires = [s for s in steps if s.obligatoire]
		premiere_en_attente = next(
			(s for s in etapes_obligatoires if s.statut == "En attente"), None
		)
		if premiere_en_attente and premiere_en_attente.role_validateur not in roles_courants:
			frappe.throw(
				_(
					"L'étape <b>{0}</b> (rôle requis : {1}) doit être complétée "
					"avant de pouvoir prendre cette action."
				).format(premiere_en_attente.etape, premiere_en_attente.role_validateur),
				title=_("Étape précédente non complétée"),
			)

		# Valider automatiquement la première étape En attente du rôle courant
		premiere_role = next(
			(s for s in etapes_obligatoires
			 if s.statut == "En attente" and s.role_validateur in roles_courants),
			None,
		)

		# Accès exclusif : seul l'analyste assigné peut intervenir à l'étape analyste
		_ROLES_SURPASSANTS = {"DD Manager Compliance", "DD CCO", "DD DG", "System Manager"}
		if premiere_role and self.analyste_assigne:
			if premiere_role.role_validateur == "DD Analyste":
				if frappe.session.user != self.analyste_assigne:
					if not (roles_courants & _ROLES_SURPASSANTS):
						frappe.throw(
							_(
								"Ce dossier est assigné à l'analyste <b>{0}</b>. "
								"Seul cet analyste (ou un Manager/Administrateur) peut y intervenir."
							).format(self.analyste_assigne),
							title=_("Accès exclusif"),
						)

		if premiere_role:
			frappe.db.set_value("DD Workflow Step", premiere_role.name, {
				"statut":          "Validé",
				"validateur":      frappe.session.user,
				"date_validation": now_datetime(),
			})
			from due_diligence.due_diligence.workflow_engine import _journaliser
			_journaliser(
				self.name,
				"Étape validée",
				f"Étape « {premiere_role.etape} » validée par {frappe.session.user} "
				f"— action : {action}",
				declencheur=action,
			)

	# ------------------------------------------------------------------
	# 4.1  Verrou portail — DD Client bloqué dès que le dossier est soumis
	# ------------------------------------------------------------------
	def _verrou_portail(self):
		# Vérifie l'état AVANT la sauvegarde pour ne pas bloquer la transition initiale
		doc_before = self.get_doc_before_save()
		previous_state = (doc_before.workflow_state if doc_before else None) or "Brouillon"
		if previous_state not in _ETATS_VERROUS:
			return
		if frappe.session.user == self.client_user and "DD Client" in frappe.get_roles():
			frappe.throw(
				_("Ce dossier est en cours de traitement et ne peut plus être modifié par le demandeur."),
				title=_("Dossier verrouillé"),
			)

	# ------------------------------------------------------------------
	# 4.2  Moteur de scoring — 7 axes pondérés (spec §14)
	# ------------------------------------------------------------------
	def calculer_score(self):
		import json as _json

		# ── Config dynamique (Phase 3) — poids/seuils paramétrables ──
		poids, seuils_risque = _charger_config_scoring()
		poids_p1 = {k: v / (1 - poids.get("reputationnel", 0.15))
		            for k, v in poids.items() if k != "reputationnel"}

		aggravants = []

		# ── AXE GÉOGRAPHIQUE [20%] ────────────────────────────────────
		pays = self.tiers_pays or ""
		if pays in _PAYS_SANCTIONS_CRITIQUES:
			ax_geo = 100
			aggravants.append(f"Pays {pays} — sanctions critiques ONU/UE/OFAC")
		elif pays in _PAYS_CORRUPTION_ELEVE:
			ax_geo = 60
			aggravants.append(f"Pays {pays} — corruption/blanchiment élevé (FATF)")
		elif pays in _PAYS_SURVEILLANCE:
			ax_geo = 30
			aggravants.append(f"Pays {pays} — surveillance renforcée")
		else:
			ax_geo = 0

		# ── AXE CORRUPTION/INTÉGRITÉ [25%] ───────────────────────────
		criticite = (
			frappe.db.get_value("DD Type", self.dd_type, "criticite_moyenne") or ""
		) if self.dd_type else ""
		corr_raw = _SCORE_TYPE_TIERS.get(criticite, 5)

		if self.tiers_actionnaires_pep == "Oui":
			corr_raw += 25; aggravants.append("Actionnaires PEP (+25)")
		if self.tiers_responsables_publics_participations == "Oui":
			corr_raw += 20; aggravants.append("Responsables publics au capital (+20)")
		if self.tiers_detenu_etat == "Oui":
			corr_raw += 10; aggravants.append("Détention étatique (+10)")
		if self.tiers_structures_offshore == "Oui":
			corr_raw += 35; aggravants.append("Structures offshore (+35)")
		if self.tiers_trusts_holdings == "Oui":
			corr_raw += 15; aggravants.append("Trusts/holdings opaques (+15)")
		if self.tiers_figure_listes_sanctions == "Oui":
			corr_raw += 40; aggravants.append("Présent sur listes de sanctions (+40)")
		if self.tiers_paiements_offshore == "Oui":
			corr_raw += 20; aggravants.append("Paiements offshore (+20)")
		if self.interaction_publique:
			corr_raw += 15; aggravants.append("Interaction secteur public (+15)")
		if self.tiers_relations_entites_publiques_locales == "Oui":
			corr_raw += 15; aggravants.append("Relations entités publiques locales (+15)")
		if self.tiers_risques_sanctions_secondaires == "Oui":
			corr_raw += 20; aggravants.append("Risques sanctions secondaires (+20)")

		ax_corr = min(round(corr_raw * 100 / _MAX_CORRUPTION), 100)

		# ── AXE FINANCIER [15%] ───────────────────────────────────────
		montant = flt(self.tiers_montant_contrat or 0)
		if montant >= 50_000_000:
			ax_fin = 100; aggravants.append("Montant ≥ 50 M")
		elif montant >= 10_000_000:
			ax_fin = 60;  aggravants.append("Montant ≥ 10 M")
		elif montant >= 1_000_000:
			ax_fin = 40;  aggravants.append("Montant ≥ 1 M")
		elif montant >= 100_000:
			ax_fin = 20;  aggravants.append("Montant ≥ 100 K")
		else:
			ax_fin = 0

		# ── AXE CYBERSÉCURITÉ [10%] — spec §10 ───────────────────────
		cyber_raw = 0
		if self.acces_si:
			cyber_raw += 25; aggravants.append("Accès administration SI (+25)")
		if self.tiers_sans_mfa:
			cyber_raw += 20; aggravants.append("Absence MFA (+20)")
		if self.tiers_sans_pra_pca:
			cyber_raw += 15; aggravants.append("Absence PRA/PCA (+15)")
		if self.tiers_incident_cyber:
			cyber_raw += 30; aggravants.append("Incident cybersécurité majeur (+30)")
		ax_cyber = min(round(cyber_raw * 100 / _MAX_CYBER), 100)

		# ── AXE DONNÉES PERSONNELLES [10%] — spec §11 ─────────────────
		dp_raw = 0
		if self.donnees_personnelles:
			dp_raw += 40; aggravants.append("Traitement de données personnelles (+40)")
		if self.tiers_donnees_biometriques:
			dp_raw += 25; aggravants.append("Données biométriques (+25)")
		if self.tiers_violation_rgpd:
			dp_raw += 30; aggravants.append("Violation RGPD documentée (+30)")
		if self.tiers_dpo_absent:
			dp_raw += 15; aggravants.append("Absence de DPO (+15)")
		ax_donnees = min(round(dp_raw * 100 / _MAX_DONNEES), 100)

		# ── AXE DOCUMENTAIRE [5%] — spec §13 ─────────────────────────
		# Doc obligatoire manquant OU fourni mais IA dit Non conforme → pénalisé
		docs_manquants = sum(
			1 for d in (self.required_documents or [])
			if d.obligatoire and (
				d.statut == "Attendu"
				or (d.fichier and d.ia_verification == "Non conforme")
			)
		)
		doc_raw = min(docs_manquants * 15, _MAX_DOCUMENTAIRE)
		if docs_manquants:
			aggravants.append(f"{docs_manquants} document(s) obligatoire(s) manquant(s)/non conformes (+{doc_raw})")
		ax_doc = min(round(doc_raw * 100 / _MAX_DOCUMENTAIRE), 100) if doc_raw else 0

		# ── AXE RÉPUTATIONNEL [15%] — spec §12 — IA ──────────────────
		ax_reput = self._score_reputationnel_ia()

		# ── SCORE BRUT — formule pondérée (spec §14) ──────────────────
		# Utilise les 7 axes si réputationnel calculé, sinon 6 axes redistribués.
		# Les poids viennent de DD Scoring Config si active, sinon constantes module.
		if ax_reput > 0:
			self.score_brut = round(
				ax_geo     * poids["geo"]           +
				ax_corr    * poids["corruption"]    +
				ax_fin     * poids["financier"]     +
				ax_reput   * poids["reputationnel"] +
				ax_cyber   * poids["cyber"]         +
				ax_donnees * poids["donnees"]       +
				ax_doc     * poids["documentaire"]
			)
			poids_utilises = "7 axes (réputationnel actif)"
		else:
			self.score_brut = round(
				ax_geo     * poids_p1["geo"]           +
				ax_corr    * poids_p1["corruption"]    +
				ax_fin     * poids_p1["financier"]     +
				ax_cyber   * poids_p1["cyber"]         +
				ax_donnees * poids_p1["donnees"]       +
				ax_doc     * poids_p1["documentaire"]
			)
			poids_utilises = "6 axes redistribués (réputationnel IA non renseigné)"

		# ── QUESTIONNAIRE — enrichissement compliance ─────────────────
		score_questionnaire_raw = sum(int(a.poids_applique or 0) for a in (self.answers or []))
		questionnaire_contribution = min(round(score_questionnaire_raw / 10), 20)

		# ── ATTÉNUANTS (spec §14) ─────────────────────────────────────
		attenuants = []
		attenuants_total = 0
		for champ, points, label in _ATTENUANTS:
			if getattr(self, champ, None):
				attenuants_total += points
				attenuants.append(f"{label} (-{points})")

		# Docs optionnels fournis et vérifiés conformes par l'IA → atténuant
		docs_opt_conformes = sum(
			1 for d in (self.required_documents or [])
			if not d.obligatoire and d.fichier and d.ia_verification == "Conforme"
		)
		if docs_opt_conformes:
			pts_opt = min(docs_opt_conformes * 8, 20)
			attenuants_total += pts_opt
			attenuants.append(f"{docs_opt_conformes} document(s) optionnel(s) conforme(s) IA (-{pts_opt})")

		# ── SCORE PONDÉRÉ = brut + questionnaire − atténuants ─────────
		self.score_pondere = max(
			min(self.score_brut + questionnaire_contribution, 100) - attenuants_total,
			0
		)

		# ── SCORE RÉSIDUEL = pondéré (mesures de maîtrise post-DD : à venir) ─
		self.score_residuel = self.score_pondere

		# ── EXPLICABILITÉ (spec §19) ───────────────────────────────────
		poids_spec_fmt = {k: f"{v*100:.0f}%" for k, v in _POIDS_AXES.items()}
		self.detail_scoring = _json.dumps({
			"axes": {
				"géographique":  {"score_axe": ax_geo,     "poids_spec": poids_spec_fmt["geo"],           "poids_appliqué": f"{(_POIDS_AXES if ax_reput else _POIDS_P1).get('geo', _POIDS_P1['geo'])*100:.1f}%"},
				"corruption":    {"score_axe": ax_corr,    "poids_spec": poids_spec_fmt["corruption"],    "poids_appliqué": f"{(_POIDS_AXES if ax_reput else _POIDS_P1).get('corruption', _POIDS_P1['corruption'])*100:.1f}%"},
				"financier":     {"score_axe": ax_fin,     "poids_spec": poids_spec_fmt["financier"],     "poids_appliqué": f"{(_POIDS_AXES if ax_reput else _POIDS_P1).get('financier', _POIDS_P1['financier'])*100:.1f}%"},
				"réputationnel": {"score_axe": ax_reput,   "poids_spec": poids_spec_fmt["reputationnel"], "poids_appliqué": f"{_POIDS_AXES['reputationnel']*100:.0f}%" if ax_reput else "0% (IA non renseignée)"},
				"cyber":         {"score_axe": ax_cyber,   "poids_spec": poids_spec_fmt["cyber"],         "poids_appliqué": f"{(_POIDS_AXES if ax_reput else _POIDS_P1).get('cyber', _POIDS_P1['cyber'])*100:.1f}%"},
				"données":       {"score_axe": ax_donnees, "poids_spec": poids_spec_fmt["donnees"],       "poids_appliqué": f"{(_POIDS_AXES if ax_reput else _POIDS_P1).get('donnees', _POIDS_P1['donnees'])*100:.1f}%"},
				"documentaire":  {"score_axe": ax_doc,     "poids_spec": poids_spec_fmt["documentaire"],  "poids_appliqué": f"{(_POIDS_AXES if ax_reput else _POIDS_P1).get('documentaire', _POIDS_P1['documentaire'])*100:.1f}%"},
			},
			"formule": poids_utilises,
			"aggravants": aggravants,
			"atténuants": attenuants,
			"questionnaire": {
				"brut": score_questionnaire_raw,
				"appliqué": questionnaire_contribution,
			},
			"scores": {
				"brut": self.score_brut,
				"pondéré": self.score_pondere,
				"résiduel": self.score_residuel,
			},
		}, ensure_ascii=False)

		# ── CATÉGORIE AUTO (spec §15) — seuils issus de la config ────
		categorie_auto = _categorie_from_score(self.score_residuel, seuils_risque)

		if self.categorie_risque and self.categorie_risque != categorie_auto:
			if not self.justification_score_manuel:
				frappe.throw(
					_(
						"La catégorie de risque a été modifiée manuellement. "
						"Vous devez saisir une justification dans le champ "
						"« Justification de la modification du score »."
					),
					title=_("Justification requise"),
				)
		else:
			self.categorie_risque = categorie_auto

		# ── HISTORIQUE DES SCORES (spec §17) ─────────────────────────
		self._enregistrer_historique_score(categorie_auto)

	# ------------------------------------------------------------------
	# 4.3  Historique des scores (spec §17) — n'enregistre que si changement
	# ------------------------------------------------------------------
	def _enregistrer_historique_score(self, categorie_auto):
		doc_before = self.get_doc_before_save()
		old_score  = getattr(doc_before, "score_residuel", None) if doc_before else None
		old_cat    = getattr(doc_before, "categorie_risque", None) if doc_before else None

		# Enregistrer si : nouveau dossier OU score résiduel modifié
		if old_score is not None and old_score == self.score_residuel:
			return

		if old_cat and old_cat != categorie_auto:
			delta = f"{old_cat} → {categorie_auto}"
		elif old_cat is None:
			delta = f"Nouveau — {categorie_auto}"
		else:
			delta = "—"

		self.append("score_history", {
			"date_calcul":    now_datetime(),
			"calcule_par":    frappe.session.user,
			"score_brut":     self.score_brut,
			"score_pondere":  self.score_pondere,
			"score_residuel": self.score_residuel,
			"categorie":      categorie_auto,
			"delta_categorie": delta,
			"declencheur":    "Validation",
		})

	# ------------------------------------------------------------------
	# 4.4  Alertes catégorie Interdit / Critique (spec §16)
	# ------------------------------------------------------------------
	def _alerter_categorie_critique(self):
		doc_before = self.get_doc_before_save()
		old_cat = getattr(doc_before, "categorie_risque", None) if doc_before else None
		new_cat = self.categorie_risque

		if not new_cat or new_cat == old_cat:
			return

		if new_cat == "Interdit":
			self._envoyer_alerte_direction(new_cat)
		elif new_cat == "Critique":
			self._envoyer_alerte_direction(new_cat)

	def _envoyer_alerte_direction(self, categorie):
		try:
			destinataires = _emails_role("DD Validateur") + _emails_role("DD Manager Compliance")
			if not destinataires:
				return
			couleur = "#dc2626" if categorie == "Interdit" else "#d97706"
			frappe.sendmail(
				recipients=destinataires,
				subject=_(
					"[ALERTE DD] Dossier {0} — catégorie {1}"
				).format(self.name, categorie),
				message=_(
					"<p style='font-size:16px;font-weight:600;color:{5};'>"
					"⚠ Catégorie de risque : {1}</p>"
					"<table style='border-collapse:collapse;width:100%;margin:16px 0;'>"
					"<tr style='border-bottom:1px solid #e2e8f0;'>"
					"<td style='padding:8px 12px;font-weight:600;color:#64748b;width:40%;'>Dossier</td>"
					"<td style='padding:8px 12px;'>{0}</td></tr>"
					"<tr style='border-bottom:1px solid #e2e8f0;'>"
					"<td style='padding:8px 12px;font-weight:600;color:#64748b;'>Tiers évalué</td>"
					"<td style='padding:8px 12px;'>{2}</td></tr>"
					"<tr style='border-bottom:1px solid #e2e8f0;'>"
					"<td style='padding:8px 12px;font-weight:600;color:#64748b;'>Score résiduel</td>"
					"<td style='padding:8px 12px;font-weight:700;'>{3} / 100</td></tr>"
					"<tr>"
					"<td style='padding:8px 12px;font-weight:600;color:#64748b;'>Demandeur</td>"
					"<td style='padding:8px 12px;'>{4}</td></tr>"
					"</table>"
					"<p style='margin-top:20px;'>"
					"<a href='{6}/app/dd-request/{0}' "
					"style='background:#0d1b2a;color:#fff;padding:10px 20px;"
					"border-radius:6px;text-decoration:none;font-weight:600;'>"
					"Ouvrir le dossier</a></p>"
				).format(
					self.name, categorie, self.tiers_nom or "—",
					self.score_residuel or 0, self.demandeur_nom or "—",
					couleur, frappe.utils.get_url(),
				),
				now=True,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "DD — alerte catégorie critique")

	# ------------------------------------------------------------------
	# 4.6  Axe réputationnel — analyse IA via Google Gemini (spec §12/§18)
	# ------------------------------------------------------------------
	def _score_reputationnel_ia(self):
		"""Évalue le risque réputationnel du tiers via Gemini Flash.
		Cache dans resume_reputationnel — vider le champ pour forcer le recalcul."""
		if not self.tiers_nom:
			return 0
		if self.resume_reputationnel:
			return int(self.score_reputationnel or 0)
		api_key = frappe.conf.get("gemini_api_key", "")
		if not api_key:
			return 0
		try:
			import json as _json
			import requests as _requests

			pays_info    = f" (pays : {self.tiers_pays})" if self.tiers_pays else ""
			secteur_info = f", secteur : {self.tiers_secteur}" if self.tiers_secteur else ""
			prompt = (
				f'Tu es un analyste compliance senior. Évalue le risque réputationnel '
				f'du tiers "{self.tiers_nom}"{pays_info}{secteur_info} sur une échelle 0-100.\n'
				"Critères : presse négative, scandales financiers, corruption avérée, "
				"contentieux judiciaires importants, associations avec entités sous sanctions, "
				"condamnations réglementaires.\n"
				"Si tu n'as aucune information publique sur ce tiers, réponds score=0.\n"
				"Réponds UNIQUEMENT avec un JSON valide (sans markdown) :\n"
				'{"score":0,"resume":"explication factuelle max 150 mots en français"}'
			)
			url = (
				"https://generativelanguage.googleapis.com/v1beta/models/"
				f"gemini-2.5-flash-lite:generateContent?key={api_key}"
			)
			payload = {
				"contents": [{"parts": [{"text": prompt}]}],
				"generationConfig": {
					"temperature": 0.1,
					"maxOutputTokens": 400,
					"responseMimeType": "application/json",
				},
			}
			resp = _requests.post(url, json=payload, timeout=30)
			resp.raise_for_status()
			text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
			result = _json.loads(text)
			score = max(0, min(int(result.get("score", 0)), 100))
			self.score_reputationnel = score
			self.resume_reputationnel = (result.get("resume") or "")[:500]
			return score
		except Exception:
			frappe.log_error(frappe.get_traceback(), "DD — scoring réputationnel IA")
			return 0

	# ------------------------------------------------------------------
	# 4.7  Hash SHA-256 des fichiers attachés (nouveaux uniquement)
	# ------------------------------------------------------------------
	def _hash_documents(self):
		for row in (self.required_documents or []):
			if row.fichier and not row.hash_sha256:
				try:
					row.hash_sha256 = _sha256_fichier(row.fichier)
					row.db_set("hash_sha256", row.hash_sha256, update_modified=False)
				except Exception:
					pass

	# ------------------------------------------------------------------
	# 4.7b  Vérification IA des documents (Gemini Vision)
	# ------------------------------------------------------------------
	def _analyser_documents_ia(self):
		"""Pour chaque fichier nouvellement uploadé, vérifie via Gemini Vision :
		1. Le document correspond-il au type demandé ?
		2. Extrait les informations clés (dates, noms, numéros d'enregistrement).
		"""
		api_key = frappe.conf.get("gemini_api_key", "")
		if not api_key:
			return

		for row in (self.required_documents or []):
			if not row.fichier:
				continue
			# Sauter si déjà vérifié (hors "Non vérifié")
			if row.ia_verification and row.ia_verification not in ("", "Non vérifié"):
				continue
			try:
				_verifier_document_ia(row, api_key)
				row.db_set("ia_verification", row.ia_verification, update_modified=False)
				row.db_set("ia_confiance",    row.ia_confiance,    update_modified=False)
				row.db_set("ia_motif",        row.ia_motif,        update_modified=False)
				row.db_set("ia_infos_extraites", row.ia_infos_extraites, update_modified=False)
				# Mettre à jour le statut si le doc est conforme et encore "Attendu"
				if row.ia_verification == "Conforme" and row.statut == "Attendu":
					row.db_set("statut", "Reçu", update_modified=False)
			except Exception:
				frappe.log_error(frappe.get_traceback(), f"DD — vérif IA doc '{row.nom_document}'")

	# ------------------------------------------------------------------
	# 4.8  On submit : assignation analyste + notifications email
	# ------------------------------------------------------------------
	def _assigner_analyste(self):
		if self.analyste_assigne:
			return

		# Liste triée des analystes actifs (tri alphab. pour un ordre stable)
		analystes = sorted(frappe.get_all(
			"Has Role",
			filters={"role": "DD Analyste", "parenttype": "User"},
			pluck="parent",
		))
		if not analystes:
			return
		if len(analystes) == 1:
			self.db_set("analyste_assigne", analystes[0], update_modified=False)
			return

		# Round-robin : trouver le dernier analyste assigné parmi les analystes connus
		dernier = frappe.db.get_value(
			"DD Request",
			filters={"analyste_assigne": ["in", analystes], "name": ["!=", self.name]},
			fieldname="analyste_assigne",
			order_by="creation desc",
		)

		if dernier and dernier in analystes:
			idx = analystes.index(dernier)
			prochain = analystes[(idx + 1) % len(analystes)]
		else:
			prochain = analystes[0]

		self.db_set("analyste_assigne", prochain, update_modified=False)

	# ------------------------------------------------------------------
	# 4.8c  Notification automatique du prochain acteur après transition
	# ------------------------------------------------------------------
	def _notifier_prochain_acteur(self):
		"""Quand l'état du dossier change, envoie cloche desk + email à chaque acteur
		dont l'étape vient d'être activée (rôle → utilisateurs ciblés)."""
		doc_before = self.get_doc_before_save()
		if not doc_before:
			return
		if doc_before.workflow_state == self.workflow_state:
			return

		# Uniquement la prochaine étape "En attente" (moteur séquentiel)
		# Toutes les étapes démarrent à "En attente" à la soumission — on prend
		# seulement la première par ordre pour ne pas notifier les rôles futurs.
		etapes_actives = frappe.get_all(
			"DD Workflow Step",
			filters={"parent": self.name, "parenttype": "DD Request",
			         "statut": "En attente", "obligatoire": 1},
			fields=["etape", "role_validateur", "ordre"],
			order_by="ordre asc",
			limit=1,
		)
		if not etapes_actives:
			return

		url_base = frappe.utils.get_url()
		roles_traites = set()

		for etape in etapes_actives:
			role = etape.role_validateur
			if role in roles_traites:
				continue
			roles_traites.add(role)

			# DD Analyste → uniquement l'analyste assigné ; autres rôles → tous les membres actifs
			if role == "DD Analyste" and self.analyste_assigne:
				users = [self.analyste_assigne]
			else:
				membres = frappe.get_all(
					"Has Role",
					filters={"role": role, "parenttype": "User"},
					pluck="parent",
				)
				users = (
					frappe.get_all(
						"User",
						filters={"name": ["in", membres], "enabled": 1},
						pluck="name",
					)
					if membres else []
				)

			if not users:
				continue

			sujet = _("Action requise — Dossier DD {0} · {1}").format(
				self.name, self.tiers_nom or "—"
			)
			corps = (
				"<p style='margin:0 0 12px;'>Le dossier Due Diligence ci-dessous requiert "
				"votre intervention (rôle&nbsp;: <b>{role}</b>).</p>"
				"<table style='border-collapse:collapse;width:100%;margin:0 0 20px;font-size:14px;'>"
				"<tr style='border-bottom:1px solid #e2e8f0;'>"
				"<td style='padding:7px 12px;font-weight:600;color:#64748b;width:35%;'>Référence</td>"
				"<td style='padding:7px 12px;'>{name}</td></tr>"
				"<tr style='border-bottom:1px solid #e2e8f0;'>"
				"<td style='padding:7px 12px;font-weight:600;color:#64748b;'>Tiers évalué</td>"
				"<td style='padding:7px 12px;'>{tiers}</td></tr>"
				"<tr style='border-bottom:1px solid #e2e8f0;'>"
				"<td style='padding:7px 12px;font-weight:600;color:#64748b;'>Étape à traiter</td>"
				"<td style='padding:7px 12px;font-weight:600;color:#0d1b2a;'>{etape}</td></tr>"
				"<tr style='border-bottom:1px solid #e2e8f0;'>"
				"<td style='padding:7px 12px;font-weight:600;color:#64748b;'>État du dossier</td>"
				"<td style='padding:7px 12px;'>{etat}</td></tr>"
				"<tr style='border-bottom:1px solid #e2e8f0;'>"
				"<td style='padding:7px 12px;font-weight:600;color:#64748b;'>Circuit</td>"
				"<td style='padding:7px 12px;'>{circuit}</td></tr>"
				"<tr>"
				"<td style='padding:7px 12px;font-weight:600;color:#64748b;'>Score résiduel</td>"
				"<td style='padding:7px 12px;font-weight:700;'>{score} / 100</td></tr>"
				"</table>"
				"<p><a href='{url}/app/dd-request/{name}' "
				"style='background:#0d1b2a;color:#fff;padding:10px 22px;"
				"border-radius:6px;text-decoration:none;font-weight:600;'>"
				"Ouvrir le dossier →</a></p>"
			).format(
				role=role,
				name=self.name,
				tiers=self.tiers_nom or "—",
				etape=etape.etape,
				etat=self.workflow_state,
				circuit=self.circuit_workflow or "—",
				score=self.score_residuel or 0,
				url=url_base,
			)

			# ── Cloche desk + push realtime par utilisateur ──
			for user in users:
				try:
					frappe.get_doc({
						"doctype":       "Notification Log",
						"subject":       sujet,
						"email_content": corps,
						"for_user":      user,
						"from_user":     frappe.session.user,
						"document_type": "DD Request",
						"document_name": self.name,
						"type":          "Alert",
					}).insert(ignore_permissions=True)

					frappe.publish_realtime(
						"notification",
						after_commit=True,
						user=user,
					)
				except Exception:
					frappe.log_error(
						frappe.get_traceback(),
						f"DD — cloche notification {user} ({role})",
					)

			# ── Email groupé pour le rôle (name = email dans Frappe) ──
			try:
				frappe.sendmail(
					recipients=users,
					subject=sujet,
					message=corps,
					now=True,
				)
			except Exception:
				frappe.log_error(
					frappe.get_traceback(),
					f"DD — email notification rôle {role}",
				)

		# ── Cas spécial : "En attente de documents" → notifier le client ──
		if self.workflow_state == "En attente de documents":
			self._notifier_client_docs_manquants()

	def _notifier_client_docs_manquants(self):
		"""Notifie le client (owner du dossier) qu'il doit fournir des documents."""
		client = self.owner
		if not client or client == "Administrator":
			return
		url_base = frappe.utils.get_url()
		sujet = _("Action requise — Documents à fournir pour votre dossier {0}").format(self.name)
		docs_demandes = [
			row.nom_document for row in (self.documents_complementaires or [])
			if row.statut == "En attente"
		]
		liste_docs = "".join(
			f"<li style='padding:4px 0;'>{d}</li>" for d in docs_demandes
		) if docs_demandes else "<li>Voir le détail dans votre espace</li>"

		corps = (
			f"<p>Le cabinet AMOAMAN &amp; ASSOCIÉS vous demande de fournir des documents "
			f"complémentaires pour votre dossier <b>{self.name}</b>.</p>"
			f"<ul style='margin:12px 0;padding-left:20px;'>{liste_docs}</ul>"
			f"<p><a href='{url_base}/suivi?name={self.name}' "
			f"style='background:#0d1b2a;color:#fff;padding:10px 22px;"
			f"border-radius:6px;text-decoration:none;font-weight:600;'>"
			f"Déposer mes documents →</a></p>"
		)
		try:
			frappe.get_doc({
				"doctype":       "Notification Log",
				"subject":       sujet,
				"email_content": corps,
				"for_user":      client,
				"from_user":     frappe.session.user,
				"document_type": "DD Request",
				"document_name": self.name,
				"type":          "Alert",
			}).insert(ignore_permissions=True)
			frappe.publish_realtime("notification", after_commit=True, user=client)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"DD — notification client docs manquants {self.name}")

		if self.email_contact:
			try:
				frappe.sendmail(
					recipients=[self.email_contact],
					subject=sujet,
					message=corps,
					now=True,
				)
			except Exception:
				frappe.log_error(frappe.get_traceback(), "DD — email client docs manquants")

	def _notifier_soumission(self):
		try:
			# ── Cloche desk : notification ciblée vers l'analyste assigné ──
			if self.analyste_assigne:
				sujet = _("Nouveau dossier DD soumis — {0} ({1})").format(self.name, self.tiers_nom or "")
				contenu = _(
					"<p>Le dossier <b>{0}</b> concernant <b>{1}</b> vient d'être soumis "
					"par le client et vous a été assigné.</p>"
					"<ul>"
					"<li><b>Type DD :</b> {2}</li>"
					"<li><b>Demandeur :</b> {3}</li>"
					"</ul>"
				).format(self.name, self.tiers_nom, self.dd_type, self.demandeur_nom)

				frappe.get_doc({
					"doctype": "Notification Log",
					"subject": sujet,
					"email_content": contenu,
					"for_user": self.analyste_assigne,
					"from_user": self.client_user or frappe.session.user,
					"document_type": "DD Request",
					"document_name": self.name,
					"type": "Alert",
				}).insert(ignore_permissions=True)

				frappe.publish_realtime(
					"notification",
					after_commit=True,
					user=self.analyste_assigne,
				)

			# ── Email vers l'analyste assigné uniquement (pas toute l'équipe) ──
			destinataires_equipe = (
				[self.analyste_assigne] if self.analyste_assigne
				else _emails_role("DD Analyste") + _emails_role("DD Manager Compliance")
			)
			if destinataires_equipe:
				frappe.sendmail(
					recipients=destinataires_equipe,
					subject=_("Nouveau dossier DD soumis — {0}").format(self.name),
					message=_(
						"<p>Un nouveau dossier de Due Diligence a été soumis.</p>"
						"<ul>"
						"<li><b>Référence :</b> {0}</li>"
						"<li><b>Tiers évalué :</b> {1}</li>"
						"<li><b>Type DD :</b> {2}</li>"
						"<li><b>Demandeur :</b> {3}</li>"
						"</ul>"
					).format(self.name, self.tiers_nom, self.dd_type, self.demandeur_nom),
					now=True,
				)

			if self.email_contact:
				frappe.sendmail(
					recipients=[self.email_contact],
					subject=_("Votre dossier Due Diligence a bien été reçu — {0}").format(self.name),
					message=_(
						"<p>Madame, Monsieur {0},</p>"
						"<p>Votre demande de Due Diligence concernant <b>{1}</b> "
						"(référence <b>{2}</b>) a bien été reçue par le cabinet "
						"AMOAMAN &amp; ASSOCIÉS.</p>"
						"<p>Notre équipe Compliance vous contactera prochainement.</p>"
						"<p>Cordialement,<br>Cabinet AMOAMAN &amp; ASSOCIÉS — Compliance</p>"
					).format(self.demandeur_nom, self.tiers_nom, self.name),
					now=True,
				)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "DD Request — erreur notification soumission")

	# ------------------------------------------------------------------
	# 4.8b  Avis IA automatique — déclenché à la soumission
	# ------------------------------------------------------------------
	def _generer_avis_ia_auto(self):
		"""Génère l'avis compliance IA via Gemini dès que le client soumet le dossier."""
		api_key = frappe.conf.get("gemini_api_key", "")
		if not api_key:
			return
		# Ne pas régénérer si un avis IA non soumis existe déjà
		if frappe.db.exists("DD Avis Compliance", {"dd_request": self.name, "is_ia_avis": 1, "docstatus": 0}):
			return
		try:
			import time as _time
			import requests as _requests

			prompt = (
				f"Tu es un analyste compliance senior. Rédige un avis compliance formel "
				f"pour le dossier de due diligence suivant.\n\n"
				f"Tiers évalué : {self.tiers_nom or '—'}\n"
				f"Type de DD : {self.dd_type or '—'}\n"
				f"Pays : {self.tiers_pays or '—'}\n"
				f"Secteur : {self.tiers_secteur or '—'}\n"
				f"Score brut : {self.score_brut or 0}/100\n"
				f"Score résiduel : {self.score_residuel or 0}/100\n"
				f"Catégorie de risque : {self.categorie_risque or '—'}\n"
				f"Résumé réputationnel : {self.resume_reputationnel or 'Non disponible'}\n\n"
				f"Commence ta réponse par EXACTEMENT une de ces trois lignes (rien d'autre sur cette ligne) :\n"
				f"DECISION: GO\n"
				f"DECISION: NO GO\n"
				f"DECISION: GO sous réserve\n\n"
				f"Puis rédige l'avis en français de 200 à 300 mots structuré ainsi :\n"
				f"1. Synthèse du profil de risque\n"
				f"2. Points d'attention principaux\n"
				f"3. Conditions éventuelles (si GO sous réserve)\n\n"
				f"Ton : formel, factuel, sans jargon excessif. Pas de markdown."
			)
			_MODELS = [
				"gemini-flash-lite-latest",
				"gemini-2.0-flash-lite",
				"gemini-2.5-flash-lite",
				"gemini-flash-latest",
				"gemini-2.0-flash",
			]
			_SKIP_CODES = {429, 503, 404}
			payload = {
				"contents": [{"parts": [{"text": prompt}]}],
				"generationConfig": {"temperature": 0.2, "maxOutputTokens": 700},
			}
			_headers = {"X-goog-api-key": api_key, "Content-Type": "application/json"}
			resp = None
			for model in _MODELS:
				url = (
					"https://generativelanguage.googleapis.com/v1beta/models/"
					f"{model}:generateContent"
				)
				for attempt in range(2):
					resp = _requests.post(url, headers=_headers, json=payload, timeout=45)
					if resp.status_code == 404 or resp.status_code not in {429, 503}:
						break
					_time.sleep(2 ** attempt)
				if resp.status_code not in _SKIP_CODES:
					break

			if not (resp and resp.status_code == 200):
				return

			texte = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
			lines = texte.split("\n")
			first_line = lines[0].strip()
			decisions_valides = {"GO", "NO GO", "GO sous réserve"}
			decision = "GO"
			motif = texte
			if first_line.startswith("DECISION:"):
				candidate = first_line[len("DECISION:"):].strip()
				if candidate in decisions_valides:
					decision = candidate
					motif = "\n".join(lines[1:]).strip()

			avis_doc = frappe.get_doc({
				"doctype": "DD Avis Compliance",
				"dd_request": self.name,
				"is_ia_avis": 1,
				"decision": decision,
				"motif_decision": motif,
				"date_decision": frappe.utils.today(),
			})
			avis_doc.insert(ignore_permissions=True)
			frappe.db.commit()
		except Exception:
			frappe.log_error(frappe.get_traceback(), "DD — génération avis IA (auto submit)")

	# ------------------------------------------------------------------
	# 4.8e  Moteur de workflow — initialisation au submit (spec §§3-8)
	# ------------------------------------------------------------------
	def _initialiser_workflow(self):
		from due_diligence.due_diligence.workflow_engine import (
			determiner_circuit, generer_etapes, calculer_date_sla, _journaliser,
		)
		circuit    = determiner_circuit(self)
		date_sla   = calculer_date_sla(circuit)
		etapes     = generer_etapes(circuit, self.dd_type)

		frappe.db.set_value("DD Request", self.name, {
			"circuit_workflow":   circuit,
			"date_echeance_sla":  date_sla,
			"sla_depasse":        0,
			"niveau_escalade":    0,
		})

		for etape in etapes:
			frappe.get_doc({
				"doctype":     "DD Workflow Step",
				"parent":      self.name,
				"parenttype":  "DD Request",
				"parentfield": "workflow_steps",
				**etape,
			}).insert(ignore_permissions=True)

		_journaliser(
			self.name,
			"Soumission",
			f"Dossier soumis — circuit « {circuit} » activé, SLA : {str(date_sla)[:10]}",
			nouveau_statut=circuit,
			declencheur="on_submit",
		)
		frappe.db.commit()

	# ------------------------------------------------------------------
	# 4.8c  Recalcul circuit si le score change après submit
	# ------------------------------------------------------------------
	def _recalculer_circuit_si_changement(self):
		if self.docstatus != 1:
			return
		doc_before = self.get_doc_before_save()
		if not doc_before:
			return
		old_score = getattr(doc_before, "score_residuel", None)
		if old_score is None or old_score == self.score_residuel:
			return

		from due_diligence.due_diligence.workflow_engine import determiner_circuit, _journaliser
		nouveau_circuit = determiner_circuit(self)
		ancien_circuit  = self.circuit_workflow or ""

		if nouveau_circuit != ancien_circuit:
			frappe.db.set_value("DD Request", self.name, "circuit_workflow", nouveau_circuit)
			_journaliser(
				self.name,
				"Changement de circuit",
				f"Score : {old_score} → {self.score_residuel} — circuit : {ancien_circuit} → {nouveau_circuit}",
				ancien_statut=ancien_circuit,
				nouveau_statut=nouveau_circuit,
				declencheur="Recalcul score",
			)

	# ------------------------------------------------------------------
	# 4.8d  Écart score IA / analyste — notification si trop grand
	# ------------------------------------------------------------------
	_SEUIL_ECART_SCORE = 20  # points

	def _alerter_ecart_score(self):
		if not self.score_humain:
			return
		ecart = abs((self.score_residuel or 0) - (self.score_humain or 0))
		self.db_set("ecart_score", ecart, update_modified=False)

		doc_before = self.get_doc_before_save()
		old_humain = getattr(doc_before, "score_humain", None) if doc_before else None
		if old_humain == self.score_humain:
			return

		if ecart >= self._SEUIL_ECART_SCORE:
			self._notifier_ecart_score(ecart)

	def _notifier_ecart_score(self, ecart):
		managers = frappe.get_all(
			"Has Role",
			filters={"role": "DD Manager Compliance", "parenttype": "User"},
			pluck="parent",
		)
		if not managers:
			managers = frappe.get_all(
				"Has Role",
				filters={"role": "DD Validateur", "parenttype": "User"},
				pluck="parent",
			)
		for user in managers:
			try:
				frappe.get_doc({
					"doctype": "Notification Log",
					"subject": _(
						"Écart de score important sur le dossier {0} ({1} points)"
					).format(self.name, ecart),
					"for_user": user,
					"type": "Alert",
					"document_type": "DD Request",
					"document_name": self.name,
					"email_content": _(
						"L'analyste {0} a attribué un score de <b>{1}/100</b> "
						"alors que le score IA est de <b>{2}/100</b> "
						"(écart : <b>{3} points</b>). Une révision du dossier est recommandée."
					).format(
						frappe.session.user,
						self.score_humain,
						self.score_residuel or 0,
						ecart,
					),
				}).insert(ignore_permissions=True)
			except Exception:
				frappe.log_error(frappe.get_traceback(), "DD — notification écart score")

	# ------------------------------------------------------------------
	# 4.9  Horodatage décision + notification client
	# ------------------------------------------------------------------
	def _horodater_decision(self):
		if not self.decision_finale:
			return
		doc_before = self.get_doc_before_save()
		# N'agit que si la décision vient d'être posée ou modifiée
		if doc_before and doc_before.decision_finale == self.decision_finale:
			return

		self.db_set("date_decision", now_datetime(), update_modified=False)

		if self.email_contact:
			reserves_html = (
				"<p><b>Réserves :</b> {0}</p>".format(self.reserves) if self.reserves else ""
			)
			frappe.sendmail(
				recipients=[self.email_contact],
				subject=_("Décision Due Diligence — {0}").format(self.name),
				message=_(
					"<p>Madame, Monsieur {0},</p>"
					"<p>Le cabinet AMOAMAN &amp; ASSOCIÉS a rendu sa décision "
					"concernant le dossier <b>{1}</b> (tiers : <b>{2}</b>).</p>"
					"<p><b>Décision :</b> {3}</p>"
					"{4}"
					"<p>Cordialement,<br>Cabinet AMOAMAN &amp; ASSOCIÉS — Compliance</p>"
				).format(
					self.demandeur_nom,
					self.name,
					self.tiers_nom,
					self.decision_finale,
					reserves_html,
				),
				now=True,
			)


# ------------------------------------------------------------------
# API whitelist
# ------------------------------------------------------------------

@frappe.whitelist()
def creer_avis_depuis_dossier(dd_request_name):
	"""Crée un brouillon d'avis pré-rempli depuis le dossier. Retourne name + flag existe."""
	frappe.get_doc("DD Request", dd_request_name)  # déclenche la vérification des permissions

	avis_existant = frappe.db.get_value(
		"DD Avis Compliance", {"dd_request": dd_request_name}, "name"
	)
	if avis_existant:
		return {"avis": avis_existant, "existe": True}

	avis = frappe.get_doc({
		"doctype": "DD Avis Compliance",
		"dd_request": dd_request_name,
		"redige_par": frappe.session.user,
	})
	avis.insert()
	frappe.db.commit()
	return {"avis": avis.name, "existe": False}


@frappe.whitelist()
def generer_avis_ia(dd_request_name):
	"""Génère un avis compliance complet via Gemini à partir des données du dossier."""
	doc = frappe.get_doc("DD Request", dd_request_name)

	api_key = frappe.conf.get("gemini_api_key", "")
	if not api_key:
		frappe.throw(_("Clé API Gemini non configurée (gemini_api_key dans site_config.json)."))

	try:
		import time as _time
		import requests as _requests

		prompt = (
			f"Tu es un analyste compliance senior. Rédige un avis compliance formel et structuré "
			f"pour le dossier de due diligence suivant.\n\n"
			f"Tiers évalué : {doc.tiers_nom or '—'}\n"
			f"Type de DD : {doc.dd_type or '—'}\n"
			f"Pays : {doc.tiers_pays or '—'}\n"
			f"Secteur : {doc.tiers_secteur or '—'}\n"
			f"Score brut : {doc.score_brut or 0}/100\n"
			f"Score résiduel : {doc.score_residuel or 0}/100\n"
			f"Catégorie de risque : {doc.categorie_risque or '—'}\n"
			f"Résumé réputationnel : {doc.resume_reputationnel or 'Non disponible'}\n\n"
			f"Commence ta réponse par EXACTEMENT une de ces trois lignes (rien d'autre sur cette ligne) :\n"
			f"DECISION: GO\n"
			f"DECISION: NO GO\n"
			f"DECISION: GO sous réserve\n\n"
			f"Puis rédige l'avis en français de 200 à 300 mots structuré ainsi :\n"
			f"1. Synthèse du profil de risque\n"
			f"2. Points d'attention principaux\n"
			f"3. Conditions éventuelles (si GO sous réserve)\n\n"
			f"Ton : formel, factuel, sans jargon excessif. Pas de markdown."
		)

		_MODELS = [
			"gemini-flash-lite-latest",
			"gemini-2.0-flash-lite",
			"gemini-2.5-flash-lite",
			"gemini-flash-latest",
			"gemini-2.0-flash",
			"gemini-2.5-flash",
		]
		_SKIP_CODES = {429, 503, 404}
		payload = {
			"contents": [{"parts": [{"text": prompt}]}],
			"generationConfig": {"temperature": 0.2, "maxOutputTokens": 700},
		}
		_headers = {"X-goog-api-key": api_key, "Content-Type": "application/json"}

		resp = None
		last_status = None
		for model in _MODELS:
			url = (
				"https://generativelanguage.googleapis.com/v1beta/models/"
				f"{model}:generateContent"
			)
			for attempt in range(3):
				resp = _requests.post(url, headers=_headers, json=payload, timeout=60)
				if resp.status_code == 404 or resp.status_code not in {429, 503}:
					break
				_time.sleep(2 ** attempt)
			last_status = resp.status_code
			if last_status not in _SKIP_CODES:
				break

		if last_status == 429:
			frappe.throw(_("Quota Gemini dépassé pour tous les modèles. Réessayez dans quelques minutes."))
		if last_status in {503, 404}:
			frappe.throw(_("Service Gemini indisponible. Réessayez plus tard."))

		resp.raise_for_status()
		texte = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

		# Extraire la décision de la première ligne
		lines = texte.split("\n")
		first_line = lines[0].strip()
		decisions_valides = {"GO", "NO GO", "GO sous réserve"}
		decision = "GO"
		motif = texte
		if first_line.startswith("DECISION:"):
			candidate = first_line[len("DECISION:"):].strip()
			if candidate in decisions_valides:
				decision = candidate
				motif = "\n".join(lines[1:]).strip()

		# Créer ou mettre à jour le DD Avis Compliance IA
		existant = frappe.db.get_value(
			"DD Avis Compliance",
			{"dd_request": dd_request_name, "is_ia_avis": 1, "docstatus": 0},
			"name",
		)
		if existant:
			avis_doc = frappe.get_doc("DD Avis Compliance", existant)
			avis_doc.decision = decision
			avis_doc.motif_decision = motif
			avis_doc.date_decision = frappe.utils.today()
			avis_doc.save(ignore_permissions=True)
		else:
			avis_doc = frappe.get_doc({
				"doctype": "DD Avis Compliance",
				"dd_request": dd_request_name,
				"is_ia_avis": 1,
				"decision": decision,
				"motif_decision": motif,
				"date_decision": frappe.utils.today(),
			})
			avis_doc.insert(ignore_permissions=True)

		frappe.db.commit()
		return avis_doc.name

	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), "DD — génération avis IA")
		frappe.throw(_("Erreur lors de la génération de l'avis IA. Consultez les logs."))


# ------------------------------------------------------------------
# Helpers module-level
# ------------------------------------------------------------------

def _charger_config_scoring():
	"""Retourne (poids_dict, seuils_list) depuis DD Scoring Config (single), ou les constantes module."""
	try:
		config = frappe.get_doc("DD Scoring Config", "DD Scoring Config")
	except Exception:
		config = None

	if not config:
		return _POIDS_AXES, _SEUILS_RISQUE

	poids = {
		"geo":           (config.poids_geo or 20) / 100,
		"corruption":    (config.poids_corruption or 25) / 100,
		"financier":     (config.poids_financier or 15) / 100,
		"reputationnel": (config.poids_reputationnel or 15) / 100,
		"cyber":         (config.poids_cyber or 10) / 100,
		"donnees":       (config.poids_donnees or 10) / 100,
		"documentaire":  (config.poids_documentaire or 5) / 100,
	}
	seuils = [
		(int(config.seuil_faible or 20),   "Faible"),
		(int(config.seuil_modere or 40),   "Modéré"),
		(int(config.seuil_eleve or 60),    "Élevé"),
		(int(config.seuil_critique or 80), "Critique"),
	]
	return poids, seuils


def _categorie_from_score(score, seuils=None):
	for seuil, categorie in (seuils or _SEUILS_RISQUE):
		if score <= seuil:
			return categorie
	return "Interdit"


def _sha256_fichier(file_url):
	"""Calcule le hash SHA-256 d'un fichier Frappe à partir de son URL."""
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	file_path = file_doc.get_full_path()
	h = hashlib.sha256()
	with open(file_path, "rb") as f:
		for chunk in iter(lambda: f.read(65536), b""):
			h.update(chunk)
	return h.hexdigest()


def _verifier_document_ia(row, api_key):
	"""Envoie le fichier à Gemini Vision pour vérifier sa conformité et extraire les infos clés.

	Remplit row.ia_verification, row.ia_confiance, row.ia_motif, row.ia_infos_extraites.
	Ne lève pas d'exception — les erreurs sont absorbées par l'appelant.
	"""
	import base64 as _b64
	import json as _json
	import mimetypes as _mime
	import requests as _requests

	# ── Charger le fichier ────────────────────────────────────────────
	try:
		file_doc = frappe.get_doc("File", {"file_url": row.fichier})
		file_path = file_doc.get_full_path()
	except Exception:
		return

	with open(file_path, "rb") as fh:
		data = fh.read()

	# Limiter à 5 Mo (Gemini inline limit)
	if len(data) > 5 * 1024 * 1024:
		row.ia_verification = "Incertain"
		row.ia_motif = "Fichier trop volumineux pour la vérification IA (> 5 Mo)."
		return

	mime = _mime.guess_type(file_path)[0] or "application/octet-stream"
	# Gemini Vision accepte : image/jpeg, image/png, image/webp, image/heic, application/pdf
	_MIMES_OK = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "application/pdf"}
	if mime not in _MIMES_OK:
		row.ia_verification = "Incertain"
		row.ia_motif = f"Format non analysable par l'IA ({mime})."
		return

	b64_data = _b64.b64encode(data).decode()

	# ── Prompt ───────────────────────────────────────────────────────
	prompt = (
		f"Tu es un expert en conformité documentaire. Analyse ce document et réponds UNIQUEMENT "
		f"avec un JSON valide (sans markdown, sans commentaires).\n\n"
		f"Document attendu : « {row.nom_document} »\n\n"
		f"Tâches :\n"
		f"1. Détermine si ce document est bien un « {row.nom_document} » (ou un document équivalent).\n"
		f"2. Extrait les informations importantes : dates (création, expiration, signature), "
		f"noms de personnes ou d'entreprises, numéros d'identification/enregistrement, "
		f"montants, adresses, tout autre élément pertinent.\n\n"
		f"Format de réponse JSON strict :\n"
		f'{{"conforme": true/false, "confiance": 0-100, "motif": "explication courte max 80 mots", '
		f'"infos": {{"dates": [], "noms": [], "numeros": [], "autres": []}}}}'
	)

	payload = {
		"contents": [{
			"parts": [
				{"inline_data": {"mime_type": mime, "data": b64_data}},
				{"text": prompt},
			]
		}],
		"generationConfig": {
			"temperature": 0.1,
			"maxOutputTokens": 600,
			"responseMimeType": "application/json",
		},
	}

	# ── Appel API — fallback sur plusieurs modèles Vision ────────────
	_MODELS_VISION = [
		"gemini-2.5-flash-lite",
		"gemini-2.0-flash-lite",
		"gemini-2.5-flash",
		"gemini-2.0-flash",
	]
	headers = {"X-goog-api-key": api_key, "Content-Type": "application/json"}
	resp = None
	for model in _MODELS_VISION:
		url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
		resp = _requests.post(url, headers=headers, json=payload, timeout=60)
		if resp.status_code not in {404, 429, 503}:
			break

	if not resp or resp.status_code != 200:
		row.ia_verification = "Incertain"
		row.ia_motif = f"Service IA indisponible (HTTP {resp.status_code if resp else '?'})."
		return

	# ── Parser la réponse ─────────────────────────────────────────────
	try:
		text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
		result = _json.loads(text)
	except Exception:
		row.ia_verification = "Incertain"
		row.ia_motif = "Réponse IA non parseable."
		return

	conforme  = result.get("conforme", False)
	confiance = max(0, min(int(result.get("confiance", 0)), 100))
	motif     = (result.get("motif") or "")[:500]
	infos     = result.get("infos", {})

	row.ia_verification  = "Conforme" if conforme else ("Incertain" if confiance >= 40 else "Non conforme")
	row.ia_confiance     = confiance
	row.ia_motif         = motif
	row.ia_infos_extraites = _json.dumps(infos, ensure_ascii=False) if infos else ""


@frappe.whitelist()
def fournir_document_complementaire(request_name, row_name, file_url):
	"""Le client dépose un fichier contre une ligne de document complémentaire."""
	doc = frappe.get_doc("DD Request", request_name)

	# Seul le propriétaire du dossier (client) peut déposer
	if frappe.session.user != doc.owner and not frappe.has_permission("DD Request", "write"):
		frappe.throw(_("Vous n'êtes pas autorisé à déposer des documents sur ce dossier."))

	row = next((r for r in doc.documents_complementaires if r.name == row_name), None)
	if not row:
		frappe.throw(_("Ligne de document introuvable."))
	if row.statut == "Fourni":
		frappe.throw(_("Ce document a déjà été fourni."))

	row.fichier    = file_url
	row.statut     = "Fourni"
	row.date_fourni = frappe.utils.now_datetime()
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	# Vérifie si tous les docs obligatoires sont fournis
	tous_fournis = all(
		r.statut == "Fourni"
		for r in doc.documents_complementaires
		if r.obligatoire
	)
	_notifier_analyste_doc_fourni(doc, row.nom_document, tous_fournis)

	return {"tous_fournis": tous_fournis}


def _notifier_analyste_doc_fourni(doc, nom_document, tous_fournis):
	"""Notifie l'analyste (et les managers si tout est fourni) qu'un document a été déposé."""
	url_base = frappe.utils.get_url()

	if tous_fournis:
		sujet = _("Tous les documents fournis — Dossier {0} prêt pour reprise").format(doc.name)
		corps = (
			f"<p>Le client a fourni tous les documents complémentaires demandés "
			f"pour le dossier <b>{doc.name}</b> ({doc.tiers_nom or '—'}).</p>"
			f"<p>Vous pouvez reprendre l'analyse.</p>"
			f"<p><a href='{url_base}/app/dd-request/{doc.name}' "
			f"style='background:#16a34a;color:#fff;padding:10px 22px;"
			f"border-radius:6px;text-decoration:none;font-weight:600;'>"
			f"Reprendre l'analyse →</a></p>"
		)
		# Notifier l'analyste + les managers compliance
		destinataires = []
		if doc.analyste_assigne:
			destinataires.append(doc.analyste_assigne)
		managers = frappe.get_all(
			"Has Role",
			filters={"role": "DD Manager Compliance", "parenttype": "User"},
			pluck="parent",
		)
		destinataires += frappe.get_all(
			"User", filters={"name": ["in", managers], "enabled": 1}, pluck="name"
		) if managers else []
	else:
		sujet = _("Document fourni — Dossier {0} · {1}").format(doc.name, nom_document)
		corps = (
			f"<p>Le client a déposé le document <b>{nom_document}</b> "
			f"sur le dossier <b>{doc.name}</b> ({doc.tiers_nom or '—'}).</p>"
			f"<p>Des documents restent encore en attente.</p>"
			f"<p><a href='{url_base}/app/dd-request/{doc.name}' "
			f"style='background:#0d1b2a;color:#fff;padding:10px 22px;"
			f"border-radius:6px;text-decoration:none;font-weight:600;'>"
			f"Voir le dossier →</a></p>"
		)
		destinataires = [doc.analyste_assigne] if doc.analyste_assigne else []

	for user in destinataires:
		try:
			frappe.get_doc({
				"doctype":       "Notification Log",
				"subject":       sujet,
				"email_content": corps,
				"for_user":      user,
				"from_user":     "Administrator",
				"document_type": "DD Request",
				"document_name": doc.name,
				"type":          "Alert",
			}).insert(ignore_permissions=True)
			frappe.publish_realtime("notification", after_commit=True, user=user)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"DD — notif analyste doc fourni {user}")

	if destinataires:
		try:
			frappe.sendmail(recipients=destinataires, subject=sujet, message=corps, now=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "DD — email analyste doc fourni")


@frappe.whitelist()
def get_dd_clients(doctype, txt, searchfield, start, page_len, filters):
	"""Retourne les utilisateurs actifs ayant le rôle DD Client (pour le champ client_user)."""
	return frappe.db.sql(
		"""
		SELECT u.name, u.full_name
		FROM `tabUser` u
		INNER JOIN `tabHas Role` r ON r.parent = u.name AND r.parenttype = 'User'
		WHERE r.role = 'DD Client'
		  AND u.enabled = 1
		  AND (u.name LIKE %(txt)s OR u.full_name LIKE %(txt)s)
		ORDER BY u.full_name
		LIMIT %(page_len)s OFFSET %(start)s
		""",
		{"txt": f"%{txt}%", "page_len": int(page_len), "start": int(start)},
	)


def _emails_role(role):
	"""Retourne la liste des emails des utilisateurs actifs ayant ce rôle."""
	users = frappe.get_all(
		"Has Role",
		filters={"role": role, "parenttype": "User"},
		pluck="parent",
	)
	if not users:
		return []
	return frappe.get_all(
		"User",
		filters={"name": ["in", users], "enabled": 1},
		pluck="email",
	)
