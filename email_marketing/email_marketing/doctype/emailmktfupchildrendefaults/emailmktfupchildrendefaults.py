# Copyright (c) 2023, RS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class EmailMktFupChildrenDefaults(Document):
	def get_value(self):
		return self.value # perhaps later there need to be a differenctiation between (Dynamic) Link or Value settings
