import frappe
from datetime import datetime, timedelta
import calendar

login_required = True
no_cache = 1


def get_context(context):
    context.active_page = "tableau-de-bord"
    context.title = "Tableau de Bord — AMOAMAN & ASSOCIÉS"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/connexion"
        raise frappe.Redirect

    user = frappe.session.user
    roles = frappe.get_roles(user)
    is_analyst = any(r in roles for r in ("DD Analyste", "DD Manager Compliance", "Administrator"))

    # Scope: analystes voient tout, utilisateurs standard voient le leur
    filters = {} if is_analyst else {"owner": user}

    requests = frappe.get_all(
        "DD Request",
        filters=filters,
        fields=["name", "tiers_nom", "dd_type", "workflow_state", "creation",
                "categorie_risque", "docstatus", "modified"],
        order_by="modified desc",
        page_length=500,
        ignore_permissions=True,
    )

    total = len(requests)

    # --- Distribution par statut ---
    etats_en_cours = {"Soumis", "En préqualification", "En analyse Compliance",
                      "En validation Manager", "En validation Direction"}
    etats_attente = {"En attente de documents"}
    etats_go = {"Clôturé — GO", "Clôturé — GO sous réserve"}
    etats_nogo = {"Clôturé — NO GO"}

    cnt_en_cours = sum(1 for r in requests if r.workflow_state in etats_en_cours)
    cnt_attente = sum(1 for r in requests if r.workflow_state in etats_attente)
    cnt_go = sum(1 for r in requests if r.workflow_state in etats_go)
    cnt_nogo = sum(1 for r in requests if r.workflow_state in etats_nogo)
    cnt_brouillon = total - cnt_en_cours - cnt_attente - cnt_go - cnt_nogo

    def pct(n):
        return round(n * 100 / total) if total else 0

    dist = [
        {"label": "En cours", "count": cnt_en_cours, "pct": pct(cnt_en_cours), "color": "#2563eb"},
        {"label": "En attente", "count": cnt_attente, "pct": pct(cnt_attente), "color": "#d97706"},
        {"label": "Clôturé GO", "count": cnt_go, "pct": pct(cnt_go), "color": "#16a34a"},
        {"label": "Clôturé NO GO", "count": cnt_nogo, "pct": pct(cnt_nogo), "color": "#dc2626"},
        {"label": "Brouillon", "count": cnt_brouillon, "pct": pct(cnt_brouillon), "color": "#94a3b8"},
    ]
    dist = [d for d in dist if d["count"] > 0]

    # --- Volume par mois (6 derniers mois) ---
    today = datetime.today()
    months = []
    for i in range(5, -1, -1):
        d = today.replace(day=1) - timedelta(days=1)
        for _ in range(i):
            d = d.replace(day=1) - timedelta(days=1)
        first = datetime(today.year, today.month, 1) - timedelta(days=30 * i)
        first = first.replace(day=1)
        last_day = calendar.monthrange(first.year, first.month)[1]
        months.append({
            "label": first.strftime("%b").upper(),
            "year": first.year,
            "month": first.month,
            "count": 0,
        })

    for r in requests:
        try:
            d = r.creation if isinstance(r.creation, datetime) else datetime.fromisoformat(str(r.creation))
            for m in months:
                if m["year"] == d.year and m["month"] == d.month:
                    m["count"] += 1
        except Exception:
            pass

    max_vol = max((m["count"] for m in months), default=1) or 1

    # Variation vs mois précédent
    last_count = months[-2]["count"] if len(months) >= 2 else 0
    curr_count = months[-1]["count"]
    if last_count > 0:
        variation = round((curr_count - last_count) / last_count * 100)
    elif curr_count > 0:
        variation = 100
    else:
        variation = 0

    # --- Risques ---
    cnt_faible = sum(1 for r in requests if (r.categorie_risque or "").lower() in ("faible", ""))
    cnt_modere = sum(1 for r in requests if (r.categorie_risque or "").lower() == "modéré")
    cnt_eleve = sum(1 for r in requests if (r.categorie_risque or "").lower() in ("élevé", "eleve", "élevé"))
    cnt_critique = sum(1 for r in requests if (r.categorie_risque or "").lower() == "critique")

    pct_faible = pct(cnt_faible)
    pct_modere = pct(cnt_modere)
    pct_eleve = pct(cnt_eleve)
    pct_critique = pct(cnt_critique)

    # Score de conformité fictif basé sur la proportion GO
    total_clos = cnt_go + cnt_nogo
    score_conformite = round(cnt_go * 100 / total_clos) if total_clos > 0 else None

    # --- Derniers dossiers (table) ---
    recents = requests[:10]

    context.update({
        "total": total,
        "is_analyst": is_analyst,
        "dist": dist,
        "months": months,
        "max_vol": max_vol,
        "variation": variation,
        "cnt_faible": cnt_faible, "pct_faible": pct_faible,
        "cnt_modere": cnt_modere, "pct_modere": pct_modere,
        "cnt_eleve": cnt_eleve, "pct_eleve": pct_eleve,
        "cnt_critique": cnt_critique, "pct_critique": pct_critique,
        "score_conformite": score_conformite,
        "cnt_en_cours": cnt_en_cours,
        "cnt_go": cnt_go,
        "cnt_nogo": cnt_nogo,
        "recents": recents,
    })
