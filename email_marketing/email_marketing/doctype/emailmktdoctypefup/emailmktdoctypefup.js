// Copyright (c) 2023, RS and contributors
// For license information, please see license.txt

frappe.ui.form.on('EmailMktDocTypeFup', {
	refresh: function(frm) {
		frm.docfield_updater = new FollowUpDocFields(frm);

		frm.events.target_doc_discovery(frm);

		// limit the doctypes to only root and real ones
		frm.set_query('source_doctype', () => {
			return {
				filters: {
					'issingle': 0,
					'istable': 0
				}
			}
		});

		frm.set_query('target_doctype', () => {
			return {
				filters: {
					'issingle': 0,
					'istable': 0
				}
			}
		});

		// for new docs, the following child_table settings are hidden and therefore not set
		if (frm.doc.__islocal) {
			return;
		}

		//
		// EmailMktFupConditions
		frm.set_query('comparison_doctype', 'conditions', () => {
			return {
				filters: {
					'issingle': 0,
					'istable': 0
				}
			}
		});

		//
		// EmailMktFupDefaults
		frm.docfield_updater.update_possible_docfields('target_column', frm.doc.target_doctype, null, 'property_defaults');
		frm.docfield_updater.update_possible_docfields('source_column', frm.doc.source_doctype, null, 'property_defaults');

		//
		// EmailMktFupChildrenDefaults
		frm.set_query('child_doctype', 'children_defaults', () => {
			return {
				query: 'email_marketing.email_marketing.doctype.emailmktdoctypefup.emailmktdoctypefup.get_child_doctypes',
				filters: {
					'doctype': frm.doc.target_doctype
				}
			}
		});
	},

	async target_doc_discovery_column(frm) {
		if (frm.doc.target_doc_discovery === 'Dynamic Link' && frm.doc.target_doctype) {
			let fields = await frm.docfield_updater.doctype_fields(frm.doc.target_doctype);
			let doctype_ref_col = fields.filter(f => f.fieldname == frm.doc.target_doc_discovery_column)[0];

			if (doctype_ref_col) {
				frm.docfield_updater.update_possible_docfields('target_doc_discovery_doctype_column', frm.doc.target_doctype, { 'fieldname': doctype_ref_col.options });
				return;
			}
		}

		// make invalid filter to get empty select options
		frm.docfield_updater.update_possible_docfields('target_doc_discovery_doctype_column', frm.doc.target_doctype, { 'fieldname': '__NaN__' });
	},

	target_doc_discovery(frm) {
		frm.docfield_updater.update_possible_docfields('target_doc_discovery_column', frm.doc.target_doctype, frm.doc.target_doc_discovery);
		frm.events.target_doc_discovery_column(frm);
	}
});

class FollowUpDocFields {
	constructor(frm) {
		this.frm = frm;
		this.doctypes_resolved = {};
	}

	async doctype_fields(doctype) {
		if (!this.doctypes_resolved[doctype]) {
			await frappe.model.with_doctype(doctype);
			this.doctypes_resolved[doctype] = true;
		}

		let fields = frappe.get_doc('DocType', doctype).fields;

		// add meta fields
		// for (let field of frappe.model.std_fields) {
		// 	fields.push(field);
		// }

		return fields.concat(frappe.model.std_fields);
	}

	async update_possible_docfields(property_name, doctype, filter_type, child_table_name) {
		if (!property_name || !doctype) {
			return;
		}

		// get doctype fields
		let fields = await this.doctype_fields(doctype);

		fields = fields.map((d) => {
			if (typeof filter_type === 'object') {
				// all properties must match
				for (let key in filter_type) {
					if (d[key] !== filter_type[key]) {
						return;
					}
				}
			} else if (typeof filter_type === 'string' && d.fieldtype !== filter_type) {
				return;
			}

			return { label: `${d.label ? __(d.label) : ''} (${d.fieldtype})`, value: d.fieldname };
		}).filter((d) => d);

		if (child_table_name) {
			// init property on child table
			this.frm.fields_dict[child_table_name].grid.update_docfield_property(property_name, 'options', [''].concat(fields));
		} else {
			// init property on cur_frm doctype
			this.frm.set_df_property(property_name, 'options', [''].concat(fields));
		}
	}
}

