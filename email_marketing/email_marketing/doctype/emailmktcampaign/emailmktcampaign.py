# Copyright (c) 2022, RS and contributors
# For license information, please see license.txt

# from typing import Dict, List

import frappe
from frappe.exceptions import DoesNotExistError
import frappe.utils
from frappe.model.document import Document
# from frappe.email.smtp import get_outgoing_email_account
from frappe.utils.background_jobs import enqueue
from email.header import decode_header, make_header
from frappe.utils.data import cstr, now_datetime, time_diff_in_seconds, add_days
from email.utils import formataddr

#
# Console execution for test/dev:
# email_campaign = frappe.get_doc('EmailMktCampaign', 'vorteils.app Onboarding')
# email_campaign.evaluate_campaign_nodes()
#

class EmailMktCampaign(Document):
	def onload(self):
		self.setup_newsletter_status() # copied from newsletter.py

	def init_nodes(self):
		if hasattr(self, 'nodes_initialized'):
			return

		self.nodes_initialized = True

		for structured_node in self.campaign_nodes:
			structured_node.init_from_campaign(self)


	@frappe.whitelist()
	def start_processing(self):
		self.status = 'Running'
		self.save()

		self.schedule_processing()

	def unschedule_processing(self):
		frappe.db.delete('EmailMktScheduledProcessings', {
			'reference_doctype': self.doctype,
			'reference_name': self.name
		})

	def schedule_processing(self, schedule_at=None):
		# create reference to this
		try:
			frappe.get_doc({
				'doctype': 'EmailMktScheduledProcessings',
				'reference_doctype': self.doctype,
				'reference_name': self.name,
				'scheduled_at': (schedule_at or now_datetime())
			}).insert(ignore_permissions=True)
		except Exception:
			# schedule record is already present
			if frappe.message_log:
				frappe.message_log.pop()

		try:
			scheduled_job = frappe.get_doc('Scheduled Job Type', {'method': 'email_marketing.tasks.process_active_campaigns'})
		except DoesNotExistError:
			# if not present in scheduler, run delayed, but it'll start immediately (only feasible for dev)
			enqueue('email_marketing.tasks.process_active_campaigns', job_name='email_marketing.tasks.process_active_campaigns')

			if frappe.message_log:
				frappe.message_log.pop()
			return


		# if scheduled_job.is_job_in_queue():
		# 	pass

		# The scheduler runs every hour anyways, but if this campaign should run earlier, we manipulate the scheduler
		# to catch it up asap.
		if not schedule_at or time_diff_in_seconds(schedule_at, scheduled_job.get_next_execution()) < 0:
			scheduled_job.last_execution = add_days(now_datetime(), -1)
			scheduled_job.flags.ignore_permissions = True
			scheduled_job.save()


		# from frappe.utils.background_jobs import get_jobs
		# job_name = 'Run Campaign {}/{}'.format(self.doctype, self.name)
		# queued_jobs = get_jobs(site=frappe.local.site, queue='default', job_name=job_name, key='job_name')[frappe.local.site]
		# self.queue_action('evaluate_campaign_nodes', queue='default',
		# 									job_name=job_name)

	def evaluate_campaign_nodes(self):
		self.unschedule_processing() # remove current scheduling
		self.init_nodes()

		is_auto_commit_set = bool(frappe.db.auto_commit_on_many_writes)
		frappe.db.auto_commit_on_many_writes = not frappe.flags.in_test

		# run all root_nodes
		for root_node in [n for n in self.campaign_nodes if n.is_root_node()]:
			root_node.evaluate_node()

		frappe.db.auto_commit_on_many_writes = is_auto_commit_set

		# check if/when further processing should be scheduled.
		schedule_reschedule = self.reschedule_required_in()
		if schedule_reschedule == True:
			# reschedule ... for now try it in an hour again
			self.schedule_processing(frappe.utils.add_to_date(now_datetime(), hours=1))
		else:
			self.schedule_processing(schedule_reschedule)

		frappe.db.commit()

	def reschedule_required_in(self):
		schedule_reschedule_in_general = False
		reschedule_in = None

		for child_node in self.campaign_nodes:
			schedule_in = child_node.is_marked_for_reschedule()
			if not schedule_in:
				continue

			if schedule_in == True:
				schedule_reschedule_in_general = True
			elif not reschedule_in:
				reschedule_in = schedule_in
			elif schedule_in < reschedule_in:
				reschedule_in = schedule_in

		return reschedule_in if reschedule_in else schedule_reschedule_in_general

	@frappe.whitelist()
	def stop_processing(self):
		self.status = 'Finished'
		self.save()
		self.unschedule_processing()

	@frappe.whitelist()
	def reopen_processing(self):
		self.status = 'Planned'
		self.save()
		self.unschedule_processing()

	def has_specific_target_audiences(self):
		"""
		Campaigns may have a kind like a "Newsletter", where a Static or Dynamic target audience segment
		builds the recipients base to be addressed.
		It also can be an event-driven automation campaign, which then doesn't have any audience defined.
		"""
		return len(self.campaign_nodes) > 0

	@frappe.whitelist()
	def generate_audiences(self, count_only=True, only_first_package=False, limit=None):
		if hasattr(self, 'cached_generated_members') and self.cached_generated_members != None:
			if count_only:
				return len(self.cached_generated_members)

			if limit:
				return self.cached_generated_members[0:limit]

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
				members = subscriber_group.filter_members(members)

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

		# Simulate the "event_creation" property for generated audiences by campaign_start,
		# (for those, which don't already simulate an "event_creation").
		for audience_member in audience_members:
			if not 'event_creation' in audience_member:
				# audience_member['event_creation'] = self.respect_events_from
				audience_member.event_creation = self.respect_events_from

		self.cached_generated_members = audience_members

		return audience_members

	def did_node_run_for_receipient(self):
		# TODO: (for combination layers)
		return False

	# def	send_scheduled_newsletter_mails(self):
	# 	is_auto_commit_set = bool(frappe.db.auto_commit_on_many_writes)
	# 	frappe.db.auto_commit_on_many_writes = not frappe.flags.in_test

	# 	for due_email in self.relevant_emails():
	# 		for audience_member in self.generate_audiences(count_only=False):
	# 			self.prepare_and_send_email(due_email, audience_member['reference_doctype'], audience_member['reference_name'], audience_member['email_id'])

	# 	frappe.db.auto_commit_on_many_writes = is_auto_commit_set

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
	def prepare_and_send_email(self, node_name_or_doc, receiver_doctype_or_doc, receiver_id, recipient_email_address, test_mail: bool = False, event=None):

		prepared_email_dict = self.prepare_email(node_name_or_doc,
																						 receiver_doctype_or_doc,
																						 receiver_id,
																						 recipient_email_address)

		# If email is not sent in testing-situation, the event (with nodes) are permitted, and the mail
		# will be associated to the event
		if event:
			test_mail = False

		frappe.sendmail(
			subject=prepared_email_dict['subject'],
			sender=prepared_email_dict['sender_name'],
			recipients=[prepared_email_dict['to_address']],
			message=prepared_email_dict['message_body'],
			# attachments=self.get_attachments(), # TODO single attachment in child table possible, otherwise refer to an Email Template
			# inline_images= # TODO
			# template='newsletter', # TODO: render in the native template before
			add_unsubscribe_link=False, # unsubscribe links are permitted as variables for template/signature
			# unsubscribe_method="/unsubscribe",
			# unsubscribe_params={"name": self.name},
			reference_doctype='EmailMktEventStream' if event else None, # email_node.doctype,
			reference_name=event.triggering_node if event else None, # email_node.name,
			queue_separately=True,
			delayed=False if test_mail else True,
			send_priority=0
		)

		return True

	def get_node_by_name(self, name):
		if isinstance(name, str):
			return next((e for e in self.campaign_nodes if e.name == name), None)
			# preparation_email.onload() # initializer doesnt run for loaded children
		else:
			# return object, if that was permitted
			return name


	@frappe.whitelist(methods='POST')
	def prepare_email(self, email_name_or_node, receiver_doctype_or_doc, receiver_id=None, email_id=None):
		# if isinstance(email_name_or_node, str):
		# 	preparation_email = next((e for e in self.campaign_nodes if e.name == email_name_or_node), None)
		# 	preparation_email.onload() # initializer doesnt run for loaded children
		# else:
		# 	preparation_email = email_name_or_node
		preparation_email = self.get_node_by_name(email_name_or_node)
		if not preparation_email:
			return

		if isinstance(receiver_doctype_or_doc, Document):
			receipient_doc = receiver_doctype_or_doc
		else:
			receipient_doc = frappe.get_doc(receiver_doctype_or_doc, receiver_id)

		# if another dest email_id was permitted, use that (perhaps the receiver elements doctype doesnt own an email_id, but that's required)
		if email_id:
			receipient_doc.email_id = email_id

		if not hasattr(receipient_doc, 'email_id') or not receipient_doc.email_id:
			frappe.throw('A Receiver E-Mail Address (email_id) must be known to generate the email')

		sending_user = frappe.get_cached_doc('User', self.sending_user)

		if self.sender_name_source == 'E-Mail Account':
			different_sender_name = self.sender_name_from_email_account(self.email_account, 'EmailMktCampaign')
		elif self.sender_name_source == 'Sending User':
			different_sender_name = sending_user.full_name
		elif self.sender_name_source == 'Freetext':
			different_sender_name = self.alternative_sender_name

		subject, message_body = preparation_email.prepare_email(receipient_doc.email_id, receipient_doc, **{
			# 'user': sending_user,
			'different_sender': self.sending_user,
			'different_sender_name': different_sender_name,
			'email_id': receipient_doc.email_id,
			'receipient_doc': receipient_doc
		})

		sending_email_address = frappe.get_cached_doc('Email Account', self.email_account).email_id

		sender_name = cstr(make_header(decode_header(formataddr((different_sender_name, sending_email_address)))))
		to_address = cstr(make_header(decode_header(formataddr((self.full_name_for_doc(receipient_doc), receipient_doc.email_id)))))

		return {
			'sender_name': sender_name,
			'to_address': to_address,
			'subject': subject,
			'message_body': message_body,
			'test_email_receipient': sending_user.name,
			'email_node': preparation_email
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
