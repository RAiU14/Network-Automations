import re
import os
import logging
import datetime
from typing import List, Dict, Union
    
# Static strings
NA = "Not available"
YET_TO_CHECK = "Yet to check"

log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
# Configure logging only once to avoid collisions when multiple modules import each other
if not logging.getLogger().handlers:
    logging.basicConfig(
        filename=os.path.join(log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"),
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

# Stanza splitter: grabs each "interface ..." block (multiline)
_INTERFACE_BLOCK_RE = re.compile(r'(?ms)^interface\s+\S+.*?(?=^interface\s+\S+|\Z)')

# IP line patterns inside a stanza (IOS/IOS-XE typical):
# - "ip address 10.1.2.3 255.255.255.0"
# - "ip address 10.1.2.3/24"
# - may be followed by "secondary" (we ignore those and take the primary)
_IP_LINE_RE = re.compile(
    r'^\s*ip\s+address\s+'
    r'(?P<ip>\d{1,3}(?:\.\d{1,3}){3})'
    r'(?:\s+(?:\d{1,3}(?:\.\d{1,3}){3}|/\d{1,2}))?'
    r'(?:\s+secondary)?\s*$',
    re.IGNORECASE | re.MULTILINE
)

_IP_RE = re.compile(r'^\s*(\d+)\.(\d+)\.(\d+)\.(\d+)\s*$')

def sanitize_ipv4(value: str) -> str:
    if value is None:
        return "Not available"
    s = str(value).strip()
    if s == "" or s.lower() in {"n/a", "na", "not available", "unavailable"}:
        return "Not available"

    if "/" in s:
        s = s.split("/", 1)[0].strip()
    elif " " in s and _IP_RE.search(s.split(" ")[0] or ""):
        s = s.split(" ", 1)[0].strip()

    m = _IP_RE.match(s)
    if not m:
        return "Require Manual Check"

    octets = [int(x) for x in m.groups()]
    if any(o < 0 or o > 255 for o in octets):
        return "Require Manual Check"

    s_norm = ".".join(str(o) for o in octets)
    if s_norm in {"0.0.0.0", "255.255.255.255"}:
        return "Require Manual Check"
    return s_norm

def get_ip(log_data: str):
    try:
        #
        return "Require Manual Check"
    except Exception:
        return None

def log_type(log_data):
    if not isinstance(log_data, str):
        logging.error("Invalid input type for log_data")
        return f"Not a .txt or.log file"

def get_hostname(log_data):
    try:
        logging.info("Starting hostname search.")
        match = re.search(r"hostname\s+(\S+)", log_data)
        logging.debug("Category Search Completed.")
        return match.group(1) if match else "Require Manual Check"
    except Exception as e:
        logging.debug("Category Search failed - hostname not found in log.")
        return f"Require Manual Check"

def get_model_number(log_data: str) -> str:
    """
    Extract router model (PID) from show inventory or license section.
    Works for ASR, ISR, C8K routers.
    """
    try:
        logging.info("Starting model number extraction.")

        if not log_data:
            return "Require Manual Check"

        # Look for "PID:" fields (core chassis, RP, or module lines)
        pattern = re.compile(
            r'(?mi)(?:^|\n)\s*PID:\s*([A-Z0-9\-_/]+)\s*,\s*VID:',
        )
        pids = pattern.findall(log_data)
        if pids:
            # Prioritize chassis-like or route-processor identifiers
            for pid in pids:
                if re.search(r'(?:ASR|ISR|C8\d{3,4}|C8300|C8000)', pid, re.I):
                    logging.debug(f"Model PID found: {pid}")
                    return pid.strip()
            # otherwise return first valid PID
            return pids[0].strip()

        # fallback: license section (e.g. "license udi pid ISR4461/K9 sn FDO...")
        lic_match = re.search(r'(?mi)license\s+udi\s+pid\s+(\S+)', log_data)
        if lic_match:
            model = lic_match.group(1).strip()
            logging.debug(f"Model extracted from license section: {model}")
            return model

        logging.warning("Model number not found. Returning 'Require Manual Check'.")
        return "Require Manual Check"

    except Exception as e:
        logging.error(f"Error in get_model_number: {e}")
        return "Require Manual Check"

def get_ip_address(file_path):
    try:
        logging.info("Starting IP address extraction from file path.")
        file_name = os.path.basename(file_path) if isinstance(file_path, str) else str(file_path)
        logging.debug(f"Target file name is: {file_name}")

        # 1) Filename-first: collect candidates, return the first that sanitizes cleanly
        logging.debug("Attempting to find IP address within the filename.")
        filename_candidates = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?)", file_name)
        logging.debug(f"Found {len(filename_candidates)} candidates in filename.")

        for cand in filename_candidates:
            ip_norm = sanitize_ipv4(cand)
            if ip_norm not in {"Not available", "Require Manual Check"}:
                logging.info(f"Successfully extracted and sanitized IP from filename: {ip_norm}")
                return (file_name, ip_norm)
            logging.debug(f"Skipping filename candidate '{cand}' as invalid after sanitization.")
        
        logging.debug("No valid IP address found in filename. Proceeding to file content.")

        # 2) Content fallback (only if needed)
        try:
            with open(file_path, "r", errors="ignore") as f:
                log_data = f.read()
            logging.debug(f"Successfully read file content ({len(log_data)} chars) for content search.")

            # Find all IPv4-ish tokens (allowing optional CIDR), sanitize each, pick first valid
            content_candidates = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?)", log_data)
            logging.debug(f"Found {len(content_candidates)} candidates in file content.")

            for cand in content_candidates:
                ip_norm = sanitize_ipv4(cand)
                if ip_norm not in {"Not available", "Require Manual Check"}:
                    logging.info(f"Successfully extracted and sanitized IP from file content: {ip_norm}")
                    return (file_name, ip_norm)
                logging.debug(f"Skipping content candidate '{cand}' as invalid after sanitization.")

            logging.debug("No valid IP address found via simple regex scan of content. Trying helper function.")

            # --- Last chance: call existing get_ip helper if available ---
            try:
                from_content = get_ip(log_data)
                logging.debug(f"Result from get_ip helper: {from_content}")

                ip_norm = sanitize_ipv4(from_content)
                if ip_norm not in {"Not available", "Require Manual Check"}:
                    logging.info(f"Successfully extracted and sanitized IP via get_ip helper: {ip_norm}")
                    return (file_name, ip_norm)
                logging.debug(f"get_ip helper result was invalid after final sanitization.")
            except NameError:
                 logging.warning(f"get_ip helper is not defined, skipping final content check for {file_name}.")
            except Exception as e:
                # LOGGING PRESENT: Helper function failure
                logging.warning(f"get_ip helper failed on {file_name}: {e}")

        except Exception as inner:
            logging.warning(f"Content fallback failed while reading {file_name}: {inner}")

        logging.info("No valid IP found in filename or content; returning 'Require Manual Check'.")
        return (file_name, "Require Manual Check")

    except Exception as e:
        logging.error(f"Critical error in get_ip_address: {str(e)}")
        safe_name = os.path.basename(file_path) if isinstance(file_path, str) else "UNKNOWN"
        return (safe_name, "Require Manual Check")

def get_serial_number(log_data: str) -> str:
    """
    Extract router serial number (SN) from show inventory or license section.
    Works for ASR, ISR, C8K routers.
    """
    try:
        logging.info("Starting serial number extraction.")

        if not log_data:
            return "Require Manual Check"

        # Look for SN in show inventory
        pattern = re.compile(
            r'(?mi)\bSN:\s*([A-Z0-9]+)\b'
        )
        sns = pattern.findall(log_data)
        if sns:
            # prefer 10–12 char SNs (typical Cisco format)
            for sn in sns:
                if 8 <= len(sn) <= 14:
                    logging.debug(f"Serial found: {sn}")
                    return sn.strip()
            return sns[0].strip()

        # fallback: license UDI line
        lic_match = re.search(r'(?mi)license\s+udi\s+pid\s+\S+\s+sn\s+([A-Z0-9]+)', log_data)
        if lic_match:
            serial = lic_match.group(1).strip()
            logging.debug(f"Serial extracted from license section: {serial}")
            return serial

        logging.warning("Serial number not found. Returning 'Require Manual Check'.")
        return "Require Manual Check"

    except Exception as e:
        logging.error(f"Error in get_serial_number: {e}")
        return "Require Manual Check"

