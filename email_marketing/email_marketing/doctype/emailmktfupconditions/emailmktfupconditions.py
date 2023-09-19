# Copyright (c) 2023, RS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class EmailMktFupConditions(Document):
	def matches(self, doc):
		try:
			cmp_left = doc.get_value(self.doctype_column)
		except AttributeError:
			frappe.throw('Doctype "{}" has no column "{}" for Fup Comparison'.format(doc.doctype, self.doctype_column))

		cmp_right = self.comparison_value

		if self.operator == '=':
			return cmp_left == cmp_right
		elif self.operator == '!=':
			return cmp_left != cmp_right
		elif self.operator == '<':
			return cmp_left < cmp_right
		elif self.operator == '<=':
			return cmp_left <= cmp_right
		elif self.operator == '>':
			return cmp_left > cmp_right
		elif self.operator == '>=':
			return cmp_left >= cmp_right

		frappe.throw('Unknown operator: {}'.format(self.operator))
