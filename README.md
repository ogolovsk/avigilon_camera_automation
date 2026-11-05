# Camera Automation Toolkit

Playwright-based automation for Avigilon cameras supporting both legacy and WebUI Next interfaces.

## Features

- 🔐 **Multi-authentication support**: Form-based, WebUI Next (React), and HTTP Basic Auth
- 📊 **Inventory collection**: Part number, serial, MAC address, firmware version
- 🔧 **Configuration**: Hostname, 802.1X (PEAP), SNMP v2c
- 🔄 **Bulk operations**: Reboot multiple cameras

- �🛡️ **Robust error handling**: Continues processing on failures, tracks failed devices
- 📈 **Execution summary**: Total cameras, successful/failed logins, detailed reports

## ✅ Requirements

- Python 3.12 (the known-working environment uses Python 3.12.12)
- [Playwright](https://playwright.dev/python/)
- Google Chrome or Chromium browser
- `.env` file with credentials

## 📦 Installation

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
```

`requirements.txt` pins the complete, known-working Python dependency set.
Use it on every Mac rather than installing unversioned packages. Playwright's
browser binary is tied to the Playwright package version, so always run
`python -m playwright install chromium` after installing or upgrading it.

### Updating dependencies safely

Keep production installs pinned. To evaluate newer versions, use a separate
virtual environment, update the candidate versions in `requirements.txt`, run
`python -m playwright install chromium`, and test all operations against at
least one legacy and one WebUI Next camera. Commit the updated
`requirements.txt` only after that test passes. If an upgrade fails, capture
the traceback plus `python -m pip freeze`; that identifies the incompatible
package combination without changing the working environment.

Create a `.env` file in your project root:

```env
# Camera credentials
CAMERA_USER=administrator
CAMERA_PASS=your_password

# 802.1X credentials
EAP_IDENTITY=sec-camera
EAP_PASSWORD=your_eap_password

# Inventory paths (optional - defaults shown below)
# CAMERA_INVENTORY_ONEDRIVE=/Users/oleg/Library/CloudStorage/OneDrive-NorfolkPublicSchools/Docker/Inventory
# CAMERA_INVENTORY_LOCAL=./inventory

# Legacy fallback path (optional)
# CAMERA_INVENTORY_PATH=/path/to/inventory
```

**Note**: Copy `.env.example` to `.env` and fill in your values. python-dotenv expects plain `KEY=value` format (no `export` or quotes).

### Environment Variables

- `CAMERA_USER` - Camera admin username (required)
- `CAMERA_PASS` - Camera admin password (required)
- `EAP_IDENTITY` - 802.1X username for camera authentication
- `EAP_PASSWORD` - 802.1X password for camera authentication

### Inventory Profiles

The scripts now support inventory profiles similar to netops-automation:

- **onedrive** - Uses `CAMERA_INVENTORY_ONEDRIVE` (default: OneDrive path)
- **local** - Uses `CAMERA_INVENTORY_LOCAL` (default: `./inventory`)
- **custom path** - You can set `CAMERA_INVENTORY_PATH` for a custom default

The `.env` file is loaded from:
1. Current working directory (`./.env`)
2. Project root directory
3. Home directory (`~/.avigilon.env`)

Precedence: Environment variables → .env file → hardcoded defaults

## 🗂️ Inventory Structure

The scripts use the inventory path from:
1. `CAMERA_INVENTORY_PATH` environment variable (if set)
2. Default profile: `onedrive` (resolves to `CAMERA_INVENTORY_ONEDRIVE`)

Directory structure:

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

### Read-only discrepancy audit

`audit_camera_discrepancies.py` checks Active cameras missing from a NetBox core
ARP audit and additional ARP MACs. It reuses the inventory login and about-page
selectors, tests HTTP/HTTPS, and saves live model, serial, firmware and MAC to a
separate JSON report. Source inventory files and camera settings are unchanged.
A reachable web server without a readable MAC and serial is reported as
unconfirmed, rather than a successful inventory check.

```bash
.venv/bin/python audit_camera_discrepancies.py \
  --arp-audit /path/to/camera_arp_audit.json \
  --output-dir /path/to/reports
```
