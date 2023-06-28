# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
import requests
import time
from frappe import _
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password
from erpnext_shipping.erpnext_shipping.utils import show_error_alert

ARAMEX_PROVIDER = "Aramex"
CALCULATE_RATE_URL = "https://ws.aramex.net/ShippingAPI.V2/RateCalculator/Service_1_0.svc/json/CalculateRate"
CREATE_SHIPMENTS_URL = (
    "https://ws.aramex.net/ShippingAPI.V2/Shipping/Service_1_0.svc/json/CreateShipments"
)
PRINT_LABEL_URL = (
    "https://ws.aramex.net/ShippingAPI.V2/Shipping/Service_1_0.svc/json/PrintLabel"
)
TRACK_SHIPMENTS_URL = (
    "https://ws.aramex.net/ShippingAPI.V2/Tracking/Service_1_0.svc/json/TrackShipments"
)


class Aramex(Document):
    pass


class AramexUtils:
    def __init__(self):
        # self.config.password = get_decrypted_password(
        #     'Aramex', 'Aramex', 'password', raise_exception=False)
        self.enabled = frappe.db.get_single_value("Aramex", "enabled")
        self.config = frappe.db.get_singles_dict("Aramex")
        self.config["password"] = get_decrypted_password(
            "Aramex", "Aramex", "password", raise_exception=False
        )

        if not self.enabled:
            link = frappe.utils.get_link_to_form(
                "Aramex", "Aramex", frappe.bold("Aramex Settings")
            )
            frappe.throw(
                _("Please enable Aramex Integration in {0}".format(link)),
                title=_("Mandatory"),
            )

    def get_available_services(
        self, pickup_address, delivery_address, shipment_parcel, pickup_date
    ):
        # Retrieve rates at Aramex from specification stated.
        parcel_list = self.get_parcel_list(json.loads(shipment_parcel))
        shipment_parcel_params = self.get_formatted_parcel_params(parcel_list)

        # url = self.get_formatted_request_url(
        #     pickup_address, delivery_address, shipment_parcel_params)

        if not self.config["account_number"] or not self.config["account_pin"]:
            return []

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = self.generate_rate_calculation_payload(
            pickup_address=pickup_address,
            delivery_address=delivery_address,
            shipment_parcel=shipment_parcel,
            pickup_date=pickup_date,
        )

        try:
            response_data = requests.post(
                url=CALCULATE_RATE_URL, headers=headers, data=json.dumps(payload)
            )
            response_data = json.loads(response_data.text)
            if response_data["HasErrors"]:
                return []
            available_services = []
            available_service = {
                "carrier": "Aramex",
                # "carrier_name": "Aramex",
                "service_name": "PPX",
                "is_preferred": 0,
                "real_weight": 0,
                "total_price": response_data["TotalAmount"]["Value"],
                "price_info": response_data["TotalAmount"],
            }
            available_services.append(available_service)
            return available_services
        except Exception:
            show_error_alert("fetching Aramex prices")

        return []

    def create_shipment(
        self,
        pickup_address,
        delivery_address,
        shipment_parcel,
        description_of_content,
        pickup_date,
        pickup_time,
        value_of_goods,
        pickup_contact,
        delivery_contact,
        service_info,
        delivery_company_name,
    ):
        # Create a transaction at Aramex
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = self.generate_create_shipment_payload(
            pickup_address,
            pickup_contact,
            delivery_address,
            delivery_contact,
            pickup_date,
            pickup_time,
            shipment_parcel,
            description_of_content,
            value_of_goods,
            delivery_company_name,
        )
        try:
            response_data = requests.post(
                url=CREATE_SHIPMENTS_URL, headers=headers, data=json.dumps(payload)
            )

            response_data = json.loads(response_data.text)

            if response_data["HasErrors"]:
                return {}
            shipmet = response_data["Shipments"][0]

            return {
                "shipment_id": shipmet["ID"],
                "carrier": "Aramex",
                "carrier_service": shipmet["ShipmentDetails"]["ProductType"],
                "shipment_label": shipmet["ShipmentLabel"]["LabelURL"],
                "awb_number": shipmet["ID"],
                "tracking_url": f'https://www.aramex.com/us/en/track/results?mode=0&ShipmentNumber={shipmet["ID"]}',
            }
        except Exception:
            show_error_alert("creating Aramex Shipment")

    def get_label(self, awb_number):
        # Retrieve shipment label from Aramex
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = self.generate_shipment_label_payload(awb_number)
        try:
            shipment_label_response = requests.post(
                url=PRINT_LABEL_URL, headers=headers, data=json.dumps(payload)
            )
            shipment_label = json.loads(shipment_label_response.text)
            if shipment_label["HasErrors"]:
                message = _(
                    "Please make sure Shipment (ID: {0}), exists and is a complete Shipment on Aramex."
                ).format(awb_number)
                frappe.msgprint(msg=_(message), title=_("Label Not Found"))

            return shipment_label["ShipmentLabel"]["LabelURL"]

        except Exception:
            show_error_alert("printing Aramex Label")
        return []

    def get_tracking_data(self, awb_number):
        # Get Aramex Tracking Info
        from erpnext_shipping.erpnext_shipping.utils import get_tracking_url

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = self.generate_tracking_payload(awb_number)
        try:
            tracking_data_response = requests.post(
                url=TRACK_SHIPMENTS_URL, headers=headers, data=json.dumps(payload)
            )
            tracking_data = json.loads(tracking_data_response.text)
            if tracking_data["HasErrors"]:
                return {}
            trackingResult = tracking_data["TrackingResults"][0]
            return {
                "tracking_status": trackingResult["Value"][0]["UpdateDescription"]
                if len(trackingResult["Value"])
                else "",
                # 'tracking_status_info': tracking_data['state'],
                "tracking_url": f"https://www.aramex.com/us/en/track/results?mode=0&ShipmentNumber={awb_number}",
            }

            # if 'trackings' in tracking_data:
            #     tracking_status = 'In Progress'
            #     if tracking_data['state'] == 'DELIVERED':
            #         tracking_status = 'Delivered'
            #     if tracking_data['state'] == 'RETURNED':
            #         tracking_status = 'Returned'
            #     if tracking_data['state'] == 'LOST':
            #         tracking_status = 'Lost'
            #     awb_number = None if not tracking_data['trackings'] else tracking_data['trackings'][0]
            #     tracking_url = get_tracking_url(
            #         carrier=tracking_data['carrier'],
            #         tracking_number=awb_number
            #     )
        except Exception:
            show_error_alert("updating Aramex Shipment")
        return []

    def get_formatted_request_url(
        self, pickup_address, delivery_address, shipment_parcel_params
    ):
        """Returns formatted request URL for Aramex."""
        url = "https://api.aramex.com/v1/services?from[country]={from_country_code}&from[zip]={from_zip}&to[country]={to_country_code}&to[zip]={to_zip}&{shipment_parcel_params}sortBy=totalPrice&source=PRO".format(
            from_country_code=pickup_address.country_code,
            from_zip=pickup_address.pincode,
            to_country_code=delivery_address.country_code,
            to_zip=delivery_address.pincode,
            shipment_parcel_params=shipment_parcel_params,
        )
        return url

    def get_formatted_parcel_params(self, parcel_list):
        """Returns formatted parcel params for Aramex URL."""
        shipment_parcel_params = ""
        for index, parcel in enumerate(parcel_list):
            shipment_parcel_params += "packages[{index}][height]={height}&packages[{index}][length]={length}&packages[{index}][weight]={weight}&packages[{index}][width]={width}&".format(
                index=index,
                height=parcel["height"],
                length=parcel["length"],
                weight=parcel["weight"],
                width=parcel["width"],
            )
        return shipment_parcel_params

    def get_service_dict(self, response):
        """Returns a dictionary with service info."""
        available_service = frappe._dict()
        available_service.service_provider = ARAMEX_PROVIDER
        available_service.carrier = response["carrier_name"]
        available_service.carrier_name = response["name"]
        available_service.service_name = ""
        available_service.is_preferred = 0
        available_service.total_price = response["price"]["base_price"]
        available_service.actual_price = response["price"]["total_price"]
        available_service.service_id = response["id"]
        available_service.available_dates = response["available_dates"]
        return available_service

    def get_shipment_address_contact_dict(self, address, contact):
        """Returns a dict with Address and Contact Info for Aramex Payload."""
        return {
            "city": address.city,
            "company": address.address_title,
            "country": address.country_code,
            "email": contact.email,
            "name": contact.first_name,
            "phone": contact.phone,
            "state": address.country,
            "street1": address.address_line1,
            "street2": address.address_line2,
            "surname": contact.last_name,
            "zip_code": address.pincode,
        }

    def get_parcel_list(self, shipment_parcel):
        parcel_list = []
        for parcel in shipment_parcel:
            for count in range(parcel.get("count")):
                formatted_parcel = {}
                formatted_parcel["height"] = parcel.get("height")
                formatted_parcel["width"] = parcel.get("width")
                formatted_parcel["length"] = parcel.get("length")
                formatted_parcel["weight"] = parcel.get("weight")
                parcel_list.append(formatted_parcel)
        return parcel_list

    def generate_rate_calculation_payload(
        self,
        pickup_address,
        delivery_address,
        shipment_parcel,
        pickup_date=None,
        service_info=None,
    ):
        shipment_parcel = json.loads(shipment_parcel)
        payload = {
            "ClientInfo": self.get_client_info(),
            "OriginAddress": {
                "Line1": pickup_address["address_line1"],
                "Line2": pickup_address["address_line2"] or "",
                "Line3": "",
                "City": pickup_address["city"],
                "StateOrProvinceCode": "",
                "PostCode": pickup_address["pincode"],
                "CountryCode": pickup_address["country_code"],
                "Longitude": 0,
                "Latitude": 0,
                "BuildingNumber": None,
                "BuildingName": None,
                "Floor": None,
                "Apartment": None,
                "POBox": None,
                "Description": None,
            },
            "DestinationAddress": {
                "Line1": delivery_address["address_line1"],
                "Line2": delivery_address["address_line1"] or "",
                "Line3": "",
                "City": delivery_address["city"],
                "StateOrProvinceCode": "",
                "PostCode": delivery_address["pincode"],
                "CountryCode": delivery_address["country_code"],
                "Longitude": 0,
                "Latitude": 0,
                "BuildingNumber": None,
                "BuildingName": None,
                "Floor": None,
                "Apartment": None,
                "POBox": None,
                "Description": None,
            },
            "ShipmentDetails": {
                "Dimensions": None,
                "ActualWeight": {"Unit": "KG", "Value": shipment_parcel[0]["weight"]},
                "ChargeableWeight": None,
                "DescriptionOfGoods": "Books",
                "GoodsOriginCountry": "IN",
                "NumberOfPieces": shipment_parcel[0]["count"] or 1,
                "ProductGroup": "EXP",
                "ProductType": "PPX",
                "PaymentType": "P",
                "PaymentOptions": "",
                "CustomsValueAmount": None,
                "CashOnDeliveryAmount": None,
                "InsuranceAmount": None,
                "CashAdditionalAmount": None,
                "CashAdditionalAmountDescription": "",
                "CollectAmount": None,
                "Services": "",
                "Items": [],
            },
        }
        return payload

    def generate_create_shipment_payload(
        self,
        pickup_address,
        pickup_contact,
        delivery_address,
        delivery_contact,
        pickup_date,
        pickup_time,
        shipment_parcel,
        description_of_content,
        value_of_goods,
        delivery_company_name,
    ):
        shipment_parcel = json.loads(shipment_parcel)
        payload = {
            "ClientInfo": self.get_client_info(),
            "LabelInfo": {"ReportID": 9729, "ReportType": "URL"},
            "Shipments": [
                {
                    "Shipper": {
                        "AccountNumber": self.config["account_number"],
                        "PartyAddress": {
                            "Line1": pickup_address["address_line1"],
                            "Line2": pickup_address["address_line2"] or "",
                            "Line3": "",
                            "City": pickup_address["city"],
                            "StateOrProvinceCode": "",
                            "PostCode": pickup_address["pincode"],
                            "CountryCode": pickup_address["country_code"],
                        },
                        "Contact": {
                            "Department": "",
                            "PersonName": f"{pickup_contact['first_name']} {pickup_contact['last_name']}",
                            "Title": "",
                            "CompanyName": pickup_contact["company_name"] or "",
                            "PhoneNumber1": pickup_contact["phone"],
                            "PhoneNumber1Ext": "",
                            "PhoneNumber2": "",
                            "PhoneNumber2Ext": "",
                            "CellPhone": pickup_contact["phone"],
                            "EmailAddress": pickup_contact["email"],
                            "Type": "",
                        },
                    },
                    "Consignee": {
                        "AccountNumber": self.config["account_number"],
                        "PartyAddress": {
                            "Line1": delivery_address["address_line1"],
                            "Line2": delivery_address["address_line2"] or "",
                            "Line3": "",
                            "City": delivery_address["city"],
                            "StateOrProvinceCode": "",
                            "PostCode": delivery_address["pincode"],
                            "CountryCode": delivery_address["country_code"],
                        },
                        "Contact": {
                            "Department": "",
                            "PersonName": f"{delivery_contact['first_name']} {delivery_contact['last_name']}",
                            "Title": "",
                            "CompanyName": delivery_company_name,
                            "PhoneNumber1": delivery_contact["phone"],
                            "PhoneNumber1Ext": "",
                            "PhoneNumber2": "",
                            "PhoneNumber2Ext": "",
                            "CellPhone": delivery_contact["phone"],
                            "EmailAddress": delivery_contact["email_id"],
                            "Type": "",
                        },
                    },
                    "ShippingDateTime": self.getShippingDate(
                        f"{pickup_date} {pickup_time}"
                    ),
                    "Details": {
                        "Dimensions": {
                            "Length": shipment_parcel[0]["length"],
                            "Width": shipment_parcel[0]["width"],
                            "Height": shipment_parcel[0]["height"],
                            "Unit": "CM",
                        },
                        "ActualWeight": {
                            "Unit": "KG",
                            "Value": shipment_parcel[0]["weight"],
                        },
                        "ChargeableWeight": None,
                        "DescriptionOfGoods": description_of_content,
                        "GoodsOriginCountry": "IN",
                        "NumberOfPieces": shipment_parcel[0]["count"],
                        "ProductGroup": "EXP",
                        "ProductType": "PPX",
                        "PaymentType": "P",
                        "PaymentOptions": "",
                        "CustomsValueAmount": {
                            "CurrencyCode": "INR",
                            "Value": value_of_goods,
                        },
                        "InsuranceAmount": None,
                        "AdditionalProperties": [
                            {
                                "CategoryName": "CustomsClearance",
                                "Name": "ShipperTaxIdVATEINNumber",
                                "Value": "123456789101",
                            },
                            {
                                "CategoryName": "CustomsClearance",
                                "Name": "ConsigneeTaxIdVATEINNumber",
                                "Value": "987654321012",
                            },
                            {
                                "CategoryName": "CustomsClearance",
                                "Name": "TaxPaid",
                                "Value": "1",
                            },
                            {
                                "CategoryName": "CustomsClearance",
                                "Name": "InvoiceDate",
                                "Value": "08/17/2020",
                            },
                            {
                                "CategoryName": "CustomsClearance",
                                "Name": "InvoiceNumber",
                                "Value": "Inv123456",
                            },
                            {
                                "CategoryName": "CustomsClearance",
                                "Name": "TaxAmount",
                                "Value": "120.52",
                            },
                            {
                                "CategoryName": "CustomsClearance",
                                "Name": "IOSS",
                                "Value": "IM1098494352",
                            },
                            {
                                "CategoryName": "CustomsClearance",
                                "Name": "ExporterType",
                                "Value": "UT",
                            },
                        ],
                    },
                }
            ],
        }
        return payload

    def generate_shipment_label_payload(self, awb_number):
        payload = {
            "ClientInfo": self.get_client_info(),
            "LabelInfo": {"ReportID": 9729, "ReportType": "URL"},
            "ShipmentNumber": awb_number,
        }
        return payload

    def generate_tracking_payload(self, awb_number):
        payload = {
            "ClientInfo": self.get_client_info(),
            "GetLastTrackingUpdateOnly": True,
            "Shipments": [awb_number],
        }
        return payload

    def getShippingDate(self, shippingDate):
        pattern = "%Y-%m-%d %H:%M:%S"
        epoch = int(time.mktime(time.strptime(shippingDate, pattern))) * 1000
        return r"/Date(" + epoch.__str__() + ")/"

    def get_client_info(self):
        return {
            "UserName": self.config["user_name"],
            "Password": self.config["password"],
            "Version": "v1.0",
            "AccountNumber": self.config["account_number"],
            "AccountPin": self.config["account_pin"],
            "AccountEntity": self.config["account_entity"],
            "AccountCountryCode": self.config["account_country_code"],
            "Source": 24,
        }
