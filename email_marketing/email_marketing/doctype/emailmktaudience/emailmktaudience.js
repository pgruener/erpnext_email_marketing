// Copyright (c) 2022, RS and contributors
// For license information, please see license.txt

frappe.ui.form.on('EmailMktAudience', {
	refresh(frm) {
		const doc = frm.doc;

		if (!doc.__islocal && !doc.__unsaved && in_list(frappe.boot.user.can_write, doc.doctype)) {
			frm.add_custom_button(__('Count'), () => {
				frm.call('generate').then(() => { frm.refresh(); });
			});
		}
	}
});
