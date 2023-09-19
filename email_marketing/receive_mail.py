import json
import boto3
import requests
import re
import email
import html

import frappe
from frappe.utils.password import get_decrypted_password

from email_marketing.email_marketing.amazon_sns_validation import validate as valid_sns_message

# Receive email from Amazon SNS (simple notification service), download it from s3 bucket
# and perform the inbound processing.
@frappe.whitelist(allow_guest=True, methods=['POST'])
def receive_mail_via_sns():
	# Get the message from the SNS.
	message = json.loads(frappe.request.data) # message_id = event['Records'][0]['ses']['mail']['messageId']

	# verify that message really came from amazon
	if not valid_sns_message(message):
		frappe.throw('Invalid SNS message received {}'.format(message))

	# detect matching EmailMktEmailReceiver profile for this message
	email_receiver = detect_email_receiver_settings(message)

	if not email_receiver:
		frappe.throw('No EmailMktEmailReceiver found for SNS Arc {}'.format(message['TopicArn']))

	handle_s3_sns_message(message, email_receiver)

def handle_s3_sns_message(message, email_receiver):
	if message['Type'] == 'SubscriptionConfirmation':
		# The subscriptions needs to be confirmed by a separate GET call back to amazon.
		res = requests.get(message['SubscribeURL'])

		if res.status_code == 200:
			# read SubscriptionArn from response
			subscription_arn = re.search(r'<SubscriptionArn>([^<]+)', res.text)[1]

			email_receiver.sns_subscription_active = subscription_arn
			email_receiver.flags.ignore_permissions = True
			email_receiver.save()

	elif message['Type'] == 'UnsubscribeConfirmation':
		email_receiver.sns_subscription_active = None
		email_receiver.flags.ignore_permissions = True
		email_receiver.save()

	elif message['Type'] == 'Notification':
		if not message['Message']:
			return

		message_message = json.loads(message['Message'])

		# make sure the message is structured as expected
		if not message_message['receipt'] or not message_message['receipt']['action'] or not message_message['mail']:
			frappe.throw('Unexpected SNS message structure received')

		receipt = message_message['receipt']

		if receipt['action']['type'] != 'S3':
			frappe.throw('Unexpected SNS action received: {}'.format(receipt['action']['type']))

		# ignore mails which were detected to be a virus (if set up in EmailMktEmailReceiver)
		if not email_receiver.ignore_virus_mails and 'virusVerdict' in receipt and receipt['virusVerdict']['status'] != 'PASS':
			return

		# ignore mails which were considered to be spam (if set up in EmailMktEmailReceiver)
		if not email_receiver.ignore_spam_mails and 'spamVerdict' in receipt and receipt['spamVerdict']['status'] != 'PASS':
			return

		# find corresponding email_account
		email_account = email_receiver.target_email_account_for_receiver_email(receipt['recipients'])

		if not email_account:
			return # ignore mail, if no email_account could be found for the email receiver

		# Establish the S3 client session.
		message_id = message_message['mail']['messageId']
		topic_arn_parts = re.search(r':([^:]+):([^:]+):([^:]+)$', receipt['action']['topicArn'])
		s3_region = topic_arn_parts[1]
		s3_bucket_name = receipt['action']['bucketName']

		s3_session = boto3.Session(	aws_access_key_id=email_receiver.aws_sns_api_key,
																aws_secret_access_key=get_decrypted_password(email_receiver.doctype, email_receiver.name, 'aws_sns_api_secret'),
																region_name=s3_region)

		# Get the message from S3.
		email_mime = get_message_from_s3(s3_session, s3_bucket_name, message_message['mail']['messageId'])

		# simulate inbound processing
		orig_user = frappe.session.user

		try:
			mailobject = email.message_from_string(email_mime.decode('utf-8'))
			receivers = [r.strip() for r in (','.join(filter(None, [mailobject['To'], mailobject['Cc']]))).split(',')]

			# forward email (if any forwarding rules active)
			forwarding_rules = email_receiver.matching_email_forwarding_rules(receivers)
			if forwarding_rules:
				forward_email_via_ses(forwarding_rules, email_account, mailobject, s3_session)

			# if all of the matched forwarding rules are set to "skip_original_delivery", do not insert the communication
			if not forwarding_rules or next((True for rule in forwarding_rules if not rule.skip_original_delivery), False):
				# attachment creation is not authorized with common users - prefer a super user or checkout correct permission
				# fails in frappe.email.receive.py #save_attachments_in_doc() #587 (on _file.save())
				frappe.set_user(email_receiver.receiving_user or 'Administrator')

				email_account.insert_communication(email_mime)

			# delete from s3
			s3_session.client('s3').delete_object(Bucket=s3_bucket_name, Key=message_id)

		finally:
			frappe.set_user(orig_user)

