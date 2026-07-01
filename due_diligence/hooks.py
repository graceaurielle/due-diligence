app_name = "due_diligence"
app_title = "Due Diligence"
app_publisher = "grace atse"
app_description = "application pour la gestion des due-diligence"
app_email = "gatse007@gmail.com"
app_license = "mit"

# Fixtures — exportées/importées via bench migrate
# Ordre important : States & Actions avant Workflow (contraintes FK)
# Phase 1 : DD Type (13 types seeds)
# Phase 2 : Role (8 rôles DD)
# Phase 3 : Workflow State, Workflow Action Master, Workflow
# Phase 6 : Print Format
# Phase 7 : Notification
fixtures = [
	{"dt": "DD Type", "filters": []},
	{
		"dt": "Role",
		"filters": [["role_name", "in", [
			"DD Client", "DD Analyste", "DD Manager Compliance", "DD Validateur",
			"DD Juridique", "DD DPO", "DD Cyber", "DD Financier",
			"DD RSSI", "DD CCO", "DD DG", "DD Manager Metier",
		]]]
	},
	{
		"dt": "Workflow State",
		"filters": [["workflow_state_name", "in", [
			"Brouillon", "Soumis", "En préqualification",
			"En screening réglementaire", "En analyse Compliance",
			"En analyse financière", "En revue juridique",
			"En revue cybersécurité", "En revue DPO",
			"En attente de documents", "En attente validation métier",
			"En attente validation Manager", "En attente validation Compliance",
			"En attente validation CCO", "En attente validation DG",
			"En validation Manager", "En validation Direction",
			"Escaladé", "Suspendu",
			"Clôturé — GO", "Clôturé — NO GO", "Clôturé — GO sous réserve",
			"Rejeté", "Accepté", "Accepté sous réserve",
			"Clôturé", "Sous surveillance continue",
		]]]
	},
	{
		"dt": "Workflow Action Master",
		"filters": [["workflow_action_name", "in", [
			"Soumettre le dossier", "Prendre en préqualification",
			"Bloquer — tiers sanctionné",
			"Démarrer l'analyse", "Démarrer le screening réglementaire",
			"Passer en analyse Compliance",
			"Demander des documents complémentaires", "Reprendre l'analyse",
			"Envoyer en analyse financière",
			"Envoyer en revue cybersécurité", "Envoyer en revue juridique", "Envoyer en revue DPO",
			"Envoyer en validation métier", "Envoyer en validation Compliance",
			"Envoyer en validation CCO", "Envoyer en validation DG",
			"Valider — GO", "Valider — NO GO", "Valider — GO sous réserve",
			"Mettre sous surveillance", "Suspendre le dossier", "Reprendre le dossier",
		]]]
	},
	{
		"dt": "Workflow",
		"filters": [["name", "=", "Due Diligence Workflow"]]
	},
	{
		"dt": "Print Format",
		"filters": [["name", "=", "Avis Compliance"]]
	},
	{"dt": "DD Section", "filters": []},
	{"dt": "DD Question", "filters": []},
	{
		"dt": "Notification",
		"filters": [["name", "in", [
			"DD - Nouveau dossier soumis",
			"DD - Documents supplémentaires requis",
			"DD - Dossier clôturé avis disponible",
			"DD - En attente de validation Manager",
		]]]
	},
	# Phase 8 : Custom DocPerm — lecture du DocType Workflow pour les rôles DD
	# (workflow.js lit Workflow via frappe.db.get_value pour vérifier enable_action_confirmation)
	{
		"dt": "Custom DocPerm",
		"filters": [["parent", "=", "Workflow"]]
	},
]

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "due_diligence",
# 		"logo": "/assets/due_diligence/logo.png",
# 		"title": "Due Diligence",
# 		"route": "/due_diligence",
# 		"has_permission": "due_diligence.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/due_diligence/css/due_diligence.css"
app_include_js = "/assets/due_diligence/js/desk.js"

# include js, css files in header of web template
# web_include_css = "/assets/due_diligence/css/due_diligence.css"
# web_include_js = "/assets/due_diligence/js/due_diligence.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "due_diligence/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "due_diligence/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "due_diligence.utils.jinja_methods",
# 	"filters": "due_diligence.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "due_diligence.install.before_install"
# after_install = "due_diligence.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "due_diligence.uninstall.before_uninstall"
# after_uninstall = "due_diligence.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "due_diligence.utils.before_app_install"
# after_app_install = "due_diligence.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "due_diligence.utils.before_app_uninstall"
# after_app_uninstall = "due_diligence.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "due_diligence.notifications.get_notification_config"

# Permissions
# -----------
# DD Client ne voit que ses propres DD Request (portail + desk)
permission_query_conditions = {
	"DD Request": "due_diligence.permissions.get_permission_query_conditions",
}

# Portail web : vérifie que le visiteur est bien le owner du dossier
has_website_permission = {
	"DD Request": "due_diligence.permissions.has_website_permission",
}

# Desk : DD Analyste (et rôles spécialistes) ne peut écrire que sur ses dossiers assignés
has_permission = {
	"DD Request": "due_diligence.permissions.has_permission",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"DD Request": {
		# Extension : OCR, screening AML/PEP, e-signature — non implémenté MVP
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		# Vérification SLA toutes les 4 heures
		"0 */4 * * *": [
			"due_diligence.due_diligence.tasks.verifier_sla_workflows",
		],
	},
}

# Testing
# -------

# before_tests = "due_diligence.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "due_diligence.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "due_diligence.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "due_diligence.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["due_diligence.utils.before_request"]
# after_request = ["due_diligence.utils.after_request"]

# Job Events
# ----------
# before_job = ["due_diligence.utils.before_job"]
# after_job = ["due_diligence.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"due_diligence.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

