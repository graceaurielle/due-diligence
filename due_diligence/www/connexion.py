import frappe

no_cache = 1


def get_context(context):
    if frappe.session.user != "Guest":
        frappe.local.flags.redirect_location = "/mes-demandes"
        raise frappe.Redirect

    redirect_to = frappe.form_dict.get("redirect-to", "/mes-demandes")

    context.update({
        "title": "Connexion — AMOAMAN & ASSOCIÉS",
        "redirect_to": redirect_to,
    })
