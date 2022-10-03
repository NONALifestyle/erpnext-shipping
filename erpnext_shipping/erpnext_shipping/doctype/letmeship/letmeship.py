# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from cmath import pi
import datetime
from erpnext.stock.doctype.shipment.shipment import Shipment
import requests
import frappe
import json
import re
import xmltodict
from frappe import _
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password
from erpnext_shipping.erpnext_shipping.utils import show_error_alert

LETMESHIP_PROVIDER = 'LetMeShip'


class LetMeShip(Document):
    pass


class LetMeShipUtils():
    def __init__(self):
        self.api_password = get_decrypted_password(
            'LetMeShip', 'LetMeShip', 'api_password', raise_exception=False)
        self.api_id, self.enabled = frappe.db.get_value(
            'LetMeShip', 'LetMeShip', ['api_id', 'enabled'])

        if not self.enabled:
            link = frappe.utils.get_link_to_form(
                'LetMeShip', 'LetMeShip', frappe.bold('LetMeShip Settings'))
            frappe.throw(_('Please enable LetMeShip Integration in {0}'.format(
                link)), title=_('Mandatory'))

    def get_available_services(self, delivery_to_type, pickup_address,
                               delivery_address, shipment_parcel, description_of_content, pickup_date,
                               value_of_goods, pickup_contact=None, delivery_contact=None):
        # Retrieve rates at LetMeShip from specification stated.
        if not self.enabled or not self.api_id or not self.api_password:
            return []

        self.set_letmeship_specific_fields(pickup_contact, delivery_contact)
        pickup_address.address_title = self.trim_address(pickup_address)
        delivery_address.address_title = self.trim_address(delivery_address)
        parcel_list = self.get_parcel_list(
            json.loads(shipment_parcel), description_of_content)

        url = 'https://api.letmeship.com/v1/available'
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Access-Control-Allow-Origin': 'string'
        }
        payload = self.generate_payload(
            pickup_address=pickup_address,
            pickup_contact=pickup_contact,
            delivery_address=delivery_address,
            delivery_contact=delivery_contact,
            description_of_content=description_of_content,
            value_of_goods=value_of_goods,
            parcel_list=parcel_list,
            pickup_date=pickup_date
        )
        try:
            available_services = []
            response_data = requests.post(
                url=url,
                auth=(self.api_id, self.api_password),
                headers=headers,
                data=json.dumps(payload)
            )
            response_data = json.loads(response_data.text)
            if 'serviceList' in response_data:
                for response in response_data['serviceList']:
                    available_service = self.get_service_dict(response)
                    available_services.append(available_service)

                return available_services
            else:
                frappe.throw(_('An Error occurred while fetching LetMeShip prices: {0}')
                             .format(response_data['message']))
        except Exception:
            show_error_alert("fetching LetMeShip prices")

        return []

    # def create_shipment(self, pickup_address, delivery_address, shipment_parcel, description_of_content,
    # 	pickup_date, value_of_goods, service_info, pickup_contact=None, delivery_contact=None):
    # 	# Create a transaction at LetMeShip
    # 	if not self.enabled or not self.api_id or not self.api_password:
    # 		return []

    # 	self.set_letmeship_specific_fields(pickup_contact, delivery_contact)
    # 	pickup_address.address_title = self.trim_address(pickup_address)
    # 	delivery_address.address_title = self.trim_address(delivery_address)
    # 	parcel_list = self.get_parcel_list(json.loads(shipment_parcel), description_of_content)

    # 	url = 'https://api.letmeship.com/v1/shipments'
    # 	headers = {
    # 		'Content-Type': 'application/json',
    # 		'Accept': 'application/json',
    # 		'Access-Control-Allow-Origin': 'string'
    # 	}
    # 	payload = self.generate_payload(
    # 		pickup_address=pickup_address,
    # 		pickup_contact=pickup_contact,
    # 		delivery_address=delivery_address,
    # 		delivery_contact=delivery_contact,
    # 		description_of_content=description_of_content,
    # 		value_of_goods=value_of_goods,
    # 		parcel_list=parcel_list,
    # 		pickup_date=pickup_date,
    # 		service_info=service_info)
    # 	try:
    # 		response_data = requests.post(
    # 			url=url,
    # 			auth=(self.api_id, self.api_password),
    # 			headers=headers,
    # 			data=json.dumps(payload)
    # 		)
    # 		response_data = json.loads(response_data.text)
    # 		if 'shipmentId' in response_data:
    # 			shipment_amount = response_data['service']['priceInfo']['totalPrice']
    # 			awb_number = ''
    # 			url = 'https://api.letmeship.com/v1/shipments/{id}'.format(id=response_data['shipmentId'])
    # 			tracking_response = requests.get(url, auth=(self.api_id, self.api_password),headers=headers)
    # 			tracking_response_data = json.loads(tracking_response.text)
    # 			if 'trackingData' in tracking_response_data:
    # 				for parcel in tracking_response_data['trackingData']['parcelList']:
    # 					if 'awbNumber' in parcel:
    # 						awb_number = parcel['awbNumber']
    # 			return {
    # 				'service_provider': LETMESHIP_PROVIDER,
    # 				'shipment_id': response_data['shipmentId'],
    # 				'carrier': service_info['carrier'],
    # 				'carrier_service': service_info['service_name'],
    # 				'shipment_amount': shipment_amount,
    # 				'awb_number': awb_number,
    # 			}
    # 		elif 'message' in response_data:
    # 			frappe.throw(_('An Error occurred while creating Shipment: {0}')
    # 				.format(response_data['message']))
    # 	except Exception:
    # 		show_error_alert("creating LetMeShip Shipment")

    def get_label(self, shipment_id):
        # Retrieve shipment label from LetMeShip
        try:
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Access-Control-Allow-Origin': 'string'
            }
            url = 'https://api.letmeship.com/v1/shipments/{id}/documents?types=LABEL'.format(
                id=shipment_id)
            shipment_label_response = requests.get(
                url,
                auth=(self.api_id, self.api_password),
                headers=headers
            )
            shipment_label_response_data = json.loads(
                shipment_label_response.text)
            if 'documents' in shipment_label_response_data:
                for label in shipment_label_response_data['documents']:
                    if 'data' in label:
                        return json.dumps(label['data'])
            else:
                frappe.throw(_('Error occurred while printing Shipment: {0}')
                             .format(shipment_label_response_data['message']))
        except Exception:
            show_error_alert("printing LetMeShip Label")

    def get_tracking_data(self, shipment_id):
        from erpnext_shipping.erpnext_shipping.utils import get_tracking_url
        # return letmeship tracking data
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Access-Control-Allow-Origin': 'string'
        }
        try:
            url = 'https://api.letmeship.com/v1/tracking?shipmentid={id}'.format(
                id=shipment_id)
            tracking_data_response = requests.get(
                url,
                auth=(self.api_id, self.api_password),
                headers=headers
            )
            tracking_data = json.loads(tracking_data_response.text)
            if 'awbNumber' in tracking_data:
                tracking_status = 'In Progress'
                if tracking_data['lmsTrackingStatus'].startswith('DELIVERED'):
                    tracking_status = 'Delivered'
                if tracking_data['lmsTrackingStatus'] == 'RETURNED':
                    tracking_status = 'Returned'
                if tracking_data['lmsTrackingStatus'] == 'LOST':
                    tracking_status = 'Lost'
                tracking_url = get_tracking_url(
                    carrier=tracking_data['carrier'],
                    tracking_number=tracking_data['awbNumber']
                )
                return {
                    'awb_number': tracking_data['awbNumber'],
                    'tracking_status': tracking_status,
                    'tracking_status_info': tracking_data['lmsTrackingStatus'],
                    'tracking_url': tracking_url,
                }
            elif 'message' in tracking_data:
                frappe.throw(_('Error occurred while updating Shipment: {0}')
                             .format(tracking_data['message']))
        except Exception:
            show_error_alert("updating LetMeShip Shipment")

    def generate_payload(self, pickup_address, pickup_contact, delivery_address, delivery_contact,
                         description_of_content, value_of_goods, parcel_list, pickup_date, service_info=None):
        payload = {
            'pickupInfo': self.get_pickup_delivery_info(pickup_address, pickup_contact),
            'deliveryInfo': self.get_pickup_delivery_info(delivery_address, delivery_contact),
            'shipmentDetails': {
                'contentDescription': description_of_content,
                'shipmentType': 'PARCEL',
                'shipmentSettings': {
                    'saturdayDelivery': False,
                    'ddp': False,
                                'insurance': False,
                                'pickupOrder': False,
                                'pickupTailLift': False,
                                'deliveryTailLift': False,
                                'holidayDelivery': False,
                },
                'goodsValue': value_of_goods,
                'parcelList': parcel_list,
                'pickupInterval': {
                    'date': pickup_date
                }
            }
        }

        if service_info:
            payload['service'] = {
                'baseServiceDetails': {
                    'id': service_info['id'],
                    'name': service_info['service_name'],
                    'carrier': service_info['carrier'],
                    'priceInfo': service_info['price_info'],
                },
                'supportedExWorkType': [],
                'messages': [''],
                'description': '',
                'serviceInfo': '',
            }
            payload['shipmentNotification'] = {
                'trackingNotification': {
                    'deliveryNotification': True,
                    'problemNotification': True,
                    'emails': [],
                    'notificationText': '',
                },
                'recipientNotification': {
                    'notificationText': '',
                    'emails': []
                }
            }
            payload['labelEmail'] = True
        return payload

    def trim_address(self, address):
        # LetMeShip has a limit of 30 characters for Company field
        if len(address.address_title) > 30:
            return address.address_title[:30]

    def get_service_dict(self, response):
        """Returns a dictionary with service info."""
        available_service = frappe._dict()
        basic_info = response['baseServiceDetails']
        price_info = basic_info['priceInfo']
        available_service.service_provider = LETMESHIP_PROVIDER
        available_service.id = basic_info['id']
        available_service.carrier = basic_info['carrier']
        available_service.carrier_name = basic_info['name']
        available_service.service_name = ''
        available_service.is_preferred = 0
        available_service.real_weight = price_info['realWeight']
        available_service.total_price = price_info['netPrice']
        available_service.price_info = price_info
        return available_service

    def set_letmeship_specific_fields(self, pickup_contact, delivery_contact):
        pickup_contact.phone_prefix = pickup_contact.phone[:3]
        pickup_contact.phone = re.sub(
            '[^A-Za-z0-9]+', '', pickup_contact.phone[3:])

        pickup_contact.title = 'MS'
        if pickup_contact.gender == 'Male':
            pickup_contact.title = 'MR'

        delivery_contact.phone_prefix = delivery_contact.phone[:3]
        delivery_contact.phone = re.sub(
            '[^A-Za-z0-9]+', '', delivery_contact.phone[3:])

        delivery_contact.title = 'MS'
        if delivery_contact.gender == 'Male':
            delivery_contact.title = 'MR'

    def get_parcel_list(self, shipment_parcel, description_of_content):
        parcel_list = []
        for parcel in shipment_parcel:
            formatted_parcel = {}
            formatted_parcel['height'] = parcel.get('height')
            formatted_parcel['width'] = parcel.get('width')
            formatted_parcel['length'] = parcel.get('length')
            formatted_parcel['weight'] = parcel.get('weight')
            formatted_parcel['quantity'] = parcel.get('count')
            formatted_parcel['contentDescription'] = description_of_content
            parcel_list.append(formatted_parcel)
        return parcel_list

    def get_pickup_delivery_info(self, address, contact):
        return {
            'address': {
                'countryCode': address.country_code,
                'zip': address.pincode,
                'city': address.city,
                'street': address.address_line1,
                'addressInfo1': address.address_line2,
                'houseNo': '',
            },
            'company': address.address_title,
            'person': {
                'title': contact.title,
                'firstname': contact.first_name,
                'lastname': contact.last_name
            },
            'phone': {
                'phoneNumber': contact.phone,
                'phoneNumberPrefix': contact.phone_prefix
            },
            'email': contact.email
        }