def get_uptime(log_data):
    try:
        logging.info("Starting uptime search.")
        hostname = get_hostname(log_data)
        logging.debug(f"Hostname obtained for uptime search: '{hostname}'")
        # If hostname isn't available, don't attempt a bogus regex match
        if not hostname or hostname == "Not available":
            logging.debug("Uptime search skipped due to unavailable hostname.")
            return "Not available"
        # Escape hostname to prevent regex meta-characters from breaking the pattern
        escaped_hostname = re.escape(hostname)
        pattern = rf"{escaped_hostname}\s+uptime is\s+(.+)"
        logging.debug(f"Searching for uptime using pattern: '{pattern}'")
        match = re.search(pattern, log_data)
        if match:
            uptime_result = match.group(1).strip()
            logging.info(f"Successfully extracted uptime: {uptime_result}")
            return uptime_result
        else:
            # ACTION 4a: Return fallback if no match
            logging.info("Uptime pattern did not match. Returning 'Require Manual Check'.")
            return "Require Manual Check"
    except Exception as e:
        logging.error(f"Error in get_uptime: {str(e)}")
        return f"Require Manual Check"

def get_current_sw_version(log_data: str) -> str:
    try:
        logging.info("Starting software version extraction (ASR/ISR/C8k-safe).")
        if not log_data:
            logging.debug("Empty log. Returning 'Not available'.")
            return "Not available"

        # Narrow to the most likely local blocks to avoid matching CDP neighbors:
        # Prefer text right after a "show ver(son)" command if present.
        m_block = re.search(r'(?is)(?:^|\n)[^\n#]*#\s*sh(?:ow)?\s+ver(?:sion)?\b(.{0,4000})', log_data)
        likely = m_block.group(0) if m_block else log_data

        # 1) Explicit IOS XE banner
        m = re.search(r'(?mi)Cisco\s+IOS\s+XE\s+Software,\s*Version\s+([0-9A-Za-z.\(\)-]+)', likely)
        if m:
            v = m.group(1).strip()
            logging.info(f"Version (IOS XE explicit): {v}")
            return v

        # 2) Classic IOS banner
        m = re.search(r'(?mi)Cisco\s+IOS\s+Software.*?\bVersion\s+([0-9A-Za-z.\(\)-]+)', likely)
        if m:
            v = m.group(1).strip()
            logging.info(f"Version (IOS classic banner): {v}")
            return v

        # 3) Platform-tag banners used by ASR/ISR/C8k (e.g., asr1000, isr4k, c8000be)
        m = re.search(
            r'(?mi)^\s*(?:asr\d{3,4}\w*|isr\d{3,4}\w*|c[89]000\w*)\s+Software.*?\bVersion\s+([0-9A-Za-z.\(\)-]+)',
            likely
        )
        if m:
            v = m.group(1).strip()
            logging.info(f"Version (platform-tag banner): {v}")
            return v

        # 4) "Image Version = <... Version X>" (often in redundancy output)
        m = re.search(r'(?mi)Image\s+Version\s*=\s*.*?\bVersion\s+([0-9A-Za-z.\(\)-]+)', log_data)
        if m:
            v = m.group(1).strip()
            logging.info(f"Version (Image Version = ...): {v}")
            return v

        # 5) Pull from system image filename (…universalk9.<version>.SPA.bin)
        m = re.search(r'(?mi)System\s+image\s+file\s+is\s+".*?\b(\d+\.\d+(?:\.\d+)?[a-z]?)\b', log_data)
        if m:
            v = m.group(1).strip()
            logging.info(f"Version (from image filename): {v}")
            return v

        # 6) Fallback: running-config line "version X[.Y[.Z]]" (train only)
        # Limit to first 200 lines to avoid matching neighbors’ config dumps.
        head = "\n".join(log_data.splitlines()[:200])
        m = re.search(r'(?mi)^\s*version\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)\b', head)
        if m:
            v = m.group(1).strip()
            logging.warning(f"Version (running-config train only): {v}")
            return v

        logging.info("No version found. Returning 'Not available'.")
        return "Not available"

    except Exception as e:
        logging.error(f"Error in get_current_sw_version: {e}")
        return "Not available"

def get_last_reboot_reason(log_data):
    try:
        logging.info("Starting last reboot reason search.")
        
        # First try to match "Last reload reason"
        logging.debug("Attempt 1: Searching for 'Last reload reason'.")
        match = re.search(r"Last reload reason\s*:\s*(.+)", log_data, re.IGNORECASE)
        if match:
            result = match.group(1).strip()
            logging.info(f"Reboot reason found (Attempt 1): {result}")
        else:
            # Fallback: match "System returned to ROM by ..."
            logging.debug("Attempt 1 failed. Attempt 2: Searching for 'System returned to ROM by'.")
            match = re.search(r"System returned to ROM by\s+(.+)", log_data, re.IGNORECASE)
            if match:
                result = match.group(1).strip()
                logging.info(f"Reboot reason found (Attempt 2, fallback): {result}")
            else:
                # ACTION 3: Return final fallback
                result = "Require Manual Check"
                logging.info("No common reboot reason pattern matched. Returning 'Require Manual Check'.")
        
        logging.debug("Last reboot reason search completed.")
        return result

    except Exception as e:
        logging.error(f"Error in get_last_reboot_reason: {str(e)}")
        return f"Require Manual Check"

def get_cpu_utilization(log_data):
    try:
        logging.info("Starting CPU utilization search.")
        logging.debug("Searching for 'five minutes: <util>%' pattern.")
        match = re.search(r"five minutes:\s+(\d+)%", log_data)
        if match:
            # ACTION 2a: Format and return the result
            cpu_util = match.group(1) + "%"
            logging.info(f"Successfully extracted 5-minute CPU utilization: {cpu_util}")
            return cpu_util
        else:
            # ACTION 2b: Return fallback if no match
            logging.info("CPU utilization pattern did not match. Returning 'Require Manual Check'.")
            return "Require Manual Check"
    except Exception as e:
        logging.error(f"Error in get_cpu_utilization: {str(e)}")
        return f"Require Manual Check"

