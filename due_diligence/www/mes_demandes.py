import frappe

login_required = True
no_cache = 1


def get_context(context):
    # Valeurs par défaut toujours présentes — évite tout UndefinedError Jinja
    context.requests = []
    context.kpi_en_cours = 0
    context.kpi_attente = 0
    context.kpi_clotures = 0
    context.active_page = "mes-demandes"
    context.title = "Mes demandes — AMOAMAN & ASSOCIÉS"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/connexion?redirect-to=/mes-demandes"
        raise frappe.Redirect

    user = frappe.session.user

    etats_en_cours = {"Soumis", "En préqualification", "En analyse Compliance",
                      "En validation Manager", "En validation Direction"}
    etats_attente = {"En attente de documents"}
    etats_clotures = {"Clôturé — GO", "Clôturé — NO GO", "Clôturé — GO sous réserve"}

    requests = frappe.get_all(
        "DD Request",
        filters={"client_user": user},
        fields=["name", "tiers_nom", "dd_type", "workflow_state", "creation", "categorie_risque", "docstatus"],
        order_by="creation desc",
        page_length=100,
        ignore_permissions=True,
    )

    context.requests = requests
    context.kpi_en_cours = sum(1 for r in requests if r.workflow_state in etats_en_cours)
    context.kpi_attente = sum(1 for r in requests if r.workflow_state in etats_attente)
    context.kpi_clotures = sum(1 for r in requests if r.workflow_state in etats_clotures)
