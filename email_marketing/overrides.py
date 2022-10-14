import json
from six import string_types
import frappe
# import frappe.email.doctype.email_template as orig_email_template
from frappe.email.doctype.email_template.email_template import get_email_template as orig_get_email_template

@frappe.whitelist()
def get_email_template(template_name, doc, different_sender=None, different_sender_name=None):
	"""
	Injects into the email template rendering to:
	- apply further variables (different_sender + _name)
	- apply a signature, if it is defined in the email template.
	"""
	if isinstance(doc, string_types):
		doc = json.loads(doc)

	# initialize additional properties (at least with empty string, if nothing is set)
	doc['different_sender'] = '' if different_sender is None else different_sender
	doc['different_sender_name'] = '' if different_sender is None else (different_sender_name or '')

	result = orig_get_email_template(template_name, doc)

	signature_name = frappe.db.get_value('Email Template', template_name, 'signature')
	if signature_name:
		signature = orig_get_email_template(signature_name, doc)

		if signature:
			result['message'] += '\n\n<br/>' + signature['message']

	return result
