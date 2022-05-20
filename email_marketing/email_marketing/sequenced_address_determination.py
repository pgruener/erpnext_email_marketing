import frappe
import json

def read_preferred_email_for_supplier(supplier):
	email = None
	possible_references = frappe.db.get_value('Supplier', supplier,
																						['supplier_primary_contact',
																						'supplier_primary_address',
																						'primary_address'], as_dict=True)

	if possible_references.supplier_primary_contact:
		email = frappe.db.get_value('Contact', possible_references.supplier_primary_contact, 'email_id')

	if not email and possible_references.supplier_primary_address:
		email = frappe.db.get_value('Address', possible_references.supplier_primary_address, 'email_id')

	if not email and possible_references.primary_address:
		email = frappe.db.get_value('Address', possible_references.primary_address, 'email_id')

	if not email:
		supplier_addresses = read_address_by_type_priorization('Supplier', supplier, ['Current', 'Billing', 'Office', 'Warehouse', 'Shop'])
		# get first supplier_addresses with email_id
		for supplier_address in supplier_addresses:
			if supplier_address.email_id:
				email = supplier_address.email_id
				break

	return email

# detects the best email address for the buying department
def read_preferred_quote_email_for_customer(customer):
	# find email address for maintained contacts for the customer
	customer_contacts = read_contacts_for_party('Customer', customer, ['is_primary_contact', 'is_billing_contact'])

	# get first customer_addresses with email_id
	for customer_contact in customer_contacts:
		if customer_contact.email_id:
			return customer_contact.email_id

	# if no fitting contacts with email were found, read the customers' addresses
	customer_addresses = read_address_by_type_priorization('Customer', customer, ['Current', 'Office', 'Billing', 'Warehouse', 'Shop'])
	for customer_address in customer_addresses:
		if customer_address.email_id:
			return customer_address.email_id


def read_preferred_order_email_for_customer(customer):
	# for now keep it the same, but actually for sales orders, an organizational party is required (instead of the buying department)
	return read_preferred_quote_email_for_customer(customer)


def read_address_by_type_priorization(party_doctype, party_name, priorized_types = []):
	address_list = frappe.db.get_all('Dynamic Link', fields=('parent'),
		filters={
			'parenttype': 'Address',
			'link_doctype': party_doctype,
			'link_name': party_name
		})

	# read addresses
	address_list = frappe.get_all('Address',
		filters={
			'name': ['in', [d.parent for d in address_list]],
			'address_type': ['in', priorized_types]
		},
		fields=['name', 'address_type', 'address_line1', 'address_line2', 'city', 'state', 'pincode', 'country', 'email_id', 'is_primary_address']
	)

	# sort by priority asc and is_primary_address desc
	return sorted(address_list, key=lambda k: priorized_types.index(k.address_type))

def read_contacts_for_party(party_doctype, party_name, priorized_types = []):
	contact_links = frappe.db.get_all('Dynamic Link', fields=('parent'),
		filters={
			'parenttype': 'Contact',
			'link_doctype': party_doctype,
			'link_name': party_name
		})

	# read contacts
	contacts = frappe.get_all('Contact',
		filters={
			'name': ['in', [d.parent for d in contact_links]]
		},
		fields=['name', 'email_id', 'is_primary_contact', 'is_billing_contact']
	)

	# order by given properties as priority, if prio attributes are 1 (True)
	for contact in contacts:
		for priority in priorized_types:
			if contact[priority] == 1:
				contact.priority = priorized_types.index(priority)

		if not 'priority' in contact:
			contact.priority = 99

	return sorted(contacts, key=lambda k: k.priority)

# def read_preferred_email_for_x(x):
# 	pass
# 	# email_id = frappe.db.get_value('Supplier', supplier, 'preferred_email')
# 	# if email_id:
# 	# 	return frappe.db.get_value('Contact', email_id, 'email_id')
def target_contacts_for_doc(doc):
	# frappe.throw('{}'.format(type(doc)))
	if isinstance(doc, str):
		doc = json.loads(doc)
	elif isinstance(doc, frappe.model.document.Document):
		doc = doc.as_dict()

	# frappe.throw('{}'.format(doc))

	frappe.get_cached_doc(doc['doctype'], doc['name']).check_permission('read')

	doctype = None
	party = None

	if doc['doctype'] == 'Purchase Order':
		if doc['supplier']:
			doctype = 'Supplier'
			party = doc['supplier']

	elif doc['doctype'] == 'Quotation':
		if doc['quotation_to'] == 'Customer' and doc['party_name']:
			doctype = 'Customer'
			party = doc['party_name']

	elif doc['doctype'] == 'Sales Order':
		if doc['customer']:
			doctype = 'Customer'
			party = doc['customer']

	if not party: # if still no party was found, try the properties without any preference
		possible_properties = { 'customer': 'Customer', 'supplier': 'Supplier', 'party_name': None }

		# loop through all possible properties
		for property_name, property_doctype in possible_properties.items():
			if doc[property_name]:
				if property_name == 'party_name':
					doctype = doc['party_to'] if 'party_to' in doc else None
				else:
					doctype = property_doctype

				party = doc[property_name]
				break

	if not party or not doctype: # use doc itself as target
		party = doc['name']
		doctype = doc['doctype']

	return read_contacts_for_party(doctype, party, ['is_primary_contact'])


def target_contact_for_doc(doc):
	contacts = target_contacts_for_doc(doc)
	if contacts and len(contacts) > 0:
		return contacts[0]['name']

def target_contact_name_for_doc(doc):
	# frappe.throw('{}'.format(doc))
	contact = target_contact_for_doc(doc)
	if contact:
		return contact['name']
