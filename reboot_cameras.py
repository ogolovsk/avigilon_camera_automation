import csv
import os
import time
from playwright.sync_api import sync_playwright, TimeoutError
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.getenv("CAMERA_USER")
PASSWORD = os.getenv("CAMERA_PASS")

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
    except TimeoutError:
        pass

    try:
        # Try WebUI Next login
        page.wait_for_selector("#textfield_username", timeout=5000)
        page.fill("#textfield_username", USERNAME)
        page.fill("#textfield_password", PASSWORD)
        page.get_by_role("button", name="Sign in", exact=True).click()
        print(" → WebUI Next login succeeded.")
        page.wait_for_timeout(3000)
        return
    except TimeoutError:
        print(f" → No login form found on {ip} — assuming HTTP Basic Auth handled it.")

# --- Prompt for school ---
school = input("Select a school number in format - 001, 016 etc.: ").strip()

# --- File path ---
base_dir = "/Users/oleg/Library/CloudStorage/OneDrive-NorfolkPublicSchools/Docker/Inventory"
csv_path = os.path.join(base_dir, school, "camera_data.csv")

if not os.path.isfile(csv_path):
    print(f"[ERROR] File not found: {csv_path}")
    exit(1)

# --- Track failures ---
failed_cameras = []

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
            print(f"\n=== Rebooting camera {ip} ({hostname}) ===")

            try:
                page.goto(f"http://{ip}")
                try_login(page, ip)

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
                print(f"[ERROR] {ip}: Reboot failed")

        browser.close()

# --- Print summary ---
if failed_cameras:
    print("\n=== FAILED CAMERAS ===")
    print(f"{'IP Address':<15} {'Hostname':<30} {'Error'}")
    print("-" * 70)
    for f in failed_cameras:
        print(f"{f['ip_address']:<15} {f['hostname']:<30} {f['error']}")
else:
    print("\n✅ All cameras rebooted successfully.")
