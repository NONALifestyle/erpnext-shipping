# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt
from __future__ import unicode_literals
import frappe
import json
from nona.nona.notifications.notifications import send_delivery_status_update_notification
from six import string_types
from frappe import _
from frappe.utils import flt
from erpnext.stock.doctype.shipment.shipment import get_company_contact
from erpnext_shipping.erpnext_shipping.utils import (
    get_address,
    get_contact,
    match_parcel_service_type_carrier,
)
from erpnext_shipping.erpnext_shipping.doctype.aramex.aramex import (
    ARAMEX_PROVIDER,
    AramexUtils,
)

from erpnext_shipping.erpnext_shipping.doctype.delhivery.delhivery import (
    DELHIVERY_PROVIDER,
    DelhiveryUtils,
)


@frappe.whitelist()
def fetch_shipping_services(
    pickup_address_name,
    delivery_address_name,
):
    # Return Shipping Rates for the various Shipping Providers
    shipment_services = [{"carrier": "Custom"}]
    aramex_enabled = frappe.db.get_single_value("Aramex", "enabled")
    pickup_address = get_address(pickup_address_name)
    delivery_address = get_address(delivery_address_name)

    if (
        pickup_address.get("country") == "India"
        and delivery_address.get("country") == "India"
    ):
        delhivery_enabled = frappe.db.get_single_value("Delhivery", "enabled")
        if delhivery_enabled:
            shipment_services.append(
                {
                    "carrier": DELHIVERY_PROVIDER,
                }
            )

    else:
        if aramex_enabled:
            shipment_services.append({"carrier": ARAMEX_PROVIDER})

    return shipment_services


@frappe.whitelist()
def create_shipment(
    shipment,
    pickup_from_type,
    delivery_to_type,
    pickup_address_name,
    delivery_address_name,
    shipment_parcel,
    description_of_content,
    pickup_date,
    pickup_time,
    value_of_goods,
    service_data,
    pickup_company_name,
    delivery_company_name,
    shipment_notific_email=None,
    tracking_notific_email=None,
    pickup_contact_name=None,
    delivery_contact_name=None,
    delivery_notes=[],
):
    # Create Shipment for the selected provider
    service_info = json.loads(service_data)
    shipment_info, pickup_contact, delivery_contact = None, None, None
    pickup_address = get_address(pickup_address_name)
    delivery_address = get_address(delivery_address_name)

    if pickup_from_type != "Company":
        pickup_contact = get_contact(pickup_contact_name)
    else:
        pickup_contact = get_company_contact(user=pickup_contact_name)
        pickup_contact["company_name"] = pickup_company_name

    if delivery_to_type != "Company":
        delivery_contact = get_contact(delivery_contact_name)
    else:
        delivery_contact = get_company_contact(user=pickup_contact_name)

    if service_info["carrier"] == ARAMEX_PROVIDER:
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
            delivery_company_name=delivery_company_name,
        )

    elif service_info["carrier"] == DELHIVERY_PROVIDER:
        delhivery = DelhiveryUtils()
        shipment_info = delhivery.create_shipment(
            pickup_address=pickup_address,
            delivery_address=delivery_address,
            shipment_parcel=shipment_parcel,
            description_of_content=description_of_content,
            value_of_goods=value_of_goods,
            delivery_contact=delivery_contact,
            delivery_company_name=delivery_company_name,
        )

    else:
        fields = [
            "carrier",
            "awb_number",
            "tracking_status",
        ]
        for field in fields:
            frappe.db.set_value("Shipment", shipment, field, service_info.get(field))

        frappe.db.set_value("Shipment", shipment, "status", "Booked")
        frappe.db.set_value("Shipment", shipment, "service_provider", "Local")
        frappe.db.set_value("Shipment", shipment, "shipment_id", shipment)

    if shipment_info:
        fields = [
            "shipment_id",
            "carrier",
            "carrier_service",
            "shipment_label",
            "awb_number",
        ]
        for field in fields:
            frappe.db.set_value("Shipment", shipment, field, shipment_info.get(field))
        frappe.db.set_value("Shipment", shipment, "status", "Booked")
        frappe.db.set_value("Shipment", shipment, "service_provider", "Partner")

        if delivery_notes:
            update_delivery_note(
                delivery_notes=delivery_notes, shipment_info=shipment_info
            )

    return shipment_info


@frappe.whitelist()
def print_shipping_label(carrier, awb_number):
    if carrier == ARAMEX_PROVIDER:
        aramex = AramexUtils()
        shipping_label = aramex.get_label(awb_number)
    if carrier == DELHIVERY_PROVIDER:
        delhivery = DelhiveryUtils()
        shipping_label = delhivery.get_label(awb_number)
    return shipping_label


@frappe.whitelist()
def update_tracking(shipment, carrier, shipment_id, awb_number, tracking_status=None):
    # Update Tracking info in Shipment
    prev_shipment = frappe.get_doc("Shipment", shipment)
    tracking_data = None
    if carrier == ARAMEX_PROVIDER:
        aramex = AramexUtils()
        tracking_data = aramex.get_tracking_data(awb_number)

    elif carrier == DELHIVERY_PROVIDER:
        delhivery = DelhiveryUtils()
        """In case of Delhivery, shipment_id is the LR Number which is used for tracking and awb_number is used to generate the url for end user"""
        tracking_data = delhivery.get_tracking_data(awb_number, lrnum=shipment_id)

    else:
        frappe.db.set_value("Shipment", shipment, "tracking_status", tracking_status)

    if tracking_data:
        # fields = ['awb_number', 'tracking_status',
        #           'tracking_status_info', 'tracking_url']
        fields = ["tracking_status", "tracking_url"]
        for field in fields:
            frappe.db.set_value("Shipment", shipment, field, tracking_data.get(field))

        frappe.db.set_value("Shipment", shipment, "status", "Booked")

    shipment = frappe.get_doc("Shipment", shipment)
    send_delivery_status_update_notification(shipment, prev_shipment)

    # if delivery_notes:
    #     update_delivery_note(delivery_notes=delivery_notes, tracking_info=tracking_data)


def update_delivery_note(delivery_notes, shipment_info=None, tracking_info=None):
    # Update Shipment Info in Delivery Note
    # Using db_set since some services might not exist
    if isinstance(delivery_notes, string_types):
        delivery_notes = json.loads(delivery_notes)

    delivery_notes = list(set(delivery_notes))

    for delivery_note in delivery_notes:
        dl_doc = frappe.get_doc("Delivery Note", delivery_note)
        if shipment_info:
            dl_doc.db_set("delivery_type", "Parcel Service")
            dl_doc.db_set("parcel_service", shipment_info.get("carrier"))
            dl_doc.db_set("parcel_service_type", shipment_info.get("carrier_service"))
        if tracking_info:
            dl_doc.db_set("tracking_number", tracking_info.get("awb_number"))
            dl_doc.db_set("tracking_url", tracking_info.get("tracking_url"))
            dl_doc.db_set("tracking_status", tracking_info.get("tracking_status"))
            dl_doc.db_set(
                "tracking_status_info", tracking_info.get("tracking_status_info")
            )
