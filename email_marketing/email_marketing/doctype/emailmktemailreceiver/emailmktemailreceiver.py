# Copyright (c) 2022, RS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import fnmatch
import boto3

class EmailMktEmailReceiver(Document):
	def before_insert(self):
		self.sns_subscription_active = None

	def target_email_account_for_receiver_email(self, inbound_email_address):
		if isinstance(inbound_email_address, list):
			inbound_email_addresses = inbound_email_address
		else:
			inbound_email_addresses = [inbound_email_address]

		for mapping in self.email_account_mappings:
			for inbound_email_address in inbound_email_addresses:
				if fnmatch.fnmatch(inbound_email_address, mapping.fn_match_pattern):
					return frappe.get_cached_doc('Email Account', mapping.email_account)

	def matching_email_forwarding_rules(self, inbound_email_address):
		if isinstance(inbound_email_address, list):
			inbound_email_addresses = inbound_email_address
		else:
			inbound_email_addresses = [inbound_email_address]

		matching_rules = []
		for email_forwarding_rule in self.email_forwarding_rules:
			for inbound_email_addr in inbound_email_addresses:
				# skip if rule is already appended in matching_rules
				if email_forwarding_rule in matching_rules:
					continue

				if fnmatch.fnmatch((inbound_email_addr or '').lower(), (email_forwarding_rule.inbound_email_addr_pattern or '').lower()):
					matching_rules.append(email_forwarding_rule)

		return matching_rules

	def s3_session(self, force_new=False):
		if not hasattr(self, 's3_session_instance'):
			self.s3_session_instance = None

		if (not self.s3_session_instance or force_new) and self.aws_sns_api_key and self.ses_receiving_region:
			self.s3_session_instance = boto3.Session(	aws_access_key_id=self.aws_sns_api_key,
																								# aws_secret_access_key=get_decrypted_password(self.doctype, self.name, 'aws_sns_api_secret'),
																								aws_secret_access_key=self.get_password('aws_sns_api_secret'),
																								region_name=self.ses_receiving_region)

		return self.s3_session_instance
