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
    print("[*] Starting multi-module self-healing verification...")
    
    # 1. Start the license server
    print("[*] Launching license validation server...")
    server_process = subprocess.Popen([sys.executable, "license_server.py"])
    time.sleep(3)
    
    # Check if server started
    if server_process.poll() is not None:
        print("[-] License server failed to start!")
        sys.exit(1)
        
    try:
        # 2. Get license key
        print("[*] Simulating PayPal webhook purchase...")
        paypal_payload = {
            "event_type": "BILLING.SUBSCRIPTION.CREATED",
            "email": "cyrussifa@gmail.com",
            "plan_type": "Pro Developer"
        }
        res = send_post("/webhooks/paypal", paypal_payload)
        if not res or "license_key" not in res:
            print("[-] Failed to create mock subscription!")
            sys.exit(1)
            
        key = res["license_key"]
        print(f"[+] Active license key generated: {key}")
        
        # 3. Register license
        print("[*] Registering license with CLI...")
        subprocess.run([sys.executable, "self_healer.py", "--register", key], capture_output=True)
        
        # 4. Setup multi-module code: test_framework.py and utils.py
        print("[*] Creating utils.py with NameError bug...")
        with open("utils.py", "w", encoding="utf-8") as f:
            f.write('''# utils.py
def calculate_average(numbers):
    # Typo: 'summ' instead of 'sum'
    total = summ(numbers)
    return total / len(numbers)
''')
            
        print("[*] Creating test_framework.py which imports utils...")
        with open("test_framework.py", "w", encoding="utf-8") as f:
            f.write('''# test_framework.py
import utils

print("Starting verification framework...")
data = [10, 20, 30, 40]
avg = utils.calculate_average(data)
print(f"The average is: {avg}")
''')

        # 5. Run the healer
        print("\n[+] Running self_healer.py on test_framework.py...")
        run_res = subprocess.run(
            [sys.executable, "self_healer.py", "test_framework.py"],
            capture_output=True,
            text=True
        )
        print(run_res.stdout)
        if run_res.stderr:
            print(f"Stderr:\n{run_res.stderr}")
            
        # 6. Verify success
        print("[*] Validating if utils.py was correctly hot-patched...")
        with open("utils.py", "r", encoding="utf-8") as f:
            healed_code = f.read()
            
        print("\n--- healed utils.py code ---")
        print(healed_code)
        print("----------------------------")
        
        if "sum(" in healed_code and "summ(" not in healed_code:
            print("[+] Success! The self-healer parsed the traceback, detected the crash in utils.py, hot-patched it, and re-executed successfully!")
        else:
            print("[-] Failure: The bug inside utils.py was not corrected.")
            sys.exit(1)
            
    finally:
        print("\n[*] Cleaning up. Terminating license server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except Exception:
            server_process.kill()
            
        if os.path.exists("utils.py"):
            try:
                os.remove("utils.py")
            except Exception:
                pass

if __name__ == "__main__":
    main()
