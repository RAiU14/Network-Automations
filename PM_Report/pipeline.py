# PM_Report/facade.py
import os
import re
import logging

from .Switching.ios_xe import Cisco_IOS_XE as IOSXE  # XE stays eager

from concurrent.futures import ThreadPoolExecutor, as_completed

# -------- lazy loader for IOS (prevents import errors from blocking XE) ----------
def _load_ios():
    try:
        from .Switching.ios import Cisco_IOS as IOS
        return IOS
    except Exception as e:
        logging.warning(f"[Pipeline] IOS parser not loadable: {e}")
        return None


# Toggle classic IOS parsing
ENABLE_IOS = True          # you said enabled

# (Optional, ignore for now) staged rollout 0..1
IOS_ROLLOUT_RATIO = 1.0    # not used yet; full rollout

# --- scope show version (supports dashed & plain echoes) -----------------------
_SHOW_VER_START = re.compile(r'(?im)^\s*-+\s*sh(?:ow)?\s+ver(?:sion)?\s*-+\s*$')
_SHOW_VER_ECHO = re.compile(r'(?im)^.*?\bsh(?:ow)?\s+ver(?:sion)?\s*$')
_NEXT_SECTION   = re.compile(r'(?im)^\s*-+\s*sh(?:ow)?\b')
_NEXT_SECTION_PROMPT = re.compile(r'(?im)^\s*\S+[>#]\s*sh(?:ow)?\b')

def _scope_show_version(text: str) -> str:
    """Extract only the show version block; tolerate dashed or plain echo headers."""
    if not text:
        return ""
    m = _SHOW_VER_START.search(text) or _SHOW_VER_ECHO.search(text)
    if not m:
        logging.debug("No explicit 'show version' header found; returning empty scope.")
        return ""
    start = m.end()
    n = _NEXT_SECTION.search(text, pos=start) or _NEXT_SECTION_PROMPT.search(text, pos=start)
    end = n.start() if n else len(text)
    scoped = text[start:end]
    logging.debug(f"Scoped show-version block size: {len(scoped)} chars.")
    return scoped

# --- scope show inventory (dashed & echo) -------------------------------------
_SHOW_INV_START = re.compile(r'(?im)^\s*-+\s*sh(?:ow)?\s+inventory\s*-+\s*$')
_SHOW_INV_ECHO  = re.compile(r'(?im)^\s*sh(?:ow)?\s+inventory\s*$')

def _scope_show_inventory(text: str) -> str:
    """Extract only the show inventory block; tolerate dashed or plain echo headers."""
    if not text:
        return ""
    m = _SHOW_INV_START.search(text) or _SHOW_INV_ECHO.search(text)
    if not m:
        logging.debug("No explicit 'show inventory' header found; returning empty scope.")
        return ""
    start = m.end()
    # End at next dashed 'show' header or end of text
    n = _NEXT_SECTION.search(text, pos=start)
    end = n.start() if n else len(text)
    scoped = text[start:end]
    logging.debug(f"Scoped show-inventory block size: {len(scoped)} chars.")
    return scoped

# --- router platform hint from show inventory ---------------------------------
# Match common ISR/ASR PIDs in the inventory's "PID:" lines
_INV_PID_LINE = re.compile(r'(?im)^\s*PID:\s*([A-Z0-9\-_/]+)', re.IGNORECASE)

# Families that imply IOS-XE (router)
_INV_ISR = re.compile(r'(?i)\bISR(43\d{1}|44\d{1}|4451|4461|44\d{2}|4\d{2,3})\b|ISR4\d{2,3}')
_INV_ASR = re.compile(r'(?i)\bASR1\d{3}\b|ASR100[0-9]|ASR1001[-A-Z]*')

def _platform_hint_from_inventory(inv_block: str) -> str | None:
    """
    Returns 'ios_xe' if inventory PID lines indicate ISR/ASR family, else None.
    """
    if not inv_block:
        return None
    for m in _INV_PID_LINE.finditer(inv_block):
        pid = m.group(1) or ""
        if _INV_ASR.search(pid) or _INV_ISR.search(pid):
            logging.debug(f"Inventory PID hint suggests router (XE): {pid}")
            return "ios_xe"
    return None

