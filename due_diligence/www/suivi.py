import frappe

login_required = True
no_cache = 1

_ETAPES = [
    "Soumis",
    "En préqualification",
    "En analyse Compliance",
    "En validation Manager",
    "En validation Direction",
]
_ETATS_CLOS = {"Clôturé — GO", "Clôturé — NO GO", "Clôturé — GO sous réserve"}


def get_context(context):
    context.doc = None
    context.etat = ""
    context.is_clos = False
    context.etapes_etat = []
    context.active_page = "mes-suivis"
    context.title = "Suivi — AMOAMAN & ASSOCIÉS"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/connexion"
        raise frappe.Redirect

    name = frappe.form_dict.get("name", "")
    if not name:
        frappe.local.flags.redirect_location = "/mes-demandes"
        raise frappe.Redirect

    try:
        doc = frappe.get_doc("DD Request", name, ignore_permissions=True)
    except frappe.DoesNotExistError:
        frappe.local.flags.redirect_location = "/mes-demandes"
        raise frappe.Redirect

    # Vérification d'accès explicite : le hook has_website_permission n'est pas
    # appelé automatiquement par frappe.get_doc() dans un contrôleur de page portail.
    from due_diligence.permissions import has_website_permission
    if not has_website_permission(doc, "read", frappe.session.user):
        frappe.local.flags.redirect_location = "/mes-demandes"
        raise frappe.Redirect

    etat = doc.workflow_state or "Brouillon"
    is_clos = etat in _ETATS_CLOS

    # Timeline : marque les étapes passées
    etapes_etat = []
    idx_actuel = None
    if etat in _ETAPES:
        idx_actuel = _ETAPES.index(etat)
    elif is_clos:
        idx_actuel = len(_ETAPES)  # après toutes les étapes

    for i, e in enumerate(_ETAPES):
        if idx_actuel is not None and i < idx_actuel:
            statut = "done"
        elif idx_actuel is not None and i == idx_actuel:
            statut = "active"
        else:
            statut = "pending"
        etapes_etat.append({"label": e, "statut": statut})

    avis = None
    if is_clos:
        avis = frappe.db.get_value(
            "DD Avis Compliance",
            {"dd_request": name, "docstatus": 1},
            ["name", "decision", "date_decision", "reserves", "recommandations"],
            as_dict=True,
        )

    context.update({
        "doc": doc,
        "etat": etat,
        "is_clos": is_clos,
        "etapes_etat": etapes_etat,
        "avis": avis,
        "active_page": "mes-suivis",
        "title": f"Suivi — {doc.tiers_nom} — AMOAMAN & ASSOCIÉS",
    })