def get_memory_info(log_data):
    """
    Return [total_bytes, used_bytes, free_bytes, 'used_pct%'] from router logs.
    Prefers canonical 'show memory statistics' table; falls back to pool summary.
    Works across ASR / ISR / C8k samples you've provided.
    """
    try:
        logging.info("Starting memory info extraction.")
        if not log_data:
            return ["Not available", "Not available", "Not available", "Not available"]

        # --- A) Canonical table row under 'show memory statistics' ---
        # Example:
        #   Processor  7F...  3840898288  401685452  3439212836 ...
        m = re.search(
            r'(?mi)^\s*Processor\s+\S+\s+(\d+)\s+(\d+)\s+(\d+)',
            log_data
        )
        if m:
            total = int(m.group(1))
            used  = int(m.group(2))
            free  = int(m.group(3))
            pct   = f"{(used / total * 100):.2f}%" if total else "Not available"
            logging.info(f"Memory (table): total={total} used={used} free={free} util={pct}")
            return [str(total), str(used), str(free), pct]

        # --- B) Pool summary one-liner (from 'show process memory sorted') ---
        # Example:
        #   Processor Pool Total: 1690459984 Used:  362785224 Free: 1327674760
        m = re.search(
            r'(?mi)Processor\s+Pool\s+Total:\s*(\d+)\s*Used:\s*(\d+)\s*Free:\s*(\d+)',
            log_data
        )
        if m:
            total = int(m.group(1))
            used  = int(m.group(2))
            free  = int(m.group(3))
            pct   = f"{(used / total * 100):.2f}%" if total else "Not available"
            logging.info(f"Memory (pool): total={total} used={used} free={free} util={pct}")
            return [str(total), str(used), str(free), pct]

        # Last-chance: try near the top (some captures truncate later sections)
        head = "\n".join(log_data.splitlines()[:400])
        m = re.search(r'(?mi)Processor\s+Pool\s+Total:\s*(\d+)\s*Used:\s*(\d+)\s*Free:\s*(\d+)', head)
        if m:
            total = int(m.group(1))
            used  = int(m.group(2))
            free  = int(m.group(3))
            pct   = f"{(used / total * 100):.2f}%" if total else "Not available"
            logging.info(f"Memory (pool/head): total={total} used={used} free={free} util={pct}")
            return [str(total), str(used), str(free), pct]

        logging.warning("No memory statistics matched.")
        return ["Not available", "Not available", "Not available", "Not available"]

    except Exception as e:
        logging.error(f"Error in get_memory_info: {str(e)}")
        return ["Not available", "Not available", "Not available", "Not available"]

def get_flash_info(log_data: str):
    """
    Parse bootflash usage ONLY from show tech output.
    Returns [total_bytes, used_bytes, free_bytes, 'used_pct%'] as strings.
    Handles:
      - 'show bootflash' / 'show bootflash: all'
      - 'Directory of bootflash:' or 'Directory of bootflash:/'
      - Summary lines placed far below the directory listing
    """
    try:
        logging.info("Starting flash info extraction (bootflash only).")
        NA = ["Not available", "Not available", "Not available", "Not available"]
        if not log_data:
            return NA

        # Summary patterns
        pat_avail_used = re.compile(
            r'(?mi)\b(\d+)\s+bytes\s+available\s*\(\s*(\d+)\s+bytes\s+used\s*\)'
        )
        pat_total_free = re.compile(
            r'(?mi)\b(\d+)\s+bytes\s+total\s*\(\s*(\d+)\s+bytes\s+free\s*\)'
        )

        def as_row_from_avail_used(avail:int, used:int):
            total = avail + used
            pct = f"{(used / total * 100):.2f}%" if total else "Not available"
            return [str(total), str(used), str(avail), pct]

        def as_row_from_total_free(total:int, free:int):
            used = max(total - free, 0)
            pct = f"{(used / total * 100):.2f}%" if total else "Not available"
            return [str(total), str(used), str(free), pct]

        # ---- 1) Try to carve a reliable bootflash block ----
        # A) From 'show bootflash' header to 'Filesystem: bootflash'
        m_hdr = re.search(r'(?is)(^[-\s]*show\s+bootflash(?::\s*all)?\s*-*.*?$)', log_data)
        m_fs  = re.search(r'(?is)^Filesystem:\s*bootflash\b.*?$', log_data)
        if m_hdr and m_fs and m_fs.start() > m_hdr.start():
            blk = log_data[m_hdr.start():m_fs.end()+500]  # include trailer
            m = pat_avail_used.search(blk)
            if m:
                avail, used = int(m.group(1)), int(m.group(2))
                logging.info("Bootflash summary found (show bootflash block, avail/used).")
                return as_row_from_avail_used(avail, used)
            m = pat_total_free.search(blk)
            if m:
                total, free = int(m.group(1)), int(m.group(2))
                logging.info("Bootflash summary found (show bootflash block, total/free).")
                return as_row_from_total_free(total, free)

        # B) From 'Directory of bootflash' to 'Filesystem: bootflash'
        m_dir = re.search(r'(?is)^Directory\s+of\s+bootflash:\/?\s*$', log_data, re.MULTILINE)
        if m_dir:
            # Look far enough to cover very long listings but keep bounded
            end = m_fs.end()+500 if m_fs and m_fs.start() > m_dir.start() else min(len(log_data), m_dir.end()+250000)
            blk = log_data[m_dir.start():end]
            # Fast skip if explicitly no info
            if re.search(r'(?mi)No\s+space\s+information\s+available', blk):
                logging.warning("Bootflash block says: No space information available.")
                return NA
            m = pat_avail_used.search(blk)
            if m:
                avail, used = int(m.group(1)), int(m.group(2))
                logging.info("Bootflash summary found (dir block, avail/used).")
                return as_row_from_avail_used(avail, used)
            m = pat_total_free.search(blk)
            if m:
                total, free = int(m.group(1)), int(m.group(2))
                logging.info("Bootflash summary found (dir block, total/free).")
                return as_row_from_total_free(total, free)

        # ---- 2) Global fallback with context guard (bootflash nearby) ----
        for m in pat_avail_used.finditer(log_data):
            span_start, span_end = max(0, m.start()-2000), min(len(log_data), m.end()+500)
            ctx = log_data[span_start:span_end]
            if re.search(r'(?mi)\bFilesystem:\s*bootflash\b', ctx) or \
               re.search(r'(?mi)^Directory\s+of\s+bootflash:\/?\s*$', ctx):
                avail, used = int(m.group(1)), int(m.group(2))
                logging.info("Bootflash summary found (global, avail/used, context-verified).")
                return as_row_from_avail_used(avail, used)

        for m in pat_total_free.finditer(log_data):
            span_start, span_end = max(0, m.start()-2000), min(len(log_data), m.end()+500)
            ctx = log_data[span_start:span_end]
            if re.search(r'(?mi)\bFilesystem:\s*bootflash\b', ctx) or \
               re.search(r'(?mi)^Directory\s+of\s+bootflash:\/?\s*$', ctx):
                total, free = int(m.group(1)), int(m.group(2))
                logging.info("Bootflash summary found (global, total/free, context-verified).")
                return as_row_from_total_free(total, free)

        logging.warning("No bootflash space summary matched.")
        return NA

    except Exception as e:
        logging.error(f"Error in get_flash_info: {e}")
        return ["Not available", "Not available", "Not available", "Not available"]

# ====================================================================
# DYNAMIC PATTERN DEFINITIONS
# These patterns are the core of the temperature status function.
# NOTE: Named groups (?P<ID> and ?P<STATUS>) are used for dynamic extraction.
# ====================================================================
TEMPERATURE_PATTERNS = {
    # ------------------- TIER 1: POSITIVE PATTERNS -------------------
    "positive_patterns": [
        {
            "name": "P1.1_System_Summary_OK",
            "description": "Matches 'Switch N: SYSTEM TEMPERATURE is OK' (Catalyst Summary)",
            "regex": r"Switch\s+(?P<ID>\d+):\s*SYSTEM\s+TEMPERATURE\s+is\s+OK\s*$",
            "source_type": "Switch"
        },
        {
            "name": "P1.2_Global_State_GREEN",
            "description": "Matches 'Temperature State: GREEN' (Catalyst Summary)",
            "regex": r"Temperature\s+State\s*:\s*GREEN\s*$",
            "source_type": "Global"
        },
        {
            "name": "P1.3_Sensor_List_Switch_GREEN",
            "description": "Matches 'SYSTEM INLET N GREEN' or 'SYSTEM HOTSPOT N GREEN' (Catalyst 9200 Sensor List)",
            "regex": r"SYSTEM\s+(?:INLET|OUTLET|HOTSPOT)\s+(?P<ID>\d+)\s+GREEN\s+",
            "source_type": "Switch"
        },
        {
            "name": "P1.5_Environmental_Alarms_Clear",
            "description": "Matches explicit 'environmental alarms: no alarms' (General Positive)",
            "regex": r"environmental\s+alarms:\s+no\s+alarms",
            "source_type": "Global"
        },
        {
            "name": "P1.7_No_Temp_Alarms",
            "description": "Matches the global 'no temperature alarms' header (4500/6500)",
            "regex": r"no\s+temperature\s+alarms",
            "source_type": "Global"
        },
        {
            "name": "P1.8_Sensor_Table_OK",
            "description": "Matches the modular table rows with explicit 'ok' status (4500/6500)",
            # ID is Module ID, status is implicit 'ok'
            "regex": r"^\s*(?P<ID>\d+)\s+.*?\(\s*\d+C,\d+C,\d+C\)\s*ok",
            "source_type": "Switch"
        }
    ],
    # ------------------- TIER 2: NEGATIVE PATTERNS -------------------
    "negative_patterns": [
        {
            "name": "N2.1_Explicit_Critical_State",
            "description": "Matches explicit failure keywords like CRITICAL or RED in status fields",
            "regex": r"(?:Status|State|System\s+Temperature)\s*:\s*(CRITICAL|RED|FAULT|FAILED|WARNING|ALERT)",
            "source_type": "Global"
        },
        {
            "name": "N2.2_System_Summary_NOT_OK",
            "description": "Matches 'SYSTEM TEMPERATURE is NOT OK' (Catalyst Summary)",
            "regex": r"Switch\s+(?P<ID>\d+):\s*SYSTEM\s+TEMPERATURE\s+is\s+NOT\s*OK\s*$",
            "source_type": "Switch"
        }
    ]
}

