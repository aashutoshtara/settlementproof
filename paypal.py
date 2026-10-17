"""Read-only PayPal sandbox integration. No live host or money mutation endpoints."""
import base64
import json
import os
import re
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError

BASE = "https://api-m.sandbox.paypal.com"
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("PayPal redirect refused")

def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise ValueError("Invalid PayPal resource ID")
    return value

class SandboxClient:
    def __init__(self, client_id=None, secret=None, transport=None):
        self.client_id = client_id or os.getenv("PAYPAL_SANDBOX_CLIENT_ID")
        self.secret = secret or os.getenv("PAYPAL_SANDBOX_CLIENT_SECRET")
        self.token = None
        self.transport = transport or build_opener(NoRedirect()).open
        self.calls = []
    def request(self, path, oauth=False):
        if oauth:
            if not self.client_id or not self.secret:
                raise ValueError("Set PAYPAL_SANDBOX_CLIENT_ID and PAYPAL_SANDBOX_CLIENT_SECRET in the server environment.")
            authorization = "Basic " + base64.b64encode(f"{self.client_id}:{self.secret}".encode()).decode()
            request = Request(BASE + "/v1/oauth2/token", data=b"grant_type=client_credentials", headers={"Authorization": authorization, "Content-Type": "application/x-www-form-urlencoded"})
        else:
            if not self.token:
                self.token = self.request("/v1/oauth2/token", oauth=True)["access_token"]
            if not re.fullmatch(r"/v2/(checkout/orders|payments/captures|payments/refunds)/[A-Za-z0-9_-]+", path):
                raise ValueError("Only approved read endpoints are permitted")
            request = Request(BASE + path, headers={"Authorization": "Bearer " + self.token, "Accept": "application/json"})
        try:
            with self.transport(request, timeout=20) as response:
                result = json.load(response)
                if not oauth:
                    self.calls.append({"method": "GET", "path": path, "status": response.status})
                return result
        except HTTPError as exc:
            # Never return upstream bodies, tokens or Authorization headers to browser/logs.
            raise ValueError(f"PayPal sandbox returned HTTP {exc.code}; verify access and resource ID.") from None
    def order_bundle(self, order_id, expected_capture, expected_refund="0.00", currency="USD", refund_ids=None):
        order_id = identifier(order_id)
        order = self.request("/v2/checkout/orders/" + order_id)
        resources, capture_ids, known_refunds = [], set(), set(refund_ids or [])
        for unit in order.get("purchase_units", []):
            for capture in unit.get("payments", {}).get("captures", []):
                capture_ids.add(identifier(capture["id"]))
            for refund in unit.get("payments", {}).get("refunds", []):
                known_refunds.add(identifier(refund["id"]))
        for capture_id in sorted(capture_ids):
            capture = self.request("/v2/payments/captures/" + capture_id)
            resources.append(self.normalize(capture, "capture", order_id))
        for refund_id in sorted(known_refunds):
            refund = self.request("/v2/payments/refunds/" + identifier(refund_id))
            # The refund up link is the authoritative parent capture reference.
            parent = next((link["href"].rsplit("/", 1)[-1] for link in refund.get("links", []) if link.get("rel") == "up" and "/v2/payments/captures/" in link.get("href", "")), None)
            if parent not in capture_ids:
                raise ValueError("Refund does not link to a capture in this order")
            resources.append({**self.normalize(refund, "refund", order_id), "capture_id": parent})
        return {"source": "paypal_sandbox_api", "invoices": [{"id": "MERCHANT-" + order_id, "order_id": order_id, "label": "Sandbox order / supplied merchant expectation", "currency": currency, "expected_capture": expected_capture, "expected_refund": expected_refund}], "resources": resources, "events": [], "api_evidence": self.calls,
                "coverage_note": "Explicit order and refund IDs only. Not a complete account export; unlisted refunds may be absent. No webhook deliveries imported."}
    @staticmethod
    def normalize(resource, kind, order_id):
        return {"id": resource["id"], "kind": kind, "order_id": order_id, "amount": resource["amount"]["value"], "currency": resource["amount"]["currency_code"], "status": resource["status"]}