@frappe.whitelist()
def create_shipment():
    epoch = 1663762645000
    # Create a transaction at LetMeShip
    # if not self.enabled or not self.api_id or not self.api_password:
    # 	return []
    url = 'https://ws.aramex.net/ShippingAPI.V2/Shipping/Service_1_0.svc/json/CreateShipments'
    headers = {
        'Content-Type': 'application/json',
        'Accept': '*/*',
        'Connection': 'keep-alive'
    }
    print("-------------------------function called----------------")
    payload = {
        "ClientInfo": {
            "UserName": "test.api@aramex.com",
            "Password": "Aramex@12345",
            "Version": "v1.0",
            "AccountNumber": "60531487",
            "AccountPin": "654654",
            "AccountEntity": "BOM",
            "AccountCountryCode": "IN",
            "Source": 24
        },  # All Values are compulsory in ClientInfo
        "LabelInfo": {
            "ReportID": 9729,
            "ReportType": "URL"
        },
        "Shipments": [
            {
                # "Reference1": "",  # optional
                # "Reference2": "",  # optional
                # "Reference3": "",  # optional
                "Shipper": {  # compulsory
                    # "Reference1": "",  # O
                    # "Reference2": "",  # O
                    "AccountNumber": "60531487",  # Compulsory
                    "PartyAddress": {
                        "Line1": "dwayne streey 123, jhsg",  # compulsory
                        "Line2": "",  # O
                        "Line3": "",  # O
                        "City": "Mumbai",  # Conditional
                        "StateOrProvinceCode": "",  # conditional
                        "PostCode": "400093",  # conditional
                        "CountryCode": "IN",  # compulsory
                        # "Longitude": 0,
                        # "Latitude": 0,
                        # "BuildingNumber": None,
                        # "BuildingName": None,
                        # "Floor": None,
                        # "Apartment": None,
                        # "POBox": None,
                        # "Description": None
                    },
                    "Contact": {
                        "Department": "",  # O
                        "PersonName": "Dosan",  # compulsory
                        "Title": "",  # O
                        "CompanyName": "jha pvt",  # compulsory
                        "PhoneNumber1": "25655666",  # compulsory
                        "PhoneNumber1Ext": "",
                        "PhoneNumber2": "",
                        "PhoneNumber2Ext": "",
                        # "FaxNumber": "",
                        "CellPhone": "25655666",  # compulsory
                        "EmailAddress": "dosan@gmail.com",  # compulsory
                        "Type": ""
                    }
                },
                "Consignee": {  # compulsory
                    "Reference1": "",
                    "Reference2": "",
                    "AccountNumber": "",
                    "PartyAddress": {
                        "Line1": "1, bhat ji ki badi",
                        "Line2": "",
                        "Line3": "",
                        "City": "Dubai",
                        "StateOrProvinceCode": "",
                        "PostCode": "",
                        "CountryCode": "AE",
                        # "Longitude": 0,
                        # "Latitude": 0,
                        # "BuildingNumber": "",
                        # "BuildingName": "",
                        # "Floor": "",
                        # "Apartment": "",
                        # "POBox": None,
                        # "Description": ""
                    },
                    "Contact": {
                        "Department": "",
                        "PersonName": "Viki",
                        "Title": "",
                        "CompanyName": "hgh pvt ltd",
                        "PhoneNumber1": "8454097313",
                        "PhoneNumber1Ext": "",
                        "PhoneNumber2": "",
                        "PhoneNumber2Ext": "",
                        # "FaxNumber": "",
                        "CellPhone": "8454097313",
                        "EmailAddress": "vi@gmail.com",
                        "Type": ""
                    }
                },
                # "ThirdParty": {  # conditional
                #     "Reference1": "",
                #     "Reference2": "",
                #     "AccountNumber": "",
                #     "PartyAddress": {
                #         "Line1": "",
                #         "Line2": "",
                #         "Line3": "",
                #         "City": "",
                #         "StateOrProvinceCode": "",
                #         "PostCode": "",
                #         "CountryCode": "",
                #         "Longitude": 0,
                #         "Latitude": 0,
                #         "BuildingNumber": None,
                #         "BuildingName": None,
                #         "Floor": None,
                #         "Apartment": None,
                #         "POBox": None,
                #         "Description": None
                #     },
                #     "Contact": {
                #         "Department": "",
                #         "PersonName": "",
                #         "Title": "",
                #         "CompanyName": "",
                #         "PhoneNumber1": "",
                #         "PhoneNumber1Ext": "",
                #         "PhoneNumber2": "",
                #         "PhoneNumber2Ext": "",
                #         "FaxNumber": "",
                #         "CellPhone": "",
                #         "EmailAddress": "",
                #         "Type": ""
                #     }
                # },

                # compulsory
                # "ShippingDateTime": '2022-09-30',
                # "ShippingDateTime": '1663762645000',
                "ShippingDateTime": r'/Date(' + epoch.__str__() + ')/',
                # "DueDate": r'/Date(' + epoch.__str__() + ')/',  # optional
                # "Comments": "",  # O
                # "PickupLocation": "",  # O
                # "OperationsInstructions": "",  # O
                # "AccountingInstrcutions": "",  # O
                "Details": {  # Compulsory
                    "Dimensions": None,  # o
                    "ActualWeight": {  # M
                        "Unit": "KG",
                        "Value": 2.0
                    },
                    "ChargeableWeight": None,
                    "DescriptionOfGoods": "Books",
                    "GoodsOriginCountry": "IN",
                    "NumberOfPieces": 1,  # compulsory -> Pieces > 0 MAX = 100
                    "ProductGroup": "EXP",  # compulsory
                    "ProductType": "PPX",  # compulsory
                    "PaymentType": "P",  # compulsory
                    # conditional based on payment type(COD or Prepaid)->
                    "PaymentOptions": "",
                    "CustomsValueAmount": {
                        "CurrencyCode": "USD",
                        "Value": 200
                    },
                    # "CashOnDeliveryAmount": None,
                    "InsuranceAmount": None,
                    # "CashAdditionalAmount": None,
                    # "CashAdditionalAmountDescription": "",
                    # "CollectAmount": None,
                    # "Services": "",
                    # "Items": [
                    #     {
                    #         "PackageType": "Box",
                    #         "Quantity": "1",
                    #         "Weight": None,
                    #         "CustomsValue": {
                    #             "CurrencyCode": "USD",
                    #             "Value": 10
                    #         },
                    #         "Comments": "Ravishing Gold Facial Kit Long Lasting Shining Appearance For All Skin Type 125g",
                    #         "GoodsDescription": "new Gold Facial Kit Long  Shining Appearance",
                    #         "Reference": "",
                    #         "CommodityCode": "98765432"
                    #     }
                    # ],
                    "AdditionalProperties": [
                        {
                            "CategoryName": "CustomsClearance",
                            "Name": "ShipperTaxIdVATEINNumber",
                            "Value": "123456789101"
                        },
                        {
                            "CategoryName": "CustomsClearance",
                            "Name": "ConsigneeTaxIdVATEINNumber",
                            "Value": "987654321012"
                        },
                        {
                            "CategoryName": "CustomsClearance",
                            "Name": "TaxPaid",
                            "Value": "1"
                        },
                        {
                            "CategoryName": "CustomsClearance",
                            "Name": "InvoiceDate",
                            "Value": "08/17/2020"
                        },
                        {
                            "CategoryName": "CustomsClearance",
                            "Name": "InvoiceNumber",
                            "Value": "Inv123456"
                        },
                        {
                            "CategoryName": "CustomsClearance",
                            "Name": "TaxAmount",
                            "Value": "120.52"
                        },
                        {
                            "CategoryName": "CustomsClearance",
                            "Name": "IOSS",
                            "Value": "IM1098494352"
                        },
                        {
                            "CategoryName": "CustomsClearance",
                            "Name": "ExporterType",
                            "Value": "UT"
                        }
                    ]
                },
                # "Attachments": [],  # O
                # "ForeignHAWB": "",  # conditional
                # "TransportType ": 0,
                # "PickupGUID": "",  # O
                # "Number": None,  # O
                # "ScheduledDelivery": None
            }
        ],
        # "Transaction": {
        #     "Reference1": "",
        #     "Reference2": "",
        #     "Reference3": "",
        #     "Reference4": "",
        #     "Reference5": ""
        # }  # Option Values
    }
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Access-Control-Allow-Origin': 'string'
    }
    try:
        response_data = requests.post(
            url=url,
            headers=headers,
            data=json.dumps(payload)
        )
        print("----------response_data--------")
        response_data = json.loads(response_data.text)
        print(response_data)
        return {}

        if 'shipmentId' in response_data:
            shipment_amount = response_data['service']['priceInfo']['totalPrice']
            awb_number = ''
            url = 'https://api.letmeship.com/v1/shipments/{id}'.format(
                id=response_data['shipmentId'])
            tracking_response = requests.get(url, auth=(
                self.api_id, self.api_password), headers=headers)
            tracking_response_data = json.loads(tracking_response.text)
            if 'trackingData' in tracking_response_data:
                for parcel in tracking_response_data['trackingData']['parcelList']:
                    if 'awbNumber' in parcel:
                        awb_number = parcel['awbNumber']
            return {
                'service_provider': LETMESHIP_PROVIDER,
                'shipment_id': response_data['shipmentId'],
                'carrier': service_info['carrier'],
                'carrier_service': service_info['service_name'],
                'shipment_amount': shipment_amount,
                'awb_number': awb_number,
            }
        elif 'message' in response_data:
            frappe.throw(_('An Error occurred while creating Shipment: {0}')
                         .format(response_data['message']))
    except Exception:
        show_error_alert("creating LetMeShip Shipment")


