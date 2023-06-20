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

DELHIVERY_PROVIDER = "Delhivery"
GENERATE_TOKEN_URL = "https://btob-api-dev.delhivery.com/ums/login/"
CREATE_SHIPMENTS_URL = "https://btob-api-dev.delhivery.com/v3/manifest"
GET_SHIPMENT_URL = "https://btob-api-dev.delhivery.com/v3/manifest?job_id="
PRINT_LABEL_URL = "https://btob-api-dev.delhivery.com/v3/get-label-urls/a4"
TRACK_SHIPMENTS_URL = "https://btob-api-dev.delhivery.com/v3/track/"


class Delhivery(Document):
    pass


class DelhiveryUtils:
    def __init__(self):
        self.enabled = frappe.db.get_single_value("Delhivery", "enabled")
        self.config = frappe.db.get_singles_dict("Delhivery")
        self.config["password"] = get_decrypted_password(
            "Delhivery", "Delhivery", "password", raise_exception=False
        )

        if not self.enabled:
            link = frappe.utils.get_link_to_form(
                "Delhivery", "Delhivery", frappe.bold("Delhivery Settings")
            )
            frappe.throw(
                _("Please enable Delhivery Integration in {0}".format(link)),
                title=_("Mandatory"),
            )

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
        count = 0

        while count < 3:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.config['token']}",
                }
                response = requests.post(
                    url=CREATE_SHIPMENTS_URL, headers=headers, data=json.dumps(payload)
                )
                if response.status_code == 200:
                    break
                if response.status_code == 401:
                    print("Token Expired", count)
                    self.generate_token()
                    count += 1
                    continue
            except Exception as e:
                frappe.throw(e)

        response_data = json.loads(response.text)
        print("esponse_data--------- create manifest")
        print(response_data)
        time.sleep(2)

        shipment = self.get_shipment(response_data["job_id"])

        print("shipment-----response in create---- create manifest")
        print(shipment)

        shipment_value = shipment["status"]["value"]

        return {
            "shipment_id": response_data["job_id"],
            "carrier": "Delhivery",
            "carrier_service": "",
            "shipment_label": "",
            "awb_number": shipment_value["lrnum"],
        }

    def get_label(self, awb_number):
        # Retrieve shipment label from Delhivery
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config['token']}",
        }
        count = 0
        while count < 3:
            try:
                response = requests.get(
                    url=f"{PRINT_LABEL_URL}/{220042522}?document=true", headers=headers
                )
                if response.status_code == 200:
                    break
                elif response.status_code == 401:
                    self.generate_token()
                    count += 1
                    continue
                else:
                    response.raise_for_status()
            except Exception as e:
                frappe.throw(e)
        shipment_label = json.loads(response.text)

        return shipment_label["data"]

    def get_tracking_data(self, awb_number):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config['token']}",
        }
        count = 0
        while count < 3:
            try:
                response = requests.get(
                    url=f"{TRACK_SHIPMENTS_URL}{awb_number}", headers=headers
                )
                if response.status_code == 200:
                    break
                elif response.status_code == 401:
                    self.generate_token()
                    count += 1
                    continue
                else:
                    response.raise_for_status()
            except Exception as e:
                frappe.throw(e)
        tracking_data = json.loads(response.text)
        return {
            "tracking_status": tracking_data["data"]["status"],
            "tracking_url": "",
        }

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
            "ident": "",
            "pickup_location": "New Test NONA",
            "dropoff_location": {
                "consignee": "PT-GANDHI ROAD-KANCHIPURAM",
                "address": "Pantaloons, Mogili House,66-68, Gandhi Road",
                "city": "KANCHIPURAM",
                "region": "TAMIL NADU",
                "zip": "110011",
                "phone": "733136233",
            },
            "return_address": {
                "address": "738 Udhay nagar",
                "zip": "201301",
                "name": "shopper stop",
                "city": "gurgaon",
                "region": "haryana",
                "phone": "8383838383",
            },
            "d_mode": "Prepaid",
            "amount": 0.0,
            "rov_insurance": True,
            "invoices": [{"ident": "TEST1", "n_value": 10478, "ewaybill": ""}],
            "weight": 73600.0,
            "suborders": [
                {"ident": "", "count": 1, "description": "Box1"},
                {"ident": "", "count": 1, "description": "Box2"},
                {"ident": "", "count": 1, "description": "Box3"},
                {"ident": "", "count": 1, "description": "Box4"},
                {"ident": "", "count": 1, "description": "Box5"},
            ],
            "dimensions": [{"length": 5.0, "width": 5.0, "height": 5.0, "count": 5}],
            "consignee_gst_tin": "",
            "seller_gst_tin": "",
        }
        return payload

    def get_shipment(self, job_id):
        count = 0
        while count < 3:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.config['token']}",
                }
                response = requests.get(
                    url=f"{GET_SHIPMENT_URL}{job_id}", headers=headers
                )
                if response.status_code == 200:
                    response_data = json.loads(response.text)
                    if not response_data["status"]["type"] == "Complete":
                        time.sleep(1)
                        continue
                    else:
                        break
                if response.status_code == 401:
                    print("Token Expired", count)
                    self.generate_token()
                    count += 1
                    continue
                else:
                    response.raise_for_status()
            except Exception as e:
                frappe.throw(e)

        print("get shipment  response_data==============")
        print(response_data)
        return response_data

    def generate_token(self):
        print("in generate_toke-----")
        print(self)
        print(vars(self))
        try:
            print("in try-----")
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = {
                "username": self.config["user_name"],
                "password": self.config["password"],
            }
            response = requests.post(
                url=GENERATE_TOKEN_URL, headers=headers, data=json.dumps(payload)
            )
            response_data = json.loads(response.text)
            self.config["token"] = response_data["jwt"]
            frappe.db.set_value("Delhivery", "Delhivery", "token", response_data["jwt"])

        except Exception as e:
            print(e)