# --- OS detection simplified & hardened ---------------------------------------
def detect_os(text: str) -> str:
    """
    Determine Cisco OS type using the scoped 'show version' block.
    If inconclusive, fall back to scoped 'show inventory' for ISR/ASR hint → ios_xe.
    Returns: 'ios_xe', 'ios', or 'Not an IOS/IOSXE file'.
    """
    logging.debug("[detect_os] Starting refined detection (show-version first).")
    if not text:
        return "Unsupported file"

    ver = _scope_show_version(text)

    # If we truly cannot find a show version block, we will consider an inventory hint later.
    if ver:
        # 1) Disqualify NX-OS / ASA / FTD early based on show version
        if re.search(r'Nexus\s+Operating\s+System\s+\(NX-OS\)|^\s*NXOS:\s+version\b', ver, flags=re.IGNORECASE | re.MULTILINE):
            logging.debug("NX-OS tokens found in show-version → Not IOS/IOSXE.")
            match = re.search(r'Nexus\s+Operating\s+System\s+\(NX-OS\)|^\s*NXOS:\s+version\b', ver, flags=re.IGNORECASE | re.MULTILINE)
            print(match.group(0))
            return "Not an IOS/IOSXE file"
        if re.search(r'\bAdaptive\s+Security\s+Appliance\b|\bFirepower\s+Threat\s+Defense\b', ver, flags=re.IGNORECASE | re.MULTILINE):
            logging.debug("ASA/FTD tokens found in show-version → Not IOS/IOSXE.")
            match = re.search(r'\bAdaptive\s+Security\s+Appliance\b|\bFirepower\s+Threat\s+Defense\b', ver, flags=re.IGNORECASE | re.MULTILINE)
            print(match.group(0))
            return "Not an IOS/IOSXE file"

        # 2) IOS-XE tokens
        if re.search(r'(?i)\bIOS[- ]?XE\b', ver) or re.search(r'(?i)IOS[- ]?XE\s+Software', ver, flags=re.IGNORECASE | re.MULTILINE):
            logging.debug("IOS-XE indicators present in show-version.")
            match = re.search(r'(?i)\bIOS[- ]?XE\b', ver) or re.search(r'(?i)IOS[- ]?XE\s+Software', ver, flags=re.IGNORECASE | re.MULTILINE)
            print(match.group(0))
            return "ios_xe"

        # 3) Classic IOS tokens (ensure no XE)
        if re.search(r'(?i)Cisco\s+IOS\s+Software\b', ver) and not re.search(r'(?i)\bIOS[- ]?XE\b', ver, flags=re.IGNORECASE | re.MULTILINE):
            logging.debug("Classic IOS indicators present in show-version.")
            match = re.search(r'(?i)Cisco\s+IOS\s+Software\b', ver) and not re.search(r'(?i)\bIOS[- ]?XE\b', ver, flags=re.IGNORECASE | re.MULTILINE)
            print(match.group(0))
            return "ios"

    # 4) Fallback: show inventory (router-only hint)
    inv = _scope_show_inventory(text)
    hint = _platform_hint_from_inventory(inv)
    if hint:
        return hint  # 'ios_xe' for ISR/ASR

    # 5) Nothing definitive
    logging.debug("No Cisco OS tokens matched; returning 'Not an IOS/IOSXE file'.")
    return "Not an IOS/IOSXE file"

def detect_os_from_file(file_path: str) -> str:
    try:
        with open(file_path, "r", errors="ignore") as f:
            return detect_os(f.read())
    except Exception:
        return "Not an IOS/IOSXE file"

# -------- placeholder row (keeps your 31-column contract) -----------------------
def _placeholder_entry(file_path, reason_text="Require Manual check"):
    fname = os.path.basename(file_path)
    U = "Not an IOS/IOSXE file"
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
        "__os_kind": "N/A"
    }

