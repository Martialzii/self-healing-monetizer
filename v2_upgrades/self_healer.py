import subprocess
import sys
import json
import urllib.request
import urllib.error
import os
import argparse
import re

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
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass
            
    config["license_key"] = key
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        print(f"[+] License key successfully registered locally in {CONFIG_FILE}!")
    except Exception as e:
        print(f"[-] Failed to register license key: {e}")
        sys.exit(1)

def get_config_val(key_name):
    """Get value from environment variable or local config file."""
    val = os.environ.get(key_name.upper())
    if val:
        return val
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get(key_name)
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

def parse_crash_site(traceback_text, main_target):
    """
    Parse traceback text to find the exact file and line number that crashed.
    Returns (crash_file, line_number). If not found or not local, defaults to main_target.
    """
    if not traceback_text:
        return main_target, None
        
    pattern = r'File "([^"]+)", line (\d+)'
    matches = re.findall(pattern, traceback_text)
    if not matches:
        return main_target, None
        
    last_file, last_line = matches[-1]
    abs_path = os.path.abspath(last_file)
    current_dir = os.path.abspath(os.getcwd())
    
    if os.path.exists(abs_path) and abs_path.startswith(current_dir):
        return abs_path, int(last_line)
        
    if os.path.exists(last_file):
        return os.path.abspath(last_file), int(last_line)
        
    return main_target, None

def get_local_dependencies(target_file):
    """Scan the target file for local imports and return their paths and contents."""
    dependencies = {}
    if not os.path.exists(target_file):
        return dependencies
        
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            code = f.read()
    except Exception:
        return dependencies
        
    import_patterns = [
        r'^\s*import\s+([a-zA-Z0-9_\.]+)',
        r'^\s*from\s+([a-zA-Z0-9_\.]+)\s+import'
    ]
    
    imported_modules = []
    for pattern in import_patterns:
        for match in re.finditer(pattern, code, re.MULTILINE):
            module_name = match.group(1).split('.')[0]
            imported_modules.append(module_name)
            
    current_dir = os.path.dirname(os.path.abspath(target_file))
    for mod in set(imported_modules):
        possible_paths = [
            os.path.join(current_dir, f"{mod}.py"),
            os.path.join(os.getcwd(), f"{mod}.py")
        ]
        for path in possible_paths:
            if os.path.exists(path) and path != os.path.abspath(target_file):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        dependencies[path] = f.read()
                    break
                except Exception:
                    pass
    return dependencies

def ask_gemini_for_patch(api_key, prompt):
    print("[!] Consulting Google Gemini API (cloud-based) for surgical hot-patch...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return text.strip()
    except Exception as e:
        print(f"[-] Failed to communicate with Gemini API: {e}")
    return None

def ask_ollama_for_patch(prompt):
    print(f"[!] Consulting local model ({MODEL_NAME}) for surgical hot-patch...")
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

def run_target_script(script_path):
    print(f"[*] Executing target script: {script_path}")
    result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def main():
    parser = argparse.ArgumentParser(description="Self-healing CLI with License Validation & Cloud LLMs")
    parser.add_argument("target", nargs="?", help="The target script to run and heal")
    parser.add_argument("--register", "-r", help="Register your subscription license key")
    args = parser.parse_args()

    if args.register:
        register_license(args.register)
        sys.exit(0)

    if not args.target:
        parser.print_help()
        sys.exit(1)

    key = get_config_val("license_key")
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
            
            crash_file, crash_line = parse_crash_site(stderr, target)
            print(f"[*] Crash Site Detected: {os.path.basename(crash_file)} (Line {crash_line if crash_line else 'Unknown'})")
            
            try:
                with open(crash_file, "r", encoding="utf-8") as f:
                    current_code = f.read()
            except Exception as e:
                print(f"[-] Failed to read script {crash_file}: {e}")
                break
                
            dependencies = get_local_dependencies(target)
            if crash_file != os.path.abspath(target):
                try:
                    with open(target, "r", encoding="utf-8") as f:
                        dependencies[target] = f.read()
                except Exception:
                    pass
            
            context_str = ""
            if dependencies:
                context_str += "\n=== PROJECT DEPENDENCY CONTEXT ===\n"
                for path, content in dependencies.items():
                    if os.path.abspath(path) != os.path.abspath(crash_file):
                        context_str += f"\n--- File: {os.path.basename(path)} ---\n{content}\n"
                context_str += "==================================\n"
            
            prompt = (
                f"You are an autonomous self-healing engineering loop.\n"
                f"The script crashed. The target script we executed is: {os.path.basename(target)}\n"
                f"The crash occurred inside: {os.path.basename(crash_file)} (line {crash_line if crash_line else 'unknown'}).\n"
                f"{context_str}\n"
                f"Here is the code of the crashing file ({os.path.basename(crash_file)}):\n"
                f"{current_code}\n\n"
                f"Error Log:\n{stderr}\n\n"
                f"Please fix the code inside {os.path.basename(crash_file)}. Provide ONLY the corrected code for {os.path.basename(crash_file)}. "
                f"Do NOT wrap it in markdown codeblocks (no backticks) and provide NO explanations."
            )
            
            provider = get_config_val("provider") or "ollama"
            gemini_key = get_config_val("gemini_api_key")
            
            fixed_code = None
            if provider.lower() == "gemini" and gemini_key:
                fixed_code = ask_gemini_for_patch(gemini_key, prompt)
            else:
                fixed_code = ask_ollama_for_patch(prompt)
                
            if fixed_code:
                if fixed_code.startswith("```"):
                    lines = fixed_code.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    fixed_code = "\n".join(lines).strip()
                
                try:
                    with open(crash_file, "w", encoding="utf-8") as f:
                        f.write(fixed_code)
                    print(f"[+] Applied hot-patch to {os.path.basename(crash_file)}. Retrying...")
                except Exception as e:
                    print(f"[-] Failed to write hot-patch to {crash_file}: {e}")
                    break
            else:
                print("[-] No patch received. Aborting.")
                break
    else:
        print("\n[-] Failed to heal the script after 3 attempts.")

if __name__ == "__main__":
    main()
