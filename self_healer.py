import subprocess
import sys
import json
import urllib.request
import os
import argparse

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
LICENSE_SERVER_URL = "http://127.0.0.1:8000/validate"
CONFIG_FILE = ".self_healer_config.json"

def get_best_model():
    """Dynamically find the best available model on the local Ollama instance."""
    try:
        req = urllib.request.urlopen("http://127.0.0.1:11434/api/tags")
        data = json.loads(req.read().decode("utf-8"))
        models = [m["name"] for m in data.get("models", [])]
        
        preferred = ["deepseek-coder-v2:16b", "llama3:latest", "llama3.2:3b", "gemma:2b"]
        for p in preferred:
            if p in models:
                return p
        if models:
            return models[0]
    except Exception:
        pass
    return "llama3:latest"

MODEL_NAME = get_best_model()

def register_license(key):
    """Save the license key to the local config file."""
    config = {"license_key": key}
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        print(f"[+] License key successfully registered locally in {CONFIG_FILE}!")
    except Exception as e:
        print(f"[-] Failed to register license key: {e}")
        sys.exit(1)

def get_registered_license():
    """Get license key from environment variable or local config file."""
    # Check env var first
    key = os.environ.get("SELF_HEALER_LICENSE_KEY")
    if key:
        return key
    
    # Check config file
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("license_key")
        except Exception:
            pass
    return None

def validate_license(key):
    """Verify license key with backend server."""
    print("[*] Verifying license subscription...")
    payload = {"license_key": key}
    req = urllib.request.Request(
        LICENSE_SERVER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if response.status == 200 and res_data.get("status") == "active":
                print(f"[+] License Validated! (Plan: {res_data.get('plan_type')}, Owner: {res_data.get('email')})")
                return True
            else:
                reason = res_data.get("reason", "Unknown verification failure")
                print(f"[-] Access Denied: {reason}")
                return False
    except urllib.error.HTTPError as e:
        try:
            err_data = json.loads(e.read().decode("utf-8"))
            reason = err_data.get("reason", "Unknown HTTP error")
        except Exception:
            reason = f"HTTP Error {e.code}"
        print(f"[-] Access Denied: {reason}")
        return False
    except Exception as e:
        print(f"[-] Failed to communicate with license server: {e}")
        print("[-] Please ensure the license server is running or check your internet connection.")
        return False

def run_target_script(script_path):
    print(f"[*] Executing target script: {script_path}")
    result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def ask_local_model_for_patch(script_path, code, error_log):
    print(f"[!] Script crashed. Consulting local model ({MODEL_NAME}) for surgical hot-patch...")
    prompt = (
        f"You are an autonomous self-healing engineering loop. The script {script_path} failed.\n"
        f"Original code:\n{code}\n"
        f"Error log:\n{error_log}\n"
        f"Provide ONLY corrected code without markdown format, explanations, or backticks."
    )
    payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False}
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data.get("response", "").strip()
    except Exception as e:
        print(f"[-] Failed to communicate with Ollama: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Self-healing CLI with License Validation")
    parser.add_argument("target", nargs="?", help="The target script to run and heal")
    parser.add_argument("--register", "-r", help="Register your subscription license key")
    args = parser.parse_args()

    # Handle license registration
    if args.register:
        register_license(args.register)
        sys.exit(0)

    # If no target specified
    if not args.target:
        parser.print_help()
        sys.exit(1)

    # Retrieve and validate license key
    key = get_registered_license()
    if not key:
        print("[-] Error: No registered license key found.")
        print("    To register, run: python self_healer.py --register <LICENSE_KEY>")
        print("    Or set the environment variable: SELF_HEALER_LICENSE_KEY")
        sys.exit(1)

    if not validate_license(key):
        print("[-] Aborting: Valid license is required to run the self-healer.")
        sys.exit(1)

    target = args.target
    for attempt in range(1, 4):
        print(f"\n[--- Attempt {attempt} ---]")
        return_code, stdout, stderr = run_target_script(target)
        if return_code == 0:
            print("[+] Success! Script executed with exit code 0.")
            if stdout: 
                print(f"Output:\n{stdout}")
            break
        else:
            print(f"[-] Execution Failed on attempt {attempt}.")
            if stderr:
                print(f"Error Log:\n{stderr}")
            
            try:
                with open(target, "r", encoding="utf-8") as f:
                    current_code = f.read()
            except Exception as e:
                print(f"[-] Failed to read target script {target}: {e}")
                break
                
            fixed_code = ask_local_model_for_patch(target, current_code, stderr)
            if fixed_code:
                # Remove markdown code formatting if the model still generated it
                if fixed_code.startswith("```"):
                    lines = fixed_code.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    fixed_code = "\n".join(lines).strip()
                
                try:
                    with open(target, "w", encoding="utf-8") as f:
                        f.write(fixed_code)
                    print(f"[+] Applied hot-patch to {target}. Retrying...")
                except Exception as e:
                    print(f"[-] Failed to write hot-patch to {target}: {e}")
                    break
            else:
                print("[-] No patch received. Aborting.")
                break
    else:
        print("\n[-] Failed to heal the script after 3 attempts.")

if __name__ == "__main__":
    main()
