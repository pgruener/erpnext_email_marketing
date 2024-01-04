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

#### Added an optional Signature Reference from each Email Template to another one.

So an Email Template may now also be a Signature.
The Signatures at the Email Account or the User are too inflexible (also jinja isn't rendered on construction),
and the Signature should be maintainable "centrally". Not each user on its own.

And for several use-cases other Signatures are needed. E.g. in service mails, a hotline Number should be
added, but on Lead Mails the signature should promote some interessting features etc. And if writing Lead Mails
for different product categories, they should be adjusted as well.

So to get this flexibility done "easy" we added an optional reference of a "Signature Email Template" for each
Email Template which should be used.
On selection, the signature will be processed with jinja in the same context, as the whole template is processed.

Those to html results are concatenated with a separating <br>.

#### Added an additional email recipient determination for several doctypes

As the basic "simple" determination of recipients works easy with Leads, it doesn't for Purchase Orders or Quotations,
when the contact or address is just maintained in the customer master data.

Now there is a priorization available, to detect the "best" destination email address for the DocTypes "Purchase Order",
"Quotation" and "Sales Order".
But this determination is only called as fallback, if no recipient email address could be found with previously called
simple (standard) determination.

# Automatic choice of Email Template for standard text.

On initiative E-Mail creation it's tried to detect a recipient and a sender e-mail address. If both can be detected,
chances are good, to generate a good pre-defined E-Mail, if an Email Template is available for the current doctype.

If all those conditions are fitting, the Email text is generated by the discovered Email Template.

# E-Mail Template jinja helpers

We added some jinja methods, which we need in frequently used templates:

## rs_salutation(contact, doc=None)

Generates a salutation by custom rules defined in DocType `EmailMktSalutation`.

A Contact name or User Name can be given.
For several DocTypes different rules can apply.
E.g.

- For a invoice to a billing center, we're not using the first name, as we don't know the person itself.
- But for a Timesheet approval, which is sent to the known Project Leader, we could want to use a more "kindly" salutation.



## rs_salutation_for_doc(doc_or_doctype, docname=None)

The same as `rs_salutation` but it receives a document, for which it detects the
best corresponding Contact itself.

## rs_target_contact_for_doc(doc)

Calls the determination routine for a Contact of a given document.
This has still a very MVP state and needs improvement for sure.

## rs_year_from_date

We oftenly need the year of a document in several emails, but only the year.
And we don't want to populate the same formatter many times. So we created
this simple helper to extract the 4 digit year from a date and return None
if nothing was applied (as is might not be always set in the corresponding
doctype).

# Receiving Inbound E-Mails

In some of our scenarios, it's not useful (or necessary) to persist emails in some
mailboxes, which are regularly observed from ERPNext, to receive new emails.

The source of truth can be the ERPNext itself for some domains.

So we've created the doctype **EmailMktEmailReceiver** to declare email services, which
are getting enabled to transfer emails directly into our ERPNext.

## EmailMktEmailReceiver

This E-Mail Receiver doctype defines transmitters, which are allowed
to POST emails into ERPNext. The posting message structures are will be separated by the **inbound_transmitter**

When this endpoint is defined, this endpoint might send all kind of emails, into the system. Independent of the used "To:" in the E-Mail Address.

At this point we map the inbound messages back to the ERPNext standard
**Email Account** doctype.

But the mapping can be done a bit more flexible, as the **email_id** doesn't have to match exactly; we're providing a fbmatch matching to
detect the correct target **Email Account** with the Child Table **EmailMktEmailReceiverAccounts**.

### EmailMktEmailReceiverAccounts

| Pattern                   | Email Account |
| ------------------------- | ------------- |
| service@royal-software.de | Service Mails |
| sales@royal-software.de   | Sales Mails   |
| privacy@royal-software.de | Privacy Mails |
| *@royal-software.de       | Catch all     |

With that you get the flexibility to map common typos or special departments, to specific *Email Accounts*, but don't need to adjust
the whole AWS stack for each email.

If you don't like a Catch All rule, this is not required to be setup.

If no *Email Account* can be detected for the incoming E-Mail, it's just ignored and not created in ERPNext.

If the sender of the E-Mail should get a response, that he sent an E-Mail to an unknown address, this should be configurred correctly in the **inbound_transmitter**.

E.g. in AWS's SES the **Email receiving -> Rule set** provides conditions, where the definition is possible, if it should accept emails for a whole domain, for all of its subdomains, or for a single e-mail address.

If a mail is sent to a E-Mail Address, which is not passing one of those conditions, the email is directly rejected with a *Mail Delivery Notice*.

The [Patterns](https://docs.python.org/3/library/fnmatch.html) may use * for any amount of wildcard characters, or ? for single wildcard characters to match the receiving email addresses.

### inbound_transmitter

We started with the **inbound_transmitter** for Amazon S3/SES, but this will extend in
the future.
So the "inbound_transmitter" categorizes the transferring servies.

Currently supported transmitters:
* [Receiving from Amazon SES / SNS with S3](#receiving-inbound-mails-from-amazon-ses)

Each inbound receiver is completely under the responsibility of a single Company and furthermore
allows a precise assignment to it, which is necessary for applying further rules, like responsibility
detection, etc.

After the desired "inbound_transmitter" is chosen, the corresponding configuration requirements will appear.

## Receiving Inbound Mails from Amazon SES

Amazon SES allows several options of how to handle inbound mails.
We don't want to setup a lambda or some other decentralized processing, so the only two
options, which are feasable are:

1. Publish to Amazon SNS topic
2. Deliver to S3 bucket (and Publish that to an SNS topic)

The first option seems slick, but only allows 150KB for each email as maximum load. So that's not viable for rich email applications.

The best match for our cases is the S3 bucket with the combined SNS topic.

So the email comes in, Amazon uploads the raw message to S3 and sends a message to the SNS topic.
The SNS Topic will have a subscription from our ERPNext system, which is immediately informed, when
an email arrives.
This Inbound Module then downloads the email from S3, generates the E-Mail in ERPNext and destroys
the S3 entity afterwards.

The matching **EmailMktEmailReceiver** profile is detected by the **SNS Topic**,
which needs to be unique.

In AWS the following configurations needs to be done:

- In the chosen inbound region a [Domain Identity](https://eu-west-1.console.aws.amazon.com/ses/home?region=eu-west-1#/verified-identities/create) needs to be created, which needs to get verified as instructed there.
   Access the [list of verified identities](https://eu-west-1.console.aws.amazon.com/ses/home?region=eu-west-1#/verified-identities)

   To configure the verified Domain that emails are passed to Amazon, a DNS MX record needs to be setup in the [pattern](https://docs.aws.amazon.com/ses/latest/dg/regions.html#region-endpoints): inbound-smtp.**region**.amazonaws.com

- In the section [Email receiving](https://eu-west-1.console.aws.amazon.com/ses/home?region=eu-west-1#/email-receiving) a **Rule Set** needs to be created (or extended) with the action **Deliver to Amazon S3 bucket**

   ProTip: *The bucket and the corresponding SNS topic can be created directly in this wizard.*

   Within the new SNS Topic, the Policy needs to defined, that your SES service is permitted to post
   messages to this topic.

   You can use this Policy JSON for the SNS topic if you replace the following variables:

   * AWS_ACCOUNT_ID: [Get it in the Support Center (in the top of the left navbar)](https://us-east-1.console.aws.amazon.com/support/home?region=eu-west-1#/)
   * REGION_ID: The region you have chosen for S3 and Inbound emails. If you use different ones, be sure to maintain it correctly in the JSON
   * BUCKET_NAME: The bucket name you created
   * SNS_TOPIC_NAME: The name of the created SNS Topic, which receives the notifications about new emails.

      ```
      {
         "Version": "2008-10-17",
         "Statement": [
            {
               "Sid": "AllowSNSPublish",
               "Effect": "Allow",
               "Principal": {
               "Service": "ses.amazonaws.com"
               },
               "Action": "SNS:Publish",
               "Resource": "arn:aws:sns:*REGION_ID*:*AWS_ACCOUNT_ID*:*SNS_TOPIC_NAME*",
               "Condition": {
                  "StringEquals": {
                     "AWS:SourceAccount": "*AWS_ACCOUNT_ID*"
                  },
                  "StringLike": {
                     "AWS:SourceArn": "arn:aws:ses:*"
                  }
               }
            }
         ]
      }
      ```

      You can use this Policy JSON for the newly created S3 bucket (and replace the corresponding variables):

      ```
      {
         "Version": "2012-10-17",
         "Statement": [
            {
               "Sid": "AllowSESPuts",
               "Effect": "Allow",
               "Principal": {
                  "Service": "ses.amazonaws.com"
               },
               "Action": "s3:PutObject",
               "Resource": "arn:aws:s3:::*BUCKET_NAME*/*",
               "Condition": {
                  "StringEquals": {
                     "aws:Referer": "*AWS_ACCOUNT_ID*"
                  }
               }
            }
         ]
      }
      ```

      Within the newly created SNS Topic a Subscription needs to be created, which will point to
      our ERPNext instance.
      The protocol of the subscription should be **HTTPS**. This enables the property field, which
      will be the target for the ERPNext API URL, which will be called for each inbound e-mail.

      You'll find your correct ERPNext endpoint URL in [The Email Receiver configuration DocType](#EmailMktEmailReceiver).

- [Create a Policy](https://us-east-1.console.aws.amazon.com/iamv2/home#/policies) with permission to
   * subscribe to the inbound_email SNS topic
   * read objects of the S3 Bucket
   * delete objects of the S3 Bucket

   You can also use this Policy JSON if you replace the variables with your matching values:

   * AWS_ACCOUNT_ID: [Get it in the Support Center (in the top of the left navbar)](https://us-east-1.console.aws.amazon.com/support/home?region=eu-west-1#/)
   * REGION_ID: The region you have chosen for S3 and Inbound emails. If you use different ones, be sure to maintain it correctly in the JSON
   * BUCKET_NAME: The bucket name you created
   * SNS_TOPIC_NAME: The name of the created SNS Topic, which receives the notifications about new emails.

      ```
      {
         "Version": "2012-10-17",
         "Statement": [
            {
                  "Sid": "VisualEditor1",
                  "Effect": "Allow",
                  "Action": [
                     "s3:GetObject",
                     "ses:SendRawEmail",
                     "s3:DeleteObject"
                  ],
                  "Resource": [
                     "arn:aws:s3:::*BUCKET_NAME*/*",
                     "arn:aws:ses:*REGION_ID*:*AWS_ACCOUNT_ID*:identity/*"
                  ]
            }
         ]
      }
      ```

   If you want to enable also the list of the bucket, to reprocess mails, which couldnt be processed (due to system shutdown or other problems) on demand, you'll need to add the "s3:ListBucket" permission for the resource "arn:aws:s3:::*BUCKET_NAME*" (without "/*") as well.


      ```
      {
         "Version": "2012-10-17",
         "Statement": [
            {
                  "Sid": "VisualEditor2",
                  "Effect": "Allow",
                  "Action": [
                     "s3:ListBucket",
                  ],
                  "Resource": [
                     "arn:aws:s3:::*BUCKET_NAME*",
                     "arn:aws:ses:*REGION_ID*:*AWS_ACCOUNT_ID*:identity/*"
                  ]
            }
         ]
      }
      ```


- [Create a User](https://us-east-1.console.aws.amazon.com/iam/home#/users$new?step=details) (IAM), which is assigned to the policy
- Generate API Key and Secret for the new User

#### License

MIT