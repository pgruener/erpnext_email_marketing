// Copyright (c) 2022, RS and contributors
// For license information, please see license.txt

frappe.ui.form.on('EmailMktCampaign', {
	refresh(frm) {
		const doc = frm.doc;

		if (!doc.__islocal && !doc.__unsaved
				&& in_list(frappe.boot.user.can_write, doc.doctype)) {

			frm.add_custom_button(__('Count Audiences'), () => {
				frm.call('generate_audiences').then(frm.refresh);
			});

			switch (doc.status) {
				case 'Planned':
					frm.add_custom_button(__('Start Campaign'), () => {
						frappe.confirm(__('Really Start Campaign?'), () => {
							frm.call('start_processing').then(() => { frm.refresh(); });
						});
					}, 'fa fa-play', 'btn-success');

					break;

				case 'Running':
					frm.add_custom_button(__('Stop Campaign'), () => {
						frappe.confirm(__('Really Stop Campaign?'), () => {
							frm.call('stop_processing').then(() => { frm.refresh(); });
						});
					}, 'fa fa-stop', 'btn-success');

					break;

				case 'Finished':
					frm.add_custom_button(__('Re-Open'), () => {
						frappe.confirm(__('Really Open the Campaign again?'), () => {
							frm.call('reopen_processing').then(() => { frm.refresh(); });
						});
					});

					break;
				// case 'Aborted':
			}
		}

		if (frm.fields_dict?.campaign_emails?.grid) {
			frm.fields_dict.campaign_emails.grid.get_field('based_on').get_query = (_doc, _cdt, cdn) => {
				return {
					filters: {
						'parent': doc.name,
						'name': ['!=', cdn]
					}
				}
			}

			frm.fields_dict.campaign_emails.grid.get_field('wait_event_in_email').get_query = (doc, cdt, cdn) => {
				return {
					filters: {
						'parent': locals[cdt][cdn]?.wait_event_in_email_campaign || doc.name,
						'name': ['!=', cdn]
					}
				}
			}

			frm.fields_dict.campaign_emails.grid.get_field('combination_layer_1').get_query = (doc, _cdt, cdn) => {
				return {
					filters: {
						'parent': doc.name,
						'name': ['!=', cdn]
					}
				}
			}

			frm.fields_dict.campaign_emails.grid.get_field('combination_layer_2').get_query = (doc, _cdt, cdn) => {
				return {
					filters: {
						'parent': doc.name,
						'name': ['!=', cdn]
					}
				}
			}
			// if (frm.fields_dict?.campaign_emails?.grid && !Object.entries(frm.fields_dict.campaign_emails.grid.custom_buttons).length) {
				// frm.fields_dict.campaign_emails.grid.add_custom_button(__('Test Mail'), this.btn_test_email.bind(this));
		}

		frm.events.setup_dashboard(frm);
	},

	setup_dashboard(frm) {
		if(!frm.doc.__islocal && cint(frm.doc.email_sent)
			&& frm.doc.__onload && frm.doc.__onload.status_count) {
			var stat = frm.doc.__onload.status_count;
			var total = frm.doc.scheduled_to_send;
			if(total) {
				$.each(stat, function(k, v) {
					stat[k] = flt(v * 100 / total, 2) + '%';
				});

				frm.dashboard.add_progress("Status", [
					{
						title: stat["Not Sent"] + " Queued",
						width: stat["Not Sent"],
						progress_class: "progress-bar-info"
					},
					{
						title: stat["Sent"] + " Sent",
						width: stat["Sent"],
						progress_class: "progress-bar-success"
					},
					{
						title: stat["Sending"] + " Sending",
						width: stat["Sending"],
						progress_class: "progress-bar-warning"
					},
					{
						title: stat["Error"] + "% Error",
						width: stat["Error"],
						progress_class: "progress-bar-danger"
					}
				]);
			}
		}
	},

	// btn_test_email(_event) {
	// 	const selectedRecords = cur_frm.fields_dict.campaign_emails.grid.get_selected();

	// 	if (!selectedRecords.length) {
	// 		return
	// 	}

  //   for (let row of cur_frm.fields_dict.campaign_emails.grid.get_data()) {
  //     if (selectedRecords.findIndex(sel => sel === row.name) === -1) {
  //       continue;
  //     }

  //   }
	// }
});

