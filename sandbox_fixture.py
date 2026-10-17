"""Isolated fake-money sandbox fixture setup, never imported by the app.

Creates exactly one USD100 order, captures it after browser buyer approval,
and refunds exactly USD25. The API origin cannot be configured.
"""
import argparse
import base64
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener
from paypal import BASE, NoRedirect, identifier

DEFAULT_STATE = Path(__file__).parent / "data/sandbox-setup.json"
ALLOWED = {
    "POST": [r"/v1/oauth2/token", r"/v2/checkout/orders", r"/v2/checkout/orders/[A-Za-z0-9_-]+/capture", r"/v2/payments/captures/[A-Za-z0-9_-]+/refund"],
    "GET": [r"/v2/checkout/orders/[A-Za-z0-9_-]+", r"/v2/payments/captures/[A-Za-z0-9_-]+", r"/v2/payments/refunds/[A-Za-z0-9_-]+"],
}

def load_credentials(config=None):
    values = {}
    if config:
        path = Path(config)
        if path.stat().st_mode & 0o077:
            raise ValueError("Credential config must be private (chmod 600).")
        values = json.loads(path.read_text())
        if not isinstance(values, dict):
            raise ValueError("Credential config must be a JSON object.")
    client_id = os.getenv("PAYPAL_SANDBOX_CLIENT_ID") or values.get("PAYPAL_SANDBOX_CLIENT_ID") or values.get("client_id")
    secret = os.getenv("PAYPAL_SANDBOX_CLIENT_SECRET") or values.get("PAYPAL_SANDBOX_CLIENT_SECRET") or values.get("client_secret") or values.get("secret")
    if not isinstance(client_id, str) or not isinstance(secret, str) or not client_id or not secret:
        raise ValueError("Sandbox client ID and secret must be configured locally.")
    return client_id, secret

