import frappe

login_required = True
no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/connexion"
        raise frappe.Redirect

    user = frappe.session.user
    roles = set(frappe.get_roles(user))

    _ROLES_EQUIPE = frozenset({
        "DD Analyste", "DD Manager Compliance", "DD Validateur",
        "DD Cyber", "DD DPO", "DD Financier", "DD Juridique",
        "System Manager",
    })

    if roles & _ROLES_EQUIPE:
        # L'équipe voit tous les avis soumis
        avis_list = frappe.get_all(
            "DD Avis Compliance",
            filters={"docstatus": 1},
            fields=["name", "dd_request", "tiers_nom", "client_nom", "decision",
                    "date_decision", "categorie_risque", "date_expiration"],
            order_by="date_decision desc",
            ignore_permissions=True,
        )
    else:
        # DD Client : uniquement les avis soumis sur ses propres dossiers
        mes_dossiers = frappe.get_all(
            "DD Request",
            filters={"owner": user},
            pluck="name",
            ignore_permissions=True,
        )
        if not mes_dossiers:
            avis_list = []
        else:
            avis_list = frappe.get_all(
                "DD Avis Compliance",
                filters={"docstatus": 1, "dd_request": ["in", mes_dossiers]},
                fields=["name", "dd_request", "tiers_nom", "client_nom", "decision",
                        "date_decision", "categorie_risque", "date_expiration"],
                order_by="date_decision desc",
                ignore_permissions=True,
            )

    context.update({
        "avis_list": avis_list,
        "active_page": "mes-avis",
        "title": "Mes avis — AMOAMAN & ASSOCIÉS",
    })
