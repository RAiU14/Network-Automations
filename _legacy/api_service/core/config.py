from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "Database" / "JSON_Files"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_EOX_DB_PATH = DATA_DIR / "eox_pid.json"

CISCO_BASE_URL = "https://www.cisco.com"
HTTP_TIMEOUT_SECONDS = 30
USER_AGENT = "NTT-Network-Automation/1.0"
