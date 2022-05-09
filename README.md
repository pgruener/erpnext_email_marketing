## Email Marketing

Several adjustments for the E-Mail capabilities, to get them better fit for our needs.

### Manual sending capabilities

#### Different Sender name

We frequently have to send emails in the name of another colleague.
We enabled this feature to optionally change the
- Sender Name
- Sender E-Mail Address

Those parameters are now available in any E-Mail Template (for jinja), to access the changed user.
different_sender (email)
different_sender_name (full name)

The alternative name is also applied on the SMTP Envelope, as this is grabbed from the frappe.session.user by default.

#### Additional (filtered) property for E-Mail Templates

We created another Template property (additionally to the existing one), which is not hidden by default in the collapsed menu, as this is the most frequent
thing for us.

There are 3 primary things about the original one, which didn't fit to our scenario:
1. It is hidden
2. The value help is returning all of the available Templates. That's not very efficient for the coworkers, as they have to know exactly what they're looking for.
   We added a property to the Template, to assign a Template to specific DocTypes. And only those are returned in this property.
3. Replacing the whole E-Mail: We're not using this functionality to find text partials for the email, but for the whole E-Mail.
   So our new Template selection replaces the whole content of the existing E-Mail.

#### Disabled auto PDF generation (and attaching of it)

There was a hardly coded "true", which enabled "Attach Document Print" by default to each E-Mail.
So as it is the default, internal data was sent out (created in the pdf) accidentally.
In the most situations we won't attach the generation. And if we want to, then this manual step
is good in this inverted state.

We're thinking about making this dependent on the DocType, as for Invoices and Purchase Orders it
makes sense.. but for now we're fine with the disabled property.

#### License

MIT