# Copyright (c) 2022, RS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import fnmatch

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
