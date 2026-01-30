# Camera Automation Toolkit

Playwright-based automation for Avigilon cameras supporting both legacy and WebUI Next interfaces.

## Features

- 🔐 **Multi-authentication support**: Form-based, WebUI Next (React), and HTTP Basic Auth
- 📊 **Inventory collection**: Part number, serial, MAC address, firmware version
- 🔧 **Configuration**: Hostname, 802.1X (PEAP), SNMP v2c
- 🔄 **Bulk operations**: Reboot multiple cameras
- 🛡️ **Robust error handling**: Continues processing on failures, tracks failed devices
- 📈 **Execution summary**: Total cameras, successful/failed logins, detailed reports

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

```env
CAMERA_USER=administrator
CAMERA_PASS=your_password
EAP_IDENTITY=sec-camera
EAP_PASSWORD=your_eap_password
```

**Note**: Do not use `export` or quotes - python-dotenv expects plain `KEY=value` format.

## 🗂️ Inventory Structure

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

### inventory_cameras.py

Collects device information from all cameras:
- Part number
- Serial number
- Firmware version
- MAC address

**Features:**
- Detects and handles WebUI Next vs legacy cameras
- Skips failed cameras and continues processing
- Saves sorted `{school}_camera_inventory.csv` by IP address
- Displays summary: total cameras, successful/failed logins, failed IPs

**Usage:**
```bash
python inventory_cameras.py
# Select school: 001, 016, etc.
```

### reboot_cameras.py

Reboots cameras in bulk with comprehensive error handling.

**Features:**
- Supports all authentication types
- Clears page state on failures to prevent browser hang
- Tracks failed cameras with hostname and error
- Summary statistics

**Usage:**
```bash
python reboot_cameras.py
# Select school: 001, 016, etc.
```

### camera_name_802.py

Configures cameras with:
- Hostname
- 802.1X (PEAP/MSCHAPv2)
- SNMP v2c

**Features:**
- Updates hostname via setup-network page
- Creates 802.1X config with EAP identity/password
- Enables SNMP with read community string
- Authentication failure detection
- Summary with failed device tracking

**Usage:**
```bash
python camera_name_802.py
# Select school: 001, 016, etc.
```

## 🔍 Error Handling

All scripts now include:
- **Authentication verification**: Detects failed WebUI Next logins
- **Page state reset**: Navigates to `about:blank` on error to prevent browser hang
- **Continue on failure**: Processes all cameras even if some fail
- **Summary statistics**: Shows total cameras, successful/failed counts, failed IPs

Example output:
```
======================================================================
SUMMARY
======================================================================
Total number of cameras: 25
Login succeeded: 23
Login failed: 2

IP addresses of cameras with failed login:
  - 10.115.112.64
  - 10.115.112.99
```

## 🔧 Troubleshooting

**Authentication failures:**
- Verify `.env` file uses `KEY=value` format (no `export` or quotes)
- Check credentials are correct for WebUI Next cameras
- Ensure HTTP Basic Auth is configured if no login form appears

**Browser hangs on failed camera:**
- Scripts now automatically reset page state - this should be resolved

**Missing data from WebUI Next cameras:**
- Inventory collection works for legacy cameras
- WebUI Next cameras may need different selectors - inspect page elements
