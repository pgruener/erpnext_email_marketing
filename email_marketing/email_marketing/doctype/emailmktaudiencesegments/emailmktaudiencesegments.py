# Copyright (c) 2022, RS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class EmailMktAudienceSegments(Document):
	@frappe.whitelist()
	def generate(self):
		segment = frappe.get_cached_doc('EmailMktSegment', self.segment)
		members = segment.generate()

		return members
