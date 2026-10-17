"""Entirely invented merchant data. No customer information."""
from copy import deepcopy

def demo():
    invoices = [
        {"id": "INV-1001", "order_id": "ORDER-1001", "label": "Everyday tote / settled", "currency": "USD", "expected_capture": "120.00", "expected_refund": "0.00"},
        {"id": "INV-1002", "order_id": "ORDER-1002", "label": "Ceramic set / unbooked return", "currency": "USD", "expected_capture": "250.00", "expected_refund": "0.00"},
        {"id": "INV-1003", "order_id": "ORDER-1003", "label": "Desk lamp / repeated delivery", "currency": "USD", "expected_capture": "89.50", "expected_refund": "0.00"},
        {"id": "INV-1004", "order_id": "ORDER-1004", "label": "Linen throw / waiting for capture", "currency": "USD", "expected_capture": "175.00", "expected_refund": "0.00"},
        {"id": "INV-1005", "order_id": "ORDER-1005", "label": "Notebook / currency mismatch", "currency": "EUR", "expected_capture": "65.00", "expected_refund": "0.00"},
        {"id": "INV-1006", "order_id": "ORDER-1006", "label": "Gift bundle / partial return matched", "currency": "USD", "expected_capture": "100.00", "expected_refund": "25.00"}]
    resources = []
    for i, status in zip(invoices, ["COMPLETED", "PARTIALLY_REFUNDED", "COMPLETED", "PENDING", "COMPLETED", "PARTIALLY_REFUNDED"]):
        resources.append({"kind": "capture", "id": "CAP-" + i["id"].split("-")[1], "order_id": i["order_id"], "currency": "USD", "amount": i["expected_capture"], "status": status})
    for suffix, value in [("1002", "50.00"), ("1006", "25.00")]:
        resources.append({"kind": "refund", "id": "REF-" + suffix, "capture_id": "CAP-" + suffix, "order_id": "ORDER-" + suffix, "currency": "USD", "amount": value, "status": "COMPLETED"})
    events = [{"id": "EVT-" + r["id"], "order_id": r["order_id"], "resource_id": r["id"], "event_type": "PAYMENT.CAPTURE.REFUNDED" if r["kind"] == "refund" else "PAYMENT.CAPTURE." + ("PENDING" if r["status"] == "PENDING" else "COMPLETED")} for r in resources]
    events.append(deepcopy(events[2]))
    return {"source": "synthetic_demo", "invoices": invoices, "resources": resources, "events": events}
