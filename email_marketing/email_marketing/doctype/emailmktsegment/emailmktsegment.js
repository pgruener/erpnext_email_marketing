// Copyright (c) 2022, RS and contributors
// For license information, please see license.txt

frappe.ui.form.on('EmailMktSegment', {
	refresh(frm) {
		// init name with a random number
		if (frm.is_new() && !frm.fields_dict.__newname.get_value()) {
			frm.set_value('__newname', 'S' + Math.floor(Math.random() * 999999));
		}

		const doc = frm.doc;

		if (!doc.__islocal && !doc.__unsaved && in_list(frappe.boot.user.can_write, doc.doctype)) {
			frm.add_custom_button(__('Count'), () => {
				frm.call('generate').then(() => { frm.refresh(); });
			});
		}
	},

	// /**
	//  * Opens the modal for filter and segment definition
	//  */
	// btn_open_segment_definition(frm) {
	// 	new frappe.ui.form.MultiSelectDialog({
	// 		doctype: frm.doc.result_doctype,
	// 		target: frm,
	// 		setters: {
	// 				// schedule_date: null,
	// 				// status: null
	// 		},
	// 		add_filters_group: 1,
	// 		date_field: 'creation',
	// 		// columns: ['name'],
	// 		// allow_child_item_selection: 1,
	// 		// child_fieldname: "items", // child table fieldname, whose records will be shown & can be filtered
	// 		// child_columns: ["item_code", "qty"], // child item columns to be displayed
	// 		get_query() {
	// 				return {
	// 						filters: { docstatus: ['!=', 2] }
	// 				}
	// 		},
	// 		action(selections, args) {
	// 			console.log(args); // list of selected item names
	// 			console.log(args.filtered_children); // list of selected item names
	// 			console.log(selections); // list of selected item names
	// 		}
	// 	});
	// },

	// result_doctype(frm) {
	// 	frm.events.set_fieldname_select(frm);
	// },

	setup(frm) {
		frm.set_query('parent_segment', () => {
			let filters = {
				name: ['!=', frm.doc.name]
			}

			if (frm.doc.parent_segment) {
				filters.parent_segment = ['!=', frm.doc.name]
			}

			if (frm.doc.result_doctype) {
				filters.result_doctype = ['=', frm.doc.result_doctype]
			}

			return { filters: filters };
		})
	},

	async parent_segment(frm) {
		const newParentSegment = frm.doc.parent_segment;

		// only request&change doctype if segment wasnt persisted yet
		if (newParentSegment && frm.is_new()) {
			const res = await frappe.db.get_value('EmailMktSegment', newParentSegment, 'result_doctype');

			frm.set_value('result_doctype', res.message?.result_doctype);
		}
	},

	// // copied from webhook.js - webhook.set_fieldname_select
	// set_fieldname_select(frm) {
	// 	if (!frm.doc.result_doctype) {
	// 		return;
	// 	}

	// 	frappe.model.with_doctype(frm.doc.result_doctype, () => {
	// 		// get doctype fields
	// 		let fields = $.map(frappe.get_doc('DocType', frm.doc.result_doctype).fields, (d) => {
	// 			if (frappe.model.no_value_type.includes(d.fieldtype) && !(frappe.model.table_fields.includes(d.fieldtype))) {
	// 				return null;
	// 			} else if (d.fieldtype === 'Currency' || d.fieldtype === 'Float') {
	// 				return { label: d.label, value: d.fieldname };
	// 			} else {
	// 				return { label: `${__(d.label)} (${d.fieldtype})`, value: d.fieldname };
	// 			}
	// 		});

	// 		// add meta fields
	// 		for (let field of frappe.model.std_fields) {
	// 			if (field.fieldname == 'name') {
	// 				fields.unshift({ label: 'Name (Doc Name)', value: 'name' });
	// 			} else {
	// 				fields.push({ label: `${__(field.label)} (${field.fieldtype})`, value: field.fieldname });
	// 			}
	// 		}

	// 		frm.fields_dict.segmentation_operations.grid.update_docfield_property(
	// 			'fieldname', 'options', [''].concat(fields)
	// 		);
	// 	});
	// }
});

frappe.ui.form.on('EmailMktSegmentSelections', {
	// fieldname(frm, cdt, cdn) {
	// 	// TODO: init corresponding operators/values
	// 	debugger
	// 	if (!frm.doc.result_doctype) {
	// 		return;
	// 	}

	// 	let row = locals[cdt][cdn];
	// 	let df = frappe.get_meta(frm.doc.result_doctype).fields.filter((field) => field.fieldname == row.fieldname);

	// 	if (!df.length) {
	// 		// check if field is a meta field
	// 		df = frappe.model.std_fields.filter((field) => field.fieldname == row.fieldname);
	// 	}

	// 	row.key = df.length ? df[0].fieldname : 'name';
	// 	frm.refresh_field('segmentation_operations');
	// }

	btn_segment_filters(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		let selections = frappe.model.get_value(row.doctype, row.name, 'segment_filters');
		try {
			selections = JSON.parse(selections);
		} catch(e) {
			selections = [];
		}

		new frappe.ui.form.MultiSelectDialog({
			doctype: frm.doc.result_doctype,
			target: frm,
			setters: [],
			add_filters_group: 1,
			date_field: 'creation',
			primary_action_label: __('Update'),
			get_query() {
				return {
						filters: { docstatus: ['!=', 2] }
				}
			},
			init() {
				// call super
				frappe.ui.form.MultiSelectDialog.prototype.init.call(this);

				// hide "Make {DocType}" Button
				this.dialog.get_secondary_btn()?.addClass('hide');

				// setup the memoized filters (synchron each after each other)
				if (this.filter_group && selections) {
					let promises = [];

					for (const filter of selections) {
						promises.push(() => this.filter_group.add_filter(...filter));
					}

					frappe.run_serially(promises).then(() => {
						this.get_results();
					});

					// console.log(this.dialog.fields_dict.filter_area.$wrapper)
					this.filter_group.toggle_empty_filters(false);
				}

				// hide primary filters
				this.dialog.fields_dict.search_term.$wrapper.addClass('hide')
				// const fields = this.get_fields();
				// const sectionBreakIdx = fields.indexOf(fields.find(fld => fld.fieldtype === 'Section Break'));
				// for (let i = 0; i <= sectionBreakIdx + 1; ++i) {
				// 	if (!fields[i].fieldname) {
				// 		continue;
				// 	}
				// 	this.dialog.fields_dict[fields[i].fieldname].$wrapper.addClass('hide');
				// }
			},
			action(_selected_item_names, _settings) {
				frappe.model.set_value(row.doctype, row.name, 'segment_filters', JSON.stringify(this.filter_group.get_filters()));
				// console.log(_selected_item_names); // list of selected item names

				this.dialog.hide();
			}
		});
	},
});
