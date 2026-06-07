import http.server
import json
import sqlite3
import uuid
import urllib.parse
from datetime import datetime, timedelta

PORT = 8000
DB_FILE = "licenses.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            license_key TEXT PRIMARY KEY,
            email TEXT,
            provider TEXT,
            plan_type TEXT,
            status TEXT,
            created_at TEXT,
            expires_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

class LicenseHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to log cleanly
        print(f"[*] [Server] {format % args}")

    def send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path == '/licenses':
            # Admin route to inspect licenses
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT * FROM licenses")
            rows = c.fetchall()
            conn.close()
            
            licenses = []
            for r in rows:
                licenses.append({
                    "license_key": r[0],
                    "email": r[1],
                    "provider": r[2],
                    "plan_type": r[3],
                    "status": r[4],
                    "created_at": r[5],
                    "expires_at": r[6]
                })
            self.send_json(200, {"licenses": licenses})
        else:
            self.send_json(404, {"error": "Not Found"})

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_json(400, {"error": "Invalid JSON"})
            return

        if parsed_path.path == '/validate':
            self.handle_validate(data)
        elif parsed_path.path == '/webhooks/paypal':
            self.handle_paypal_webhook(data)
        elif parsed_path.path == '/webhooks/github':
            self.handle_github_webhook(data)
        else:
            self.send_json(404, {"error": "Not Found"})

    def handle_validate(self, data):
        license_key = data.get("license_key")
        if not license_key:
            self.send_json(400, {"error": "license_key is required"})
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT email, plan_type, status, expires_at FROM licenses WHERE license_key = ?", (license_key,))
        row = c.fetchone()
        conn.close()

        if not row:
            self.send_json(403, {"status": "inactive", "reason": "License key not found"})
            return

        email, plan_type, status, expires_at_str = row
        
        # Check if license is active
        if status != "active":
            self.send_json(403, {"status": "inactive", "reason": f"License is {status}"})
            return

        # Check expiration
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.now() > expires_at:
                self.send_json(403, {"status": "inactive", "reason": "License expired"})
                return

        self.send_json(200, {
            "status": "active",
            "email": email,
            "plan_type": plan_type,
            "expires_at": expires_at_str
        })

    def handle_paypal_webhook(self, data):
        # Handle PayPal subscription webhooks
        event_type = data.get("event_type")
        resource = data.get("resource", {})
        
        print(f"[+] [PayPal Webhook] Received event: {event_type}")
        
        if event_type == "BILLING.SUBSCRIPTION.CREATED" or event_type == "PAYMENT.SALE.COMPLETED":
            # For a subscription, we extract the subscriber's email
            # In sandbox/mock, we get it from data
            email = data.get("email") or resource.get("subscriber", {}).get("email_address") or "cyrussifa@gmail.com"
            plan_type = data.get("plan_type") or "Developer Lite"
            
            # Generate a new license key
            new_key = f"SH-PAYPAL-{uuid.uuid4().hex[:16].upper()}"
            created_at = datetime.now().isoformat()
            expires_at = (datetime.now() + timedelta(days=30)).isoformat() # 30-day monthly cycle
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute(
                "INSERT INTO licenses VALUES (?, ?, ?, ?, ?, ?, ?)",
                (new_key, email, "paypal", plan_type, "active", created_at, expires_at)
            )
            conn.commit()
            conn.close()
            
            print(f"[+] [PayPal] Generated license {new_key} for {email}")
            self.send_json(200, {"status": "success", "license_key": new_key})
        else:
            self.send_json(200, {"status": "ignored"})

    def handle_github_webhook(self, data):
        # Handle GitHub Marketplace Purchase webhook
        action = data.get("action")
        marketplace_purchase = data.get("marketplace_purchase", {})
        
        print(f"[+] [GitHub Webhook] Received action: {action}")
        
        if action in ["purchased", "changed"]:
            account = marketplace_purchase.get("account", {})
            username = account.get("login", "github_user")
            email = account.get("email") or f"{username}@github.com"
            plan = marketplace_purchase.get("plan", {})
            plan_name = plan.get("name", "Developer Lite")
            
            new_key = f"SH-GITHUB-{uuid.uuid4().hex[:16].upper()}"
            created_at = datetime.now().isoformat()
            expires_at = (datetime.now() + timedelta(days=365)).isoformat() # Github plans can be yearly/monthly; default to 1 year
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute(
                "INSERT INTO licenses VALUES (?, ?, ?, ?, ?, ?, ?)",
                (new_key, email, "github", plan_name, "active", created_at, expires_at)
            )
            conn.commit()
            conn.close()
            
            print(f"[+] [GitHub] Generated license {new_key} for {email} (user: {username})")
            self.send_json(200, {"status": "success", "license_key": new_key})
        else:
            self.send_json(200, {"status": "ignored"})

def run_server():
    init_db()
    server_address = ('', PORT)
    httpd = http.server.HTTPServer(server_address, LicenseHandler)
    print(f"[*] License Server running on port {PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server...")
        httpd.server_close()

if __name__ == '__main__':
    run_server()