def extract_env_sections(log_data: str) -> str:
    """
    Extracts content blocks likely from 'show environment' commands.
    This ensures the parser only looks at relevant data.
    """
    sections = []
    
    # 1. Search for commands in a command prompt environment (e.g., 'SWITCH#show env')
    command_blocks = re.split(r'(?m)^[^\r\n#]*#\s*', log_data)
    for block in command_blocks:
        if re.match(r'(?i)^\s*sh(?:ow)?\s+env(?:ironment)?(?:\s+all)?', block.strip()):
            sections.append(block.strip())

    if not sections:
        # 2. Fallback for log formats where commands are wrapped in dashes (e.g., 'show tech')
        pattern_dash = r"(-{5,}\s*show environment(?:\s+all)?\s*-{5,}[\s\S]*?-{5,}\s*show)"
        matches_dash = re.findall(pattern_dash, log_data, re.IGNORECASE | re.DOTALL)
        sections.extend(matches_dash)
        
    if not sections:
        # 3. Final attempt: Return the whole log if it seems like a show env output without header
        if re.search(r'(?mi)temperature|temp|hotspot', log_data):
            return log_data

    return "\n".join(sections)

def get_temperature_status(log_data: str) -> list[str]:
    """
    Routers: overall Temperature health from env outputs.
    Returns exactly one value: ["OK"] | ["NOT OK"] | ["Not available"].

    Rules:
      - If any temperature-related line shows Warning/Failed/Critical/etc -> ["NOT OK"]
      - "Not Present"/"N/A"/"Absent" are ignored
      - If nothing temperature-related is found -> ["Not available"]

    Sources in this order (with abbreviations handled):
      1) show environment all   (show env all / sh environment all / sh env all)
      2) show environment       (show env / sh environment / sh env)
      3) show platform hardware chassis environment all
      4) show platform power / show power  (rarely has temps; included just in case)
    """
    logging.info("Starting temperature status extraction (routers)")

    # ---------- helpers kept INSIDE the function ----------
    def _cmd_block_regex(cmd_variants: list[str]) -> re.Pattern:
        dash_cmds = [re.escape(cv) for cv in cmd_variants]
        dash = rf"(?:-{{5,}}\s*(?:{'|'.join(dash_cmds)})\s*-{{5,}})"
        echo = rf"(?:^|\n)\s*(?:{'|'.join(dash_cmds)})\s*(?:\r?\n|$)"
        return re.compile(rf"(?is){dash}|{echo}")

    def _find_block(log: str, cmd_variants: list[str]) -> str | None:
        start_pat = _cmd_block_regex(cmd_variants)
        m = start_pat.search(log)
        if not m:
            return None
        start = m.end()
        m2 = re.search(r"(?is)\n-+\s*show\s+.+?-+\s*\n", log[start:])
        if m2:
            return log[start:start + m2.start()]
        m3 = re.search(r"(?im)^\s*show\s+\S.*$", log[start:])
        if m3:
            return log[start:start + m3.start()]
        return log[start:]

    def _state_of_line(line: str) -> str | None:
        s = line.lower()
        if re.search(r"\b(not\s*present|n/?a|absent)\b", s):
            return "IGNORE"
        if re.search(r"\b(normal|good|ok)\b", s):
            return "OK"
        if re.search(r"\b(warn|fault|fail|critical|shutdown|alarm|bad|not\s*ok|degraded|overheat|over\s*temp)\b", s):
            return "NOT OK"
        return None

    def _overall_temp_from_block(block: str) -> list[str]:
        if not block:
            return ["Not available"]
        lines = block.splitlines()
        any_relevant = False
        for ln in lines:
            l = ln.strip()
            if not l:
                continue
            # Temperature relevance
            if not re.search(r"\b(Temp|Temperature|Celsius|°C|Hotspot|Inlet|Outlet)\b", l, re.I):
                continue
            any_relevant = True
            st = _state_of_line(l)
            if st == "NOT OK":
                return ["NOT OK"]
            # OK/IGNORE continue
        return ["OK"] if any_relevant else ["Not available"]

    def _gather_blocks(log: str) -> list[str]:
        search_order = [
            ["show environment all", "show env all", "sh environment all", "sh env all"],
            ["show environment", "show env", "sh environment", "sh env"],
            ["show platform hardware chassis environment all"],
            ["show platform power", "show power"],
        ]
        blocks = []
        for variants in search_order:
            blk = _find_block(log, variants)
            if blk:
                blocks.append(blk)
        return blocks
    # ---------- end helpers ----------

    try:
        for blk in _gather_blocks(log_data):
            res = _overall_temp_from_block(blk)
            if res[0] != "Not available":
                logging.info(f"Temperature overall status: {res[0]}")
                return res

        logging.warning("No Temperature-relevant environment info found in any block")
        return ["Not available"]

    except Exception as e:
        logging.error(f"Error in get_temperature_status: {e}")
        return ["Not available"]

# Helper to check if a state string is "OK" (Unchanged)
def is_fan_ok(state: str) -> bool:
    """Checks if a fan state string indicates an 'OK' status."""
    st = state.strip().upper()
    return st == "OK" or "NOT PRESENT" in st or st == "GOOD" or st == "NORMAL" or st == "FANTRAY_OK" or st == "GREEN"

# Helper for extracting environment sections (Unchanged)
def extract_env_sections(log_data: str) -> str:
    sections = []
    # Simplified command extraction for brevity
    command_blocks = re.split(r'(?m)^[^\r\n#]*#\s*', log_data)
    
    for block in command_blocks:
        if re.match(r'(?i)^\s*sh(?:ow)?\s+env(?:ironment)?(?:\s+all)?', block.strip()):
            sections.append(block.strip())

    if not sections:
        pattern_dash = r"(-{5,}\s*show environment(?:\s+all)?\s*-{5,}[\s\S]*?-{5,}\s*show)"
        matches_dash = re.findall(pattern_dash, log_data, re.IGNORECASE | re.DOTALL)
        sections.extend(matches_dash)
    
    return "\n".join(sections)

