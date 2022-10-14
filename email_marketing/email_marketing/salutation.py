import frappe
import email_marketing.email_marketing.sequenced_address_determination as sequenced_address_determination

# @frappe.whitelist()
def rs_salutation(contact=None, doc=None):
  doctype = doc

  if doc and isinstance(doc, dict):
    doctype = doc.doctype

  return salutation_for_contact(contact, doctype, frappe.session.user)


def rs_salutation_for_doc(doc_or_doctype, docname = None):
  doc = doc_or_doctype
  if isinstance(doc_or_doctype, str):
    doc = frappe.get_cached_doc(doc_or_doctype, docname)

  return salutation_for_contact(sequenced_address_determination.target_contact_for_doc(doc), doc.doctype, frappe.session.user)


def salutation_for_contact(contact=None, doctype=None, user=None):
  # load contact if given contact is string
  if isinstance(contact, str):
    if contact:
      try:
        contact = frappe.get_doc('Contact', contact).as_dict()
      except frappe.DoesNotExistError:
        frappe.message_log.pop()

        try:
          contact = frappe.get_doc('User', contact).as_dict()
        except frappe.DoesNotExistError:
          frappe.message_log.pop()

        del frappe.response['exc_type']

  if not contact or not isinstance(contact, dict):
    contact = dict(first_name='', last_name='')


  matching_dict = dict(
    target_doctype=doctype,
    language=frappe.get_cached_doc('User', user or frappe.session.user).language,
    gender=contact.gender if 'gender' in contact else None,
    salutation=contact.salutation if 'salutation' in contact else None
  )
  # frappe.throw('{}'.format(contact))
  # frappe.throw('{}'.format(matching_dict))

  salutation = detect_salutation(matching_dict)
  if not salutation:
    return None

  # first character of first_name and last_name
  contact['first_name_1c'] = contact['first_name'][0] if contact['first_name'] else None
  contact['last_name_1c'] = contact['last_name'][0] if contact['last_name'] else None
  contact['full_name'] = ' '.join(filter(None, [contact['first_name'], contact['last_name']])) if contact else None

  return frappe.render_template(salutation.salutation_pattern, contact)

# priorized access sequence for determination of the "best fitting" salutation configuration
def detect_salutation(matching_dict, salutations = None, skip_permutations=False):
  # EmailMktSalutation
  if not salutations:
    salutations = frappe.cache().hget('email_marketing_cache', 'salutations')
    if not salutations:
      salutations = frappe.get_all('EmailMktSalutation', fields=['target_doctype', 'language', 'gender', 'salutation', 'salutation_pattern'])
      frappe.cache().hset('email_marketing_cache', 'salutations', salutations)

  # get salutation by matching the most of concrete details in a row
  for salutation_dict in salutations:
    exact_match = True
    for matching_key in matching_dict:
      # print("\nmatching_key: {}     -      {}".format(matching_key, matching_dict[matching_key]))

      if matching_dict[matching_key] != salutation_dict.get(matching_key) and not ( not matching_dict[matching_key] and not salutation_dict.get(matching_key)):
        exact_match = False
        # print("not matched ({})".format(salutation_dict.get(matching_key)))
        break

    if exact_match:
      return salutation_dict

  # if this method was called recursively stop, as those mutations lead to unexpected results
  if skip_permutations:
    return

  orig_matching_dict = matching_dict.copy()

  # if no salutation was found reduce concrete details in matcher and retry
  if matching_dict['salutation']:
    matching_dict['salutation'] = None
    salutation_dict = detect_salutation(matching_dict, salutations, True)
    if salutation_dict:
      return salutation_dict

  matching_dict = orig_matching_dict.copy()

  if matching_dict['gender']:
    matching_dict['gender'] = None
    salutation_dict = detect_salutation(matching_dict, salutations, True)
    if salutation_dict:
      return salutation_dict


  matching_dict = orig_matching_dict.copy()

  if matching_dict['target_doctype']:
    matching_dict['target_doctype'] = None
    salutation_dict = detect_salutation(matching_dict, salutations, True)
    if salutation_dict:
      return salutation_dict

  matching_dict = orig_matching_dict.copy()

  if matching_dict['language']:
    matching_dict['language'] = None
    salutation_dict = detect_salutation(matching_dict, salutations, False)
    if salutation_dict:
      return salutation_dict

    if orig_matching_dict['language'] != 'en':
      matching_dict['language'] = 'en'
      salutation_dict = detect_salutation(matching_dict, salutations, False)
      if salutation_dict:
        return salutation_dict
