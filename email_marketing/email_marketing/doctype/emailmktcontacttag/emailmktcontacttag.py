# Copyright (c) 2022, RS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime
from frappe.model.document import Document

class EmailMktContactTag(Document):
	def before_save(self):
		if self.valid_to and self.valid_to <= now_datetime():
			self.active = False
		elif self.valid_from and self.valid_from > now_datetime():
			self.active = False
		else:
			self.active = True

		# notify email campaigns/segments, which depend on the tag, that a change happened
		self.update_segments()

	def after_delete(self):
		self.update_segments()

	def update_segments(self):
		pass