def get_fan_status(log_data: str) -> list[str]:
    """
    Routers: overall FAN health from env/power outputs.
    Returns exactly one value: ["OK"] | ["NOT OK"] | ["Not available"].

    Rules:
      - If any fan-related line shows Warning/Failed/Critical/etc -> ["NOT OK"]
      - "Not Present"/"N/A"/"Absent" are ignored (do not flip to NOT OK)
      - OK/Normal/Good / speed-only lines keep scanning
      - If nothing fan-related is found in any block -> ["Not available"]

    Sources in this order (with abbreviations handled):
      1) show environment all   (show env all / sh environment all / sh env all)
      2) show environment       (show env / sh environment / sh env)
      3) show platform hardware chassis environment all
      4) show platform power / show power
    """
    logging.info("Starting fan status extraction (routers)")

    # ---------- helpers kept INSIDE the function ----------
    def _cmd_block_regex(cmd_variants: list[str]) -> re.Pattern:
        # dashed show-tech style: ------------------ show environment all ------------------
        dash_cmds = [re.escape(cv) for cv in cmd_variants]
        dash = rf"(?:-{{5,}}\s*(?:{'|'.join(dash_cmds)})\s*-{{5,}})"
        # plain echo: show environment all
        echo = rf"(?:^|\n)\s*(?:{'|'.join(dash_cmds)})\s*(?:\r?\n|$)"
        return re.compile(rf"(?is){dash}|{echo}")

    def _find_block(log: str, cmd_variants: list[str]) -> str | None:
        start_pat = _cmd_block_regex(cmd_variants)
        m = start_pat.search(log)
        if not m:
            return None
        start = m.end()

        # Prefer to end at next dashed section header that starts with 'show ...'
        m2 = re.search(r"(?is)\n-+\s*show\s+.+?-+\s*\n", log[start:])
        # Or end at next CLI echo of a show command
        m3 = re.search(r"(?im)^\s*show\s+\S.*$", log[start:])
        # Choose the earlier boundary if both exist
        cuts = [c.start() for c in (m2, m3) if c]
        if cuts:
            end = start + min(cuts)
            return log[start:end]
        return log[start:]

    def _state_of_line(line: str) -> str | None:
        s = line.lower()
        # ignore when not installed or N/A
        if re.search(r"\b(not\s*present|n/?a|absent)\b", s):
            return "IGNORE"
        # good/ok/normal states
        if re.search(r"\b(normal|good|ok)\b", s):
            return "OK"
        # problem indicators commonly seen across platforms
        if re.search(r"\b(warn|warning|fault|fail|failed|critical|shutdown|alarm|bad|not\s*ok|degraded|stalled|not\s*spinning)\b", s):
            return "NOT OK"
        return None  # unknown; don’t count either way

    def _overall_fan_from_block(block: str) -> list[str]:
        if not block:
            return ["Not available"]

        lines = block.splitlines()
        any_relevant = False

        # 1) Classic SYSTEM FAN STATUS section (e.g., ISR 39xx)
        #    Lines like: "Fan 1 OK", "Fan 2 Not Present", "Fan 3 Fail"
        for ln in lines:
            if re.search(r"(?i)^\s*system\s+fan\s+status\b", ln):
                any_relevant = True
                # scan subsequent lines until a blank or non-fan line
                for row in lines[lines.index(ln)+1:]:
                    r = row.strip()
                    if not r:
                        break
                    if not re.search(r"(?i)\bfan\s*\d+", r):
                        # allow lines like "Blower 0 OK"
                        if not re.search(r"(?i)\b(blower|tray)\b", r):
                            break
                    st = _state_of_line(r)
                    if st == "NOT OK":
                        return ["NOT OK"]
                # If we had a SYSTEM FAN STATUS header and didn't see NOT OK, that's OK
                return ["OK"]

        # 2) Compact summaries (Catalyst 8k style): "FC FANS:  Fan1 Fan2 OK"
        for ln in lines:
            l = ln.strip()
            if re.search(r"(?i)\bFC\s*FANS\b", l) or re.search(r"(?i)\bfan(?:\s*tray)?\b", l):
                if re.search(r"(?i)\b(ok)\b", l):
                    any_relevant = True
                if re.search(r"(?i)\b(fail|fault|critical|alarm|not\s*ok|shutdown|bad)\b", l):
                    return ["NOT OK"]

        # 3) Speed-only hints (ASR/C8k/ISR): "Fan Speed 65%" / "RPM: fan0 ... 5320 RPM"
        for ln in lines:
            l = ln.strip()
            if re.search(r"(?i)\bfan\s*speed\b|\brpm\b", l):
                any_relevant = True
                # If a line explicitly has a bad token, mark NOT OK; else treat speed as OK indicator
                if re.search(r"(?i)\b(fail|fault|critical|alarm|not\s*ok|shutdown|bad|stalled|not\s*spinning)\b", l):
                    return ["NOT OK"]

        # 4) General fan relevance pass (catch-alls)
        for ln in lines:
            l = ln.strip()
            if not l:
                continue
            if re.search(r"(?i)\b(fan|blower)\b", l):
                any_relevant = True
                st = _state_of_line(l)
                if st == "NOT OK":
                    return ["NOT OK"]

        return ["OK"] if any_relevant else ["Not available"]

    def _gather_blocks(log: str) -> list[str]:
        search_order = [
            ["show environment all", "show env all", "sh environment all", "sh env all"],
            ["show environment", "show env", "sh environment", "sh env"],
            ["show platform hardware chassis environment all"],
            ["show platform power", "show power"],
        ]
        blocks = []
        for variants in search_order:
            blk = _find_block(log, variants)
            if blk:
                blocks.append(blk)
        return blocks
    # ---------- end helpers ----------

    try:
        for blk in _gather_blocks(log_data):
            res = _overall_fan_from_block(blk)
            if res[0] != "Not available":
                logging.info(f"Fan overall status: {res[0]}")
                return res

        logging.warning("No Fan-relevant environment info found in any block")
        return ["Not available"]

    except Exception as e:
        logging.error(f"Error in get_fan_status: {e}")
        return ["Not available"]
 
def get_power_supply_status(log_data: str) -> list[str]:
    """
    Routers: overall PSU health from env/power outputs.
    Returns exactly one value: ["OK"] | ["NOT OK"] | ["Not available"].

    Rules:
      - If any PSU/PEM related line shows Warning/Failed/Critical/etc -> ["NOT OK"]
      - "Not Present"/"N/A"/"Absent" are ignored (do not flip to NOT OK)
      - OK/Normal/Good keeps scanning
      - If nothing PSU-related is found in any block -> ["Not available"]

    Sources in this order (with abbreviations handled):
      1) show environment all   (show env all / sh environment all / sh env all)
      2) show environment       (show env / sh environment / sh env)
      3) show platform hardware chassis environment all
      4) show platform power / show power
    """
    logging.info("Starting power supply status extraction (routers)")

    # ---------- helpers kept INSIDE the function ----------
    def _cmd_block_regex(cmd_variants: list[str]) -> re.Pattern:
        # dashed show-tech style: ------------------ show environment all ------------------
        dash_cmds = [re.escape(cv) for cv in cmd_variants]
        dash = rf"(?:-{{5,}}\s*(?:{'|'.join(dash_cmds)})\s*-{{5,}})"
        # plain echo: show environment all
        echo = rf"(?:^|\n)\s*(?:{'|'.join(dash_cmds)})\s*(?:\r?\n|$)"
        return re.compile(rf"(?is){dash}|{echo}")

    def _find_block(log: str, cmd_variants: list[str]) -> str | None:
        start_pat = _cmd_block_regex(cmd_variants)
        m = start_pat.search(log)
        if not m:
            return None
        start = m.end()
        # end at next dashed show-tech section header
        m2 = re.search(r"(?is)\n-+\s*show\s+.+?-+\s*\n", log[start:])
        if m2:
            return log[start:start + m2.start()]
        # or at next CLI echo
        m3 = re.search(r"(?im)^\s*show\s+\S.*$", log[start:])
        if m3:
            return log[start:start + m3.start()]
        return log[start:]

    def _state_of_line(line: str) -> str | None:
        s = line.lower()
        if re.search(r"\b(not\s*present|n/?a|absent)\b", s):
            return "IGNORE"
        if re.search(r"\b(normal|good|ok)\b", s):
            return "OK"
        if re.search(r"\b(warn|fault|fail|critical|shutdown|alarm|bad|not\s*ok|degraded)\b", s):
            return "NOT OK"
        return None

    def _overall_psu_from_block(block: str) -> list[str]:
        if not block:
            return ["Not available"]
        lines = block.splitlines()
        any_relevant = False
        for ln in lines:
            l = ln.strip()
            if not l:
                continue
            # PSU relevance
            if not re.search(r"\b(PEM|PSU|Power\s*Supply|PowerSupply|AC\s*Input|DC\s*Output|Vout|Vin|Iout)\b", l, re.I):
                continue
            any_relevant = True
            st = _state_of_line(l)
            if st == "NOT OK":
                return ["NOT OK"]
            # OK/IGNORE just continue
        return ["OK"] if any_relevant else ["Not available"]

    def _gather_blocks(log: str) -> list[str]:
        search_order = [
            ["show environment all", "show env all", "sh environment all", "sh env all"],
            ["show environment", "show env", "sh environment", "sh env"],
            ["show platform hardware chassis environment all"],
            ["show platform power", "show power"],
        ]
        blocks = []
        for variants in search_order:
            blk = _find_block(log, variants)
            if blk:
                blocks.append(blk)
        return blocks
    # ---------- end helpers ----------

    try:
        for blk in _gather_blocks(log_data):
            res = _overall_psu_from_block(blk)
            if res[0] != "Not available":
                logging.info(f"Power supply overall status: {res[0]}")
                return res

        logging.warning("No PSU-relevant environment info found in any block")
        return ["Not available"]

    except Exception as e:
        logging.error(f"Error in get_power_supply_status: {e}")
        return ["Not available"]

