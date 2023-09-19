# Copyright (c) 2023, RS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc

class EmailMktDocTypeFup(Document):
	def is_valid_for(self, doc, comparison_side):
		"""
		Checks if the follow-up conditions are matching the given doc.
		doc: The doc to check against.
		comparison_side: 'Source' or 'Target'
		"""
		# generate groups of conditions by those with the same doctype_column & operator
		condition_groups = {}
		for condition in [c for c in self.conditions if c.comparison_side == comparison_side]:
			condition_groups.setdefault((condition.doctype_column, condition.operator), []).append(condition)

		# check conditions: all condition_groups must be true, while only one of the conditions in a group must be true
		for (_doctype_column, _operator), conditions in condition_groups.items():
			if not any([condition.matches(doc) for condition in conditions]):
				return False

		return True

	def create_follow_up_doc(self, source_doc, persist=True):
		# Currently the fup docs are generated in the process background, so the permissions may be ignored (for now)
		ignore_permissions = True

		def postprocess(source_doc, target_doc):
			self.sync_follow_up_doc(source_doc, target_doc, persist=False)

		target_doc = get_mapped_doc(source_doc.doctype, source_doc.name, {source_doc.doctype: {'doctype': self.target_doctype}}, postprocess=postprocess, ignore_permissions=ignore_permissions)

		if persist:
			target_doc.insert(ignore_permissions=ignore_permissions)

		return self.mark_to_doc(target_doc)

	def detect_follow_up_docs(self, source_doc):
		"""
		Selects the follow-up docs, which are connected as follow-up to the given doc.
		"""
		target_docs = []
		target_doc_names = []
		if self.target_doc_discovery == 'Link':
			target_doc_names = frappe.get_all(self.target_doctype, filters={self.target_doc_discovery_column: source_doc.name}, order_by='creation desc')
		elif self.target_doc_discovery == 'Dynamic Link':
			target_doc_names = frappe.get_all(self.target_doctype, filters={self.target_doc_discovery_column: source_doc.name, self.target_doc_discovery_doctype_column: self.source_doctype}, order_by='creation desc')
		elif self.target_doc_discovery == 'Custom Method':
			target_docs = eval(self.target_doc_discovery_custom_method)(source_doc, self)
		else:
			# no target doc discovery method set
			return

		if target_doc_names:
			target_docs = [frappe.get_doc(self.target_doctype, d) for d in target_doc_names]

		return [self.mark_to_doc(target_doc) for target_doc in target_docs if self.is_valid_for(target_doc, 'Target')]

	def mark_to_doc(self, doc):
		if not doc.flags.marked_fups:
			doc.flags.marked_fups = []

		doc.flags.marked_fups.append(self)

		return doc

	def sync_follow_up_doc(self, source_doc, target_doc, persist=True):
		"""
		Updates the follow-up doc with the given values.
		"""
		# skip if target_doc is already persisted and sync_target is not set
		# but dont skip if target_doc is new
		if not target_doc.is_new() and not self.sync_target:
			return

		if self.sync_target_method:
			if get_module_method(self.sync_target_method)(source_doc, target_doc, self) == False:
				return

		# check if method *sync_after_save_from* is available in target doc
		if hasattr(target_doc, 'sync_after_save_from'):
			if target_doc.sync_after_save_from(source_doc, self) == False:
				return

		# iterate property_defaults and children_defaults
		for property_default in self.property_defaults:
			if property_default.copy_policy == 'Copy if Target is Empty':
				if target_doc.get(property_default.target_column):
					continue
			elif property_default.copy_policy == 'Copy on Creation' and not target_doc.is_new():
				continue
			elif property_default.copy_policy == 'Copy':
				pass

			if property_default.source_column:
				target_doc.set(property_default.target_column, source_doc.get(property_default.source_column))
			else:
				target_doc.set(property_default.target_column, property_default.target_value)

		target_children_empty = {}

		for children_default in self.children_defaults:
			if not children_default.child_doctype:
				# each child-record definition starts with a child_doctype
				continue

			target_children = target_doc.get(children_default.child_doctype_fieldname)

			if not target_children:
				# cache this information, as with children_defaults, a record could have been already created during the same process.
				target_children_empty[children_default.child_doctype_fieldname] = True

			if children_default.copy_policy_record == 'Create Only if no records are present' and not target_children_empty[children_default.child_doctype_fieldname]:
				continue # skip if there is already one or more records

			# get all following children_defaults records until the next record has a child_doctype set
			property_defaults = self.children_defaults[children_default.idx:next((d.idx - 1 for d in self.children_defaults if d.idx > children_default.idx and d.child_doctype), self.children_defaults[-1].idx)]

			if children_default.copy_policy_record == 'Skip Create on matching # left values':
				# compare the first self.copy_policy_record_left_matching_values values of property_defaults with the properties of the existing child records
				for target_child in target_children:
					matched_required_values = True
					for property_default in property_defaults[0..self.copy_policy_record_left_matching_values - 1]:
						if property_default.get_value() != target_child.get(property_default.property):
							matched_required_values = False
							break

					if matched_required_values:
						# skip creating a new child record, as a comparable one already exists
						continue

			# generate a new child record with the defined property_defaults
			# build key-val dict from property_defaults
			property_defaults_dict = {}
			for property_default in property_defaults:
				property_defaults_dict[property_default.column] = property_default.get_value()

			target_doc.append(children_default.child_doctype_fieldname, property_defaults_dict)

		# Currently the fup docs are generated in the process background, so the permissions may be ignored (for now)
		if persist:
			target_doc.flags.ignore_permissions = True
			target_doc.save()

	def fup_value(self, property_ident):
		return next((v.value for v in self.fup_values if v.identifier == property_ident), None)

	@classmethod
	def detect_follow_ups(cls, doc):
		"""
		Detects all follow-up definitions (not docs), which are valid for the given doc as source doc.
		"""
		docs = []

		for fup_name in frappe.get_all('EmailMktDocTypeFup', filters={'source_doctype': doc.doctype}):
			fup = frappe.get_cached_doc('EmailMktDocTypeFup', fup_name)
			if fup.is_valid_for(doc, 'Source'):
				docs.append(fup)

		return docs

