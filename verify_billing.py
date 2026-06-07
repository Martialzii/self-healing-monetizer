import subprocess
import sys
import json
import urllib.request
import time
import os

SERVER_URL = "http://127.0.0.1:8000"

def send_post(endpoint, data):
    req = urllib.request.Request(
        f"{SERVER_URL}{endpoint}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"[-] HTTP Request failed: {e}")
        return None

def main():
    print("[*] Starting billing and licensing verification...")
    
    # 1. Start the license server (inherits stdout/stderr so we can see its output)
    print("[*] Launching license validation server...")
    server_process = subprocess.Popen(
        [sys.executable, "license_server.py"]
    )
    
    # Give server time to bind and run
    time.sleep(3)
    
    # Check if the process is still running
    poll = server_process.poll()
    if poll is not None:
        print(f"[-] License server exited immediately with code {poll}!")
        sys.exit(1)
    
    try:
        # 2. Simulate PayPal subscription webhook
        print("\n[+] Testing PayPal webhook subscription...")
        paypal_payload = {
            "event_type": "BILLING.SUBSCRIPTION.CREATED",
            "email": "cyrussifa@gmail.com",
            "plan_type": "Developer Lite",
            "resource": {
                "subscriber": {
                    "email_address": "cyrussifa@gmail.com"
                }
            }
        }
        paypal_res = send_post("/webhooks/paypal", paypal_payload)
        if not paypal_res or "license_key" not in paypal_res:
            print("[-] PayPal webhook mock failed!")
            sys.exit(1)
        
        paypal_key = paypal_res["license_key"]
        print(f"[+] PayPal license generated: {paypal_key}")
        
        # 3. Simulate GitHub Marketplace purchase webhook
        print("\n[+] Testing GitHub Marketplace purchase webhook...")
        github_payload = {
            "action": "purchased",
            "marketplace_purchase": {
                "account": {
                    "login": "cyrus-github",
                    "email": "cyrussifa@gmail.com"
                },
                "plan": {
                    "name": "Developer Pro"
                }
            }
        }
        github_res = send_post("/webhooks/github", github_payload)
        if not github_res or "license_key" not in github_res:
            print("[-] GitHub webhook mock failed!")
            sys.exit(1)
            
        github_key = github_res["license_key"]
        print(f"[+] GitHub license generated: {github_key}")
        
        # 4. Test registering PayPal key and running healer
        print("\n[+] Registering PayPal license key in CLI...")
        reg_res = subprocess.run(
            [sys.executable, "self_healer.py", "--register", paypal_key],
            capture_output=True,
            text=True
        )
        print(reg_res.stdout)
        
        print("[+] Running self_healer.py (should succeed license check)...")
        # Restore the bug in test_framework.py for verification
        with open("test_framework.py", "w", encoding="utf-8") as f:
            f.write('''# test_framework.py
import sys

def calculate_average(numbers):
    total = summ(numbers)
    return total / len(numbers)

print("Starting verification framework...")
data = [10, 20, 30, 40]
avg = calculate_average(data)
print(f"The average is: {avg}")
''')
        
        run_res = subprocess.run(
            [sys.executable, "self_healer.py", "test_framework.py"],
            capture_output=True,
            text=True
        )
        print(run_res.stdout)
        if "Success!" not in run_res.stdout:
            print("[-] Self-healer failed to execute under valid PayPal license!")
            sys.exit(1)
            
        # 5. Test invalid license key blocking
        print("\n[+] Testing access restriction with an invalid license key...")
        subprocess.run(
            [sys.executable, "self_healer.py", "--register", "SH-INVALID-KEY-1234"],
            capture_output=True,
            text=True
        )
        invalid_res = subprocess.run(
            [sys.executable, "self_healer.py", "test_framework.py"],
            capture_output=True,
            text=True
        )
        print(invalid_res.stdout)
        if "Access Denied" not in invalid_res.stdout:
            print("[-] Self-healer allowed execution with an invalid license key!")
            sys.exit(1)
        else:
            print("[+] Invalid license key successfully blocked.")

        print("\n[+] All license server, webhook generation, registration, and verification tests PASSED!")

    finally:
        print("\n[*] Cleaning up. Terminating license validation server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except Exception:
            server_process.kill()

if __name__ == "__main__":
    main()