frappe.ui.form.on('EmailMktCampaignEmail', {
	async btn_test_email(frm, cdt, cdn) {
		// const row = locals[cdt][cdn];
		// let attrValue = frappe.model.get_value(row.doctype, row.name, 'campaign_emails');

		const doc = locals[cdt][cdn];

		if (doc?.entry_type !== 'Email') {
			return
		}

		let d = new frappe.ui.Dialog({
			title: __('Test E-Mail'),
			size: 'extra-large',
			fields: [
					{
							label: __('Sender Name'),
							fieldname: 'sender_name',
							fieldtype: 'Data',
							read_only: 1
					},
					{
							label: __('Receipient'),
							fieldname: 'to_address',
							fieldtype: 'Data',
							read_only: 1
					},
					{
							label: __('Subject'),
							fieldname: 'subject',
							fieldtype: 'Data',
							read_only: 1
					},
					{
							fieldname: 'col_break_1',
							fieldtype: 'Column Break'
					},
					{
							label: __('Test E-Mail Recipient'),
							fieldname: 'test_email_receipient',
							fieldtype: 'Data',
							default: ''
					},
					{
							label: 'Recipient DocType',
							fieldname: 'receipient_doctype',
							fieldtype: 'Link',
							options: 'DocType'
					},
					{
							label: 'Recipient Doc',
							fieldname: 'receipient_id',
							fieldtype: 'Dynamic Link',
							options: 'receipient_doctype',
							async change() {
								// event is permitted whenever value was changed from user
								if (!d.get_value('receipient_id')) {
									return
								}

								// !d.demo_receipientsIdx && (d.demo_receipientsIdx = 0)
								// const receiver = d.demo_receipients[d.demo_receipientsIdx]

								const response = await frm.call('prepare_email', {
									preparation_email_name: cdn,
									receiver_doctype: d.get_value('receipient_doctype'),
									receiver_id: d.get_value('receipient_id')
									// receiver_doctype: receiver.reference_doctype,
									// receiver_id: receiver.reference_name,
									// email_id: receiver.email_id
								});

								const responseValues = response?.message;

								if (!responseValues) {
									frappe.show_alert({
										message: __('An error occured during email preparation'),
										indicator: 'red'
									});

									return;
								}

								d.set_values(responseValues);

								// re-generate preview mail
								// needs to be assigned separately, as the setter doesn't return a promise, which breaks
								// the field_group calling this setter (indirectly).
								d.fields_dict.prepared_email_body?.set_value(responseValues.email_body);
							}
					},
					{
							fieldname: 'section_break_1',
							fieldtype: 'Section Break'
					},
					{
							label: __('Body'),
							fieldname: 'prepared_email_body',
							fieldtype: 'HTML',
							read_only: 1
					}
			],
			primary_action_label: __('Send Test E-Mail'),
			async primary_action(_values) {
				const res = await frm.call('prepare_and_send_email', {
					node_name_or_doc: cdn,
					receiver_doctype: d.get_value('receipient_doctype'),
					receiver_id: d.get_value('receipient_id'),
					recipient_email_address: d.get_value('test_email_receipient'),
					test_mail: true
				});

				if (res?.message !== true) {
					frappe.show_alert({
						message: __('Sending of Test E-Mail failed.'),
						indicator: 'red'
					});

					return;
				}

				frappe.show_alert({
					message: __('A Test E-Mail was sent'),
					indicator: 'green'
				});

				d.hide();
			}
		});

		d.show();

		// load a few demo receivers if present
		const receipientsResponse = await frm.call('generate_audiences', { count_only: false, only_first_package: true, limit: 10 })
		d.demo_receipients = receipientsResponse?.message

		if (!d.demo_receipients?.length) {
			frappe.show_alert({
				message: __('No possible receipients can be collected by the defined audiences. Please define an audience with results first'),
				indicator: 'red'
			});

			d.hide();
			return
		}


		await d.set_values({
			receipient_doctype: d.demo_receipients[0].reference_doctype,
			receipient_id: d.demo_receipients[0].reference_name
		});

		d.fields.find(e => e.fieldname === 'receipient_id')?.change();

		// d.fields_dict.receipient_id.$input.trigger('change')

		// await d.fields_dict.receipient_doctype.set_value(d.demo_receipients[0].reference_doctype)
		// d.fields_dict.receipient_id.set_value(d.demo_receipients[0].reference_name)

		// d.fields_dict.receipient_id.$input.trigger('change')
	}
});
