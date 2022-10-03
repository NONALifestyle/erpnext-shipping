# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt
from __future__ import unicode_literals
import frappe
import json
from six import string_types
from frappe import _
from frappe.utils import flt
from erpnext.stock.doctype.shipment.shipment import get_company_contact
from erpnext_shipping.erpnext_shipping.utils import get_address, get_contact, match_parcel_service_type_carrier
from erpnext_shipping.erpnext_shipping.doctype.letmeship.letmeship import LETMESHIP_PROVIDER, LetMeShipUtils, aramexShippingRate
from erpnext_shipping.erpnext_shipping.doctype.aramex.aramex import ARAMEX_PROVIDER, AramexUtils
from erpnext_shipping.erpnext_shipping.doctype.sendcloud.sendcloud import SENDCLOUD_PROVIDER, SendCloudUtils


@frappe.whitelist()
def fetch_shipping_rates(pickup_from_type, delivery_to_type, pickup_address_name, delivery_address_name,
                         shipment_parcel, description_of_content, pickup_date, value_of_goods,
                         pickup_contact_name=None, delivery_contact_name=None):
    # Return Shipping Rates for the various Shipping Providers
    shipment_prices = []
    # letmeship_enabled = frappe.db.get_single_value('LetMeShip', 'enabled')
    aramex_enabled = frappe.db.get_single_value('Aramex', 'enabled')
    # bluedart_enabled = frappe.db.get_single_value('BlueDart', 'enabled')
    sendcloud_enabled = frappe.db.get_single_value('SendCloud', 'enabled')
    pickup_address = get_address(pickup_address_name)
    delivery_address = get_address(delivery_address_name)

    # Fetch Aramex Rates
    if aramex_enabled:
        aramex = AramexUtils()
        aramex_prices = aramex.get_available_services(
            pickup_address=pickup_address,
            delivery_address=delivery_address,
            shipment_parcel=shipment_parcel,
            pickup_date=pickup_date
        ) or []
        # aramex_prices = match_parcel_service_type_carrier(
        #     aramex_prices, ['carrier_name', 'carrier'])
        shipment_prices = shipment_prices + aramex_prices

    # Fetch BlueDart Rates
    # if bluedart_enabled:
    #     aramex = AramexUtils()
    #     aramex_prices = aramex.get_available_services(
    #         pickup_address=pickup_address,
    #         delivery_address=delivery_address,
    #         shipment_parcel=shipment_parcel,
    #         pickup_date=pickup_date
    #     ) or []
    #     # aramex_prices = match_parcel_service_type_carrier(
    #     #     aramex_prices, ['carrier_name', 'carrier'])
    #     shipment_prices = shipment_prices + aramex_prices

    if sendcloud_enabled and pickup_from_type == 'Company':
        sendcloud = SendCloudUtils()
        sendcloud_prices = sendcloud.get_available_services(
            delivery_address=delivery_address,
            shipment_parcel=shipment_parcel
        ) or []
        # remove after fixing scroll issue
        shipment_prices = shipment_prices + sendcloud_prices[:4]
    shipment_prices = sorted(shipment_prices, key=lambda k: k['total_price'])
    print("---------shipment_prices-------")
    print(shipment_prices)
    return shipment_prices


