import frappe

login_required = True
no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/connexion"
        raise frappe.Redirect

    name = frappe.form_dict.get("name", "")
    doc = None
    if name:
        try:
            doc = frappe.get_doc("DD Request", name, ignore_permissions=True)
        except frappe.DoesNotExistError:
            doc = None
        else:
            from due_diligence.permissions import has_website_permission
            if not has_website_permission(doc, "read", frappe.session.user):
                doc = None

    context.update({
        "doc": doc,
        "active_page": "mes-demandes",
        "title": "Demande soumise — AMOAMAN & ASSOCIÉS",
    })
