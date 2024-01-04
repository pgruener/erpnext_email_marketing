// Copyright (c) 2022, RS and contributors
// For license information, please see license.txt

frappe.ui.form.on('EmailMktEmailReceiver', {
	refresh: function(frm) {
		const endpoint = `${location.protocol}//${location.host}/api/method/email_marketing.receive_mail.receive_mail_via_sns`;
		frm.fields_dict.aws_sns_api_endpoint.set_value(endpoint);
	}
});
