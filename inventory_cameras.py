import csv
import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

# --- Env vars ---
USERNAME = os.getenv("CAMERA_USER")
PASSWORD = os.getenv("CAMERA_PASS")

if not USERNAME or not PASSWORD:
    print("[ERROR] CAMERA_USER or CAMERA_PASS not set.")
    exit(1)

# --- Prompt for school number ---
school = input("Select a school number in format - 001, 016 etc.: ").strip()

# --- Build input/output paths ---
base_dir = "/Users/oleg/Library/CloudStorage/OneDrive-NorfolkPublicSchools/Docker/Inventory"
csv_path = os.path.join(base_dir, school, "camera_data.csv")
output_path = os.path.join(base_dir, school, f"{school}_camera_inventory.csv")

if not os.path.isfile(csv_path):
    print(f"[ERROR] File not found: {csv_path}")
    exit(1)

# --------------------------------------------------------------------
# LOGIN HANDLER
# Supports:
# 1. Old HTML login form
# 2. WebUI Next / Material UI React login
# 3. Basic Auth fallback
# --------------------------------------------------------------------
def try_login(page, ip):

    # --- Legacy login form ---
    try:
        page.wait_for_selector("#input-username", timeout=2000)
        page.fill("#input-username", USERNAME)
        page.fill("#input-password", PASSWORD)
        page.click("#btn-signin")
        print(" → Legacy form-based login succeeded.")
        page.wait_for_timeout(2000)
        return
    except:
        pass

    # --- New React WebUI Next login ---
    try:
        # Wait for Material UI login fields
        page.wait_for_selector("#textfield_username", timeout=6000)
        page.fill("#textfield_username", USERNAME)
        page.fill("#textfield_password", PASSWORD)

        # Click the Material UI "Sign in" button
        page.get_by_role("button", name="Sign in", exact=True).click()
        print(" → WebUI Next login succeeded.")
        page.wait_for_timeout(3000)
        return
    except:
        pass

    # --- Basic Auth fallback ---
    print(f" → No login form present on {ip} — assuming Basic Auth.")

# --- Helper for safely reading locator text ---
def safe_text(locator):
    try:
        return locator.text_content().strip()
    except:
        return ""

# --------------------------------------------------------------------
# DATA COLLECTION
# --------------------------------------------------------------------
inventory_data = []

with open(csv_path, newline='', encoding='utf-8-sig') as csvfile:
    reader = csv.DictReader(csvfile)
    print("CSV loaded successfully.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            http_credentials={"username": USERNAME, "password": PASSWORD}
        )
        page = context.new_page()

        for row in reader:
            ip = row["ip_address"].strip()
            hostname = row.get("hostname", "").strip()

            print(f"\n=== Collecting from {ip} ({hostname}) ===")

            result = {
                "ip_address": ip,
                "hostname": hostname,
                "part_number": "",
                "serial_number": "",
                "firmware_version": "",
                "mac_address": "",
                "status": "OK"
            }

            try:
                # --- LOGIN ---
                page.goto(f"http://{ip}")
                try_login(page, ip)

                # --- ABOUT PAGE ---
                page.goto(f"http://{ip}/web/about.shtml")
                page.wait_for_timeout(1500)

                # Extract values from IDs
                result["part_number"]      = safe_text(page.locator("#text-partNumber"))
                result["serial_number"]    = safe_text(page.locator("#text-serialNumber"))
                result["firmware_version"] = safe_text(page.locator("#text-firmwareVersion"))
                result["mac_address"]      = safe_text(page.locator("#text-macAddress"))

                print(
                    f" → Part#: {result['part_number']}, "
                    f"Serial#: {result['serial_number']}, "
                    f"FW: {result['firmware_version']}"
                )

            except Exception as e:
                result["status"] = "Failed"
                print(f"[ERROR] {ip}: Failed to collect info")

            inventory_data.append(result)

        browser.close()

# --------------------------------------------------------------------
# WRITE RESULTS
# --------------------------------------------------------------------
fieldnames = [
    "ip_address", "hostname",
    "part_number", "serial_number",
    "firmware_version", "mac_address",
    "status"
]

# Sort inventory by IP address (numeric-safe)
from ipaddress import ip_address
inventory_data.sort(key=lambda x: ip_address(x["ip_address"]))

with open(output_path, "w", newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(inventory_data)

print(f"\n✅ Inventory report saved to: {output_path}")
