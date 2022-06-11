// Copyright (c) 2022, RS and contributors
// For license information, please see license.txt

frappe.ui.form.on('EmailMktEmailReceiver', {
	setup: function(frm) {
		frm.fields_dict.aws_sns_endpoint = frappe.ui.form.make_control({
			parent: frm.fields_dict.sns_subscription_active.wrapper.closest('form'),
			df: {
				label: 'AWS SNS Endpoint',
				fieldname: 'aws_sns_api_endpoint',
				fieldtype: 'Data',
				read_only: true
			},
			render_input: true,
			doc: frm.doc
		});
	},

	refresh: function(frm) {
		const endpoint = `${location.protocol}//${location.host}/api/method/email_marketing.receive_mail.receive_mail_via_sns`;
		frm.fields_dict.aws_sns_endpoint.set_value(endpoint);
	}
});