def get_debug_status(log_data):
    try:
        logging.info("Starting debug status extraction.")
        match = re.search(r"sh|show\w*\s*de\w*", log_data, re.IGNORECASE)
        if match:
            hostname = get_hostname(log_data)
            if hostname == "Not available" or not hostname:
                logging.debug("Hostname not found in log data.")
                return "Not available"
            # Escape hostname to avoid regex issues with special characters
            end_anchor = rf"\n{re.escape(hostname)}#"
            debug_section_match = re.search(
                rf"Ip Address\s+Port\s*-+\|----------\s*([\s\S]*?){end_anchor}",
                log_data[match.end():],
                re.IGNORECASE
            )
            if debug_section_match and debug_section_match.group(1).strip():
                logging.debug("Debug status extraction completed.")
                return "Require Manual Check"
            else:
                logging.debug("No debug section found in log data.")
                return "Command not found"
        else:
            logging.debug("No debug command found in log data.")
            return "Command not found"
    except Exception as e:
        logging.error(f"Error in get_debug_status: {str(e)}")
        return f"Require Manual Check"

def get_available_ports(log_data: str):
    """
    Count ports in VLAN 1 that are not connected.
    Router-safe logic:
      1) If 'show interfaces status' block is present, count 'notconnect' + vlan '1'.
      2) Else, find VLAN 1 access ports from running-config and count those that are down
         per 'show ip interface brief'.
    Returns [[count]] for consistency with your pipeline.
    """
    try:
        logging.info("Starting available ports extraction.")

        if not log_data:
            return [[0]]

        # ---------- Path A: native 'show interfaces status' block ----------
        start_marker = r"-{18}\s+show\s+interfaces?\s+status\s+-{18}"
        end_marker = r"-{18}\s+show\s+"

        start_match = re.search(start_marker, log_data)
        if start_match:
            start_pos = start_match.end()
            end_match = re.search(end_marker, log_data[start_pos:])
            section = log_data[start_pos:start_pos + end_match.start()] if end_match else log_data[start_pos:]

            count = 0
            # Very loose parse, but robust to spacing: require 'notconnect' and vlan '1'
            for line in section.strip().splitlines()[1:]:
                parts = line.split()
                # Avoid matching headers/blank/garbage lines
                if len(parts) < 4:
                    continue
                if 'notconnect' in parts and '1' in parts:
                    # Be a bit stricter: ensure the '1' is likely the VLAN column (usually 3rd or 4th token)
                    # Typical: Port  Name  Status      Vlan   Duplex  Speed  Type
                    # ex:     Gi1/0/1 --    notconnect 1      auto    auto   10/100/1000BaseTX
                    try:
                        status_idx = parts.index('notconnect')
                        # VLAN should be right after or near it; check a few tokens ahead
                        vlan_tokens = parts[status_idx+1:status_idx+3]
                        if any(tok == '1' for tok in vlan_tokens):
                            count += 1
                        else:
                            # Fallback: if the line explicitly includes ' 1 ' somewhere reasonable
                            if parts[3] == '1':
                                count += 1
                    except ValueError:
                        pass

            logging.debug(f"Available ports (from 'show interfaces status'): {count}")
            return [[int(count)]]

        # ---------- Path B: no 'show interfaces status' -> synthesize from cfg + ip int brief ----------
        # 1) Collect access ports in VLAN 1 from running-config
        #    interface <INTF>\n  ... switchport [mode access]\n  (switchport access vlan 1)?
        vlan1_ports = set()

        # Extract interface config blocks
        for m in re.finditer(r'(?ms)^\s*interface\s+(\S+)\s*(.*?)\n(?=!\s*$|^interface|\Z)', log_data):
            intf = m.group(1)
            block = m.group(2)

            # Only consider Ethernet-like L2 ports (skip Port-Channel, Loopback, VlanSVI, Tunnel, etc.)
            if not re.match(r'^(?:GigabitEthernet|TenGigabitEthernet|TwentyFiveGigE|FortyGigabitEthernet|HundredGigabitEthernet|AppGigabitEthernet|FastEthernet)', intf):
                continue
            if re.search(r'(?mi)^\s*no\s+switchport\b', block):
                # Routed port; skip
                continue

            # Must be a switchport (explicit or implied)
            if not re.search(r'(?mi)^\s*switchport\b', block):
                continue

            # If explicitly set to access vlan 1
            if re.search(r'(?mi)^\s*switchport\s+access\s+vlan\s+1\s*$', block):
                vlan1_ports.add(intf)
                continue

            # If access mode but no explicit access VLAN, assume default VLAN 1 (your stated requirement)
            if re.search(r'(?mi)^\s*switchport\s+mode\s+access\b', block) and not re.search(r'(?mi)^\s*switchport\s+access\s+vlan\s+\d+', block):
                vlan1_ports.add(intf)
                continue

            # Exclude trunks / voice / non-1 access VLAN
            if re.search(r'(?mi)^\s*switchport\s+mode\s+trunk\b', block):
                continue
            if re.search(r'(?mi)^\s*switchport\s+access\s+vlan\s+(?!1\b)\d+', block):
                continue

        if not vlan1_ports:
            logging.debug("No VLAN 1 access ports found in running-config.")
            return [[0]]

        # 2) Determine which of those are 'not connected' using 'show ip interface brief'
        #    We'll treat 'administratively down' or 'down/down' as not connected equivalents.
        #    Build a quick lookup of interface -> (status, protocol)
        # Find the ip int brief section, if any; otherwise, scan the whole file heuristically
        brief_start = re.search(r"-{18}\s+show\s+ip\s+interface\s+brief\s+-{18}", log_data)
        brief_text = log_data[brief_start.end():] if brief_start else log_data

        downish = 0
        for intf in vlan1_ports:
            # Line starts with the exact interface name (allow optional whitespace)
            # Typical formats include:
            #   GigabitEthernet0/0/1   unassigned  YES unset  administratively down down
            #   GigabitEthernet0/0/2   unassigned  YES unset  down                   down
            pat = re.compile(rf'(?mi)^\s*{re.escape(intf)}\s+.*?(administratively\s+down|down)\s+(down|up)\b')
            if pat.search(brief_text):
                downish += 1

        logging.debug(f"Available ports (from cfg + ip int brief): {downish} / {len(vlan1_ports)} candidates")
        return [[int(downish)]]

    except Exception as e:
        logging.error(f"Error in get_available_ports: {str(e)}")
        return [["Require Manual Check"]]

