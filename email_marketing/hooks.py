from . import __version__ as app_version

app_name = "email_marketing"
app_title = "Email Marketing"
app_publisher = "RS"
app_description = "Email Marketing"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "beratung@royal-software.de"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/email_marketing/css/email_marketing.css"
# app_include_js = "/assets/email_marketing/js/email_marketing.js"
app_include_js = "/assets/email_marketing/js/communication_ext.js"

# include js, css files in header of web template
# web_include_css = "/assets/email_marketing/css/email_marketing.css"
# web_include_js = "/assets/email_marketing/js/email_marketing.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "email_marketing/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Email Template" : "email_marketing/custom/email_template.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "email_marketing.install.before_install"
# after_install = "email_marketing.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "email_marketing.uninstall.before_uninstall"
# after_uninstall = "email_marketing.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "email_marketing.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"Email Template": "email_marketing.overrides.EmailTemplate",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"all": [
		"email_marketing.tasks.email_account.notify_unreplied",
	],
# 	"daily": [
# 		"email_marketing.tasks.daily"
# 	],
	"hourly": [
		"email_marketing.tasks.process_active_campaigns"
	],
# 	"weekly": [
# 		"email_marketing.tasks.weekly"
# 	]
# 	"monthly": [
# 		"email_marketing.tasks.monthly"
# 	]
}

# Testing
# -------

# before_tests = "email_marketing.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"frappe.email.doctype.email_template.email_template.get_email_template": "email_marketing.overrides.get_email_template"
}

#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "email_marketing.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


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
# 	"email_marketing.auth.validate"
# ]


# jinja extensions
# --------------------------------

# jenv_customization
jenv = {
	'methods': [
		'rs_salutation:email_marketing.email_marketing.salutation.rs_salutation',
		'rs_salutation_for_doc:email_marketing.email_marketing.salutation.rs_salutation_for_doc',
		'rs_target_contact_for_doc:email_marketing.email_marketing.sequenced_address_determination.target_contact_name_for_doc',
		'rs_year_from_date:email_marketing.email_marketing.jinja_generic_helpers.year_from_date'
	]
}
