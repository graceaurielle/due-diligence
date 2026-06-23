import frappe

_ROLES_EQUIPE = frozenset({
	"DD Analyste", "DD Manager Compliance", "DD Validateur",
	"DD Cyber", "DD DPO", "DD Financier", "DD Juridique",
	"System Manager",
})


def has_website_permission(doc, ptype, user, verbose=False):
	"""Portail : équipe AMOAMAN voit tout, Website Users uniquement leurs dossiers."""
	if not user:
		user = frappe.session.user

	# Équipe AMOAMAN (tous rôles DD + System Manager/User) → accès complet
	if set(frappe.get_roles(user)) & _ROLES_EQUIPE:
		return True
	if frappe.db.get_value("User", user, "user_type") == "System User":
		return True

	# Website Users (DD Client) → uniquement les dossiers qui leur sont assignés (client_user)
	return doc.client_user == user


def get_permission_query_conditions(user):
	"""Filtre liste DD Request : DD Client ne voit que les dossiers où il est le client assigné.
	Les rôles d'équipe (analyste, manager…) et System Manager voient tout."""
	if not user:
		user = frappe.session.user

	roles = set(frappe.get_roles(user))

	if roles & _ROLES_EQUIPE:
		return ""

	if "DD Client" in roles:
		return "`tabDD Request`.`client_user` = {user}".format(
			user=frappe.db.escape(user)
		)

	return ""