def get_half_duplex_ports(log_data):
    try:
        logging.info("Starting half duplex ports extraction (router mode).")
        matches = re.findall(r"^(\S+).*a-half.*$", log_data, re.IGNORECASE | re.MULTILINE)

        if not matches:
            logging.debug("No half duplex ports found in log data (router mode).")
            # Keep original outer [[...]] shape: one device -> one count
            return [[0]]

        # Router (single chassis): just count all matches
        count = len(matches)
        logging.debug(f"Half duplex ports found (router mode): {count}")
        return [[int(count)]]
    except Exception as e:
        logging.error(f"Error in get_half_duplex_ports: {str(e)}")
        return [["Require Manual Check"]]

def get_interface_remark(log_data):
    try:
        logging.info("Starting interface remark extraction (router mode).")
        matches = re.findall(r"^(\S+).*a-half.*$", log_data, re.IGNORECASE | re.MULTILINE)

        if not matches:
            logging.debug("No interface remark found in log data (router mode).")
            # Keep outer list-of-lists; single device => one inner list
            return [["Not available"]]

        # Single router: return one inner list with interface names
        remarks = list(dict.fromkeys(matches))  # de-dup, keep order
        logging.debug(f"Interface remark entries (router mode): {len(remarks)}")
        return [remarks]
    except Exception as e:
        logging.error(f"Error in get_interface_remark: {str(e)}")
        return [["Require Manual Check"]]

def get_nvram_config_update(log_data):
    try:
        logging.info("Starting NVRAM config update extraction.")
        match = re.search(r"NVRAM\s+config\s+last\s+updated\s+at\s+(.+)", log_data, re.IGNORECASE)
        if match:
            logging.debug("NVRAM config update extraction completed.")
            return ["Yes", match.group(1).strip().split('by')[0].strip()]
        else:
            logging.debug("No NVRAM config update found in log data.")
            return ["No", "Not available"]
    except Exception as e:
        logging.error(f"Error in get_nvram_config_update: {str(e)}")
        return [f"Require Manual Check", "Not available"]

def get_critical_logs(log_data):
    if not isinstance(log_data, str) or not log_data:
        logging.error("Invalid input type or empty string for log_data")
        return f"Require Manual Check"
    try:
        logging.info("Starting critical logs extraction.")
        match = re.search(r'(sh|show)\s+(log|logging)\s*-+\n(.*?)(?=\n-+\s*show|\Z)', log_data, re.DOTALL | re.IGNORECASE)
        if match:
            logging_section = match.group(0)
            if any(f"-{i}-" in logging_section for i in range(3)):
                logging.debug("Critical logs extraction completed.")
                return "YES"
            else:
                logging.debug("No critical logs found in log data.")
                return "NO"
        else:
            logging.debug("No logging section found in log data.")
            return "Not available"
    except Exception as e:
        logging.error(f"Error Occurred while parsing logs!\n{e}")
        return False

def print_data(data):
    try:
        logging.info("Starting data printing.")
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            else:
                print(f"{key}: {value}")
        print("\n")
        logging.debug("Data printing completed.")
    except Exception as e:
        logging.error(f"Error in print_data: {str(e)}")
        # print(f"Error in print_data: {str(e)}")

def process_file(file_path, text: str | None = None):
    """
    Process router (ASR/ISR/C8k) log file.
    Always assumes a single device — no stacking or modules.
    """
    try:
        logging.info(f"Starting router log processing: {file_path}")

        # Load text content
        if text is None:
            with open(file_path, 'r', errors='ignore') as f:
                log_data = f.read()
        else:
            log_data = text

        # Gather info
        memory_info = get_memory_info(log_data)
        flash_info = get_flash_info(log_data)
        if isinstance(flash_info, dict):
            flash_info = flash_info.get('1', ["Not available"] * 4)
        elif isinstance(flash_info, str):
            flash_info = ["Not available"] * 4

        ip_addr_info = get_ip_address(file_path)

        # Identify platform type
        platform_type = detect_platform_type(log_data)

        # Compose output row
        data = {
            "File name": [ip_addr_info[0]],
            "Host name": [get_hostname(log_data)],
            "Model number": [get_model_number(log_data)],
            "Serial number": [get_serial_number(log_data)],
            "Interface ip address": [ip_addr_info[1]],
            "Uptime": [get_uptime(log_data)],
            "Current s/w version": [get_current_sw_version(log_data)],
            "Platform Type": [platform_type],
            "Last Reboot Reason": [get_last_reboot_reason(log_data)],
            "Any Debug?": [get_debug_status(log_data)],
            "CPU Utilization": [get_cpu_utilization(log_data)],
            "Total memory": [memory_info[0]],
            "Used memory": [memory_info[1]],
            "Free memory": [memory_info[2]],
            "Memory Utilization (%)": [memory_info[3]],
            "Total flash memory": [flash_info[0]],
            "Used flash memory": [flash_info[1]],
            "Free flash memory": [flash_info[2]],
            "Used Flash (%)": [f"{flash_info[3]:.2f}%" if isinstance(flash_info[3], (int, float)) else flash_info[3]],
            "Fan status": [get_fan_status(log_data)],
            "Temperature status": [get_temperature_status(log_data)],
            "PowerSupply status": [get_power_supply_status(log_data)],
            "Available Free Ports": [get_available_ports(log_data)],
            "Any Half Duplex": [get_half_duplex_ports(log_data)],
            "Interface/Module Remark": [get_interface_remark(log_data)],
            "Config Status": [get_nvram_config_update(log_data)[0]],
            "Config Save Date": [get_nvram_config_update(log_data)[1]],
            "Critical logs": [get_critical_logs(log_data)],

            # Defaults for future enrichment
            "Current SW EOS": ["Yet to check"],
            "Suggested s/w ver": ["Yet to check"],
            "s/w release date": ["Yet to check"],
            "Latest S/W version": ["Yet to check"],
            "Production s/w is deffered or not?": ["Yet to check"],
            "End-of-Sale Date: HW": ["Yet to check"],
            "Last Date of Support: HW": ["Yet to check"],
            "End of Routine Failure Analysis Date: HW": ["Yet to check"],
            "End of Vulnerability/Security Support: HW": ["Yet to check"],
            "End of SW Maintenance Releases Date: HW": ["Yet to check"],
            "Remark": ["Yet to check"]
        }

        logging.info(f"Completed router file processing: {file_path}")
        return data

    except Exception as e:
        logging.error(f"Error in process_file_router: {str(e)}")
        return {}