@frappe.whitelist()
def create_shipment(shipment, pickup_from_type, delivery_to_type, pickup_address_name,
                    delivery_address_name, shipment_parcel, description_of_content, pickup_date, pickup_time,
                    value_of_goods, service_data, pickup_company_name, shipment_notific_email=None, tracking_notific_email=None,
                    pickup_contact_name=None, delivery_contact_name=None, delivery_notes=[]):
    # Create Shipment for the selected provider
    service_info = json.loads(service_data)
    print("------service_info------")
    print(service_info)
    print("-------pickup_from_type---------")
    print(pickup_from_type)
    print("-------pickup_company_name---------")
    print(pickup_company_name)
    print("-----pickup_contact_name--------")
    print(pickup_contact_name)
    shipment_info, pickup_contact,  delivery_contact = None, None, None
    pickup_address = get_address(pickup_address_name)
    delivery_address = get_address(delivery_address_name)

    if pickup_from_type != 'Company':
        pickup_contact = get_contact(pickup_contact_name)
    else:
        pickup_contact = get_company_contact(user=pickup_contact_name)
        pickup_contact['company_name'] = pickup_company_name

    if delivery_to_type != 'Company':
        delivery_contact = get_contact(delivery_contact_name)
    else:
        delivery_contact = get_company_contact(user=pickup_contact_name)

    if service_info['carrier'] == LETMESHIP_PROVIDER:
        letmeship = LetMeShipUtils()
        shipment_info = letmeship.create_shipment(
            pickup_address=pickup_address,
            delivery_address=delivery_address,
            shipment_parcel=shipment_parcel,
            description_of_content=description_of_content,
            pickup_date=pickup_date,
            value_of_goods=value_of_goods,
            pickup_contact=pickup_contact,
            delivery_contact=delivery_contact,
            service_info=service_info
        )

    if service_info['carrier'] == ARAMEX_PROVIDER:
        aramex = AramexUtils()
        shipment_info = aramex.create_shipment(
            pickup_address=pickup_address,
            delivery_address=delivery_address,
            shipment_parcel=shipment_parcel,
            description_of_content=description_of_content,
            pickup_date=pickup_date,
            pickup_time=pickup_time,
            value_of_goods=value_of_goods,
            pickup_contact=pickup_contact,
            delivery_contact=delivery_contact,
            service_info=service_info,
        )

    if service_info['carrier'] == SENDCLOUD_PROVIDER:
        sendcloud = SendCloudUtils()
        shipment_info = sendcloud.create_shipment(
            shipment=shipment,
            delivery_address=delivery_address,
            shipment_parcel=shipment_parcel,
            description_of_content=description_of_content,
            value_of_goods=value_of_goods,
            delivery_contact=delivery_contact,
            service_info=service_info,
        )

    print("--------shipment_info-----")
    print(shipment_info)
    if shipment_info:
        fields = ['shipment_id',
                  'carrier',
                  'carrier_service',
                  'shipment_label',
                  'awb_number']
        for field in fields:
            frappe.db.set_value('Shipment', shipment, field,
                                shipment_info.get(field))
        frappe.db.set_value('Shipment', shipment, 'status', 'Booked')

        if delivery_notes:
            update_delivery_note(
                delivery_notes=delivery_notes, shipment_info=shipment_info)

    return shipment_info


@frappe.whitelist()
def print_shipping_label(carrier, shipment_id):
    if carrier == LETMESHIP_PROVIDER:
        letmeship = LetMeShipUtils()
        shipping_label = letmeship.get_label(shipment_id)
    elif carrier == ARAMEX_PROVIDER:
        aramex = AramexUtils()
        shipping_label = aramex.get_label(shipment_id)
    elif carrier == SENDCLOUD_PROVIDER:
        sendcloud = SendCloudUtils()
        shipping_label = sendcloud.get_label(shipment_id)
    return shipping_label


@frappe.whitelist()
def update_tracking(shipment, carrier, shipment_id, delivery_notes=[]):
    # Update Tracking info in Shipment
    tracking_data = None
    if carrier == LETMESHIP_PROVIDER:
        letmeship = LetMeShipUtils()
        tracking_data = letmeship.get_tracking_data(shipment_id)
    elif carrier == ARAMEX_PROVIDER:
        aramex = AramexUtils()
        tracking_data = aramex.get_tracking_data(shipment_id)
    elif carrier == SENDCLOUD_PROVIDER:
        sendcloud = SendCloudUtils()
        tracking_data = sendcloud.get_tracking_data(shipment_id)

    if tracking_data:
        # fields = ['awb_number', 'tracking_status',
        #           'tracking_status_info', 'tracking_url']
        fields = ['tracking_status', 'tracking_url']
        for field in fields:
            frappe.db.set_value('Shipment', shipment, field,
                                tracking_data.get(field))

        # frappe.db.set_value('Shipment', shipment, 'status', 'Delivered')
        frappe.db.set_value('Shipment', shipment, 'status', 'Booked')

        if delivery_notes:
            update_delivery_note(
                delivery_notes=delivery_notes, tracking_info=tracking_data)


def update_delivery_note(delivery_notes, shipment_info=None, tracking_info=None):
    # Update Shipment Info in Delivery Note
    # Using db_set since some services might not exist
    if isinstance(delivery_notes, string_types):
        delivery_notes = json.loads(delivery_notes)

    delivery_notes = list(set(delivery_notes))

    for delivery_note in delivery_notes:
        dl_doc = frappe.get_doc('Delivery Note', delivery_note)
        if shipment_info:
            dl_doc.db_set('delivery_type', 'Parcel Service')
            dl_doc.db_set('parcel_service', shipment_info.get('carrier'))
            dl_doc.db_set('parcel_service_type',
                          shipment_info.get('carrier_service'))
        if tracking_info:
            dl_doc.db_set('tracking_number', tracking_info.get('awb_number'))
            dl_doc.db_set('tracking_url', tracking_info.get('tracking_url'))
            dl_doc.db_set('tracking_status',
                          tracking_info.get('tracking_status'))
            dl_doc.db_set('tracking_status_info',
                          tracking_info.get('tracking_status_info'))
