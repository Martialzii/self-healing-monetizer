import http.server
import json
import sqlite3
import uuid
import urllib.parse
from datetime import datetime, timedelta

PORT = 8000
DB_FILE = "licenses.db"

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Self-Healer Billing & Licensing Gateway</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0c16;
            --card-bg: #14162e;
            --accent-purple: #8b5cf6;
            --accent-blue: #3b82f6;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --success: #10b981;
            --error: #ef4444;
            --border: rgba(255, 255, 255, 0.08);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.6;
            padding-bottom: 50px;
            overflow-x: hidden;
        }

        header {
            background: linear-gradient(90deg, rgba(139, 92, 246, 0.1) 0%, rgba(59, 130, 246, 0.1) 100%);
            border-bottom: 1px solid var(--border);
            padding: 20px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            backdrop-filter: blur(12px);
            z-index: 100;
        }

        .logo {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 24px;
            font-weight: 700;
            background: linear-gradient(135deg, #a78bfa 0%, #60a5fa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .logo-dot {
            width: 12px;
            height: 12px;
            background-color: var(--accent-purple);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--accent-purple);
        }

        nav {
            display: flex;
            gap: 15px;
        }

        nav button {
            background: none;
            border: none;
            color: var(--text-muted);
            padding: 10px 16px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.3s ease;
        }

        nav button:hover, nav button.active {
            color: var(--text-main);
            background-color: rgba(255, 255, 255, 0.05);
        }

        nav button.active {
            box-shadow: inset 0 -2px 0 var(--accent-purple);
            border-radius: 8px 8px 0 0;
        }

        .container {
            max-width: 1200px;
            margin: 40px auto;
            padding: 0 20px;
        }

        .hero {
            text-align: center;
            padding: 60px 0;
            position: relative;
        }

        .hero::before {
            content: '';
            position: absolute;
            width: 300px;
            height: 300px;
            background: radial-gradient(circle, rgba(139, 92, 246, 0.15) 0%, transparent 70%);
            top: -50px;
            left: 50%;
            transform: translateX(-50%);
            z-index: -1;
        }

        .hero h1 {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 48px;
            font-weight: 800;
            margin-bottom: 20px;
            line-height: 1.2;
        }

        .hero h1 span {
            background: linear-gradient(135deg, #c084fc 0%, #6366f1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero p {
            font-size: 18px;
            color: var(--text-muted);
            max-width: 600px;
            margin: 0 auto 30px;
        }

        /* Tabs Section */
        .tab-content {
            display: none;
            animation: fadeIn 0.4s ease;
        }

        .tab-content.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Cards Grid */
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 30px;
            margin-top: 40px;
        }

        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 30px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }

        .card:hover {
            transform: translateY(-5px);
            border-color: rgba(139, 92, 246, 0.3);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }

        .card h2 {
            font-size: 24px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .card p {
            color: var(--text-muted);
            margin-bottom: 20px;
            font-size: 15px;
        }

        .price-tag {
            font-size: 36px;
            font-weight: 800;
            margin-bottom: 25px;
            color: var(--text-main);
        }

        .price-tag span {
            font-size: 16px;
            color: var(--text-muted);
            font-weight: 400;
        }

        .btn {
            display: block;
            width: 100%;
            background: linear-gradient(135deg, var(--accent-purple) 0%, #6366f1 100%);
            color: white;
            border: none;
            padding: 12px 20px;
            font-size: 16px;
            font-weight: 600;
            border-radius: 10px;
            cursor: pointer;
            text-align: center;
            transition: opacity 0.2s ease;
        }

        .btn:hover {
            opacity: 0.9;
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid var(--border);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.12);
        }

        /* Database View / Table */
        .table-container {
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
            margin-top: 30px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }

        th, td {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
        }

        th {
            background-color: rgba(255, 255, 255, 0.02);
            color: var(--text-muted);
            font-weight: 600;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        tr:last-child td {
            border-bottom: none;
        }

        .badge {
            display: inline-block;
            padding: 4px 8px;
            font-size: 12px;
            font-weight: 600;
            border-radius: 6px;
            text-transform: capitalize;
        }

        .badge-active {
            background-color: rgba(16, 185, 129, 0.1);
            color: var(--success);
        }

        .badge-expired {
            background-color: rgba(239, 68, 68, 0.1);
            color: var(--error);
        }

        /* Forms */
        .form-group {
            margin-bottom: 20px;
        }

        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: var(--text-muted);
        }

        input {
            width: 100%;
            background-color: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
            padding: 12px 16px;
            border-radius: 10px;
            color: white;
            font-size: 16px;
            transition: border-color 0.2s;
        }

        input:focus {
            outline: none;
            border-color: var(--accent-purple);
        }

        /* Checkout Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.8);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }

        .modal.active {
            display: flex;
        }

        .modal-content {
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 20px;
            width: 480px;
            padding: 40px;
            position: relative;
        }

        .close-modal {
            position: absolute;
            top: 20px;
            right: 20px;
            font-size: 24px;
            cursor: pointer;
            color: var(--text-muted);
        }

        .success-box {
            background-color: rgba(16, 185, 129, 0.08);
            border: 1px solid rgba(16, 185, 129, 0.2);
            padding: 20px;
            border-radius: 12px;
            margin-top: 20px;
            word-break: break-all;
        }

        .code-snippet {
            background-color: #05060b;
            padding: 15px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 14px;
            margin: 10px 0;
            border: 1px solid rgba(255, 255, 255, 0.05);
            color: #60a5fa;
            position: relative;
        }

        .copy-btn {
            position: absolute;
            top: 10px;
            right: 10px;
            background-color: rgba(255, 255, 255, 0.1);
            border: none;
            color: white;
            padding: 4px 8px;
            font-size: 11px;
            border-radius: 4px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">
            <div class="logo-dot"></div>
            Self-Healer Gateway
        </div>
        <nav>
            <button class="active" onclick="switchTab('product')">Product</button>
            <button onclick="switchTab('buy')">Buy Subscriptions</button>
            <button onclick="switchTab('admin')">Admin Console</button>
            <button onclick="switchTab('validator')">License Validator</button>
        </nav>
    </header>

    <div class="container">
        <!-- PRODUCT TAB -->
        <div id="tab-product" class="tab-content active">
            <div class="hero">
                <h1>Self-Healing Autonomous <span>Engineering Loop</span></h1>
                <p>Deploy resilient, auto-correcting software. When script bugs occur, the loop hot-patches them instantly using local or cloud LLMs.</p>
            </div>

            <div class="grid">
                <div class="card">
                    <h2>⚙️ Crash Protection</h2>
                    <p>Captures standard error, stack traces, and local line states, sending targeted debug insights to the AI engine.</p>
                </div>
                <div class="card">
                    <h2>📂 Multi-File Awareness</h2>
                    <p>Automatically scans project dependencies, parsing local module imports to resolve errors that cross script boundaries.</p>
                </div>
                <div class="card">
                    <h2>🔒 Monetization Ready</h2>
                    <p>Integrate PayPal & GitHub Marketplace webhooks directly to validate and control remote execution permissions.</p>
                </div>
            </div>
        </div>

        <!-- BUY TAB -->
        <div id="tab-buy" class="tab-content">
            <div style="text-align: center; margin-bottom: 40px;">
                <h1 style="font-family: 'Space Grotesk', sans-serif;">Flexible Plans</h1>
                <p style="color: var(--text-muted);">Purchase access linked to your email address.</p>
            </div>

            <div class="grid" style="max-width: 900px; margin: 0 auto;">
                <div class="card">
                    <h2>Developer Lite</h2>
                    <p>Great for individual developers looking to heal their local systems using Ollama.</p>
                    <div class="price-tag">$5 <span>/ month</span></div>
                    <button class="btn" onclick="openCheckout('Developer Lite', 'paypal')">Buy with PayPal</button>
                </div>
                <div class="card">
                    <h2>Pro Developer</h2>
                    <p>High-tier integration featuring cloud model support (Gemini) and CI actions.</p>
                    <div class="price-tag">$19 <span>/ month</span></div>
                    <button class="btn" onclick="openCheckout('Pro Developer', 'github')">Buy with GitHub</button>
                </div>
            </div>
        </div>

        <!-- ADMIN TAB -->
        <div id="tab-admin" class="tab-content">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h1 style="font-family: 'Space Grotesk', sans-serif;">Active Licenses Database</h1>
                <button class="btn" style="width: auto;" onclick="loadLicenses()">Refresh Data</button>
            </div>

            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>License Key</th>
                            <th>Email Address</th>
                            <th>Provider</th>
                            <th>Plan Type</th>
                            <th>Status</th>
                            <th>Expires At</th>
                        </tr>
                    </thead>
                    <tbody id="licenses-table-body">
                        <tr>
                            <td colspan="6" style="text-align: center; color: var(--text-muted);">Click "Refresh Data" to load database.</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- VALIDATOR TAB -->
        <div id="tab-validator" class="tab-content">
            <div style="max-width: 500px; margin: 0 auto; background-color: var(--card-bg); padding: 40px; border-radius: 16px; border: 1px solid var(--border);">
                <h2 style="font-family: 'Space Grotesk', sans-serif; margin-bottom: 20px; text-align: center;">License Key Tester</h2>
                
                <div class="form-group">
                    <label for="validation-key">Enter License Key</label>
                    <input type="text" id="validation-key" placeholder="SH-PAYPAL-XXXX or SH-GITHUB-XXXX">
                </div>
                
                <button class="btn" onclick="validateKeyOnScreen()">Validate Key</button>

                <div id="validation-result" style="margin-top: 25px; display: none;">
                </div>
            </div>
        </div>
    </div>

    <!-- MOCK CHECKOUT MODAL -->
    <div id="checkout-modal" class="modal">
        <div class="modal-content">
            <span class="close-modal" onclick="closeCheckout()">&times;</span>
            <h2 id="modal-title" style="margin-bottom: 20px; font-family: 'Space Grotesk', sans-serif;">Checkout</h2>
            
            <div id="modal-form">
                <div class="form-group">
                    <label for="checkout-email">Billing Email Address</label>
                    <input type="email" id="checkout-email" value="cyrussifa@gmail.com" required>
                </div>
                <button class="btn" id="modal-action-btn" onclick="submitMockCheckout()">Simulate Payment</button>
            </div>

            <div id="modal-success" style="display: none;">
                <h3 style="color: var(--success); margin-bottom: 10px;">🎉 Payment Successful!</h3>
                <p>We've registered your subscription. Here is your license key:</p>
                <div class="code-snippet">
                    <span id="generated-key-text">SH-PAYPAL-ABC123XYZ</span>
                    <button class="copy-btn" onclick="copyKeyText()">Copy</button>
                </div>
                <p style="font-size: 13px; color: var(--text-muted); margin-top: 15px;">To activate the CLI, run:</p>
                <div class="code-snippet" style="color: #a78bfa;">
                    python self_healer.py --register <span id="activation-key-slug">KEY</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentPlan = '';
        let currentProvider = '';

        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('nav button').forEach(el => el.classList.remove('active'));
            
            document.getElementById('tab-' + tabId).classList.add('active');
            event.target.classList.add('active');

            if (tabId === 'admin') {
                loadLicenses();
            }
        }

        function openCheckout(plan, provider) {
            currentPlan = plan;
            currentProvider = provider;
            document.getElementById('modal-title').innerText = 'Subscribe to ' + plan;
            document.getElementById('modal-action-btn').innerText = 'Simulate ' + (provider === 'paypal' ? 'PayPal' : 'GitHub') + ' Payment';
            document.getElementById('modal-form').style.display = 'block';
            document.getElementById('modal-success').style.display = 'none';
            document.getElementById('checkout-modal').classList.add('active');
        }

        function closeCheckout() {
            document.getElementById('checkout-modal').classList.remove('active');
        }

        async function submitMockCheckout() {
            const email = document.getElementById('checkout-email').value;
            if (!email) {
                alert('Please enter your email address');
                return;
            }

            let endpoint = '';
            let payload = {};

            if (currentProvider === 'paypal') {
                endpoint = '/webhooks/paypal';
                payload = {
                    "event_type": "BILLING.SUBSCRIPTION.CREATED",
                    "email": email,
                    "plan_type": currentPlan
                };
            } else {
                endpoint = '/webhooks/github';
                payload = {
                    "action": "purchased",
                    "marketplace_purchase": {
                        "account": {
                            "login": email.split('@')[0],
                            "email": email
                        },
                        "plan": {
                            "name": currentPlan
                        }
                    }
                };
            }

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (data.status === 'success') {
                    document.getElementById('generated-key-text').innerText = data.license_key;
                    document.getElementById('activation-key-slug').innerText = data.license_key;
                    document.getElementById('modal-form').style.display = 'none';
                    document.getElementById('modal-success').style.display = 'block';
                } else {
                    alert('Mock payment processing failed.');
                }
            } catch (err) {
                console.error(err);
                alert('Connection error communicating with mock gateway.');
            }
        }

        function copyKeyText() {
            const keyText = document.getElementById('generated-key-text').innerText;
            navigator.clipboard.writeText(keyText);
            alert('Copied license key to clipboard!');
        }

        async function loadLicenses() {
            const tbody = document.getElementById('licenses-table-body');
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Fetching database records...</td></tr>';
            try {
                const response = await fetch('/licenses');
                const data = await response.json();
                
                if (!data.licenses || data.licenses.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No licenses registered yet.</td></tr>';
                    return;
                }

                tbody.innerHTML = '';
                data.licenses.forEach(lic => {
                    const expires = lic.expires_at ? new Date(lic.expires_at).toLocaleDateString() : 'Never';
                    const badgeClass = lic.status === 'active' ? 'badge-active' : 'badge-expired';
                    
                    const row = `
                        <tr>
                            <td style="font-family: monospace; font-size: 14px; color: #60a5fa;">${lic.license_key}</td>
                            <td>${lic.email}</td>
                            <td style="text-transform: capitalize;">${lic.provider}</td>
                            <td>${lic.plan_type}</td>
                            <td><span class="badge ${badgeClass}">${lic.status}</span></td>
                            <td>${expires}</td>
                        </tr>
                    `;
                    tbody.innerHTML += row;
                });
            } catch (err) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--error);">Error loading records. Make sure the server is running.</td></tr>';
            }
        }

        async function validateKeyOnScreen() {
            const key = document.getElementById('validation-key').value;
            const resDiv = document.getElementById('validation-result');
            resDiv.style.display = 'block';
            resDiv.innerHTML = '<p style="color: var(--text-muted);">Validating key...</p>';

            if (!key) {
                resDiv.innerHTML = '<div class="success-box" style="background-color: rgba(239, 68, 68, 0.08); border-color: rgba(239, 68, 68, 0.2); color: var(--error);">Please enter a license key.</div>';
                return;
            }

            try {
                const response = await fetch('/validate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ license_key: key })
                });
                
                const data = await response.json();
                
                if (response.status === 200 && data.status === 'active') {
                    resDiv.innerHTML = `
                        <div class="success-box">
                            <h4 style="color: var(--success); margin-bottom: 5px;">✅ License Valid!</h4>
                            <p><strong>Owner:</strong> ${data.email}</p>
                            <p><strong>Plan:</strong> ${data.plan_type}</p>
                            <p><strong>Expires:</strong> ${data.expires_at ? new Date(data.expires_at).toLocaleString() : 'Never'}</p>
                        </div>
                    `;
                } else {
                    resDiv.innerHTML = `
                        <div class="success-box" style="background-color: rgba(239, 68, 68, 0.08); border-color: rgba(239, 68, 68, 0.2);">
                            <h4 style="color: var(--error); margin-bottom: 5px;">❌ License Denied</h4>
                            <p>${data.reason || 'Invalid verification request'}</p>
                        </div>
                    `;
                }
            } catch (err) {
                resDiv.innerHTML = '<div class="success-box" style="background-color: rgba(239, 68, 68, 0.08); border-color: rgba(239, 68, 68, 0.2); color: var(--error);">Error communicating with validation gateway.</div>';
            }
        }
    </script>
</body>
</html>
"""

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
        print(f"[*] [Server] {format % args}")

    def send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path in ['/', '/dashboard']:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode('utf-8'))
        elif parsed_path.path == '/licenses':
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
        
        if status != "active":
            self.send_json(403, {"status": "inactive", "reason": f"License is {status}"})
            return

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
        event_type = data.get("event_type")
        resource = data.get("resource", {})
        
        print(f"[+] [PayPal Webhook] Received event: {event_type}")
        
        if event_type == "BILLING.SUBSCRIPTION.CREATED" or event_type == "PAYMENT.SALE.COMPLETED":
            email = data.get("email") or resource.get("subscriber", {}).get("email_address") or "cyrussifa@gmail.com"
            plan_type = data.get("plan_type") or "Developer Lite"
            
            new_key = f"SH-PAYPAL-{uuid.uuid4().hex[:16].upper()}"
            created_at = datetime.now().isoformat()
            expires_at = (datetime.now() + timedelta(days=30)).isoformat()
            
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
        action = data.get("action")
        marketplace_purchase = data.get("marketplace_purchase", {})
        
        print(f"[+] [GitHub Webhook] Received action: {action}")
        
        if action in ["purchased", "changed"]:
            account = marketplace_purchase.get("account", {})
            username = account.get("login", "github_user")
            email = account.get("email") or f"{username}@github.com"
            plan = marketplace_purchase.get("plan", {})
            plan_name = plan.get("name", "Developer Pro")
            
            new_key = f"SH-GITHUB-{uuid.uuid4().hex[:16].upper()}"
            created_at = datetime.now().isoformat()
            expires_at = (datetime.now() + timedelta(days=365)).isoformat()
            
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
    print(f"[*] License & Subscription Server running on port {PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server...")
        httpd.server_close()

if __name__ == '__main__':
    run_server()
