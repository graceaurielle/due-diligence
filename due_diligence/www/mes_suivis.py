import frappe

login_required = True
no_cache = 1

_ETAPES = [
    ("Soumis", "Soumis"),
    ("En préqualification", "Préqualif."),
    ("En analyse Compliance", "Compliance"),
    ("En validation Manager", "Validation"),
    ("En validation Direction", "Direction"),
]
_ETATS_CLOS = {"Clôturé — GO", "Clôturé — NO GO", "Clôturé — GO sous réserve"}


def get_context(context):
    context.requests = []
    context.active_page = "mes-suivis"
    context.title = "Suivi des dossiers — AMOAMAN & ASSOCIÉS"
    context.kpi_en_cours = 0
    context.kpi_attente = 0
    context.kpi_clotures = 0
    context.kpi_total = 0

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/connexion"
        raise frappe.Redirect

    user = frappe.session.user

    requests_raw = frappe.get_all(
        "DD Request",
        filters={"owner": user},
        fields=["name", "tiers_nom", "dd_type", "workflow_state", "creation",
                "categorie_risque", "decision_finale", "analyste_assigne"],
        order_by="creation desc",
        page_length=100,
        ignore_permissions=True,
    )

    etats_en_cours = {"Soumis", "En préqualification", "En analyse Compliance",
                      "En validation Manager", "En validation Direction"}
    etats_attente = {"En attente de documents"}

    result = []
    for r in requests_raw:
        etat = r.workflow_state or "Brouillon"
        is_clos = etat in _ETATS_CLOS
        is_attente = etat in etats_attente

        idx_actuel = None
        labels = [e[0] for e in _ETAPES]
        if etat in labels:
            idx_actuel = labels.index(etat)
        elif is_clos or is_attente:
            idx_actuel = len(_ETAPES)

        steps = []
        for i, (full, short) in enumerate(_ETAPES):
            if idx_actuel is not None and i < idx_actuel:
                statut = "done"
            elif idx_actuel is not None and i == idx_actuel:
                statut = "active"
            else:
                statut = "pending"
            steps.append({"label": full, "short": short, "statut": statut})

        if idx_actuel is None:
            progress = 0
        elif is_clos or idx_actuel >= len(_ETAPES):
            progress = 100
        else:
            progress = int(((idx_actuel + 0.5) / len(_ETAPES)) * 100)

        r["etat"] = etat
        r["is_clos"] = is_clos
        r["is_attente"] = is_attente
        r["steps"] = steps
        r["progress"] = progress
        result.append(r)

    context.requests = result
    context.kpi_total = len(result)
    context.kpi_en_cours = sum(1 for r in result if r["etat"] in etats_en_cours)
    context.kpi_attente = sum(1 for r in result if r["is_attente"])
    context.kpi_clotures = sum(1 for r in result if r["is_clos"])
