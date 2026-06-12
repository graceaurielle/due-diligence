import frappe

login_required = True
no_cache = 1


def get_context(context):
    context.dd_types = []
    context.countries = []
    context.user_fullname = ""
    context.user_email = ""
    context.active_page = "nouvelle-demande"
    context.title = "Nouvelle Due Diligence — AMOAMAN & ASSOCIÉS"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/connexion?redirect-to=/nouvelle-demande"
        raise frappe.Redirect

    user_doc = frappe.get_doc("User", frappe.session.user)
    context.user_fullname = user_doc.full_name or ""
    context.user_email = user_doc.email or ""

    context.dd_types = frappe.get_all(
        "DD Type",
        filters={"actif": 1},
        fields=["name", "type_name", "criticite_moyenne", "description_metier"],
        order_by="criticite_moyenne asc, type_name asc",
        ignore_permissions=True,
    )
    context.countries = frappe.get_all(
        "Country",
        fields=["name", "country_name"],
        order_by="country_name asc",
        ignore_permissions=True,
    )
