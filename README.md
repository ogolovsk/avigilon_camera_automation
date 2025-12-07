# Camera Automation Toolkit

This toolkit automates Avigilon camera configuration tasks via Playwright, including:

- Hostname assignment
- 802.1X configuration
- SNMP setup
- Inventory collection (serial, part number, MAC, firmware)
- Camera reboot

## ✅ Requirements

- Python 3.9+
- [Playwright](https://playwright.dev/python/)
- Google Chrome or Chromium browser
- `.env` file with credentials

## 📦 Installation

```bash
pip install playwright python-dotenv
playwright install
```

Create a `.env` file in your project root:

```
CAMERA_USER=to_change
CAMERA_PASS=to_change
EAP_IDENTITY=to_change
EAP_PASSWORD=to_change
```

## 🗂️ File Structure

```
Inventory/
  ├── 001/
  │   └── camera_data.csv
  ├── 002/
  │   └── camera_data.csv
  ...
```

Each `camera_data.csv` should contain:

```csv
ip_address,hostname
10.1.112.23,MAIN-ENTRANCE
10.1.112.24,CAFETERIA-1
```

## 🧠 Scripts

### collect_inventory.py

Logs into each camera and collects:
- Part number
- Serial number
- Firmware version
- MAC address

Saves a sorted `camera_inventory.csv` in the same folder.

### reboot_cameras.py

Logs into each camera and reboots it. Supports:
- Basic Auth
- Form-based login
- React WebUI Next (Material UI)

Displays a clean summary of failed reboots.

### camera_configure.py

Updates camera configuration:
- Hostname
- 802.1X (PEAP)
- SNMP v2c

All values pulled from CSV and `.env`.
