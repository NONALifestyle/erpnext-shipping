# Copyright (c) 2023, Frappe and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
import requests
import zeep
import time
from frappe import _
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password
from erpnext_shipping.erpnext_shipping.utils import show_error_alert

BLUEDART_PROVIDER = "Bluedart"
WAYBILLGENERATIONTEST = "https://netconnect.bluedart.com/API-QA/Ver1.10/Demo/ShippingAPI/WayBill/WayBillGeneration.svc?wsdl"
WAYBILLGENERATION = "https://netconnect.bluedart.com/Ver1.10/ShippingAPI/WayBill/WayBillGeneration.svc?wsdl"


class Bluedart(Document):
    pass


class BluedartUtils:
    def __init__(self):
        self.enabled = frappe.db.get_single_value("Bluedart", "enabled")
        self.config = frappe.db.get_singles_dict("Bluedart")
        self.config["license_key"] = get_decrypted_password(
            "Bluedart", "Bluedart", "license_key", raise_exception=False
        )

        if not self.enabled:
            link = frappe.utils.get_link_to_form(
                "Bluedart", "Bluedart", frappe.bold("Bluedart Settings")
            )
            frappe.throw(
                _("Please enable Bluedart Integration in {0}".format(link)),
                title=_("Mandatory"),
            )

    def create_shipment(
        self,
        pickup_address,
        delivery_address,
        shipment_parcel,
        description_of_content,
        value_of_goods,
        pickup_contact,
        delivery_contact,
        delivery_company_name,
    ):
        payload = self.generate_create_shipment_payload(
            pickup_address,
            delivery_address,
            delivery_contact,
            shipment_parcel,
            description_of_content,
            value_of_goods,
            delivery_company_name,
        )

        auth = {
            "Api_type": "S",
            "Area": "ALL",
            "IsAdmin": "",
            "LicenceKey": "kh7mnhqkmgegoksipxr0urmqesesseup",
            "LoginID": "GG940111",
            "Password": "",
            "Version": "Ver1.10",
        }

        print(type(payload))

        try:
            client = zeep.Client(wsdl=WAYBILLGENERATIONTEST)
            print("client generated")
            response = client.service.GenerateWayBill(payload, auth)
            print("response received")
            print(response)

            awbno = response["AWBNo"]
            filedoc = frappe.get_doc(
                {
                    "doctype": "File",
                    "attached_to_doctype": "Shipment",
                    "attached_to_name": "SHIPMENT-00013",
                    "folder": "",
                    "file_name": f"{awbno}.pdf",
                    "file_url": "",
                    "is_private": 1,
                    "content": response["AWBPrintContent"],
                }
            ).save(ignore_permissions=True)
            print("file_doc generated")
            print(filedoc)
            # file = open(f"{awbno}.pdf", "wb")
            # file.write(response["AWBPrintContent"])
            # file.close()
        except Exception as e:
            frappe.throw(e)

        return {
            "shipment_id": response["AWBNo"],
            "carrier": "Bluedart",
            "carrier_service": "",
            "shipment_label": "",
            "awb_number": response["AWBNo"],
        }

    def generate_create_shipment_payload(
        self,
        pickup_address,
        delivery_address,
        delivery_contact,
        shipment_parcel,
        description_of_content,
        value_of_goods,
        delivery_company_name,
    ):
        shipment_parcel = json.loads(shipment_parcel)
        suborders = []
        weight = 0
        for parcel in shipment_parcel:
            suborders.append(
                {
                    "count": parcel["count"],
                    "description": description_of_content,
                }
            )
            weight += parcel["weight"]
        payload = {
            "Consignee": {
                "ConsigneeAddress1": "101, Building 1",
                "ConsigneeAddress2": "New Area",
                "ConsigneeAddress3": "Surat",
                "ConsigneeAttention": "MR Mustakim",
                "ConsigneeCountryCode": "IN",
                "ConsigneeEmailID": "xyz@gmail.com",
                "ConsigneeMobile": 1234567890,
                "ConsigneeName": "Mustakim",
                "ConsigneePincode": 395009,
                "ConsigneeStateCode": "",
                "ConsigneeTelephone": 12345678890,
            },
            "Services": {
                "AWBNo": "",
                "ActualWeight": 0.5,
                "CollectableAmount": 0,
                "Commodity": {
                    "CommodityDetail1": "Tshirt",
                    "CommodityDetail2": "Cotton Tshirt",
                    "CommodityDetail3": "cotton",
                },
                "CreditReferenceNo": "SSAX15",
                "CurrencyCode": "INR",
                "DeclaredValue": 1000,
                "Dimensions": {
                    "Dimension": {"Breadth": 12, "Count": 1, "Height": 36, "Length": 14}
                },
                "InvoiceNo": "",
                "IsDedicatedDeliveryNetwork": False,
                "IsForcePickup": False,
                "IsPartialPickup": False,
                "IsReversePickup": False,
                "ItemCount": 1,
                "PackType": "",
                "PickupDate": "2023-07-28T18:00:05+05:30",
                "PickupMode": "",
                "PickupTime": 1800,
                "PickupType": "",
                "PieceCount": 1,
                "ProductCode": "D",
                "ProductType": "Dutiables",
                "RegisterPickup": False,
                "SpecialInstruction": "API TESTING",
                "SubProductCode": "",
                "TotalCashPaytoCustomer": 0,
                "itemdtl": {
                    "ItemDetails": {
                        "CGSTAmount": 0,
                        "HSCode": 95059090,
                        "IGSTAmount": 0,
                        "Instruction": "",
                        "InvoiceDate": "2022-09-22T18:00:05+05:30",
                        "InvoiceNumber": 4823182,
                        "ItemID": 547919,
                        "ItemName": "Tshirt",
                        "ItemValue": 1000,
                        "Itemquantity": 1,
                        "PieceID": 1,
                        "ProductDesc1": "Others",
                        "SGSTAmount": 10,
                        "SKUNumber": 547919,
                        "SellerGSTNNumber": "27SAACBX446L1Z5",
                        "SellerName": "Nona Lifestyle",
                        "SubProduct1": "",
                        "TaxableAmount": 10,
                        "TotalValue": 1000,
                        "countryOfOrigin": "in",
                        "docType": "niv",
                        "eWaybillDate": "2022-09-22T18:00:05+05:30",
                        "eWaybillNumber": 123456789013,
                    }
                },
            },
            "Shipper": {
                "CustomerAddress1": "Plot no. E-195(A), 2nd Floor,",
                "CustomerAddress2": "RIICO Industrial Area",
                "CustomerAddress3": "Mansarovar",
                "CustomerCode": 940111,
                "CustomerEmailID": "avch@gmail.com",
                "CustomerGSTNumber": "27XXJ64909L1Z4",
                "CustomerMobile": 1234567890,
                "CustomerName": "Nona Lifestyle",
                "CustomerPincode": 122001,
                "CustomerTelephone": 1234567890,
                "IsToPayCustomer": False,
                "OriginArea": "GGN",
                "Sender": "Nona Lifestyle",
                "VendorCode": 940111,
            },
        }
        return payload