@frappe.whitelist()
def aramexShippingRate():
    print("---------aramex shipping rates function------------")
    url = "https://ws.aramex.net/ShippingAPI.V2/RateCalculator/Service_1_0.svc/json/CalculateRate"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Access-Control-Allow-Origin': 'string'
    }
    payload = {
        "ClientInfo": {
            "UserName": "test.api@aramex.com",
            "Password": "Aramex@12345",
            "Version": "v1.0",
            "AccountNumber": "60531487",
            "AccountPin": "654654",
            "AccountEntity": "BOM",
            "AccountCountryCode": "IN",
            "Source": 24
        },
        "OriginAddress": {
            "Line1": "Test Address",
            "Line2": "",
            "Line3": "",
            "City": "",
            "StateOrProvinceCode": "",
            "PostCode": "400612",
            "CountryCode": "IN",
            "Longitude": 0,
            "Latitude": 0,
            "BuildingNumber": None,
            "BuildingName": None,
            "Floor": None,
            "Apartment": None,
            "POBox": None,
            "Description": None
        },
        "DestinationAddress": {
            "Line1": "Test Address",
            "Line2": "",
            "Line3": "",
            "City": "Dubai",
            "StateOrProvinceCode": "",
            "PostCode": "",
            "CountryCode": "AE",
            "Longitude": 0,
            "Latitude": 0,
            "BuildingNumber": None,
            "BuildingName": None,
            "Floor": None,
            "Apartment": None,
            "POBox": None,
            "Description": None
        },
        "ShipmentDetails": {
            "Dimensions": None,
            "ActualWeight": {
                "Unit": "KG",
                "Value": 10
            },
            "ChargeableWeight": None,
            "DescriptionOfGoods": "Books",
            "GoodsOriginCountry": "IN",
            "NumberOfPieces": 1,
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
            "Items": []
        },
        "Transaction": {
            "Reference1": "",
            "Reference2": "",
            "Reference3": "",
            "Reference4": "",
            "Reference5": ""
        }
    }
    try:
        response_data = requests.post(
            url=url,
            headers=headers,
            data=json.dumps(payload)
        )
        print("---------------request completed------------")
        print(response_data)
        response_data = json.loads(response_data.text)

        print(response_data)
        available_services = []

        available_service = {
            "service_provider": "Aramex",
            "id": "1111",
            "carrier": "aramex",
            "carrier_name": "aramex",
            "service_name": 'aramex',
            "is_preferred": 0,
            "real_weight": 0,
            "total_price": response_data['TotalAmount']['Value'],
            "price_info": response_data['TotalAmount'],
        }
        available_services.append(available_service)
        return available_services
    except Exception:
        print(Exception)