frappe.ui.form.on("EmailMktFupConditions", {
	async doctype_column(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		let fields = await frm.docfield_updater.doctype_fields(row.comparison_side === 'Source' ? frm.doc.source_doctype : frm.doc.target_doctype);
		let df = fields.filter((field) => field.fieldname === row.doctype_column)[0];

		let oldComparisonDoctype = row.comparison_doctype;
		let oldAutoComparisonDoctype = df?.fieldtype === 'Link' && df.options === row.comparison_doctype && row.comparison_doctype;

		if (df?.fieldtype === 'Link') {
			row.comparison_doctype = df.options;

			if (oldComparisonDoctype && oldAutoComparisonDoctype !== row.comparison_doctype) {
				row.comparison_doctype_link = null;
			}
		} else if (oldAutoComparisonDoctype) {
			row.comparison_doctype = null;
			row.comparison_doctype_link = null;
		}

		frm.refresh_field(row.parentfield);
	},

	comparison_side(frm, cdt, cdn) {
		// let row = locals[cdt][cdn];
		frm.script_manager.trigger('form_render', cdt, cdn);
	},

	conditions_add(frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		// get previous row with child_doctype in reverse order
		let prev_row = frm.doc.conditions.slice().reverse().find((d) => d.comparison_side && d.idx < row.idx);
		if (!prev_row) {
			return;
		}

		// initialize comparison_side value from previous row
		row.comparison_side = prev_row.comparison_side;
		frm.script_manager.trigger('form_render', cdt, cdn);

		frm.refresh_field(row.parentfield);
	},

	form_render(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		let col_doctype = row.comparison_side === 'Source' ? frm.doc.source_doctype : frm.doc.target_doctype;

		// display columns of parent's source or target doctype (based on comparison_side value)
		frm.docfield_updater.update_possible_docfields('doctype_column', col_doctype, null, 'conditions');
	}
});

frappe.ui.form.on("EmailMktFupChildrenDefaults", {
	async column(frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		if (row.child_doctype) {
			// all is fine if child_doctype is set, as no other options are available
			return;
		}

		// get previous row with child_doctype in reverse order
		let prev_row = frm.doc.children_defaults.slice().reverse().find((d) => d.child_doctype && d.idx < row.idx);
		if (!prev_row) {
			return;
		}

		let fields = await frm.docfield_updater.doctype_fields(prev_row.child_doctype);
		let df = fields.find((field) => field.fieldname === row.column);

		let oldComparisonDoctype = row.value_doctype;
		let oldAutoComparisonDoctype = df?.fieldtype === 'Link' && df.options === row.value_doctype && row.value_doctype;

		if (df?.fieldtype === 'Link') {
			row.value_doctype = df.options;

			if (oldComparisonDoctype && oldAutoComparisonDoctype !== row.value_doctype) {
				row.value_doctype_link = null;
			}
		} else if (oldAutoComparisonDoctype) {
			row.value_doctype = null;
			row.value_doctype_link = null;
		}

		// call form_render to init column select
		frm.script_manager.trigger('form_render', cdt, cdn)

		frm.refresh_field(row.parentfield);
	},

	form_render(frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		if (row.child_doctype) {
			// update *child_doctype_fieldname* options
			frm.docfield_updater.update_possible_docfields('child_doctype_fieldname', frm.doc.target_doctype, {'fieldtype': 'Table', 'options': row.child_doctype}, 'children_defaults');

			// if *child_doctype* is set, the other options for further column/value definition are not available, so skip
			return;
		}

		// get previous row with child_doctype
		let prev_row = frm.doc.children_defaults.slice().reverse().find((d) => d.child_doctype && d.idx < row.idx);
		if (!prev_row) {
			return;
		}

		frm.docfield_updater.update_possible_docfields('column', prev_row.child_doctype, null, 'children_defaults');
	}
});
