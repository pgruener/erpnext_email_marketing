import frappe
# from frappe.utils import split_emails
import json

# from frappe.core.doctype.communication.email import mark_email_as_seen as orig_mark_email_as_seen
from email.utils import getaddresses

import email_marketing.email_marketing.sequenced_address_determination as sequenced_address_determination
# import re

# from frappe.utils import (escape_html, format_datetime,
# 	now_datetime, add_days, today, now_datetime, get_datetime, logger)

# from frappe import _

no_cache = True


@frappe.whitelist(allow_guest=False, methods=['POST'])
def detect_email_recipient_for_doc(doc):
	doc = json.loads(doc)

	if not doc:
		return

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

@frappe.whitelist(allow_guest=True, methods=['GET'])
def open(name: str = None):
	"""
	Creates an E-Mail "Open" event for the corresponding correspondence
	"""
	# responds an empty pixel and updates the communication
	# orig_mark_email_as_seen(name)

	# img url generation from frappe.email.queue.prepare_message
	# quopri.encodestring(
	# 			'<img src="https://{}/api/method/frappe.core.doctype.communication.email.mark_email_as_seen?name={}"/>'.format(
	# 				frappe.local.site, email.communication
	# 			).encode()

	try:
		if name and frappe.db.exists('EmailMktEventStream', name):
			frappe.get_doc({
				'doctype': 'EmailMktEventStream',
				'entry_type': 'Opened E-Mail',
				'reference_doctype': 'EmailMktEventStream',
				'reference_name': name,
			}).insert(ignore_permissions=True)

	finally:
		# copied from frappe.core.doctype.communication's *mark_email_as_seen*
		frappe.response.update(
			{
				"type": "binary",
				"filename": "show.png",
				"filecontent": (
					b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00"
					b"\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\r"
					b"IDATx\x9cc\xf8\xff\xff?\x03\x00\x08\xfc\x02\xfe\xa7\x9a\xa0"
					b"\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
				),
			}
		)


try:
    # from base64 import encodebytes as _bencode
    from base64 import decodebytes as _bdecode
except ImportError:
    # Py2 compatibility. TODO: test this!
    # from base64 import encodestring as _bencode
    from base64 import decodestring as _bdecode



@frappe.whitelist(allow_guest=True, methods=['GET'])
def click(tgt: str, name: str = None):
	"""
	Registers a click and redirects to the expected destination.
	"""

	# redirect to desired location
	frappe.local.response['type'] = 'redirect'
	frappe.local.response['location'] = _bdecode(tgt.encode()).decode() # decode target url

	# create event
	if name and frappe.db.exists('EmailMktEventStream', name):
		reference_doctype, reference_name = frappe.db.get_value('EmailMktEventStream', name, ['reference_doctype', 'reference_name'])
		frappe.get_doc({
				'doctype': 'EmailMktEventStream',
				'entry_type': 'Clicked Link in E-Mail',
				'reference_doctype': reference_doctype,
				'reference_name': reference_name,
				'optional_parameter_1': frappe.local.response['location']
			}).insert(ignore_permissions=True)

