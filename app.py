"""Local-only demo server, standard library only. Start: python3 app.py"""
import argparse
import json
import os
from pathlib import Path
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from assistant import investigate
from fixtures import demo
from ledger import reconcile
from paypal import SandboxClient

ROOT = Path(__file__).parent
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()
BUNDLE = demo()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    def send(self, value, status=200, mime="application/json"):
        payload = json.dumps(value).encode() if mime == "application/json" else value
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)
    def allowed(self):
        return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")
    def do_GET(self):
        if not self.allowed():
            return self.send({"error": "Host not allowed"}, 403)
        callback_path = urlsplit(self.path).path
        if callback_path in ("/paypal-return", "/paypal-cancel"):
            # Never parse, reflect, persist, or log payer/token query parameters.
            message = "Sandbox browser return received. Approval is not proof of capture. Use the separate sandbox fixture utility to verify and capture the approved test order." if callback_path == "/paypal-return" else "Sandbox checkout cancelled. No capture was triggered by this page."
            return self.send(("<!doctype html><html lang='en'><meta charset='utf-8'><title>SettlementProof sandbox</title><link rel='stylesheet' href='/style.css'><body><main><h1>Sandbox checkout</h1><p>" + message + "</p><a href='/'>Return to SettlementProof</a></main></body></html>").encode(), mime="text/html; charset=utf-8")
        if self.path == "/":
            return self.send((ROOT / "static/index.html").read_bytes().replace(b"CSRF_TOKEN", TOKEN.encode()), mime="text/html; charset=utf-8")
        if self.path in ("/style.css", "/main.js"):
            return self.send((ROOT / "static" / self.path[1:]).read_bytes(), mime="text/css" if self.path.endswith("css") else "text/javascript")
        if self.path in ("/api/report", "/api/export"):
            with LOCK:
                report = reconcile(BUNDLE)
                report["api_evidence"] = BUNDLE.get("api_evidence", [])
                report["coverage_note"] = BUNDLE.get("coverage_note", "Invented demo fixtures; no real merchant data.")
            report["sandbox_configured"] = bool(os.getenv("PAYPAL_SANDBOX_CLIENT_ID") and os.getenv("PAYPAL_SANDBOX_CLIENT_SECRET"))
            return self.send(report)
        return self.send({"error": "Not found"}, 404)
    def do_POST(self):
        global BUNDLE
        if not self.allowed() or not secrets.compare_digest(self.headers.get("X-SettlementProof-Token", ""), TOKEN):
            return self.send({"error": "Local request token required"}, 403)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 10000:
                raise ValueError("Request body must be 1-10000 bytes")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("Expected a JSON object")
            if self.path == "/api/investigate":
                query = body.get("query", "")
                if not isinstance(query, str) or len(query) > 500:
                    raise ValueError("Question must be text up to 500 characters")
                with LOCK:
                    return self.send(investigate(query, reconcile(BUNDLE)))
            if self.path == "/api/reset":
                with LOCK:
                    BUNDLE = demo()
                return self.send({"ok": True})
            if self.path == "/api/sandbox":
                # Validate merchant values before any network call.
                from money import minor
                currency = body.get("currency", "USD")
                captured, refunded = body.get("expected_capture", "0.00"), body.get("expected_refund", "0.00")
                if minor(refunded, currency) > minor(captured, currency):
                    raise ValueError("Expected refund exceeds capture")
                refund_ids = body.get("refund_ids", [])
                if not isinstance(refund_ids, list) or len(refund_ids) > 20:
                    raise ValueError("Supply at most 20 refund IDs")
                bundle = SandboxClient().order_bundle(body.get("order_id"), captured, refunded, currency, refund_ids)
                reconcile(bundle)
                with LOCK:
                    BUNDLE = bundle
                return self.send({"ok": True, "source": bundle["source"], "api_evidence": bundle["api_evidence"]})
            return self.send({"error": "Not found"}, 404)
        except (ValueError, KeyError, TypeError) as exc:
            return self.send({"error": str(exc)}, 400)
        except Exception:
            return self.send({"error": "Sandbox connection unavailable. Check connectivity and server configuration."}, 502)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"SettlementProof: http://127.0.0.1:{args.port} - local synthetic demo; no payments executed", flush=True)
    server.serve_forever()