class FixtureClient:
    def __init__(self, client_id, secret, transport=None):
        self.client_id, self.secret, self.token = client_id, secret, None
        self.transport = transport or build_opener(NoRedirect()).open
    def request(self, method, path, body=None, request_id=None):
        if method not in ALLOWED or not any(re.fullmatch(pattern, path) for pattern in ALLOWED[method]):
            raise ValueError("Sandbox endpoint or method not allowed.")
        oauth = path == "/v1/oauth2/token"
        if oauth:
            data = b"grant_type=client_credentials"
            auth = "Basic " + base64.b64encode(f"{self.client_id}:{self.secret}".encode()).decode()
            headers = {"Authorization": auth, "Content-Type": "application/x-www-form-urlencoded"}
        else:
            if method == "POST" and (not request_id or not re.fullmatch(r"[a-f0-9-]{36}", request_id)):
                raise ValueError("A persisted UUID idempotency key is required.")
            if not self.token:
                self.token = self.request("POST", "/v1/oauth2/token")["access_token"]
            headers = {"Authorization": "Bearer " + self.token, "Content-Type": "application/json", "Prefer": "return=representation"}
            if request_id:
                headers["PayPal-Request-Id"] = request_id
            data = json.dumps(body or {}).encode() if method == "POST" else None
        req = Request(BASE + path, data=data, headers=headers, method=method)
        try:
            with self.transport(req, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            raise ValueError(f"PayPal sandbox returned HTTP {exc.code}. Request ID retained; do not delete state or create a replacement blindly.") from None
        except (TimeoutError, OSError):
            raise ValueError("Sandbox request interrupted. Outcome may be unknown; request ID retained for safe retry.") from None

def save_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            json.dump(state, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise

@contextmanager
def state_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path) + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield

def approval_url(response):
    for link in response.get("links", []):
        if link.get("rel") not in ("approve", "payer-action"):
            continue
        url = link.get("href", "")
        parts = urlsplit(url)
        if parts.scheme == "https" and parts.hostname in ("www.sandbox.paypal.com", "sandbox.paypal.com") and not parts.username and not parts.password and parts.port in (None, 443):
            return url
    return None

def clean_status(response):
    status = response.get("status", "UNKNOWN")
    return status if isinstance(status, str) and re.fullmatch(r"[A-Z_]{1,40}", status) else "UNKNOWN"

class FixtureSetup:
    def __init__(self, client, state_path=DEFAULT_STATE):
        self.client, self.path = client, Path(state_path)
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {"environment": "sandbox", "amount": "100.00", "refund_amount": "25.00", "currency": "USD", "operations": {}}
        if any(self.state.get(k) != v for k,v in {"environment":"sandbox","amount":"100.00","refund_amount":"25.00","currency":"USD"}.items()):
            raise ValueError("State is not the fixed USD100/USD25 sandbox fixture.")
    def persist(self):
        save_state(self.path, self.state)
    def key(self, operation):
        record = self.state["operations"].get(operation)
        if record is None:
            record = {"request_id":str(uuid.uuid4()), "first_attempt":time.time()}
            self.state["operations"][operation] = record
            self.persist()  # Must precede the network request.
        elif time.time() - record["first_attempt"] > 5*3600:
            raise ValueError("Unresolved request is older than five hours. Inspect existing sandbox resources before any retry; do not reset state blindly.")
        return record["request_id"]
    def summary(self):
        allowed = ("environment", "order_id", "order_status", "capture_id", "capture_status", "refund_id", "refund_status", "approval_url")
        return {k:self.state[k] for k in allowed if k in self.state}
    def create(self):
        if self.state.get("order_id"):
            return self.summary()
        key = self.key("create")
        body = {"intent":"CAPTURE", "purchase_units":[{"reference_id":"settlementproof-sandbox", "description":"SettlementProof fictional sandbox fixture", "amount":{"currency_code":"USD","value":"100.00"}}],
                "payment_source":{"paypal":{"experience_context":{"shipping_preference":"NO_SHIPPING", "user_action":"PAY_NOW", "return_url":"http://127.0.0.1:8766/paypal-return", "cancel_url":"http://127.0.0.1:8766/paypal-cancel"}}}}
        response = self.client.request("POST", "/v2/checkout/orders", body, key)
        self.state.update(order_id=identifier(response["id"]), order_status=clean_status(response))
        url = approval_url(response)
        if url:
            self.state["approval_url"] = url
        self.persist()
        return self.summary()
    def capture(self):
        if self.state.get("capture_id"):
            return self.summary()
        if not self.state.get("order_id"):
            raise ValueError("Create the fixed sandbox order first.")
        order_id = identifier(self.state["order_id"])
        order = self.client.request("GET", "/v2/checkout/orders/" + order_id)
        units = order.get("purchase_units", [])
        if len(units) != 1 or units[0].get("amount") != {"currency_code":"USD","value":"100.00"} or order.get("intent") != "CAPTURE":
            raise ValueError("Order is not the expected USD100 CAPTURE sandbox fixture.")
        if order.get("status") not in ("APPROVED", "COMPLETED"):
            raise ValueError("Sandbox buyer approval is required before capture.")
        if order.get("status") == "COMPLETED":
            captures = [c for unit in units for c in unit.get("payments",{}).get("captures",[])]
            if len(captures) != 1:
                raise ValueError("Completed order lacks one identifiable capture; inspect existing sandbox resources.")
            self.state.update(order_status="COMPLETED", capture_id=identifier(captures[0]["id"]), capture_status=clean_status(captures[0]))
            self.persist()
            return self.summary()
        response = self.client.request("POST", "/v2/checkout/orders/" + order_id + "/capture", {}, self.key("capture"))
        captures = [c for unit in response.get("purchase_units",[]) for c in unit.get("payments",{}).get("captures",[])]
        if len(captures) != 1:
            raise ValueError("Expected exactly one sandbox capture. Inspect the existing order; request ID retained.")
        capture = captures[0]
        self.state.update(order_status=clean_status(response), capture_id=identifier(capture["id"]), capture_status=clean_status(capture))
        self.persist()
        return self.summary()
    def refund(self):
        if self.state.get("refund_id"):
            return self.summary()
        if not self.state.get("capture_id"):
            raise ValueError("Capture the approved sandbox order first.")
        capture_id = identifier(self.state["capture_id"])
        capture = self.client.request("GET", "/v2/payments/captures/" + capture_id)
        accepted = ("COMPLETED", "PARTIALLY_REFUNDED") if "refund" in self.state['operations'] else ("COMPLETED",)
        if capture.get("amount") != {"currency_code":"USD","value":"100.00"} or capture.get("status") not in accepted:
            raise ValueError("Capture is not the expected completed USD100 sandbox fixture.")
        response = self.client.request("POST", "/v2/payments/captures/" + capture_id + "/refund", {"amount":{"currency_code":"USD","value":"25.00"}}, self.key("refund"))
        self.state.update(refund_id=identifier(response["id"]), refund_status=clean_status(response))
        self.persist()
        return self.summary()
    def show(self):
        for kind, path in (("order","/v2/checkout/orders/"),("capture","/v2/payments/captures/"),("refund","/v2/payments/refunds/")):
            if self.state.get(kind+"_id"):
                response = self.client.request("GET", path + identifier(self.state[kind+"_id"]))
                self.state[kind+"_status"] = clean_status(response)
        self.persist()
        return self.summary()

def main(argv=None):
    parser = argparse.ArgumentParser(description="Fixed fake-money PayPal sandbox fixture. No live host supported.")
    parser.add_argument("command", choices=("create","capture","refund","show"))
    parser.add_argument("--config", help="Private local JSON credentials; never printed")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args(argv)
    try:
        client = FixtureClient(*load_credentials(args.config))
        with state_lock(args.state):
            setup = FixtureSetup(client, args.state)
            print(json.dumps(getattr(setup, args.command)(), indent=2))
        return 0
    except ValueError as exc:
        print(json.dumps({"environment":"sandbox", "error":str(exc)}))
        return 1
    except Exception:
        print(json.dumps({"environment":"sandbox", "error":"Fixture setup failed. Inspect local configuration and existing sandbox state; credentials and provider responses are not logged."}))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
