import frappe

_ROLES_EQUIPE = frozenset({
	"DD Analyste", "DD Manager Compliance", "DD Validateur",
	"DD Cyber", "DD DPO", "DD Financier", "DD Juridique",
	"System Manager",
})

# Rôles qui peuvent agir sur TOUS les dossiers (supervision)
_ROLES_SUPERIEURS = frozenset({
	"DD Manager Compliance", "DD Validateur", "System Manager",
})

# Rôles spécialistes qui ne peuvent écrire que sur leurs dossiers assignés
_ROLES_ANALYSTES = frozenset({
	"DD Analyste", "DD Cyber", "DD DPO", "DD Financier", "DD Juridique",
})


def has_permission(doc, ptype, user):
	"""Desk : contrôle d'accès en écriture par analyste assigné.
	- Managers / Validateurs / System Manager : accès complet.
	- DD Analyste et rôles spécialistes : lecture sur tout, écriture uniquement
	  sur les dossiers où ils sont analyste_assigne (ou dossier non encore assigné).
	- DD Client : lecture uniquement sur ses propres dossiers (via portal).
	"""
	if not user:
		user = frappe.session.user

	roles = set(frappe.get_roles(user))

	# System Manager et rôles de supervision → accès complet
	if roles & _ROLES_SUPERIEURS:
		return True

	# Rôles analystes / spécialistes
	if roles & _ROLES_ANALYSTES:
		# Lecture toujours autorisée
		if ptype == "read":
			return True
		# Écriture / actions : uniquement si assigné ou dossier non encore assigné
		analyste = doc.get("analyste_assigne") if hasattr(doc, "get") else getattr(doc, "analyste_assigne", None)
		return not analyste or analyste == user

	# DD Client : lecture uniquement sur ses dossiers (desk ne devrait pas s'appliquer)
	if "DD Client" in roles:
		if ptype == "read":
			return doc.get("client_user") == user if hasattr(doc, "get") else getattr(doc, "client_user", None) == user
		return False

	# Autres rôles → laisser Frappe décider via les permissions de rôle standard
	return None


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
