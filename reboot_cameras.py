import csv
import os
import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.getenv("CAMERA_USER")
PASSWORD = os.getenv("CAMERA_PASS")

if not USERNAME or not PASSWORD:
    print("[ERROR] CAMERA_USER or CAMERA_PASS not set.")
    exit(1)

# --- Login logic for all auth types ---
def try_login(page, ip):
    try:
        # Try classic form login
        page.wait_for_selector("#input-username", timeout=3000)
        page.fill("#input-username", USERNAME)
        page.fill("#input-password", PASSWORD)
        page.click("#btn-signin")
        print(" → Form-based login succeeded.")
        page.wait_for_timeout(2000)
        return
    except:
        pass

    try:
        # Try WebUI Next login
        page.wait_for_selector("#textfield_username", timeout=5000)
        page.fill("#textfield_username", USERNAME)
        page.fill("#textfield_password", PASSWORD)
        page.get_by_role("button", name="Sign in", exact=True).click()
        page.wait_for_timeout(3000)
        
        # Check if login failed
        if page.locator("#textfield_username").is_visible(timeout=2000):
            print(f" → WebUI Next login FAILED - wrong credentials on {ip}")
            raise Exception("Authentication failed")
        
        print(" → WebUI Next login succeeded.")
        return
    except Exception as e:
        if "Authentication failed" in str(e):
            raise
        print(f" → No login form found on {ip} — assuming HTTP Basic Auth handled it.")

# --- Prompt for school ---
school = input("Select a school number in format - 001, 016 etc.: ").strip()

# --- File path ---
base_dir = os.getenv(
    "CAMERA_INVENTORY_PATH",
    "/Users/oleg/Library/CloudStorage/OneDrive-NorfolkPublicSchools/Docker/Inventory"
)
csv_path = os.path.join(base_dir, school, "camera_data.csv")

if not os.path.isfile(csv_path):
    print(f"[ERROR] File not found: {csv_path}")
    exit(1)

# --- Track failures ---
failed_cameras = []
total_cameras = 0
successful_logins = 0
failed_ips = []

# --- Main loop ---
with open(csv_path, newline='', encoding='utf-8-sig') as csvfile:
    reader = csv.DictReader(csvfile)
    print("CSV loaded successfully.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            http_credentials={"username": USERNAME, "password": PASSWORD}
        )
        page = context.new_page()
        print("CSV Headers:", reader.fieldnames)

        for row in reader:
            ip = row["ip_address"].strip()
            hostname = row.get("hostname", "").strip()
            total_cameras += 1
            print(f"\n=== Rebooting camera {ip} ({hostname}) ===")

            try:
                page.goto(f"http://{ip}")
                try_login(page, ip)
                successful_logins += 1

                # System page → reboot
                page.goto(f"http://{ip}/web/setup-system.shtml")
                page.wait_for_timeout(1000)

                reboot_button = page.locator('input[value="Reboot"], #rebootButton')
                reboot_button.wait_for(state="visible", timeout=5000)
                reboot_button.click()
                print(" → Reboot command sent.")
                page.wait_for_timeout(2000)

            except Exception as e:
                failed_cameras.append({
                    "ip_address": ip,
                    "hostname": hostname,
                    "error": "Reboot failed"
                })
                failed_ips.append(ip)
                print(f"[ERROR] {ip}: Reboot failed")
                # Clear page state for next camera
                try:
                    page.goto("about:blank")
                except:
                    pass

        browser.close()

# --- Print summary ---
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"Total number of cameras: {total_cameras}")
print(f"Login succeeded: {successful_logins}")
print(f"Login failed: {len(failed_ips)}")

if failed_cameras:
    print("\n=== FAILED CAMERAS ===")
    print(f"{'IP Address':<15} {'Hostname':<30} {'Error'}")
    print("-" * 70)
    for f in failed_cameras:
        print(f"{f['ip_address']:<15} {f['hostname']:<30} {f['error']}")
else:
    print("\n✅ All cameras rebooted successfully.")
