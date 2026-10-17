"""Reconcile merchant expectations with provider snapshots and delivery evidence.

Provider resource IDs are the accounting identity; webhook delivery IDs are not.
Refunds may arrive before captures. Conflicting resource snapshots are quarantined.
"""
import hashlib
import json
from money import minor, display

def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def reconcile(bundle):
    cases, totals = [], {}
    invoices = bundle.get("invoices", [])
    if len({i["id"] for i in invoices}) != len(invoices):
        raise ValueError("Duplicate invoice IDs")
    if len({i["order_id"] for i in invoices}) != len(invoices):
        raise ValueError("Each order must have one merchant expectation")
    resources = {}
    resource_variants = {}
    conflicts = set()
    conflict_resource_orders = {}
    for r in bundle.get("resources", []):
        if r["kind"] not in ("capture", "refund"):
            raise ValueError("Unsupported resource kind")
        minor(r["amount"], r["currency"])
        key = (r["kind"], r["id"])
        versions = resource_variants.setdefault(key, [])
        if r not in versions:
            versions.append(r)
        if key in resources and resources[key] != r:
            conflicts.add(key)
            conflict_resource_orders.setdefault(key, set()).update((r['order_id'], resources[key]['order_id']))
        else:
            resources[key] = r
    events, replay_orders, conflict_orders = {}, {}, set()
    for e in bundle.get("events", []):
        event_key = e["id"]
        if event_key in events:
            if events[event_key] != e:
                conflict_orders.add(e["order_id"])
                conflict_orders.add(events[event_key]["order_id"])
            else:
                replay_orders[e["order_id"]] = replay_orders.get(e["order_id"], 0) + 1
        else:
            events[event_key] = e
    for invoice in invoices:
        currency = invoice["currency"]
        expected_capture = minor(invoice["expected_capture"], currency)
        expected_refund = minor(invoice.get("expected_refund", "0"), currency)
        if expected_refund > expected_capture:
            raise ValueError("Expected refund exceeds expected capture")
        attached = [r for versions in resource_variants.values() for r in versions if r["order_id"] == invoice["order_id"]]
        issues, evidence = [], []
        captured, refunded = 0, 0
        refund_groups = {}
        def issue(code, severity, text, action):
            issues.append({"code": code, "severity": severity, "message": text, "action": action})
        for key, implicated_orders in conflict_resource_orders.items():
            if invoice['order_id'] in implicated_orders:
                issue("CONFLICT", "high", f"{key[1]} has conflicting snapshots; excluded from totals.", "Retrieve the current resource from PayPal before closing this case.")
        for r in attached:
            evidence.append({**r, "fingerprint": fingerprint(r)[:16]})
            if (r["kind"], r["id"]) in conflicts:
                continue
            if r["currency"] != currency:
                issue("CURRENCY", "high", f"{r['id']} is denominated in {r['currency']}, expected {currency}; excluded.", "Check the merchant mapping. Never sum different currencies.")
                continue
            # A refunded capture remains original gross cash-in; refunds are separate cash-out.
            accepted = ("COMPLETED", "PARTIALLY_REFUNDED", "REFUNDED") if r["kind"] == "capture" else ("COMPLETED",)
            if r["status"] not in accepted:
                issue("PENDING", "medium", f"{r['id']} status is {r['status']}; no completed amount counted.", "Re-fetch the resource after its status settles.")
                continue
            if r["kind"] == "refund":
                parent = resources.get(("capture", r.get("capture_id")))
                if not parent or parent["order_id"] != invoice["order_id"] or parent["currency"] != currency or parent['status'] not in ('COMPLETED', 'PARTIALLY_REFUNDED', 'REFUNDED') or ("capture", parent["id"]) in conflicts:
                    issue("ORPHAN_REFUND", "high", f"Refund {r['id']} lacks a consistent parent capture; excluded.", "Retrieve and validate the parent capture.")
                    continue
                refund_groups.setdefault(parent['id'], []).append(r)
            else:
                captured += minor(r["amount"], currency)
        for capture_id, refund_records in refund_groups.items():
            refund_sum = sum(minor(r['amount'], currency) for r in refund_records)
            if refund_sum > minor(resources[('capture', capture_id)]['amount'], currency):
                issue("OVER_REFUND", "high", f"Refunds linked to {capture_id} exceed that capture; excluded from totals.", "Quarantine the linked refunds and re-fetch their parent capture.")
            else:
                refunded += refund_sum
        if captured != expected_capture:
            issue("CAPTURE_GAP", "high", f"Captured {currency} {display(captured, currency)} versus expected {display(expected_capture, currency)}.", "Match the order and capture IDs to the merchant invoice; investigate the difference.")
        if refunded != expected_refund:
            issue("REFUND_GAP", "high", f"Refunded {currency} {display(refunded, currency)} versus merchant records {display(expected_refund, currency)}.", "Review the completed refund evidence and propose a merchant-book adjustment.")
        if refunded > captured:
            issue("OVER_REFUND", "high", "Completed refunds exceed captured gross value.", "Quarantine this case and re-fetch all related resources.")
        replays = replay_orders.get(invoice["order_id"], 0)
        if replays:
            issue("REPLAY", "low", f"{replays} repeated webhook delivery record(s) ignored for accounting.", "Keep delivery evidence; use resource IDs as the accounting key.")
        if invoice["order_id"] in conflict_orders:
            issue("EVENT_CONFLICT", "high", "One webhook event ID has different payloads.", "Do not trust the deliveries; compare against authenticated API snapshots.")
        expected_net, net = expected_capture - expected_refund, captured - refunded
        case = {"invoice": invoice["id"], "order_id": invoice["order_id"], "label": invoice.get("label", invoice["id"]),
                "currency": currency, "expected_minor": expected_net, "actual_minor": net,
                "difference_minor": net - expected_net, "captured_minor": captured, "refunded_minor": refunded,
                "status": "review" if any(i["severity"] == "high" for i in issues) else "watch" if issues else "matched",
                "issues": issues, "evidence": evidence, "events": [e for e in events.values() if e["order_id"] == invoice["order_id"]],
                "replays": replays}
        cases.append(case)
        total = totals.setdefault(currency, {"expected_minor": 0, "actual_minor": 0, "difference_minor": 0})
        for k in total:
            total[k] += case[k]
    mapped = {i["order_id"] for i in invoices}
    unassigned = [r for r in resources.values() if r["order_id"] not in mapped]
    return {"source": bundle.get("source", "unknown"), "cases": cases, "totals": totals,
            "unassigned_resources": unassigned, "digest": fingerprint(bundle),
            "summary": {"orders": len(cases), "review": sum(c["status"] == "review" for c in cases),
                        "matched": sum(c["status"] == "matched" for c in cases), "replays": sum(replay_orders.values())}}
