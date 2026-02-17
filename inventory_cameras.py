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
school_name = input("Enter school name (e.g., Willard ES): ").strip()

# --- Build input/output paths ---
base_dir = os.getenv(
    "CAMERA_INVENTORY_PATH",
    "/Users/oleg/Library/CloudStorage/OneDrive-NorfolkPublicSchools/Docker/Inventory"
)
csv_path = os.path.join(base_dir, school, "camera_data.csv")

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
        page.wait_for_selector("#input-username", timeout=3000)
        page.fill("#input-username", USERNAME)
        page.fill("#input-password", PASSWORD)
        page.click("#btn-signin")
        print(" → Form-based login succeeded.")
        page.wait_for_timeout(2000)
        return
    except:
        pass

    # --- New React WebUI Next login ---
    try:
        # Wait for Material UI login fields
        page.wait_for_selector("#textfield_username", timeout=5000)
        page.fill("#textfield_username", USERNAME)
        page.fill("#textfield_password", PASSWORD)

        # Click the Material UI "Sign in" button
        page.get_by_role("button", name="Sign in", exact=True).click()
        page.wait_for_timeout(3000)
        
        # Check if login failed (error message appears)
        if page.locator("#textfield_username").is_visible(timeout=2000):
            print(f" → WebUI Next login FAILED - wrong credentials on {ip}")
            raise Exception("Authentication failed")
        
        print(" → WebUI Next login succeeded.")
        return
    except Exception as e:
        # If it's authentication failure, re-raise it to stop processing this camera
        if "Authentication failed" in str(e):
            raise
        # Otherwise it's just timeout (no WebUI Next form), continue to next method
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
total_cameras = 0
successful_logins = 0
failed_ips = []

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
            total_cameras += 1

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
                successful_logins += 1

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
                failed_ips.append(ip)
                print(f"[ERROR] {ip}: Failed to collect info")
                # Clear page state for next camera
                try:
                    page.goto("about:blank")
                except:
                    pass

            inventory_data.append(result)

        browser.close()

# --------------------------------------------------------------------
# WRITE RESULTS - Update camera_data.csv with inventory info
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

# Prefix serial numbers with tab to force text formatting in Excel
for item in inventory_data:
    if item.get("serial_number"):
        item["serial_number"] = "\t" + item["serial_number"]

# Write back to the same file
with open(csv_path, "w", newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(inventory_data)

# --------------------------------------------------------------------
# WRITE ISE PROFILER FORMAT - for ISE endpoint import
# --------------------------------------------------------------------
ise_fieldnames = [
    "MACAddress", "EndPointPolicy", "IdentityGroup", "Description", "ip",
    "StaticAssignment", "StaticGroupAssignment", "CUSTOM.Model", "CUSTOM.OS",
    "CUSTOM.School Name", "CUSTOM.Serial Number", "CUSTOM.Type of device"
]

# Convert inventory data to ISE format
ise_data = []
for item in inventory_data:
    ise_row = {
        "MACAddress": item["mac_address"].upper().replace(":", ":"),  # Ensure uppercase
        "EndPointPolicy": "'MotorolaSolutions-Device'",
        "IdentityGroup": "'MotorolaSolutions-Device'",
        "Description": item["hostname"].replace("-", " ").upper(),  # Convert hostname to description format
        "ip": item["ip_address"],
        "StaticAssignment": "FALSE",
        "StaticGroupAssignment": "FALSE",
        "CUSTOM.Model": item["part_number"],
        "CUSTOM.OS": item["firmware_version"],
        "CUSTOM.School Name": f"{school}-{school_name}",
        "CUSTOM.Serial Number": item["serial_number"],  # Already has tab prefix
        "CUSTOM.Type of device": "Security Camera"
    }
    ise_data.append(ise_row)

# Write ISE profiler endpoints file
ise_output_path = os.path.join(base_dir, school, f"{school}_camera_endpoints.csv")
with open(ise_output_path, "w", newline='') as f:
    writer = csv.DictWriter(f, fieldnames=ise_fieldnames, quoting=csv.QUOTE_NONNUMERIC)
    writer.writeheader()
    writer.writerows(ise_data)

# --- Print summary ---
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"Total number of cameras: {total_cameras}")
print(f"Login succeeded: {successful_logins}")
print(f"Login failed: {len(failed_ips)}")
if failed_ips:
    print(f"\nIP addresses of cameras with failed login:")
    for ip in failed_ips:
        print(f"  - {ip}")

print(f"\n✅ Camera data updated: {csv_path}")
print(f"✅ ISE endpoints file created: {ise_output_path}")
