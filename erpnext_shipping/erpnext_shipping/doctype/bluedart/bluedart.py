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

        self.auth = {
            "Api_type": "S",
            "Area": "ALL",
            "IsAdmin": "",
            "LicenceKey": self.config["license_key"],
            "LoginID": self.config["login_id"],
            "Password": "",
            "Version": "Ver1.10",
        }

    def create_shipment(
        self,
        shipment,
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
            shipment,
            pickup_address,
            pickup_contact,
            delivery_address,
            delivery_contact,
            shipment_parcel,
            description_of_content,
            value_of_goods,
            delivery_company_name,
        )

        print("payload---------------")
        print(payload)

        return {
            "shipment_id": "",
            "carrier": "Bluedart",
            "carrier_service": "",
            "shipment_label": "",
            "awb_number": "",
        }

        try:
            client = zeep.Client(wsdl=WAYBILLGENERATIONTEST)
            response = client.service.GenerateWayBill(payload, self.auth)
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
        shipment,
        pickup_address,
        pickup_contact,
        delivery_address,
        delivery_contact,
        shipment_parcel,
        description_of_content,
        value_of_goods,
        delivery_company_name,
    ):
        shipment_parcel = json.loads(shipment_parcel)
        shipment = json.loads(shipment)
        suborders = []
        weight = 0

        print("------------------------")
        print(shipment)
        print(pickup_address)
        print(pickup_contact)
        print(delivery_address)
        print(delivery_contact)
        print(shipment_parcel)
        print(description_of_content)
        print(value_of_goods)
        print(delivery_company_name)
        print("------------------------")
        for parcel in shipment_parcel:
            suborders.append(
                {
                    "Breadth": parcel["width"],
                    "Count": parcel["count"],
                    "Height": parcel["height"],
                    "Length": parcel["length"],
                }
            )
            weight += parcel["weight"]
        payload = {
            "Consignee": {
                "ConsigneeAddress1": delivery_address["address_line1"],
                "ConsigneeAddress2": delivery_address["address_line2"],
                "ConsigneeAddress3": "",
                "ConsigneeAttention": delivery_contact["first_name"],
                "ConsigneeCountryCode": "IN",
                "ConsigneeEmailID": delivery_contact["email_id"],
                "ConsigneeMobile": delivery_contact["mobile_no"],
                "ConsigneeName": delivery_address["address_title"],
                "ConsigneePincode": delivery_address["pincode"],
                "ConsigneeStateCode": "",
                "ConsigneeTelephone": delivery_contact["phone"],
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
                "CreditReferenceNo": shipment["name"],
                "CurrencyCode": "INR",
                "DeclaredValue": value_of_goods,
                "Dimensions": suborders,
                "InvoiceNo": "",
                "IsDedicatedDeliveryNetwork": False,
                "IsForcePickup": False,
                "IsPartialPickup": False,
                "IsReversePickup": False,
                "ItemCount": 1,
                "PackType": "",
                "PickupDate": shipment["pickup_date"],
                "PickupMode": "P",
                "PickupTime": int(shipment["pickup_to"].replace(":", "")[0:4]),
                "PickupType": "",
                "PieceCount": 1,
                "ProductCode": "D",
                "ProductType": "Dutiables",
                "RegisterPickup": True,
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
                "CustomerAddress1": pickup_address["address_line1"],
                "CustomerAddress2": pickup_address["address_line2"],
                "CustomerAddress3": "",
                "CustomerCode": 940111,
                "CustomerEmailID": pickup_contact["email"],
                "CustomerGSTNumber": "27XXJ64909L1Z4",
                "CustomerMobile": pickup_contact["mobile_no"],
                "CustomerName": pickup_address["address_title"],
                "CustomerPincode": pickup_address["pincode"],
                "CustomerTelephone": pickup_contact["phone"],
                "IsToPayCustomer": False,
                "OriginArea": "GGN",
                "Sender": "Nona Lifestyle",
                "VendorCode": 940111,
            },
        }
        return payload
