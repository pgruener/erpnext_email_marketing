# Copyright (c) 2022, RS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class EmailMktSalutation(Document):
	def after_save(self):
		frappe.cache().hdel('email_marketing_cache', 'salutations')
