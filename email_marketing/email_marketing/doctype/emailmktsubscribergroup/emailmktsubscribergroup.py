# Copyright (c) 2022, RS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class EmailMktSubscriberGroup(Document):
	# Accepts a members list of dicts, with the keys:
	# - reference_doctype
	# - reference_name
	#
	# Those will be filtered by the members (& opt-in setting) of this group (and returned).
	#
	def filter_members(self, members):
		group_members = [{'dt': m['ref_doctype'], 'dn': m['ref_name']} for m in self.as_dict()['members']]

		if self.optin_rule == 'Opt-In':
			return [m for m in members if {'dt': m['reference_doctype'], 'dn': m['reference_name']} in group_members]
		elif self.optin_rule == 'Opt-Out':
			return [m for m in members if {'dt': m['reference_doctype'], 'dn': m['reference_name']} not in group_members]
