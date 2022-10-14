# Copyright (c) 2022, RS and contributors
# For license information, please see license.txt

from typing import Dict, List

import frappe
import frappe.utils
from frappe.model.document import Document
from frappe.email.smtp import get_outgoing_email_account
from email.header import decode_header, make_header
from frappe.utils.data import cstr
from email.utils import formataddr

class EmailMktCampaign(Document):
	def onload(self):
		self.setup_newsletter_status() # copied from newsletter.py

	@frappe.whitelist()
	def start_processing(self):
		# For newsletter campaigns --------------------------------
		# shall be scheduled after:
		# a) campaign activation (Status got changed to "Running")
		# b) after *campaign_emails* child-table change, when *scheduled_at* is in the future
		# c) after *start_processing* was processed and another *scheduled_at* email is still in the future

		if self.campaign_type == 'Newsletter':
			self.send_scheduled_newsletter_mails()
			self.status = 'Running'
			self.save()

		elif self.campaign_type == 'Automation':
			pass # TODO

	@frappe.whitelist()
	def stop_processing(self):
		self.status = 'Finished'
		self.save()

	@frappe.whitelist()
	def reopen_processing(self):
		self.status = 'Planned'
		self.save()

	@frappe.whitelist()
	def generate_audiences(self, count_only=True, only_first_package=False, limit=None):
		audience_members = []
		subscriber_group = frappe.get_doc('EmailMktSubscriberGroup', self.subscriber_group) if self.subscriber_group else None

		# Only reference_doctype & reference_name are returned
		# and NOT the attributes of doc_type etc.
		# So to make sure, email_id is there, the doctype needs to be checked
		# and email addresses need to be selected for it
		for audience in self.target_audiences:
			ref_audience = frappe.get_doc('EmailMktAudience', audience.audience)

			# load the records from audience
			members = ref_audience.generate()

			audience.audience_count = len(members)

			# filter members if excluded by subscriber_group ()
			if subscriber_group:
				group_members = [{'dt': m['ref_doctype'], 'dn': m['ref_name']} for m in subscriber_group.as_dict()['members']]
				if subscriber_group.optin_rule == 'Opt-In':
					members = [m for m in members if {'dt': m['reference_doctype'], 'dn': m['reference_name']} in group_members]
				elif subscriber_group.optin_rule == 'Opt-Out':
					members = [m for m in members if {'dt': m['reference_doctype'], 'dn': m['reference_name']} not in group_members]

			members = ref_audience.enrich_members_data(members, enrich_by_fields=['email_id'], filter_conditions={'unsubscribed': False}, deduplicate_by='email_id')

			# add those records, which are not already known from other audience
			audience_members += [record for record in members if record not in audience_members]

			audience.audience_count_in_context = len(audience_members)
			audience.save()

			if only_first_package and len(members) > 0:
				break

		if count_only:
			return len(audience_members)

		if limit:
			return audience_members[0:limit]

		return audience_members


		# For automation campaigns --------------------------------


	def	send_scheduled_newsletter_mails(self):
		is_auto_commit_set = bool(frappe.db.auto_commit_on_many_writes)
		frappe.db.auto_commit_on_many_writes = not frappe.flags.in_test

		for due_email in self.get_due_emails():
			for audience_member in self.generate_audiences(count_only=False):
				self.prepare_and_send_email(due_email, audience_member['reference_doctype'], audience_member['reference_name'], audience_member['email_id'])

		frappe.db.auto_commit_on_many_writes = is_auto_commit_set

	def get_due_emails(self):
		return [e for e in self.campaign_emails if (not e.scheduled_at or frappe.utils.get_datetime(e.scheduled_at) < frappe.utils.now_datetime())]

	def sender_name_from_email_account(self, email_account, doctype = None):
		if isinstance(email_account, str):
			email_account_name = email_account
		elif getattr(email_account, 'name', False):
			email_account_name = email_account.name
		else:
			return

		check_doctype = True if doctype else False

		if email_account:
			if check_doctype:
				senders = frappe.get_all('EmailMktSendername', filters={ 'email_account': email_account_name, 'target_doctype': doctype }, fields=['sendername'], limit_page_length=1)

			if len(senders) == 0:
				senders = frappe.get_all('EmailMktSendername', filters={ 'email_account': email_account_name, 'target_doctype': ['in', [None, '']] }, fields=['sendername'], limit_page_length=1)

		# now go on checking without email_account
		if len(senders) == 0 and check_doctype:
			senders = frappe.get_all('EmailMktSendername', filters={ 'email_account': ['in', [None, '']], 'target_doctype': doctype }, fields=['sendername'], limit_page_length=1)

		if len(senders) == 0:
			senders = frappe.get_all('EmailMktSendername', filters={ 'email_account': ['in', [None, '']], 'target_doctype': ['in', [None, '']] }, fields=['sendername'], limit_page_length=1)

		if len(senders) > 0:
			return senders[0].sendername

		return email_account_name

	def setup_newsletter_status(self):
		"""Setup analytical status for current Newsletter. Can be accessible from desk."""
		if self.status == 'Running' or self.status == 'Finished':
			status_count = frappe.get_all(
				"Email Queue",
				filters={"reference_doctype": self.doctype, "reference_name": self.name},
				fields=["status", "count(name)"],
				group_by="status",
				order_by="status",
				as_list=True,
			)
			self.get("__onload").status_count = dict(status_count)

	@frappe.whitelist(methods='POST')
	def prepare_and_send_email(self, email_template_name_or_doc, receiver_doctype, receiver_id, force_email_id=None):
		prepared_email_dict = self.prepare_email(email_template_name_or_doc, receiver_doctype, receiver_id, force_email_id)

		# sender_name
		# email_id
		# subject
		# email_body
		# test_email_receipient
		# email_doc
		email_templ_doc = prepared_email_dict['email_doc']

		frappe.sendmail(
			subject=prepared_email_dict['subject'],
			sender=prepared_email_dict['sender_name'],
			recipients=[prepared_email_dict['to_address']],
			message=prepared_email_dict['email_body'],
			# attachments=self.get_attachments(), # todo in child table there cannot be attachments, can they?
			# inline_images= # TODO
			# template='newsletter', # TODO: render in the native template before
			# add_unsubscribe_link=self.send_unsubscribe_link,
			# unsubscribe_method="/unsubscribe",
			# unsubscribe_params={"name": self.name},
			reference_doctype=email_templ_doc.doctype,
			reference_name=email_templ_doc.name,
			# reference_doctype=self.doctype,
			# reference_name=self.name,
			queue_separately=True,
			send_priority=0
		)

		return True

	@frappe.whitelist(methods='POST')
	def prepare_email(self, preparation_email_name, receiver_doctype, receiver_id, email_id=None):
		if isinstance(preparation_email_name, str):
			preparation_email = next((e for e in self.campaign_emails if e.name == preparation_email_name), None)
		else:
			preparation_email = preparation_email_name

		if not preparation_email:
			return

		receiver_doc = frappe.get_cached_doc(receiver_doctype, receiver_id)

		# if another dest email_id was permitted, use that (perhaps the receiver elements doctype doesnt own an email_id, but that's required)
		if email_id:
			receiver_doc.email_id = email_id

		if not hasattr(receiver_doc, 'email_id') or not receiver_doc.email_id:
			frappe.throw('A Receiver E-Mail Address (email_id) must be known to generate the email')

		sending_user = frappe.get_cached_doc('User', self.sending_user)

		if self.sender_name_source == 'E-Mail Account':
			different_sender_name = self.sender_name_from_email_account(self.email_account, 'EmailMktCampaign')
		elif self.sender_name_source == 'Sending User':
			different_sender_name = sending_user.full_name
		elif self.sender_name_source == 'Freetext':
			different_sender_name = self.alternative_sender_name

		subject, email_body = preparation_email.prepare_email(self.sending_user, receiver_doc, **{
			# 'user': sending_user,
			'different_sender': self.sending_user,
			'different_sender_name': different_sender_name,
			'email_id': receiver_doc.email_id,
			'receiver_doc': receiver_doc
		})

		sending_email_address = frappe.get_cached_doc('Email Account', self.email_account).email_id

		sender_name = cstr(make_header(decode_header(formataddr((different_sender_name, sending_email_address)))))
		to_address = cstr(make_header(decode_header(formataddr((self.full_name_for_doc(receiver_doc), receiver_doc.email_id)))))

		return {
			'sender_name': sender_name,
			'to_address': to_address,
			'subject': subject,
			'email_body': email_body,
			'test_email_receipient': sending_user.name,
			'email_doc': preparation_email
		}

	def full_name_for_doc(self, doc):
		if doc.doctype == 'Contact':
			return ' '.join(list(filter(None, [doc.first_name, doc.last_name])))
		elif doc.doctype == 'User':
			return doc.full_name
		else:
			return doc.name

	# def get_attachments(self) -> List[Dict[str, str]]:
	# 	return frappe.get_all(
	# 		"File",
	# 		fields=["name", "file_name", "file_url", "is_private"],
	# 		filters={
	# 			"attached_to_name": self.name,
	# 			"attached_to_doctype": "EmailMktCampaign", # FIXME: not right, as it needs to be in the email child table, but there is no attachment possibility, is it?
	# 			"is_private": 0,
	# 		},
	# 	)
