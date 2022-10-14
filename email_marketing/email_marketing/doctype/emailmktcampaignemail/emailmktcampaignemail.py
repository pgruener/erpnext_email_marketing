# Copyright (c) 2022, RS and contributors
# For license information, please see license.txt

from concurrent.futures import process
import re

import frappe
import frappe.utils
from frappe.model.document import Document
# from frappe import DoesNotExistError

from email_marketing.email_marketing.doctype.emailmktaudience.emailmktaudience import enrich_members_data
from frappe.utils.data import now_datetime

# try:
from base64 import encodebytes as _bencode
# except ImportError: # Py2 compatibility
#   from base64 import encodestring as _bencode


class EmailMktCampaignEmail(Document):
	def init_from_campaign(self, campaign_doc):
		# self._generated = False
		if hasattr(self, 'campaign_doc'):
			return # object was already initialized

		# self.campaign_doc = frappe.get_cached_doc(self.parenttype, self.parent)
		self._resolved_receipients = []
		self.campaign_doc = campaign_doc
		self.subscriber_group_doc = frappe.get_cached_doc('EmailMktSubscriberGroup', self.campaign_doc.subscriber_group) if self.campaign_doc.subscriber_group else None
		# self.based_on_doc = frappe.get_cached_doc(self.doctype, self.based_on) if self.based_on else None
		self.based_on_doc = next((n for n in campaign_doc.campaign_emails if n.name == self.based_on), None) if self.based_on else None

	def is_root_node(self):
		# Wait & Combine nodes are considered as root-nodes, as they're event driven, but should still be
		# associated in the visual/structurral flow as dependent ones.
		if not self.based_on: # or (self.entry_type == 'Wait for Event' or self.entry_type == 'Combine'):
			return True

		return False

	def is_event_receiver_node(self):
		"""
		Not all nodes are able to receive events, like conditional ones like *Combine* or *Wait*.
		This method returns True or False if it is a receiver node or not.
		"""
		if self.entry_type == 'Email' or self.entry_type == 'Wait for Event':
			return True
		return False

	def get_receipients(self, processed: bool, unprocessed_receipients=None):
		# get the transfered receipients from permitted parameter, parent, or the connected ones from root, as base.
		if unprocessed_receipients:
			receipients = unprocessed_receipients
		else:
			# merge the receipients with the available events (if any)
			if self.is_root_node() and self.campaign_doc.has_specific_target_audiences():
				if hasattr(self, '_cached_audience_generation'):
					receipients = self._cached_audience_generation
				else:
					receipients = self._cached_audience_generation = self.campaign_doc.generate_audiences(count_only=False)
			else:
				receipients = []

		if self.is_event_receiver_node():
			# query the (un)processed ones, as those should be tried to continue the processing within the sub_nodes
			related_events = self.get_node_related_events_query(processed=processed).run(as_dict=True)

			if receipients:
				# filter receipients to those, which have not been processed yet and remove them from current receipients list for this node
				if related_events:
					filtered_receipients = []

					for r in receipients:
						for related_event in related_events:
							# TODO
							if processed:
								pass
							else:
								pass
							if related_event.reference_doctype == r['reference_doctype'] and related_event.reference_name == r['reference_name'] and related_event.triggering_node != self.name:
								pass

						# TODO
						# unprocessed_event = next((u for u in related_events if u.reference_doctype == r['reference_doctype'] and u.reference_name == r['reference_name'] and u.triggering_node != self.name), False)
						if unprocessed_event:
							r['event'] = unprocessed_event.event
							r['event_creation'] = unprocessed_event.event_creation
							r['triggering_node'] = unprocessed_event.triggering_node
							filtered_receipients.append(r)

					receipients = filtered_receipients
			else:
				# if no base receipients were available, just use the retrieved events as receipients
				receipients = related_events
		elif processed:
			# If processed nodes are requested, for nodes, which dont track the processing via received events
			# (like wait/combine) it's mandatory, that those receipient objects were marked, during the (fluent)
			# processing in the step before.
			receipients = [r for r in receipients if ('processing_resolved' in r and r['processing_resolved']) or next((_r for _r in self._resolved_receipients if _r['reference_doctype'] == r['reference_doctype'] and _r['reference_name'] == r['reference_name']), False)]

		if self.subscriber_group_doc:
			receipients = self.subscriber_group_doc.filter_members(receipients)

		for receipient in receipients:
			if 'processing_resolved' in receipient:
				# remove the property for processing of other node layers
				del receipient['processing_resolved']

		# reads "email_id" to the referenced docs and filter those, without email_id and those which did unsubscribe (and have an unsubscribe property)
		return enrich_members_data(receipients, enrich_by_fields=['email_id'], filter_conditions={'unsubscribed': False}, deduplicate_by='email_id')

	def get_node_related_events_query(self, processed: bool):
		stream_head = frappe.qb.DocType('EmailMktEventStream')
		stream_nodes = frappe.qb.DocType('EmailMktEventStreamNode')

		base_event_query = (frappe.qb.from_(stream_head)
													.select(stream_head.name.as_('event'))
													.select(stream_head.triggering_node)
													.select(stream_head.creation.as_('event_creation'))
													.select(stream_head.reference_doctype.as_('reference_doctype'))
													.select(stream_head.reference_name.as_('reference_name'))
													.left_join(stream_nodes)
														.on((stream_nodes.parent == stream_head.name) & (stream_nodes.parenttype == 'EmailMktEventStream') & (stream_nodes.parentfield == 'invoked_nodes') & (stream_nodes.connected_node == self.name))
													# .where(stream_head.triggering_node == self.name)
													.where(stream_head.creation >= self.campaign_doc.respect_events_from)
													.distinct()
												)

		if self.entry_type == 'Email':
			q = base_event_query.where(stream_head.entry_type == 'E-Mail sent')
		elif self.entry_type == 'Wait for Event':
			q = base_event_query.where(stream_head.entry_type == self.wait_for_event_type)

			if self.wait_for_event_type == 'Clicked Link in E-Mail':
				if self.wait_event_in_email_link_pattern:
					q = q.where(stream_head.optional_parameter_1.like(self.wait_event_in_email_link_pattern))
			elif self.wait_for_event_type == 'Opened E-Mail':
				q = q.where(stream_head.optional_parameter_1 == self.wait_event_in_email)
			elif self.wait_for_event_type.startswith('Tag '): # 'Tag added' / 'Tag removed'
				q = q.where(stream_head.optional_parameter_1 == self.waiting_for_tag)
			elif self.wait_for_event_type == 'Subscribed in Group' or self.wait_for_event_type == 'Unsubscribed in Group':
				q = q.where(stream_head.optional_parameter_1 == self.wait_for_group_change)
			elif self.wait_for_event_type == 'E-Mail sent':
				q = q.where(stream_head.optional_parameter_1 == (self.wait_event_in_email_campaign or self.campaign_doc.name))
				if self.wait_event_in_email:
					q = q.where(stream_head.optional_parameter_2 == self.wait_event_in_email)
		# elif self.entry_type.startswith('Wait'):
		# 	return # Wait* nodes dont retrieve events

		if processed:
			return q.where((stream_nodes.processed_at.isnotnull() | (stream_head.triggering_node == self.name)))
		else:
			# return q.where((stream_nodes.processed_at.isnull()) & (stream_head.triggering_node != self.name))
			# return q.where((stream_nodes.processed_at.isnull()) & (stream_head.triggering_node == self.name)).where(stream_head.triggering_node == self.name)
			# return q.where((stream_nodes.processed_at.isnull()))
			return q.where(stream_nodes.processed_at.isnull()).where(stream_head.triggering_node != self.name)


	def evaluate_node(self, processed_receipients_from_parent_node=None):
		if self.name == 'b518d7081e':
			l = 1 + 2

		# Process current node for all unprocessed events/receipients
		for receipient in self.get_receipients(processed=False, unprocessed_receipients=processed_receipients_from_parent_node):
			# import pdb; pdb.set_trace()
			self.evaluate_node_for_single_receipient(receipient)

		# Afterwards load the receipients/events, which where already processed and transfer
		# them to the sub_nodes



		dependend_nodes = self.dependend_nodes()
		if dependend_nodes:

			# if self.name == 'c089539626':
			# 	import pdb; pdb.set_trace()


			processed_receipients = self.get_receipients(processed=True)

			# TODO: Hier müssen wir rein (oder in der Zeile drüber), um zu differenzieren, ob jetzt wirklich
			# TODO: der betroffene node für den receipient bereits prozessiert wurde oder nicht, ODER ob er
			# TODO: der auslösende Node war.


			if processed_receipients:
				for dependend_node in dependend_nodes:
					dependend_node.evaluate_node(processed_receipients)

		self.last_evaluation_at = frappe.utils.now_datetime()
		self.save()

	def evaluate_node_for_single_receipient(self, receipient):
		# if the event was caused by this node itself, it may not be processed again
		if hasattr(receipient, 'triggering_node') and receipient['triggering_node'] == self.name:
			return

		blocked_until = self.has_blocking_preconditions_receipient(receipient)
		if blocked_until:
			self.mark_for_reschedule(blocked_until)
			return

		# preconditions are met for this receipient. -> perform action
		if self.entry_type == 'Email':
			# just send the emails to the detected receipients
			receipient['event'] = self.insert_event('E-Mail sent', receipient)
			self.campaign_doc.prepare_and_send_email(self, receipient['reference_doctype'], receipient['reference_name'], receipient['email_id'], event=receipient['event'])
		# TODO other entry-types like "add/remove Tag", "stop campaign for receipient" ...

	def insert_event(self, event_type, receipient, props={}):
		event = frappe.get_doc({
				'doctype': 'EmailMktEventStream',
				'entry_type': event_type,
				'triggering_node': self.name,
				'reference_doctype': receipient['reference_doctype'],
				'reference_name': receipient['reference_name'],
				'optional_parameter_1': props['optional_parameter_1'] if 'optional_parameter_1' in props else None,
				'optional_parameter_2': props['optional_parameter_2'] if 'optional_parameter_2' in props else None,
				'optional_parameter_3': props['optional_parameter_3'] if 'optional_parameter_3' in props else None,
			}).insert(ignore_permissions=True)

		# receipient['triggering_node'] = self.name

		# TODO: retrigger campaign or propagate event up to get part of the further sub-node processing
		# TODO: should happen automagically, shouldnt it?

		return event

	def insert_or_update_event_for_node(self, event_props, processed=False):
		"""
		Inserts or updates the given event node (below an event), with a processed
		timestamp (if wanted).
		"""
		event = event_props['event'] if 'event' in event_props and event_props['event'] else None
		if not event:
			return

		# persist information about the processed receipient within the nodes
		stream_node_name = frappe.db.get_value('EmailMktEventStreamNode',{
			'parent': event.name,
			'parentfield': 'invoked_nodes',
			'parenttype': 'EmailMktEventStream',
			'connected_node': self.name,
			'reference_doctype': event_props['reference_doctype'],
			'reference_name': event_props['reference_name']
			}, 'name')

		if stream_node_name:
			# update refs processed_at timestamp
			if processed:
				frappe.db.set_value('EmailMktEventStreamNode', stream_node_name, 'processed_at', now_datetime())
		else:
			frappe.get_doc({
				'doctype': 'EmailMktEventStreamNode',
				'parent': event.name,
				'parentfield': 'invoked_nodes',
				'parenttype': 'EmailMktEventStream',
				'connected_node': self.name,
				'reference_doctype': event_props['reference_doctype'],
				'reference_name': event_props['reference_name'],
				'processed_at': now_datetime() if processed else None,
			}).insert(ignore_permissions=True)

			# # TODO: the logic based on is_marked_for_reschedule is completely wrong, as its node level not event level
			# if stream_node_name:
			# 	# update refs processed_at timestamp
			# 	if not self.is_marked_for_reschedule():
			# 		frappe.db.set_value('EmailMktEventStreamNode', stream_node_name, 'processed_at', now_datetime())
			# 		# stream_node_ref.processed_at = now_datetime()
			# 		# stream_node_ref.save()
			# else:
			# # except DoesNotExistError:
			# # 	if frappe.message_log:
			# # 		frappe.message_log.pop()

			# 	# create ref
			# 	frappe.get_doc({
			# 		'doctype': 'EmailMktEventStreamNode',
			# 		'parent': receipient['event'],
			# 		'parentfield': 'invoked_nodes',
			# 		'parenttype': 'EmailMktEventStream',
			# 		'connected_node': self.name,
			# 		'reference_doctype': receipient['reference_doctype'],
			# 		'reference_name': receipient['reference_name'],
			# 		# TODO: the logic based on is_marked_for_reschedule is completely wrong, as its node level not event level
			# 		'processed_at': now_datetime() if self.is_marked_for_reschedule() else None,
			# 	}).insert(ignore_permissions=True)

	def has_blocking_preconditions_receipient(self, receipient):
		"""
		Each node may get delayed due to several pre-conditions. This method checks that and returns
		one of the following values:
		- False - Nothing is blocked anymore, this node may be processed now.
		- True - There are blocking preconditions, and we dont have an idea when it will be solved
		- datetime - A timestamp, when it is expected to have the blocking precondition solved.
		"""
		# check if combined nodes are matched as precondition
		if self.entry_type == 'Combine':
			if self.combination_operator_1 == 'Does match':
				layer_comparison = self.campaign_doc.did_node_run_for_receipient(self.combination_layer_1, receipient) == True
			else:
				layer_comparison = self.campaign_doc.did_node_run_for_receipient(self.combination_layer_1, receipient) == False

			if (layer_comparison and self.combination_type == 'And') or (not layer_comparison and self.combination_type == 'Or'):
				if self.combination_operator_2 == 'Does match':
					layer_comparison = self.campaign_doc.did_node_run_for_receipient(self.combination_layer_2, receipient) == True
				else:
					layer_comparison = self.campaign_doc.did_node_run_for_receipient(self.combination_layer_2, receipient) == False

			if not layer_comparison:
				return True # skip node for the current receipient (for now), as the combined nodes are not ready (no idea when they will be)
		else:
			# check schedules
			if self.scheduled_at:
				if self.scheduled_at > now_datetime():
					# delay continuation for this receipient if node is configured to wait a specific time
					# schedule_in = frappe.utils.time_diff_in_seconds(self.scheduled_at, now_datetime()) / 60
					# self.mark_for_reschedule(frappe.utils.time_diff_in_seconds(self.scheduled_at, now_datetime()) / 60)
					return self.scheduled_at
			elif self.send_after_days or self.send_after_hours:
				# get timediff to event source (receipient event_creation)
				should_run_at = frappe.utils.add_to_date(	receipient['event_creation'],
																									days=self.send_after_days if self.send_after_days else 0,
																									hours=self.send_after_hours if self.send_after_hours else 0)
				if should_run_at > now_datetime():
					# delay continuation for this receipient if node is configured to wait a specific time
					self.mark_for_reschedule(should_run_at)
					# schedule_in = should_run_at
					return should_run_at

		# mark the receipient as resolved
		receipient['processing_resolved'] = True
		self._resolved_receipients.append(receipient)

		return False # no blocking preconditions left

	def dependend_nodes(self):
		return [n for n in self.campaign_doc.campaign_emails if n.based_on == self.name and not n.is_root_node()]

	def prepare_email(self, receipient_email_address, target_doc, **args):
		production_email = False
		event_doc = None

		if target_doc.doctype == 'EmailMktStreamNode':
			production_email = True
			event_doc = target_doc
			target_doc = frappe.get_cached_doc(event_doc.reference_doctype, event_doc.reference_name)

		base_api_url = '{}/api/method'.format(frappe.utils.get_url())
		base_unsubscribe_url = '{}/email_marketing.api.unsubscribe?name={}'.format(base_api_url, event_doc.name if event_doc else 'TEST')

		transmission_variables = {
			'campaign': self,
			'receipient_email_address': receipient_email_address,
			'doc': target_doc,
			'open_tracking_image_html': '<img src="{}/email_marketing.api.open?name={}"/>'.format(base_api_url, event_doc.name if event_doc else 'TEST'),
			'unsubscribe_from_group': self.subscriber_group_doc.public_title if self.subscriber_group_doc and self.subscriber_group_doc.public else '',
			'unsubscribe_from_group_url': base_unsubscribe_url if self.subscriber_group_doc else '',
			'unsubscribe_general_url': '{}&general=true'.format(base_unsubscribe_url),
			'unsubscribe_as_spam_url': '{}&spam=true'.format(base_unsubscribe_url),
			'unsubscribe_from_campaign_url': '{}&campaign=true'.format(base_unsubscribe_url),
			**args
		}

		if not production_email:
			# replace wrong generated urls with its placeholders (except unsubscribe_from_group, as this is the subscriber-group name which can be useful in rendering tests)
			for key in transmission_variables:
				if key.startswith('unsubscribe_') and key != 'unsubscribe_from_group':
					transmission_variables[key] = '{{ ' + key + ' }}'
				elif key.startswith('open_tracking_image'):
					transmission_variables[key] = ''

		rendered_mail = frappe.render_template(self.email_body or '', transmission_variables)

		if self.parent_doc.email_signature:
			signature = frappe.get_cached_doc('Email Template', self.parent_doc.email_signature)
			rendered_mail += frappe.render_template(signature.response_html or signature.response, transmission_variables)

		# add click-tracking to all links
		if production_email:
			rendered_mail = self.replace_html_links(base_api_url, rendered_mail, r'(href=")(https?:\/\/[^"]+)')
			rendered_mail = self.replace_html_links(base_api_url, rendered_mail, r'(href=\')https?:\/\/([^\']+)')

		return frappe.render_template(self.subject or '', transmission_variables), rendered_mail

	def replace_html_links(self, base_api_url, html_mail, pattern):
		compiled_pattern = re.compile(pattern)

		for href_group in re.findall(compiled_pattern, html_mail):
			# dont rewrite urls to own services, as those are tracked anyways
			if base_api_url in href_group[1]:
				continue

			encoded_link = _bencode(href_group[1].encode()).decode().replace('\n', '')
			html_mail = html_mail.replace(''.join(href_group), '{}{}/email_marketing.api.click?tgt={}&name={}'.format(href_group[0], base_api_url, encoded_link, target_doc.name))
		return html_mail

	def mark_for_reschedule(self, ts=None):
		self.marked_for_reschedule = True

		if ts:
			if not hasattr(self, 'marked_for_reschedule_at') or self.marked_for_reschedule_at > ts:
				self.marked_for_reschedule_at = ts

	def is_marked_for_reschedule(self):
		if hasattr(self, 'marked_for_reschedule'):
			if hasattr(self, 'marked_for_reschedule_at'):
				return self.marked_for_reschedule_at
			return True
