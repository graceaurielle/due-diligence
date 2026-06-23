frappe.ui.form.on("DD Request", {
	onload(frm) {
		frm.set_query("client_user", () => ({
			query: "due_diligence.due_diligence.doctype.dd_request.dd_request.get_dd_clients",
		}));

		// Auto-remplir Nom du demandeur et Email depuis le profil de l'utilisateur connecté
		if (frm.is_new() && !frappe.user.has_role("DD Client")) {
			frappe.db.get_value("User", frappe.session.user, ["full_name", "email"], (r) => {
				if (r) {
					if (!frm.doc.demandeur_nom && r.full_name) frm.set_value("demandeur_nom", r.full_name);
					if (!frm.doc.email_contact && r.email)     frm.set_value("email_contact", r.email);
				}
			});
		}
	},

	client_user(frm) {
		// Auto-remplir demandeur_nom depuis le profil du client sélectionné
		if (frm.doc.client_user && !frappe.user.has_role("DD Client")) {
			frappe.db.get_value("User", frm.doc.client_user, "full_name", (r) => {
				if (r && r.full_name && !frm.doc.demandeur_nom) {
					frm.set_value("demandeur_nom", r.full_name);
				}
			});
		}
	},

	after_save(frm) {
		// Après 1er enregistrement par un interne sans client assigné → demander le client
		if (!frappe.user.has_role("DD Client") && !frm.doc.client_user) {
			const d = new frappe.ui.Dialog({
				title: __("Assigner ce dossier à un client"),
				fields: [{
					label: __("Client (utilisateur DD Client)"),
					fieldname: "client_user",
					fieldtype: "Link",
					options: "User",
					get_query: () => ({
						query: "frappe.core.doctype.user.user.user_query",
						filters: { role: "DD Client" },
					}),
					reqd: 1,
					description: __("Le client sélectionné pourra compléter ce dossier depuis le portail."),
				}],
				primary_action_label: __("Assigner"),
				primary_action(values) {
					frappe.call({
						method: "frappe.client.set_value",
						args: {
							doctype: "DD Request",
							name: frm.doc.name,
							fieldname: "client_user",
							value: values.client_user,
						},
						callback() {
							d.hide();
							frm.reload_doc();
							frappe.show_alert({
								message: __("Dossier assigné à {0}. Le client peut maintenant le compléter.", [values.client_user]),
								indicator: "green",
							});
						},
					});
				},
			});
			d.show();
		}
	},

	refresh(frm) {
		// ── Visibilité des sections selon rôle et état ──────────────────
		const isInterne = !frappe.user.has_role("DD Client");
		const isBrouillon = frm.doc.docstatus === 0;

		if (isInterne && isBrouillon) {
			// Sections que le CLIENT remplit sur le portail : cachées pour l'interne en brouillon
			const champsClientCaches = [
				// Tiers évalué (garder client_user visible, cacher les détails)
				"tiers_nom", "tiers_nom_commercial", "tiers_rccm", "tiers_nif",
				"tiers_forme_juridique", "tiers_date_creation", "tiers_pays", "cb_tiers",
				"tiers_adresse_siege", "tiers_pays_activites", "tiers_filiales_internationales", "tiers_appartient_groupe",
				// Identification opérationnelle
				"sb_id_operationnelle", "tiers_secteur", "tiers_description_activites", "tiers_nb_employes",
				"cb_id_operationnelle", "tiers_principaux_clients", "tiers_marches_geographiques",
				"tiers_secteurs_reglementes", "interaction_publique", "donnees_personnelles", "acces_si",
				// Identification capitalistique
				"sb_id_capitalistique", "tiers_actionnaires_principaux", "tiers_beneficiaires_effectifs",
				"tiers_structure_actionnariat", "tiers_actionnaires_pep", "cb_id_capitalistique",
				"tiers_responsables_publics_participations", "tiers_detenu_etat", "tiers_structures_offshore", "tiers_trusts_holdings",
				// Risque géopolitique
				"sb_risque_pays", "tiers_pays_risque_detecte", "tiers_nature_operations_pays_risque",
				"tiers_flux_financiers_internationaux", "tiers_licences_reglementaires",
				"tiers_relations_entites_publiques_locales", "tiers_risques_sanctions_secondaires",
				"tiers_figure_listes_sanctions", "tiers_paiements_offshore",
				// Questionnaire & documents
				"sb_questionnaire", "answers", "sb_documents", "required_documents",
				// Scoring & équipe (toujours cachées en brouillon)
				"sb_evaluation", "score_brut", "score_pondere", "score_residuel", "score_reputationnel",
				"resume_reputationnel", "sb_cyber_p2", "tiers_sans_mfa", "tiers_sans_pra_pca",
				"tiers_incident_cyber", "cb_cyber_p2", "tiers_donnees_biometriques", "tiers_violation_rgpd",
				"tiers_dpo_absent", "sb_attenuants", "tiers_certif_iso27001", "tiers_certif_iso37001",
				"tiers_audit_big4", "cb_attenuants", "tiers_garantie_bancaire", "tiers_etats_certifies",
				"tiers_solvabilite_forte", "categorie_risque", "justification_score_manuel", "detail_scoring",
				"sb_score_history", "score_history", "circuit_workflow", "date_echeance_sla", "sla_depasse",
				"niveau_escalade", "sb_decision", "decision_finale", "reserves", "cb_decision", "date_decision",
				"sb_workflow_steps", "workflow_steps", "sb_workflow_events", "workflow_events",
				"cb_evaluation", "analyste_assigne", "commentaire_interne", "sb_avis",
			];
			champsClientCaches.forEach(f => frm.toggle_display(f, false));

			// Bannière si pas encore de client assigné
			if (!frm.doc.client_user) {
				frm.dashboard.add_comment(
					__("Ce dossier n'est pas encore assigné à un client. Enregistrez pour choisir le client."),
					"yellow", true
				);
			} else {
				frm.dashboard.add_comment(
					__("Dossier assigné à {0} — en attente de complétion sur le portail client.", [frm.doc.client_user]),
					"blue", true
				);
			}
		}

		// Empêcher l'ajout/suppression de lignes dans le circuit de traitement
		if (frm.doc.docstatus === 1 && frm.fields_dict.workflow_steps) {
			const grid = frm.get_field("workflow_steps").grid;
			grid.cannot_add_rows = true;
			grid.cannot_delete_rows = true;
			grid.refresh();
		}

		const etatsAvis = [
			"En validation Manager",
			"En validation Direction",
			"Clôturé — GO",
			"Clôturé — NO GO",
			"Clôturé — GO sous réserve",
		];
		const rolesAutorises = [
			"DD Analyste",
			"DD Manager Compliance",
			"DD Validateur",
			"System Manager",
		];

		const peutGenerer = rolesAutorises.some(r => frappe.user.has_role(r));
		const etatValide = etatsAvis.includes(frm.doc.workflow_state);

		if (peutGenerer && etatValide) {
			frm.add_custom_button(__("Générer l'avis"), function () {
				frappe.call({
					method: "due_diligence.due_diligence.doctype.dd_request.dd_request.creer_avis_depuis_dossier",
					args: { dd_request_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Création de l'avis en cours…"),
					callback(r) {
						if (r.message) {
							const { avis, existe } = r.message;
							if (existe) {
								frappe.msgprint({
									title: __("Avis existant"),
									message: __("Un avis existe déjà pour ce dossier : {0}", [avis]),
									indicator: "orange",
								});
							}
							frappe.set_route("Form", "DD Avis Compliance", avis);
						}
					},
				});
			}, __("Compliance"));
		}

		if (peutGenerer) {
			frm.add_custom_button(__("Générer l'avis IA"), function () {
				frappe.confirm(
					__("Générer l'avis de l'IA pour ce dossier ? L'avis existant sera écrasé."),
					function () {
						frappe.call({
							method: "due_diligence.due_diligence.doctype.dd_request.dd_request.generer_avis_ia",
							args: { dd_request_name: frm.doc.name },
							freeze: true,
							freeze_message: __("Génération de l'avis IA en cours…"),
							callback(r) {
								if (r.message) {
									frm.set_value("avis_ia", r.message);
									frappe.show_alert({ message: __("Avis IA généré avec succès."), indicator: "green" });
								}
							},
						});
					}
				);
			}, __("Compliance"));
		}

		// Badge écart score
		if (frm.doc.score_humain && frm.doc.ecart_score >= 20) {
			frm.dashboard.add_comment(
				__("⚠ Écart de {0} points entre le score IA ({1}) et le score analyste ({2}).",
					[frm.doc.ecart_score, frm.doc.score_residuel, frm.doc.score_humain]),
				"orange",
				true
			);
		}
	},

	score_humain(frm) {
		const ecart = Math.abs((frm.doc.score_residuel || 0) - (frm.doc.score_humain || 0));
		frm.set_value("ecart_score", ecart);
	},
});
