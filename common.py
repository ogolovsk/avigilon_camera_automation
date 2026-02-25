# common.py - Shared configuration for avigilon_camera_automation
from __future__ import annotations
import os
import pathlib
from dotenv import load_dotenv

# Load .env file if it exists (searches current dir, then project root, then home dir)
# This runs once when the module is imported
_env_paths = [
    pathlib.Path.cwd() / ".env",
    pathlib.Path(__file__).parent / ".env",  # Project root
    pathlib.Path.home() / ".avigilon.env",
]
for _env_path in _env_paths:
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
        break

# Inventory profile mappings
# Can be extended by setting CAMERA_INVENTORY_ONEDRIVE, etc. in .env
INVENTORY_PROFILES = {
    "onedrive": pathlib.Path(
        os.getenv(
            "CAMERA_INVENTORY_ONEDRIVE",
            "/Users/oleg/Library/CloudStorage/OneDrive-NorfolkPublicSchools/Docker/Inventory",
        )
    ),
    "local": pathlib.Path(os.getenv("CAMERA_INVENTORY_LOCAL", "inventory")),
}


def resolve_inventory_path(value: str | None = None) -> str:
    """
    Resolve inventory path from profile name or path.

    Supports:
    - Profile names: 'onedrive', 'local'
    - Absolute paths: '/path/to/inventory'
    - Relative paths: 'inventory/001'
    - None: defaults to CAMERA_INVENTORY_PATH or 'onedrive' profile

    Profile paths can be customized via .env:
    - CAMERA_INVENTORY_ONEDRIVE
    - CAMERA_INVENTORY_LOCAL
    - CAMERA_INVENTORY_PATH (fallback)

    Args:
        value: Profile name or path (optional)

    Returns:
        Resolved path as string
    """
    # If no value provided, check for CAMERA_INVENTORY_PATH or default to onedrive
    if not value:
        value = os.getenv("CAMERA_INVENTORY_PATH")
        if not value:
            value = "onedrive"
    
    key = value.strip().lower()
    return str(INVENTORY_PROFILES[key]) if key in INVENTORY_PROFILES else value


def get_camera_credentials() -> tuple[str, str]:
    """
    Get camera credentials from .env file or environment variables.

    Returns:
        Tuple of (username, password)

    Raises:
        SystemExit: If credentials cannot be found

    Example:
        # In .env:
        CAMERA_USER=administrator
        CAMERA_PASS=secret123
    """
    username = os.getenv("CAMERA_USER")
    password = os.getenv("CAMERA_PASS")

    if not username or not password:
        print("[ERROR] CAMERA_USER or CAMERA_PASS not set in .env file.")
        print("Create a .env file with:")
        print("  CAMERA_USER=your_username")
        print("  CAMERA_PASS=your_password")
        exit(1)

    return username, password


def get_eap_credentials() -> tuple[str | None, str | None]:
    """
    Get EAP credentials from .env file or environment variables.

    Returns:
        Tuple of (eap_identity, eap_password) or (None, None) if not set
    """
    return os.getenv("EAP_IDENTITY"), os.getenv("EAP_PASSWORD")


def validate_csv(csv_path: str, required_headers: list[str] = None) -> None:
    """
    Validate CSV file for encoding issues and required headers.

    Checks:
    - File exists
    - UTF-8 encoding (with helpful error if not)
    - No problematic characters (like non-breaking spaces)
    - Required headers present

    Args:
        csv_path: Path to CSV file
        required_headers: List of required column names (default: ['ip_address', 'hostname'])

    Raises:
        SystemExit: If validation fails with helpful error message
    """
    import csv
    
    if required_headers is None:
        required_headers = ['ip_address', 'hostname']
    
    # Check file exists
    if not os.path.isfile(csv_path):
        print(f"[ERROR] File not found: {csv_path}")
        exit(1)
    
    # Check for problematic characters (non-breaking spaces, etc.)
    problem_lines = []
    with open(csv_path, 'rb') as f:
        for i, line in enumerate(f, 1):
            # Check for non-breaking space (0xa0) and other problematic bytes
            if b'\xa0' in line:
                problem_lines.append((i, 'non-breaking space (0xa0)'))
    
    if problem_lines:
        print(f"[ERROR] CSV file contains problematic characters:")
        for line_num, issue in problem_lines[:5]:  # Show first 5
            print(f"  Line {line_num}: {issue}")
        print("\nFix with:")
        print(f"  python3 -c \"content = open('{csv_path}', 'r', encoding='latin-1').read(); \"\\")
        print(f"            \"open('{csv_path}', 'w', encoding='utf-8').write(content.replace('\\\\xa0', ''))\"")
        exit(1)
    
    # Try to read with UTF-8 and check headers
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            
            if not headers:
                print(f"[ERROR] CSV file is empty or has no headers: {csv_path}")
                exit(1)
            
            # Check for required headers
            missing = [h for h in required_headers if h not in headers]
            if missing:
                print(f"[ERROR] CSV missing required columns: {', '.join(missing)}")
                print(f"  Found columns: {', '.join(headers)}")
                print(f"  Required columns: {', '.join(required_headers)}")
                exit(1)
            
            # Try reading first row to catch any encoding issues
            try:
                next(reader)
            except StopIteration:
                pass  # Empty file is ok
                
    except UnicodeDecodeError as e:
        print(f"[ERROR] CSV file has encoding issues: {csv_path}")
        print(f"  {str(e)}")
        print("\nTry re-saving the file as UTF-8, or use:")
        print(f"  iconv -f ISO-8859-1 -t UTF-8 {csv_path} > {csv_path}.utf8")
        print(f"  mv {csv_path}.utf8 {csv_path}")
        exit(1)
    
    print(f"✓ CSV validation passed: {os.path.basename(csv_path)}")
