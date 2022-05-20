import frappe
import json

import email_marketing.email_marketing.sequenced_address_determination as sequenced_address_determination

# from frappe.utils import (escape_html, format_datetime,
# 	now_datetime, add_days, today, now_datetime, get_datetime, logger)

# from frappe import _

no_cache = True


@frappe.whitelist(allow_guest=False, methods=['POST'])
def detect_email_recipient_for_doc(doc):
	doc = json.loads(doc)

	frappe.get_cached_doc(doc['doctype'], doc['name']).check_permission('read')

	if doc['doctype'] == 'Purchase Order':
		if doc['supplier']:
			frappe.response['data'] = sequenced_address_determination.read_preferred_email_for_supplier(doc['supplier'])

	elif doc['doctype'] == 'Quotation':
		if doc['quotation_to'] == 'Customer' and doc['party_name']:
			frappe.response['data'] = sequenced_address_determination.read_preferred_quote_email_for_customer(doc['party_name'])

	elif doc['doctype'] == 'Sales Order':
		if doc['customer']:
			frappe.response['data'] = sequenced_address_determination.read_preferred_order_email_for_customer(doc['customer'])

	# elif doc['doctype'] == 'Lead':
	# 	if doc['x']:
	# 		frappe.response['data'] = sequenced_address_determination.read_preferred_email_for_x(doc['x'])

@frappe.whitelist(allow_guest=False, methods=['POST'])
def target_contacts_for_doc(doc):
	frappe.response['data'] = sequenced_address_determination.target_contacts_for_doc(doc)


@frappe.whitelist(allow_guest=False, methods=['POST'])
def default_email_template_for_doctype(doctype):
	# Returns the default email template for the given doctype.

	# email_template = frappe.db.sql("""
	# 	SELECT `tabEmail Template`.`name`
	# 	FROM `tabEmail Template`
	# 	INNER JOIN `tabEmailMktTemplateDocTypes` template_maping
	# 		on template_maping.parent = `tabEmail Template`.name
	# 	WHERE template_maping.`linked_doctype` = %(doctype)s
	# 	LIMIT 1
	# 	""" , {'doctype': doctype}, as_dict=True)

	email_template = frappe.db.sql("""
		SELECT template_maping.parent as name
			FROM `tabEmailMktTemplateDocTypes` template_maping
		WHERE template_maping.`linked_doctype` = %(doctype)s
		LIMIT 1
		""" , {'doctype': doctype}, as_dict=True)

	template_name = None

	if len(email_template) > 0:
		template_name = email_template[0]['name']

	frappe.response['email_template'] = template_name
