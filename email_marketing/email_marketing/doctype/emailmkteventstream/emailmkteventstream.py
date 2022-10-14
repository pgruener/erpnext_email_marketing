# Copyright (c) 2022, RS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class EmailMktEventStream(Document):
	def validate(self):
		if frappe.db.exists('EmailMktEventStream', {
				'entry_type': self.entry_type,
				'triggering_node': self.triggering_node,
				'reference_doctype': self.reference_doctype,
				'reference_name': self.reference_name,
			}):

			# TODO: It's kind of correct to not allow repeated events for the same
			# TODO: reference_doc, as the campaign state should not be repeated
			# TODO: everytime a link is clicked again (for example).
			# TODO: But for stats, it should still be counted somewhere.
			# import pdb; pdb.set_trace()
			frappe.throw('Already known', frappe.DuplicateEntryError)

	# def after_insert(self):
	# 	# TODO: schedule corresponding campaign node to be processed
	# 	# TODO: in the campaign
	#
	#
	# 	# TODO: invoke the email nodes' listeners and make them register as soon as it is processed.
	# 	# email_node.insert_or_update_event_for_node(receipient, processed=True)

