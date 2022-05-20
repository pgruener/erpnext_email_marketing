if (frappe.views?.CommunicationComposer && !frappe.views.CommunicationComposer.email_enhanced_ext_rs) {
  // mark if enhancement is already applied
  frappe.views.CommunicationComposer.email_enhanced_ext_rs = true;

  /**
   * Enhance *get_fields* to propagate own fields to the dialog.
   */
  frappe.views.CommunicationComposer.email_enhanced_ext_rs__get_fields = frappe.views.CommunicationComposer.prototype.get_fields;
  frappe.views.CommunicationComposer.prototype.get_fields = function () {
    // call original "get_fields" function to display the email dialog
    let fields = frappe.views.CommunicationComposer.email_enhanced_ext_rs__get_fields.apply(this, arguments);

    // inject "different sender user" in hidden objects
    const idxTemplate = fields.findIndex(field => field.fieldname === 'email_template');
    fields.splice(idxTemplate + 1, 0,
      {
        fieldtype: 'Column Break'
      },
      {
      fieldtype: 'Link',
      options: 'User',
      label: __('Different Sender'),
      fieldname: 'different_sender',
      onchange: () => {
        const different_sender = this.dialog.fields_dict.different_sender.get_value();
        if (different_sender) {
          this.dialog.set_df_property('different_sender_name', 'hidden', false);

          const selectedSenderName = document.evaluate(`//li[contains(., "${different_sender}")]`, this.dialog.fields_dict.different_sender.input_area, null, XPathResult.ANY_TYPE, null)?.iterateNext()?.querySelector('span.small')?.innerText;
          if (selectedSenderName) {
            this.dialog.fields_dict.different_sender_name.set_value(selectedSenderName);
          }

          frappe.db.get_value('Email Account', different_sender, 'email_id').
            then((res) => {
              if (res.message.email_id) {
                // use as sender
                this.dialog.fields_dict.different_sender_name_as_outbound.set_value(1);
              } else {
                // cannot use this email as different sender, so just use the corresponding user data
                this.dialog.fields_dict.different_sender_name_as_outbound.set_value(0);
              }
            });
        } else {
          this.dialog.set_df_property('different_sender_name', 'hidden', true);
          this.dialog.fields_dict.different_sender_name.set_value('');
        }
      }
    },
    {
      fieldtype: 'Check',
      read_only: 1,
      label: __('Different Sender E-Mail is valid outbound mail'),
      fieldname: 'different_sender_name_as_outbound'
    },
    {
      fieldtype: 'Data',
      hidden: 1,
      label: __('Different Sender Name'),
      fieldname: 'different_sender_name'
    });

    const me = this;

    // inject filtered E-Mail Template before subject
    const idxSubject = fields.findIndex(field => field.fieldname === 'subject');
    fields.splice(idxSubject, 0, {
      fieldtype: 'Link',
      options: 'Email Template',
      label: __('Filtered Email Template'),
      fieldname: 'email_template_by_doctype',
      get_query: () => {
        return {
          filters: {
            linked_doctype: this.frm.doc.doctype
          }
        };
      },
      onchange: () => {
        const email_template_by_doctype = this.dialog.fields_dict.email_template_by_doctype.get_value();
        if (email_template_by_doctype) {
          frappe.call({
            method: 'frappe.email.doctype.email_template.email_template.get_email_template',
            args: {
              template_name: email_template_by_doctype,
              doc: this.doc,
              different_sender: this.dialog.fields_dict.different_sender.get_value(),
              different_sender_name: this.dialog.fields_dict.different_sender_name.get_value(),
              _lang: this.dialog.get_value('language_sel')
            },
            callback(reply) {
              me.dialog.fields_dict.content.set_value(reply.message.message);
				      me.dialog.fields_dict.subject.set_value(reply.message.subject);
            },
          });
        }
      }
    });

    return fields;
  }

  /**
   * Enhance *send_email* to inject parameters where possible.
   */
  frappe.views.CommunicationComposer.email_enhanced_ext_rs__send_email = frappe.views.CommunicationComposer.prototype.send_email;
  frappe.views.CommunicationComposer.prototype.send_email = function (_btn, form_values /*, selected_attachments, print_html, print_format */) {
    // adjust form_values for (alternative) sender name (if set)
    const different_sender = this.dialog.fields_dict.different_sender?.get_value();
    let orig_full_name = frappe.user.full_name;

    if (different_sender) {
      if (this.dialog.fields_dict.different_sender_name_as_outbound.get_value() === 1) {
        // adjust sender if this is really possible
        form_values.sender = different_sender;
      } else {
        form_values.sender = form_values.sender || (this.user_email_accounts || [])[0];
      }

      orig_full_name = frappe.user.full_name;
      frappe.user.full_name = () => {
        // inject alternative sender name
        return this.dialog.fields_dict.different_sender_name.get_value();
      };
    }

    // call original "send_email" function to display the email dialog
    let res, err;
    try {
      res = frappe.views.CommunicationComposer.email_enhanced_ext_rs__send_email.apply(this, arguments);
    } catch (e) {
      err = e;
    }

    // restore original full name method, no matter if there was an error or not
    if (orig_full_name) {
      // recover original full_name method
      frappe.user.full_name = orig_full_name;
    }

    // populate exception, if any
    if (err) {
      throw err;
    }

    return res;
  }

  /**
   * Inject into make() (called in constructor when creating new email),
   * for setup control.
   */
  frappe.views.CommunicationComposer.email_enhanced_ext_rs__make = frappe.views.CommunicationComposer.prototype.make;
  frappe.views.CommunicationComposer.prototype.make = function () {
    // In most of our cases the generation of the print format is not wanted, so disable it
    // TODO: Read custom doctype with checkable doctypes for that
    this.attach_document_print = false;

    // call original "make" function to display the email dialog
    frappe.views.CommunicationComposer.email_enhanced_ext_rs__make.apply(this, arguments);

    // further email initialization
    frappe.views.CommunicationComposer.prototype.setup_email_enhanced.call(this)
  }

  frappe.views.CommunicationComposer.prototype.setup_email_enhanced = async function() {
    this.determine_sender();
    await this.determine_recipients();
    this.determine_default_response();
  }

  frappe.views.CommunicationComposer.prototype.determine_sender = function() {
  }

  frappe.views.CommunicationComposer.prototype.determine_recipients = async function() {
    const recipients = this.dialog.fields_dict.recipients.get_value();
    if (!this.recipients && !recipients) {
      // no recipients were discovered, call more advanced determination api
      await frappe.call('email_marketing.api.detect_email_recipient_for_doc', {
        doc: this.doc
      }).then(r => {
        if (!r?.data) {
          return;
        }

        this.recipients = r.data;
        this.dialog.fields_dict.recipients.set_value(r.data);
      })
    }
  }

  frappe.views.CommunicationComposer.prototype.determine_default_response = function() {
    // TODO also get dependent from the presence of sender
    if (!this.recipients) {
      return;
    }

    // debugger
    // const template = frappe.db.get_value('EmailMktTemplateDocTypes', { linked_doctype: this.doc.doctype }, 'parent')

    frappe.call('email_marketing.api.default_email_template_for_doctype', {
        doctype: this.doc.doctype
      }).then(r => {
        if (!r?.email_template) {
          return;
        }

        this.dialog.fields_dict.email_template_by_doctype.set_value(r.email_template);
      })
  }
}