@frappe.whitelist()
def doc_fup_eval(doctype_or_doc, docname=None, persist=True, collect_all_matched_fup_docs=False, touched_fup_docs=None):
	"""
	Can be called on each doctypes *on_update* (or similiar) event(s).
	Checks if there is a follow-up customizing, which fits the EmailMktDocTypeFup
	settings and probably creates or updates a follow-up doc. It also returns
	the follow-up doc, if there is one.

	:doctype_or_doc: The doctype or doc, which is the source for the follow-up doc evaluation.
	:docname: If doctype_or_doc is a string, this is the docname of the source doc.
	:persist: If set to False, the follow-up doc is only built and not persisted by this routine.
	:collect_all_matched_fup_docs: If set to True, all matched follow-up docs are returned.
	If not (Default), only those detected follow-up docs are returned, which really were touched.
	"""
	doc = doc_from_params(doctype_or_doc, docname)

	# skip if doc is already known in touched_fup_docs
	touched_fup_docs = touched_fup_docs or []
	if next((True for fup_doc in touched_fup_docs if fup_doc.doctype == doc.doctype and fup_doc.name == doc.name), False):
		return touched_fup_docs

	touched_fup_docs.append(doc)

	for fup in [fup for fup in EmailMktDocTypeFup.detect_follow_ups(doc) if fup.is_valid_for(doc, 'Source')]:
		# check if there are already follow-up docs, which matches the settings
		fup_docs = fup.detect_follow_up_docs(doc)
		if fup_docs:
			for fup_doc in fup_docs:
				# update the already present follow-up docs
				res_doc = fup.sync_follow_up_doc(doc, fup_doc)
				if res_doc or collect_all_matched_fup_docs:
					touched_fup_docs.append(fup_doc)
		else:
			# create a new follow-up doc if not available yet
			new_doc = fup.create_follow_up_doc(doc, persist=False if fup.target_generation_method else persist)
			if fup.target_generation_method:
				# call the target_generation_method to manipulate the new_doc
				get_module_method(fup.target_generation_method)(doc, new_doc, fup)

				if persist:
					new_doc.save()

			touched_fup_docs.append(new_doc)

	touched_fup_docs = [fup_doc for fup_doc in touched_fup_docs if fup_doc]

	# also eval fup docs for all touched fup docs (only if new fups have been able to be created/persisted)
	if persist:
		for fup_doc in touched_fup_docs:
			doc_fup_eval(fup_doc, touched_fup_docs=touched_fup_docs)

	return touched_fup_docs

def doc_from_params(doctype_or_doc, docname=None):
	if isinstance(doctype_or_doc, dict):
		doc = frappe.get_doc(doctype_or_doc['doctype'], doctype_or_doc['name'])
	elif isinstance(doctype_or_doc, Document):
		doc = doctype_or_doc
	elif docname:
		doc = frappe.get_doc(doctype_or_doc, docname)
	else:
		raise ValueError('No docname given')

	return doc

def get_module_method(full_method_name):
	"""
	Returns the module method (as a callable) from the given full method name.
	e.g. 'apps.email_marketing.email_marketing.email_marketing.doctype.emailmktdoctypefup.emailmktdoctypefup.sync_target'
	"""

	# split the module path into module and method name
	module_name, method_name = full_method_name.rsplit('.', 1)

	# import the module
	# module = importlib.import_module(module_name)
	module = __import__(module_name, fromlist=[method_name])

	# get the method
	method = getattr(module, method_name)

	return method

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_child_doctypes(doctype, txt, searchfield, start, page_len, filters):
	fields = []
	target_doctype = filters.get('doctype')

	for field in [f for f in frappe.get_meta(target_doctype).fields if f.fieldtype == 'Table']:
		fields.append([field.options, field.fieldname])

	return fields
