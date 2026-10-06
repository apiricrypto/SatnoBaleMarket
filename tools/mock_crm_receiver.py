import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.getenv("MOCK_CRM_HOST", "127.0.0.1")
PORT = int(os.getenv("MOCK_CRM_PORT", "8099"))
PATH = os.getenv("MOCK_CRM_PATH", "/functions/v1/ingest_leads")
TOKEN = (os.getenv("SATNO_BALE_MARKET_INGEST_TOKEN") or "").strip()

ALLOWED = {
    "source_record_id", "source_url", "title", "organization_name", "contact_name",
    "contact_phone", "contact_email", "province", "city", "description",
    "estimated_amount", "estimated_currency", "deadline", "priority", "raw_payload",
    "captured_at",
}
_records = {}
_next_id = 1000


def _response(handler, status, body):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _validate(body):
    if not isinstance(body, dict):
        return "body must be object"
    unknown = set(body) - ALLOWED
    if unknown:
        return "unknown field: " + sorted(unknown)[0]
    for key in ("source_record_id", "title", "captured_at"):
        if not isinstance(body.get(key), str) or not body[key].strip():
            return key + " is required"
    if not isinstance(body.get("raw_payload"), dict):
        return "raw_payload must be object"
    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_POST(self):
        global _next_id
        request_id = "mock-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        if self.path != PATH:
            return _response(self, 404, {"error": "Not Found", "request_id": request_id})
        if self.headers.get("x-satno-connector") != "bale_market":
            return _response(self, 401, {"error": "Unauthorized", "request_id": request_id})
        auth = self.headers.get("Authorization") or ""
        if not TOKEN or auth != "Bearer " + TOKEN:
            return _response(self, 401, {"error": "Unauthorized", "request_id": request_id})
        if (self.headers.get("Content-Type") or "").split(";", 1)[0].lower() != "application/json":
            return _response(self, 415, {"error": "Content-Type must be application/json", "request_id": request_id})
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        if length > 128 * 1024:
            return _response(self, 413, {"error": "Request body is too large", "request_id": request_id})
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return _response(self, 400, {"error": "Body is not valid JSON", "request_id": request_id})
        error = _validate(body)
        if error:
            return _response(self, 400, {"error": error, "request_id": request_id})

        source_record_id = body["source_record_id"].strip()
        duplicate = source_record_id in _records
        if duplicate:
            record = _records[source_record_id]
        else:
            record = {
                "id": _next_id,
                "source": "bale_market",
                "source_record_id": source_record_id,
                "status": "new",
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            _records[source_record_id] = record
            _next_id += 1
        _response(
            self,
            200 if duplicate else 201,
            {"data": record, "duplicate": duplicate, "request_id": request_id},
        )


if __name__ == "__main__":
    if len(TOKEN) < 32:
        raise SystemExit("Set SATNO_BALE_MARKET_INGEST_TOKEN to a synthetic token of at least 32 characters.")
    print(f"Mock SATNO CRM receiver: http://{HOST}:{PORT}{PATH}")
    print("No token or payload content is logged.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
