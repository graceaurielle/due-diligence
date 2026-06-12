frappe.ui.form.on("DD Request", {
	refresh(frm) {
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
