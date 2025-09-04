# PM_Report/facade.py
import os
import re
import logging

from . import settings
from .Switching.ios_xe import Cisco_IOS_XE as IOSXE  # XE stays eager

# -------- lazy loader for IOS (prevents import errors from blocking XE) ----------
def _load_ios():
    try:
        from .Switching.ios import Cisco_IOS as IOS
        return IOS
    except Exception as e:
        logging.warning(f"[facade] IOS parser not loadable: {e}")
        return None

# --- scope strictly to the show version block ---
_SHOW_VER_START = re.compile(r'(?im)^\s*-+\s*show\s+version\s*-+\s*$')
_NEXT_SECTION   = re.compile(r'(?im)^\s*-+\s*show\b')

def _scope_show_version(text: str) -> str:
    if not text:
        return ""
    m = _SHOW_VER_START.search(text)
    if not m:
        return text  # fallback: whole text
    start = m.end()
    n = _NEXT_SECTION.search(text, pos=start)
    end = n.start() if n else len(text)
    return text[start:end]

# --- classify by tokens (handles "Cisco IOS, IOS-XE ..." too) ---
def detect_os(text: str) -> str:
    if not text:
        return "unsupported"
    block = _scope_show_version(text)

    # any appearance of IOS-XE token wins
    if re.search(r'(?i)\bIOS[-\s]?XE\b', block):
        return "ios_xe"

    # classic IOS only if 'Cisco IOS Software' present and no XE token
    if re.search(r'(?i)Cisco\s+IOS\s+Software', block):
        return "ios"

    return "unsupported"

def detect_os_from_file(file_path: str) -> str:
    try:
        with open(file_path, "r", errors="ignore") as f:
            return detect_os(f.read())
    except Exception:
        return "unsupported"

# -------- placeholder row (keeps your 31-column contract) -----------------------
def _placeholder_entry(file_path, reason_text="Unsupported"):
    fname = os.path.basename(file_path)
    U = "Unsupported IOS"
    return {
        "File name":[fname],
        "Host name":[U], "Model number":[U], "Serial number":[U],
        "Interface ip address":[U], "Uptime":[U], "Current s/w version":[U],
        "Last Reboot Reason":[U], "Any Debug?":[U], "CPU Utilization":[U],
        "Total memory":[U], "Used memory":[U], "Free memory":[U], "Memory Utilization (%)":[U],
        "Total flash memory":[U], "Used flash memory":[U], "Free flash memory":[U], "Used Flash (%)":[U],
        "Fan status":[U], "Temperature status":[U], "PowerSupply status":[U], "Available Free Ports":[U],
        "End-of-Sale Date: HW":[U], "Last Date of Support: HW":[U], "End of Routine Failure Analysis Date:  HW":[U],
        "End of Vulnerability/Security Support: HW":[U], "End of SW Maintenance Releases Date: HW":[U],
        "Any Half Duplex":[U], "Interface/Module Remark":[U], "Config Status":[U], "Config Save Date":[U],
        "Critical logs":[U],
        "Current SW EOS":[U], "Suggested s/w ver":[U], "s/w release date":[U],
        "Latest S/W version":[U], "Production s/w is deffered or not?":[U],
        "Remark":[reason_text],
    }

# -------- main entry: read-once → detect → dispatch ------------------------------
def extract(directory_path: str, tech_hint=None):
    rows = []
    if not isinstance(directory_path, str) or not os.path.isdir(directory_path):
        logging.error(f"[facade.extract] bad directory: {directory_path}")
        return rows

    for fn in os.listdir(directory_path):
        if not (fn.endswith(".txt") or fn.endswith(".log")):
            continue
        fp = os.path.join(directory_path, fn)
        if not os.path.isfile(fp):
            continue

        # read once
        try:
            with open(fp, "r", errors="ignore") as f:
                text = f.read()
        except Exception as e:
            rows.append(_placeholder_entry(fp, f"Error: unreadable ({e})"))
            continue

        os_kind = detect_os(text)

        row = None  # <- guard

        if os_kind == "ios_xe":
            try:
                row = IOSXE.process_file(fp)  # your existing XE entrypoint
            except Exception as e:
                row = _placeholder_entry(fp, f"Error: XE parser failed ({e})")

        elif os_kind == "ios":
            if settings.ENABLE_IOS:
                IOS = _load_ios()
                if IOS:
                    try:
                        row = IOS.process_file(fp)  # your IOS entrypoint
                    except Exception as e:
                        row = _placeholder_entry(fp, f"Error: IOS parser failed ({e})")
                else:
                    row = _placeholder_entry(fp, "Info: IOS detected but parser unavailable")
            else:
                row = _placeholder_entry(fp, "Info: IOS detected but disabled by settings")

        else:
            row = _placeholder_entry(fp, "Non-Cisco or unsupported")

        # ✅ Normalize: ensure dict, then add debug tag
        if not isinstance(row, dict):
            row = _placeholder_entry(fp, "Error: parser returned invalid data")
        row.setdefault("__os_kind", os_kind)

        rows.append(row)

    return rows