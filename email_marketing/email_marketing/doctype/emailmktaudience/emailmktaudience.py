# Copyright (c) 2022, RS and contributors
# For license information, please see license.txt

import frappe
import frappe.utils
from frappe.model.document import Document
from itertools import groupby #, sorted

class EmailMktAudience(Document):
	@frappe.whitelist()
	def generate(self):
		if self.audience_type == 'Static':
			# has properties:
			# - name
			# - reference_doctype
			# - reference_name
			res_members = []

			for static_record in self.audience_records:
				res_members.append({
					'reference_doctype': static_record.reference_doctype,
					'reference_name': static_record.reference_name,
					# in a static audience, the creation timestamp is a valid equivalent for an event_creation timestamp
					'event_creation': static_record.creation
				})

		elif self.audience_type == 'Dynamic':
			res_members = []
			idx = 0

			for audience_segment in self.audience_segments:
				idx += 1
				members = audience_segment.generate()

				if idx == 1:
					res_members = members
				elif audience_segment.operator == 'Union (or)':
					# add those, which are not already present
					res_members += [record for record in members if record not in res_members]
				elif audience_segment.operator == 'Intersect (and)':
					res_members = [record for record in members if record in res_members]
				elif audience_segment.operator == 'Except (xor)':
					res_members = [record for record in members if record not in res_members]


				audience_segment.segment_count = len(members)
				audience_segment.segment_count_in_context = len(res_members)
				audience_segment.save()

				# properties audience_segment:	operator (nothing, Union (or), Intersect (and), Except (xor))
				# 															segment, segment_count, segment_count_in_context
				# segment = frappe.get_cached_doc('EmailMktAudienceSegments', audience_segment.segment)

		self.item_count = len(res_members)
		self.last_generated_at = frappe.utils.now_datetime()
		self.save()

		return res_members

	def enrich_members_data(self, audience_members, enrich_by_fields=[], filter_conditions={}, skip_records_which_dont_fit_additional_fields=True, deduplicate_by=False):
		return enrich_members_data(audience_members, enrich_by_fields, filter_conditions, skip_records_which_dont_fit_additional_fields, deduplicate_by)

def enrich_members_data(audience_members, enrich_by_fields=[], filter_conditions={}, skip_records_which_dont_fit_additional_fields=True, deduplicate_by=False):
	obsolete_records = []
	sorted_by_doctype = sorted(audience_members, key=lambda m: m['reference_doctype'])

	for doctype, members in groupby(sorted_by_doctype, key=lambda m: m['reference_doctype']):
		base_filter = {}
		requested_fields = ['name']

		# if the querying doctype has a "unsubscribed" property, add exclude unsubscribed ones by default.
		# add filters to selection if the doctype owns the property
		for fk in filter_conditions:
			if frappe.get_meta(doctype).has_field(fk):
				base_filter[fk] = filter_conditions[fk]

		for additional_field in enrich_by_fields:
			if frappe.get_meta(doctype).has_field(additional_field):
				requested_fields.append(additional_field)
			elif skip_records_which_dont_fit_additional_fields:
				# skip the whole doctype, if the requested properties cannot be requested
				continue

		# read additional fields
		for members in batch(audience_members):
			filters = { **base_filter.copy(), 'name': ['in', [r['reference_name'] for r in members]] }

			enriched_properties = frappe.get_all(doctype, filters=filters, fields=requested_fields, limit_page_length=9999)
			for enriched_property in enriched_properties:
				# map the emails back to the audience_members
				for orig_member in [m for m in audience_members if m['reference_doctype'] == doctype and m['reference_name'] == enriched_property.name]:
					for property in requested_fields[1:]:
						orig_member[property] = enriched_property[property]

			# collect unreturned records as obsolete ones
			obsolete_records += [m for m in members if m['reference_name'] not in [e['name'] for e in enriched_properties]]

	# if there are unresolved records (e.g. cause they're blocked etc), remove them from audience
	for obsolete_record in obsolete_records:
		audience_members.remove(obsolete_record)

	# deduplicate by email_id if there were several contacts with the same email id
	if deduplicate_by: # e.g. "email_id"
		audience_members = list(dict([[r[deduplicate_by], r] for r in audience_members if deduplicate_by in list(r.keys())]).values())

	return audience_members

def batch(iterable, n=1000):
	l = len(iterable)
	for ndx in range(0, l, n):
		yield iterable[ndx:min(ndx + n, l)]
