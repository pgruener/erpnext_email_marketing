import frappe
from frappe import _
from frappe.utils.data import now_datetime
from datetime import datetime, timedelta

def process_active_campaigns():
  reschedule_at = None

  for scheduled_campaign_name in frappe.get_all('EmailMktScheduledProcessings', fields=['name', 'scheduled_at']):
    if scheduled_campaign_name.scheduled_at and scheduled_campaign_name.scheduled_at > now_datetime():
      # make sure this is rescheduled again later
      if reschedule_at:
        if scheduled_campaign_name.scheduled_at < reschedule_at:
          reschedule_at = scheduled_campaign_name.scheduled_at # get the earliest time
      else:
        reschedule_at = scheduled_campaign_name.scheduled_at

      # but dont process now
      continue

    campaign_schedule = frappe.get_doc('EmailMktScheduledProcessings', scheduled_campaign_name)

    if campaign_schedule.reference_doctype == 'EmailMktCampaign':
      try:
        # for now be specific about the scheduled campaigns
        scheduled_campaign = frappe.get_cached_doc(campaign_schedule.reference_doctype, campaign_schedule.reference_name)

        scheduled_campaign.evaluate_campaign_nodes()

        campaign_schedule.delete()
      except Exception:
        scheduled_campaign.update({'failed_at': now_datetime()})
        scheduled_campaign.save()

        frappe.log_error(
            title=_("Error occured during campaign processing of: {}").format(campaign_schedule.name),
            message=frappe.get_traceback()
          )

#
# copied from standard "Email Account", with the exception, that inbound mails can be
# retrieved from doctype "EmailMktEmailReceiver" as well, and therefore "enable_incoming"
# wont be set necessarily.
# Furthermore the "append_to" is not relevant for our notifications
def notify_unreplied():
	"""Sends email notifications if there are unreplied Communications
	and `notify_if_unreplied` is set as true."""

	inbound_receipients = frappe.get_all('EmailMktEmailReceiverAccounts', fields=['email_account'], as_list=True)

	for email_account in frappe.get_all(
		# "Email Account", "name", filters={"enable_incoming": 1, "notify_if_unreplied": 1}
		'Email Account', 'name', filters={'enable_incoming': 0, 'name': ['in', [s[0] for s in inbound_receipients]], 'notify_if_unreplied': 1}
	):
		email_account = frappe.get_doc("Email Account", email_account.name)
		# if email_account.append_to:

		# get open communications younger than x mins, for given doctype
		for comm in frappe.get_all(
			"Communication",
			"name",
			filters=[
				{"sent_or_received": "Received"},
				# {"reference_doctype": email_account.append_to},
				{"unread_notification_sent": 0},
				{"email_account": email_account.name},
				{
					"creation": (
						"<",
						datetime.now() - timedelta(seconds=(email_account.unreplied_for_mins or 30) * 60),
					)
				},
				{
					"creation": (
						">",
						datetime.now() - timedelta(seconds=(email_account.unreplied_for_mins or 30) * 60 * 3),
					)
				},
			],
		):
			comm = frappe.get_doc("Communication", comm.name)

			if frappe.db.get_value(comm.reference_doctype, comm.reference_name, "status") == "Open":
				# if status is still open
				frappe.sendmail(
					sender=email_account.email_id if email_account.enable_outgoing else '', # PGR: use email account for sending, if possible
					recipients=email_account.get_unreplied_notification_emails(),
					content=comm.content,
					subject=comm.subject,
					doctype=comm.reference_doctype,
					name=comm.reference_name,
				)

			# update flag
			comm.db_set("unread_notification_sent", 1)
