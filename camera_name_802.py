import csv
import os
import time
from playwright.sync_api import sync_playwright, TimeoutError
from dotenv import load_dotenv

load_dotenv()

# Credentials & constants
USERNAME = os.getenv("CAMERA_USER")
PASSWORD = os.getenv("CAMERA_PASS")
EAP_METHOD = "peap"
CONFIG_NAME = "WIRED-MSCHAPv2"
EAP_IDENTITY = os.getenv("EAP_IDENTITY")
EAP_PASSWORD = os.getenv("EAP_PASSWORD")
READ_COMMUNITY = "RNPS"

# --- Login handler for all camera UIs ---
def try_login(page, ip):
    try:
        # Legacy form login
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
        # WebUI Next (React/Material UI)
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

# --- File paths ---
base_dir = "/Users/oleg/Library/CloudStorage/OneDrive-NorfolkPublicSchools/Docker/Inventory"
csv_path = os.path.join(base_dir, school, "camera_data.csv")

if not os.path.isfile(csv_path):
    print(f"[ERROR] File not found: {csv_path}")
    exit(1)

# --- Load CSV and launch browser ---
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
            new_hostname = row["hostname"].strip()
            print(f"\n=== Updating {ip}: hostname '{new_hostname}' ===")

            try:
                # --- LOGIN (mixed) ---
                page.goto(f"http://{ip}")
                try_login(page, ip)

                # --- HOSTNAME CONFIG ---
                page.goto(f"http://{ip}/web/setup-network.shtml")
                page.wait_for_selector("#hostname", timeout=5000)

                for _ in range(20):
                    if page.input_value("#hostname").strip():
                        break
                    time.sleep(0.25)

                page.locator("#hostname").fill("")
                page.locator("#hostname").type(new_hostname, delay=100)
                print(" → Hostname filled.")

                page.wait_for_selector("#apply:enabled", timeout=5000)
                page.click("#apply")
                print(" → Hostname applied.")

                page.wait_for_timeout(3000)

                # --- 802.1X CONFIG ---
                page.goto(f"http://{ip}/web/setup-configdot1x.shtml")
                page.wait_for_selector("#configName", timeout=5000)

                page.select_option("#eapTypeSelect", EAP_METHOD)
                page.locator("#configName").fill("")
                page.locator("#configName").type(CONFIG_NAME, delay=100)
                page.locator("#eapIdentity").fill("")
                page.locator("#eapIdentity").type(EAP_IDENTITY, delay=100)

                if EAP_METHOD.lower() == "peap":
                    page.locator("#peapPass").fill("")
                    page.locator("#peapPass").type(EAP_PASSWORD, delay=100)

                page.wait_for_selector("#createDot1xButton:enabled", timeout=5000)
                page.click("#createDot1xButton")
                print(" → 802.1X config saved.")

                page.wait_for_timeout(2000)

                # --- SNMP CONFIG ---
                page.goto(f"http://{ip}/web/setup-snmp.shtml")
                page.wait_for_selector("#enableSnmp", timeout=5000)
                time.sleep(1)

                checkbox = page.locator("input[type='checkbox']").first
                checkbox.wait_for(state="visible", timeout=5000)

                if not checkbox.is_checked():
                    checkbox.check()
                print(" → SNMP enabled.")

                page.wait_for_selector("#input-version", timeout=5000)
                page.wait_for_selector("#readCommunityStr", timeout=5000)

                page.select_option("#input-version", "option-snmpv2c")
                page.locator("#readCommunityStr").fill("")
                page.locator("#readCommunityStr").type(READ_COMMUNITY, delay=100)
                print(f" → SNMP Read Community set to '{READ_COMMUNITY}'.")

                page.click('input[value="Apply"]')
                print(" → SNMP applied.")

                page.wait_for_timeout(2000)

            except Exception as e:
                print(f"[ERROR] {ip}: {e}")

        browser.close()