def _process_one(fp: str):
        file_name = os.path.basename(fp)
        logging.debug(f"Worker starting processing for {file_name}")
        try:
            with open(fp, "r", errors="ignore") as f:
                text = f.read()
                logging.debug(f"{file_name}: successfully read {len(text)} characters.")
        except Exception as e:
            logging.error(f"{file_name}: Error reading file: {e}")
            return _placeholder_entry(fp, f"Error: unreadable ({e})")

        os_kind = detect_os(text)
        logging.info(f"{file_name}: Detected OS kind: {os_kind}")

        row = None  # guard

        if os_kind == "ios_xe":
            try:
                logging.debug(f"{file_name}: Calling IOSXE parser.")
                row = IOSXE.process_file(fp)  # your existing XE entrypoint
                logging.info(f"{file_name}: IOSXE parser finished.")
            except Exception as e:
                logging.error(f"{file_name}: XE parser failed with exception: {e}")
                row = _placeholder_entry(fp, f"Error: XE parser failed ({e})")

        elif os_kind == "ios":
            if ENABLE_IOS:
                IOS = _load_ios()
                if IOS:
                    try:
                        logging.debug(f"{file_name}: Calling IOS parser.")
                        row = IOS.process_file(fp)  # your IOS entrypoint
                        logging.info(f"{file_name}: IOS parser finished.")
                    except Exception as e:
                        logging.error(f"{file_name}: IOS parser failed with exception: {e}")
                        row = _placeholder_entry(fp, f"Error: IOS parser failed ({e})")
                else:
                    logging.warning(f"{file_name}: IOS detected but parser is unavailable.")
                    row = _placeholder_entry(fp, "Info: IOS detected but parser unavailable")
            else:
                logging.warning(f"{file_name}: IOS detected but disabled by settings.")
                row = _placeholder_entry(fp, "Info: IOS detected but disabled by settings")

        else:
            logging.info(f"{file_name}: File is Non-Cisco or unsupported.")
            row = _placeholder_entry(fp, "Non-Cisco or unsupported")

        # Normalize: ensure dict, then add debug tag
        if not isinstance(row, dict):
            logging.error(f"{file_name}: Parser returned invalid data type ({type(row).__name__}).")
            row = _placeholder_entry(fp, "Error: parser returned invalid data")

        row["__os_kind"] = os_kind # Overwrite the placeholder default with detected kind

        logging.debug(f"Worker finished processing for {file_name}")
        return row

def extract(directory_path: str, tech_hint=None):
    rows = []
    if not isinstance(directory_path, str) or not os.path.isdir(directory_path):
        logging.error(f"[pipeline.extract] Invalid or non-existent directory path: {directory_path}")
        return rows

    # Collect eligible files (stable order)
    candidates = []
    for fn in os.listdir(directory_path):
        if not (fn.endswith(".txt") or fn.endswith(".log")):
            logging.debug(f"Skipping {fn}: not a .txt or .log file.")
            continue
        fp = os.path.join(directory_path, fn)
        if not os.path.isfile(fp):
            logging.warning(f"Skipping {fn}: not a regular file.")
            continue
        candidates.append(fp)

    if not candidates:
        logging.warning(f"No eligible log files found in directory: {directory_path}")
        return rows
    
    logging.info(f"Found {len(candidates)} eligible files for processing.")

    max_workers = min(16, (os.cpu_count() or 4) * 2)
    logging.info(f"Using ThreadPoolExecutor with max_workers={max_workers} for concurrency.")

    results = [None] * len(candidates)

    # I/O-bound concurrency, preserve original order via index
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="extract") as ex:
        future_to_index = {ex.submit(_process_one, fp): i for i, fp in enumerate(candidates)}
        for fut in as_completed(future_to_index):
            i = future_to_index[fut]
            fp = candidates[i]
            file_name = os.path.basename(fp)
            try:
                results[i] = fut.result()
                logging.debug(f"Future completed successfully for {file_name}")
            except Exception as e:
                logging.error(f"Worker future raised for {os.path.basename(fp)}: {e}")
                results[i] = _placeholder_entry(fp, f"Error: worker failed ({e})")

    logging.info("All file futures completed. Collecting results.")

    # Keep behavior: only collect valid dicts, in stable order
    for r in results:
        if isinstance(r, dict) and r:
            rows.append(r)
    
    logging.info(f"Extraction pipeline finished. Collected {len(rows)} report entries.")

    return rows

def test_os():
    directory_path = r"C:\Users\girish.n\Downloads\PM logs sets\Ultimate_logs"
    count, ios, iosxe, non = 0, 0, 0, 0
    for file_name in os.listdir(directory_path):
        file_path = os.path.join(directory_path, file_name)
        if os.path.isfile(file_path):
            os_kind = detect_os_from_file(file_path)
            count += 1
            print(f"{file_name}: {os_kind}")
            if os_kind == "ios":
                ios += 1
            elif os_kind == "ios_xe":
                iosxe += 1
            else:
                non += 1
    return count, ios, iosxe, non

if __name__ == "__main__":
    count, ios, iosxe, non = test_os()
    print(f"Total files: {count}, IOS: {ios}, IOS-XE: {iosxe}, Non-IOS: {non}")