def detect_email_receiver_settings(message):
	message_parts = re.search(r'^arn:aws:sns:([^:]+):([^:]+):([^:]+)', message['TopicArn'])

	sns_region, sns_topic = message_parts[1], message_parts[3]
	email_receiver_name = frappe.db.get_value('EmailMktEmailReceiver', {
		'inbound_transmitter': 'Amazon SES with S3 and SNS',
		'ses_receiving_region': sns_region,
		'sns_subscribed_topic': sns_topic,
		}, 'name')

	if email_receiver_name:
		email_receiver = frappe.get_cached_doc('EmailMktEmailReceiver', email_receiver_name)

	return email_receiver

def get_message_from_s3(session, bucket_name, message_id, bucket_prefix = None):
	if bucket_prefix:
		object_path = bucket_prefix + '/' + message_id
	else:
		object_path = message_id

	# Create a new S3 client.
	client_s3 = session.client('s3')

	# Get the email object from the S3 bucket.
	object_s3 = client_s3.get_object(Bucket=bucket_name, Key=object_path)

	# Read the content of the message.
	return object_s3['Body'].read()


# https://github.com/awsdocs/aws-doc-sdk-examples/blob/main/python/example_code/sns/sns_basics.py
# https://aws.amazon.com/de/blogs/messaging-and-targeting/forward-incoming-email-to-an-external-destination/

# # https://github.com/awsdocs/aws-doc-sdk-examples/blob/main/python/example_code/sns/sns_basics.py
# import logging
# logger = logging.getLogger(__name__)
#
# ultrahook rspgr http://erpnext.local:8001

def forward_email_via_ses(forwarding_rules, email_account, mailobject, s3_session):
	forward_recipients = list(set([fr.forward_to for fr in forwarding_rules if fr.forward_as == 'Recipient']))
	forward_cc = list(set([fr.forward_to for fr in forwarding_rules if fr.forward_as == 'Cc']))
	forward_bcc = list(set([fr.forward_to for fr in forwarding_rules if fr.forward_as == 'Bcc']))

	# Usually there should be a categorized recipient. But if not, grab the first available other one.
	if not forward_recipients:
		if forward_cc:
			forward_recipients = [forward_cc[0]]
		elif forward_bcc:
			forward_recipients = [forward_bcc[0]]

	# inject sender name into message
	froms_src = mailobject['From'] if isinstance(mailobject['From'], list) else [mailobject['From']]
	froms = []
	for name_addr in (email.header.decode_header(from_) for from_ in froms_src):
		name = name_addr[0][0].decode(name_addr[0][1] or 'utf-8') if isinstance(name_addr[0][0], bytes) else name_addr[0][0]

		if len(name_addr) > 1:
			addr = name_addr[1][0].decode(name_addr[1][1] or 'utf-8') if isinstance(name_addr[1][0], bytes) else name_addr[1][0]
		else:
			# in this case the mail address was not extracted from the header
			name, addr = email.utils.parseaddr(name)

		froms.append([(name or '').strip(), addr.strip()])

	injection = 'From: {}\n'.format('; '.join([' '.join(f) for f in froms]) or '')
	injection = '{}To: {}\n'.format(injection, '; '.join(mailobject['To']) if isinstance(mailobject['To'], list) else mailobject['To'] or '')

	if mailobject.get('Cc'):
		injection =  '{}Cc: {}\n'.format(injection, mailobject['Cc'])

	if mailobject.get('Bcc'):
		injection =  '{}Bcc: {}\n'.format(injection, mailobject['Bcc'])

	injection = injection + '\n--\n\n'

	if mailobject.is_multipart():
		html_part = next((p for p in mailobject.get_payload() if p.get_content_type() == 'text/html'), mailobject.get_payload(0))

		html_markup = re.sub(r'(<body[^>]*>)', '\\1' + html.escape(injection).replace('\n', '<br>'), html_part.get_payload(), flags=re.IGNORECASE)

		html_part.set_payload(html_markup)
	else:
		text_part = mailobject.get_payload()
		mailobject.set_payload(injection + text_part)

	mailobject['Reply-To'] = froms[0][1] # ', '.join(froms)
	mailobject.replace_header('Return-Path', email_account.email_id)
	mailobject.replace_header('From', email_account.email_id)
	mailobject.replace_header('To', ', '.join(forward_recipients))

	if mailobject.get('Cc'):
		mailobject.replace_header('Cc', ', '.join(forward_cc) or None)
	else:
		mailobject['Cc'] = ', '.join(forward_cc) or None

	# amz ses does not allow empty cc, so remove it if it was there from inbound mail or if it was initialized with empty value
	if not mailobject['Cc']:
		del mailobject['Cc']

	if forward_bcc:
		mailobject['Bcc'] = ', '.join(forward_bcc)

	if not mailobject['Bcc']:
		del mailobject['Bcc']

	#
	# Send the email:
	client_ses = s3_session.client('ses')

	client_ses.send_raw_email(
			Source=email_account.email_id,
			Destinations=list(set(forward_recipients + forward_cc + forward_bcc)),
			RawMessage={ 'Data': mailobject.as_string() }
		)