def detect_platform_type(log_data: str) -> str:
    """
    Return one of: 'ASR', 'ISR', 'C8K', 'UNKNOWN'.
    - ASR: ASR1k/900/903/920 and ASR9k (XR) patterns
    - ISR: classic ISR (ISR4k/ISR1k) keywording
    - C8K: Catalyst 8000 family (c8200/c8300/c8500/c8000v/c8000be)
    """
    try:
        if not log_data:
            return "UNKNOWN"

        # Scope to likely local 'show version' block to avoid neighbor noise.
        m_block = re.search(r'(?is)(?:^|\n)[^\n#]*#\s*sh(?:ow)?\s+ver(?:sion)?\b(.{0,6000})', log_data)
        text = (m_block.group(0) if m_block else log_data).lower()

        # --- ASR (incl. XR) ---
        asr_patterns = [
            r'\basr\d{3,4}\b',          # ASR1000, ASR903, ASR920, etc.
            r'cisco\s+asr',             # literal "Cisco ASR"
            r'\basr9k\b',               # shorthand for ASR9000
            r'ios\s+xr\s+software',     # XR banner
        ]
        if any(re.search(p, text, re.I) for p in asr_patterns):
            return "ASR"

        # --- Catalyst 8000 family (often "ISR replacement") ---
        c8k_patterns = [
            r'\bc8[0-9]{3}\w*\b',       # c8200/c8300/c8500 etc.
            r'\bc8000v\b',              # virtual
            r'\bc8000be\b',             # boost edge (seen in your ISR sample)
            r'catalyst\s+8000',         # textual mention
        ]
        if any(re.search(p, text, re.I) for p in c8k_patterns):
            return "C8K"

        # --- Classic ISR patterns ---
        isr_patterns = [
            r'\bISR\d{3,4}\b',                  # ISR4321, ISR4451, etc.
            r'Cisco\s+ISR',                     # literal
            r'Integrated\s+Services\s+Router',  # descriptive
            r'\bisr4k\b', r'\bISR\s*4000\b',    # 4k family terms
        ]
        if any(re.search(p, text, re.I) for p in isr_patterns):
            return "ISR"

        return "UNKNOWN"

    except Exception as e:
        logging.error(f"Error in detect_platform_type: {e}")
        return "UNKNOWN"


def os_check(log_data: str) -> bool:
    """
    Return True for supported IOS-XE routers: ASR, ISR, and C8K.
    """
    try:
        plat = detect_platform_type(log_data)
        if plat in {"ASR", "ISR", "C8K"}:
            return True
        # Fallback: if we can extract an IOS-XE style version, allow it
        ver = get_current_sw_version(log_data)
        return bool(ver and ver not in {"Not available", ""})
    except Exception as e:
        logging.error(f"Error in ios_xe_router_check: {e}")
        return False


def isr_os_check(log_data: str, include_c8k: bool = True) -> bool:
    """
    True if the device is ISR. By default, counts Catalyst 8000 family as ISR-like.
    Set include_c8k=False if you want strict 'ISR' only.
    """
    try:
        logging.info("Starting ISR check.")
        plat = detect_platform_type(log_data)
        is_isr = (plat == "ISR") or (include_c8k and plat == "C8K")
        logging.debug(f"ISR check completed. Platform={plat}, is_isr={is_isr}.")
        return is_isr
    except Exception as e:
        logging.error(f"Error in isr_os_check: {str(e)}")
        return False

def process_directory(directory_path):
    if not isinstance(directory_path, str):
        logging.error("Invalid input type for directory_path")
        return 500

    if not os.path.isdir(directory_path):
        logging.error(f"Directory does not exist or is not a directory: {directory_path}")
        return 500

    data = []
    try:
        logging.info(f"Starting directory processing: {directory_path}")

        # Collect eligible files first (stable order)
        candidates = []
        for filename in os.listdir(directory_path):
            if not (filename.endswith('.txt') or filename.endswith('.log')):
                logging.debug(f"Skipping non-log file: {filename}")
                continue
            if filename.startswith('~$') or filename.startswith('.'):
                logging.debug(f"Skipping temp/hidden file: {filename}")
                continue
            candidates.append(os.path.join(directory_path, filename))

        if not candidates:
            logging.warning("No .txt or .log files found to process.")
            return data  # empty list

        def _process_one(file_path):
            try:
                # Read once to check IOS-XE eligibility (tolerate encoding issues)
                with open(file_path, 'r', errors='ignore') as f:
                    log_data = f.read()
            except Exception as e:
                logging.error(f"Unreadable file {file_path}: {e}")
                # Return a placeholder row that will land in Excel with a clear Remark
                return _placeholder_entry(file_path)

            try:
                if os_check(log_data):
                    logging.debug(f"{os.path.basename(file_path)} is IOS XE File. Appending value!")
                    return process_file(file_path)  # your original pipeline
                else:
                    logging.debug(f"{os.path.basename(file_path)} was not IOS XE. Producing info row.")
                    return _placeholder_entry(file_path)
            except Exception as e:
                logging.error(f"Error processing {file_path}: {e}")
                return _placeholder_entry(file_path)

        # I/O-bound concurrency
        from concurrent.futures import ThreadPoolExecutor, as_completed
        max_workers = min(16, (os.cpu_count() or 4) * 2)
        futures = []
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for fp in candidates:
                futures.append(ex.submit(_process_one, fp))
            for fut in as_completed(futures):
                try:
                    result = fut.result()
                    # Keep original behavior: only collect valid dicts
                    if isinstance(result, dict) and result:
                        data.append(result)
                except Exception as e:
                    logging.error(f"Worker future raised: {e}")

        logging.debug("Data Extracted Successfully!")
        return data

    except Exception as e:
        logging.error(f"Error in process_directory: {str(e)}")
        return "Require Manual Check"
    
def _placeholder_entry(file_path, reason_text="Non-IOS_XE"):
    try:
        fname, _ = get_ip_address(file_path)  # we will not show IP for unsupported rows
    except Exception:
        fname = os.path.basename(file_path)

    U = "Unsupported IOS"

    return {
        "File name": [fname],
        "Host name": [U],
        "Model number": [U],
        "Serial number": [U],
        "Interface ip address": [U],
        "Uptime": [U],
        "Current s/w version": [U],
        "Last Reboot Reason": [U],
        "Any Debug?": [U],
        "CPU Utilization": [U],
        "Total memory": [U],
        "Used memory": [U],
        "Free memory": [U],
        "Memory Utilization (%)": [U],
        "Total flash memory": [U],
        "Used flash memory": [U],
        "Free flash memory": [U],
        "Used Flash (%)": [U],
        "Fan status": [U],
        "Temperature status": [U],
        "PowerSupply status": [U],
        "Available Free Ports": [U],
        "Any Half Duplex": [U],
        "Interface/Module Remark": [U],
        "Config Status": [U],
        "Config Save Date": [U],
        "Critical logs": [U],
        "Current SW EOS": [U],
        "Suggested s/w ver": [U],
        "s/w release date": [U],
        "Latest S/W version": [U],
        "Production s/w is deffered or not?": [U],
        "End-of-Sale Date: HW": [U],
        "Last Date of Support: HW": [U],
        "End of Routine Failure Analysis Date: HW": [U],
        "End of Vulnerability/Security Support: HW": [U],
        "End of SW Maintenance Releases Date: HW": [U],
        "Remark": ["Non-IOS_XE"],
    }


def main():
    data = []
    data = process_directory(r"C:\Users\girish.n\Downloads\SVR138028674 1")
    # data = process_file(file_path = r"C:\Users\girish.n\Downloads\PM logs sets\Ultimate_logs\STQ03-T3-ITR-RT02(10.153.82.67).txt")
    # print(data)
    for item in data:
        print(item['File name'])
        print(item['Model number'])
        print(item['Serial number'])
        # print(item['Current s/w version'])
        # print_data(item['Platform Type'])
        # print(item['Last Reboot Reason'])
        # print(item['Any Debug?'])
        # print(item['CPU Utilization'])
        # print(item['Total memory'])
        # print(item['Used memory'])
        # print(item['Free memory'])
        # print(item['Memory Utilization (%)'])
        # print(item['Total flash memory'])
        # print(item['Used flash memory'])
        # print(item['Free flash memory'])
        # print(item['Used Flash (%)'])
        # print(item['Available Free Ports'])
        print("Fan :" , item['Fan status'])
        print("Temp: ", item['Temperature status'])
        print("PSU :", item['PowerSupply status'])
        print("\n\n")
        # print(item['Fan status'])
        # print(item['Temperature status'])

if __name__ == "__main__":
    main()