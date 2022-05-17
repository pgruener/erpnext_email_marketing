frappe.ui.form.on('Email Template', {
	setup: function(frm) {
    frm.fields_dict.signature.get_query = function(doc) {
        return {
            filters: {
              // 'relevant_doctypes.linked_doctype': ['is', 'not set'],
              signature: ['is', 'not set'],
              name: ['!=', doc.name]
            }
        };
      };
	}
});
