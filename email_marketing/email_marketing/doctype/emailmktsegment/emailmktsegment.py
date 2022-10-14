# Copyright (c) 2022, RS and contributors
# For license information, please see license.txt

import frappe
import frappe.utils
from frappe.model.document import Document
from frappe.desk.search import search_widget

import json

class EmailMktSegment(Document):
	@frappe.whitelist()
	def generate(self):
		results = []
		parent_records = None
		idx = 0

		# if there is a parent_segment known, this has all the allowed records (like an additional *and* operation)
		if self.parent_segment:
			# print('parent')
			parent_segment = frappe.get_cached_doc('EmailMktSegment', self.parent_segment)
			parent_records = parent_segment.generate()

		for segmentation_operation in self.segmentation_operations:
			idx += 1

			# print('operation {}'.format(idx))
			search_widget(doctype=self.result_doctype, txt='',
										filters=json.loads(segmentation_operation.segment_filters),
										filter_fields=[],
										as_dict=True,
										page_length=999999)

			search_results = []
			for sr in frappe.response['values']:
				search_results.append({
					'reference_doctype': self.result_doctype,
					'reference_name': sr.name
				})

			frappe.response.values = []

			# print('results raw: {}'.format(search_results))
			if idx == 1:
				results = search_results
			else:
				if segmentation_operation.log_operator == 'and':
					results = [result for result in search_results if result in results]
				elif segmentation_operation.log_operator == 'or':
					# add those, which are not already present
					results += [result for result in search_results if result not in results]
				elif segmentation_operation.log_operator == 'xor':
					results = [result for result in search_results if result not in results]

			# print('results after operator: {}'.format(results))

			# always reduce the results to match parent records
			if parent_records:
				results = [result for result in results if result in parent_records]
				# print('results after parent merge: {}'.format(results))

			# update counts
			segmentation_operation.segment_count = len(search_results)
			segmentation_operation.segment_count_in_context = len(results)
			segmentation_operation.save()

		self.item_count = len(results)
		self.last_generated_at = frappe.utils.now_datetime()
		self.save()

		return results

	def perform_search(self):
		return self.generate()