@frappe.whitelist(allow_guest=True, methods=['GET'])
def unsubscribe(name: str = None, campaign: str = None, general: str = None, spam: str = None):
	"""
	Unsubscribes from a campaign group - the communication references a campaign node (EmailMktCampaignEmail),
	which knowns the campaign and the group.

	name = `EmailMktEventStream` Name
	campaign = user wants to skip the current campaign only
	general = user wants to block all emails (if general=true)
	spam = user considered as spam (if spam=true), same as general but tracked separately
	"""
	if not name or not frappe.db.exists('EmailMktEventStream', name):
		# TODO: display something or redirect
		return

	sent_event = frappe.get_doc('EmailMktEventStream', name)
	sent_email_element = frappe.get_last_doc('Email Queue', filters={'reference_doctype': 'EmailMktEventStream', 'reference_name': name})
	campaign_doc = frappe.get_cached_doc('EmailMktCampaign', frappe.db.get_value('EmailMktCampaignEmail', sent_event.nodes[0].connected_node, 'parent'))

	# subscriber_group_name = frappe.db.get_value('EmailMktCampaign', frappe.db.get_value('EmailMktCampaignEmail', sent_event.nodes[0].connected_node, 'parent'), 'subscriber_group')
	# subscriber_group_optin_direction = frappe.db.get_value('EmailMktSubscriberGroup', subscriber_group_name, 'optin_rule') if subscriber_group_name else None
	subscriber_group_optin_direction = frappe.db.get_value('EmailMktSubscriberGroup', campaign_doc.subscriber_group, 'optin_rule') if campaign_doc.subscriber_group else None


	# for email in split_emails(sent_email_element.recipients):
	for recipient_email_address in sent_email_element.recipients:
		# erpnext unsubscribe
		try:
			frappe.get_doc({
				'doctype': 'Email Unsubscribe',
				'email': getaddresses([recipient_email_address])[0][1], # get plain email address from "name <address@xyz.com>"
				'reference_doctype': campaign_doc.doctype,
				'reference_name': campaign_doc.name,
				'global_unsubscribe': True if general == 'true' or spam == 'true' else False
			}).insert(ignore_permissions=True)

			# TODO: also stop campaign for this receipient (as soon as start/stop is implemented)

		except frappe.DuplicateEntryError:
			frappe.clear_last_message()

		if campaign != 'true':
			# Add/Remove from EmailMktSubscriberGroup
			if subscriber_group_optin_direction == 'Opt-In':
				frappe.db.delete('EmailMktSubscriberGroupItem', {
					'parenttype': 'EmailMktSubscriberGroup',
					'parentfield': 'members',
					'parent': campaign_doc.subscriber_group,
					'ref_doctype': sent_event.doctype,
					'ref_name': sent_event.name
				})
			elif subscriber_group_optin_direction == 'Opt-Out':
				frappe.get_doc({
					'doctype': 'EmailMktSubscriberGroupItem',
					'parenttype': 'EmailMktSubscriberGroup',
					'parentfield': 'members',
					'parent': campaign_doc.subscriber_group,
					'ref_doctype': sent_event.doctype,
					'ref_name': sent_event.name
				}).insert(ignore_permissions=True)

		# If "Contact" is the related doctype, set "unsubscribed" = True in reference doc
		if ( general == 'true' or spam == 'true' ) and sent_event.doctype == 'Contact':
			frappe.db.set_value(sent_event.doctype, sent_event.name, 'unsubscribed', True)

		# generate event stream
		if spam == 'true':
			unsubscribe_event = 'Unsubscribed via Spam categorization'
		elif general == 'true':
			unsubscribe_event = 'Unsubscribed in general'
		elif campaign == 'true':
			unsubscribe_event = 'Unsubscribed from Campaign'
		elif campaign_doc.subscriber_group:
			unsubscribe_event = 'Unsubscribed from Group'
		else: # fallback to campaign as a campaign is always there (in difference to group), and it's not a "global" unsubscribe
			unsubscribe_event = 'Unsubscribed from Campaign'

		frappe.get_doc({
				'doctype': 'EmailMktEventStream',
				'entry_type': unsubscribe_event,
				'reference_doctype': sent_event.reference_doctype,
				'reference_name': sent_event.reference_name,
				'optional_parameter_1': 'spam={0}'.format(spam if spam == 'true' else 'false'),
				'optional_parameter_2': 'general={0}'.format(general if general == 'true' else 'false'),
				'optional_parameter_3': 'only_campaign={0}'.format(campaign if campaign == 'true' else 'false')
			}).insert(ignore_permissions=True)

	# TODO: Perhaps later: Send info mail about unsubscribe, or "double-opt-out" mail.
	# TODO: but not in "spam" case, as we're happy, that our "spam" link was used
	# TODO: instead of claiming it as "real" spam
