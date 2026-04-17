import re
import os
import logging
import datetime
import pprint as pp
from typing import List, Dict, Union

from . import IOS_Stack_Switch  # strict relative import inside package


log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
# Configure logging only once to avoid collisions when imported alongside Cisco_IOS_XE
if not logging.getLogger().handlers:
    logging.basicConfig(
        filename=os.path.join(log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"),
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

try:
    from . import IOS_Stack_Switch as _IOS_STACK
    logging.info("Successfully imported IOS_Stack_Switch module.")
except Exception as e:
    logging.error(f"Failed to import IOS_Stack_Switch: {e}")
    raise

def _stack_size(text: str) -> int:
    logging.debug(f"Entering _stack_size function with text input (first 50 chars): {text[:50]}")
    try:
        size = int(_IOS_STACK.stack_size(text))
        logging.info(f"Successfully calculated stack size: {size}")
        return size
    except Exception as e:
        logging.error(f"stack_size not available/failed in IOS_Stack_Switch: {e}")
        return 1

def _parse_stack_switch(text: str) -> dict:
    logging.debug("Entering _parse_stack_switch to find and execute a parsing function.")
    for name in ("parse_IOS_Stack_Switch", "parse_ios_stack_switch", "parse_ios_xe_stack_switch"):
        fn = getattr(_IOS_STACK, name, None)
        if callable(fn):
            logging.info(f"Found callable parsing function: {name}. Attempting to execute.")
            try:
                result = fn(text)
                logging.info(f"Successfully executed {name}. Returning result.")
                return result
            except Exception as e:
                logging.error(f"{name} raised: {e}")
                break
        else:
            # LOGGING ADDED: Function not found or not callable
            logging.debug(f"Function {name} not found or is not callable in _IOS_STACK.")
    logging.error("No parse_* function found in IOS_Stack_Switch")
    return {}

# --- Classic IOS detector (not IOS-XE) ---
def ios_check(log_data: str) -> bool:
    logging.debug("Entering ios_check to determine if the data is Classic IOS.")
    try:
        if not isinstance(log_data, str) or not log_data:
            logging.warning("Input is not a string or is empty. Returning False.")
            return False
        # explicitly exclude XE
        if re.search(r'(?i)\bIOS[\s-]?XE\b', log_data):
            logging.info("IOS-XE detected in log data. Explicitly excluding and returning False.")
            return False
        # classic IOS banner
        is_classic_ios = re.search(r'(?mi)^\s*Cisco\s+IOS\s+Software\b.*\bVersion\s+[^\s,]+', log_data) is not None
        
        # LOGGING ADDED: Final result
        logging.info(f"Classic IOS banner check completed. Result: {is_classic_ios}")
        
        return is_classic_ios
    except Exception as e:
        logging.error(f"Error in ios_check: {e}")
        return False

# TEMP alias to avoid accidental external calls to the old name
ios_check = ios_check
    
# Static strings
NA = "Not available"
YET_TO_CHECK = "Yet to check"

# Stanza splitter: grabs each "interface ..." block (multiline)
_INTERFACE_BLOCK_RE = re.compile(r'(?ms)^interface\s+\S+.*?(?=^interface\s+\S+|\Z)')

# Lines that usually accompany the management SVI
_MGMT_MARKERS = (
    r'no\s+ip\s+redirects',
    r'no\s+ip\s+unreachables',
    r'no\s+ip\s+proxy-arp',
    r'no\s+ip\s+route-cache',
)

_IP_LINE_RE = re.compile(
    r'^\s*ip\s+address\s+'
    r'(?P<ip>\d{1,3}(?:\.\d{1,3}){3})'
    r'(?:\s+(?:\d{1,3}(?:\.\d{1,3}){3}|/\d{1,2}))?'
    r'(?:\s+secondary)?\s*$',
    re.IGNORECASE | re.MULTILINE
)
_DESC_MGMT_RE = re.compile(r'(?im)^\s*description\s+.*\b(mgmt|manage|management)\b')

def get_ip(log_data: str):
    try:
        if not log_data:
            return None

        blocks = _INTERFACE_BLOCK_RE.findall(log_data)
        buckets = {"mgmt": [], "loop": [], "vlan1": []}

        for blk in blocks:
            if re.search(r'(?im)^\s*ip\s+address\s+dhcp\b', blk):
                continue

            ips = []
            for m in _IP_LINE_RE.finditer(blk):
                if re.search(r'\bsecondary\b', m.group(0), flags=re.IGNORECASE):
                    continue
                ips.append(m.group('ip'))
            if not ips:
                continue

            header = re.search(r'(?im)^interface\s+([^\r\n]+)', blk)
            iface = header.group(1) if header else ""

            name_has_mgmt = re.search(r'\b(mgmt|manage|management)\b', iface, re.IGNORECASE)
            desc_has_mgmt = bool(_DESC_MGMT_RE.search(blk))

            if name_has_mgmt or desc_has_mgmt:
                buckets["mgmt"].append(ips)
            elif re.search(r'(?im)^interface\s+loopback\d+\b', blk):
                buckets["loop"].append(ips)
            elif re.search(r'(?im)^interface\s+vlan\s*1\b', blk):
                buckets["vlan1"].append(ips)

        for key in ("mgmt", "loop", "vlan1"):
            for ips in buckets[key]:
                for raw in ips:
                    ip_norm = sanitize_ipv4(raw)
                    if ip_norm not in {"Not available", "Require Manual Check"}:
                        return ip_norm
        return "Require Manual Check"
    except Exception:
        return None

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

def log_type(log_data):
    if not isinstance(log_data, str):
        logging.error("Invalid input type for log_data")
        return f"Not a .txt or.log file"

def get_hostname(log_data: str) -> str:
    try:
        if not isinstance(log_data, str) or not log_data:
            return "Require Manual Check"

        m = re.search(r"(?im)^\s*hostname\s+([A-Za-z0-9][A-Za-z0-9._-]*)\s*$", log_data)
        if m:
            return m.group(1).strip()

        m = re.search(r"(?im)^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s+uptime\s+is\s+.+$", log_data)
        if m:
            return m.group(1).strip()

        for pat in (
            r"(?im)^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*[>#]\s*(?:sh|sho|show)\b",
            r"(?im)^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*[>#]\s*(?:term(?:inal)?\s+len|terminal\s+length)\b",
        ):
            m = re.search(pat, log_data)
            if m:
                return m.group(1).strip()

        return "Require Manual Check"
    except Exception:
        return "Require Manual Check"

def get_model_number(log_data):
    logging.info("Starting model number search.")
    try:

        # --- show version (SV) fallback ---
        sv_m = re.search(r"Model\s+Number\s*:\s*([^\s\r\n]+)", log_data, re.IGNORECASE)
        sv_model = sv_m.group(1) if sv_m else None

        if sv_model:
            logging.debug(f"SV Model found: {sv_model}")
        else:
            logging.debug("SV Model not found.")

        # --- show inventory (INV) section ---
        inv_hdr = re.search(r"-{5,}\s*show\s+inventory\s*-{5,}", log_data, re.IGNORECASE)
        inv_sec = log_data[inv_hdr.end():] if inv_hdr else ""

        if inv_hdr:
            logging.debug("Found 'show inventory' section. Proceeding with INV search.")
        else:
            logging.debug("No 'show inventory' section found.")

        # Collect NAME + PID pairs, then classify
        inv_switch_pid = {}
        inv_chassis_pid = {}

        for m in re.finditer(r'NAME:\s*"([^"]+)"[^\n]*\nPID:\s*([^\s,]+)', inv_sec, re.IGNORECASE):
            name = m.group(1).strip()
            pid  = m.group(2).strip()
            low  = name.lower()

            # Switch N
            ms = re.match(r'(?i)^\s*switch\s*(\d+)\b', name)
            if ms:
                logging.debug(f"Inventory match: Found Switch {ms.group(1)} with PID {pid}")
                inv_switch_pid[int(ms.group(1))] = pid
                continue

            # Chassis N (ignore subcomponents like Transceiver/FAN/PS/DFC/PFC/Policy/Tray)
            mc = re.match(r'(?i)^\s*chassis\s*(\d+)\b', name)
            if mc and not any(x in low for x in ("transceiver", "fan", "ps", "power", "pfc", "dfc", "policy", "tray")):
                logging.debug(f"Inventory match: Found Chassis {mc.group(1)} with PID {pid}")
                inv_chassis_pid[int(mc.group(1))] = pid

        logging.debug(f"Completed inventory parsing. Switch PIDs: {inv_switch_pid}. Chassis PIDs: {inv_chassis_pid}")

        # Decide inventory PID
        inv_pid = None
        if inv_switch_pid:
            pids = set(inv_switch_pid.values())
            if len(pids) == 1:
                inv_pid = next(iter(pids))
                logging.info(f"INV decision: Used unique Switch PID: {inv_pid}")
            else:
                inv_pid = inv_switch_pid.get(1) or inv_switch_pid[sorted(inv_switch_pid)[0]]
                logging.info(f"INV decision: Used Switch 1 or lowest-numbered Switch PID: {inv_pid}")
        elif inv_chassis_pid:
            pids = set(inv_chassis_pid.values())
            if len(pids) == 1:
                inv_pid = next(iter(pids))
                logging.info(f"INV decision: Used unique Chassis PID: {inv_pid}")
            else:
                inv_pid = inv_chassis_pid.get(1) or inv_chassis_pid[sorted(inv_chassis_pid)[0]]
                logging.info(f"INV decision: Used Chassis 1 or lowest-numbered Chassis PID: {inv_pid}")

        logging.debug(f"Intermediate Results: SV Model: {sv_model}, INV PID: {inv_pid}")

        if sv_model and inv_pid:
            if sv_model.strip().upper() != inv_pid.strip().upper():
                result = inv_pid
                logging.info(f"Final Model: Used INV PID ({inv_pid}) because it differs from SV Model ({sv_model}).")
            else:
                result = sv_model
                logging.info(f"Final Model: Used SV Model ({sv_model}) as it matches INV PID.")
        else:
            # DECISION: Fallback hierarchy
            result = inv_pid or sv_model or "Require Manual Check"
            
            if inv_pid:
                 logging.info(f"Final Model: Used INV PID ({inv_pid}) as SV Model was missing.")
            elif sv_model:
                 logging.info(f"Final Model: Used SV Model ({sv_model}) as INV PID was missing.")
            else:
                 logging.warning("Final Model: No Model/PID found from SV or INV. Returning default.")

        return result

    except Exception as e:
        logging.error(f"Error in get_model_number: {e}")
        return "Require Manual Check"

def get_ip_address(file_path):
    logging.info("Starting IP address extraction from file path.")
    try:
        file_name = os.path.basename(file_path) if isinstance(file_path, str) else str(file_path)
        logging.debug(f"Normalized file name: '{file_name}'")

        # 1) Filename-first: collect candidates, return the first that sanitizes cleanly
        filename_candidates = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?)", file_name)
        logging.debug(f"Found {len(filename_candidates)} IP candidates in the filename.")

        for cand in filename_candidates:
            ip_norm = sanitize_ipv4(cand)
            if ip_norm not in {"Not available", "Require Manual Check"}:
                # LOGGING PRESENT: Successful IP found
                logging.info(f"IP successfully extracted from filename: {ip_norm}")
                return (file_name, ip_norm)
            else:
                # LOGGING ADDED: Invalid candidate skipped
                logging.debug(f"Filename candidate '{cand}' failed validation.")
        
        logging.info("Filename search complete. No valid IP found. Proceeding to content fallback.")

        # 2) Content fallback (only if needed)
        try:
            with open(file_path, "r", errors="ignore") as f:
                log_data = f.read()
            logging.debug(f"Successfully read content from {file_name} ({len(log_data)} bytes).")

            # Find all IPv4-ish tokens (allowing optional CIDR), sanitize each, pick first valid
            content_candidates = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?)", log_data)
            logging.debug(f"Found {len(content_candidates)} IP candidates in the content.")

            for cand in content_candidates:
                ip_norm = sanitize_ipv4(cand)
                if ip_norm not in {"Not available", "Require Manual Check"}:
                    # LOGGING PRESENT: Successful IP found
                    logging.info(f"IP successfully extracted from file content: {ip_norm}")
                    return (file_name, ip_norm)
                else:
                    # LOGGING ADDED: Invalid candidate skipped
                    logging.debug(f"Content candidate '{cand}' failed validation.")

            logging.debug("Content regex search complete. Proceeding to get_ip helper.")

            # --- Last chance: call existing get_ip helper if available ---
            try:
                from_content = get_ip(log_data)
                ip_norm = sanitize_ipv4(from_content)
                if ip_norm not in {"Not available", "Require Manual Check"}:
                    # LOGGING PRESENT: Successful IP found
                    logging.info(f"IP successfully extracted via get_ip helper: {ip_norm}")
                    return (file_name, ip_norm)
                else:
                    logging.debug("get_ip helper returned an invalid or unspecific IP.")

            except Exception as e:
                logging.warning(f"get_ip helper failed on {file_name}: {e}")

        except Exception as inner:
            logging.warning(f"Content fallback failed while reading {file_name}: {inner}")

        logging.info("Exhausted all search methods. No valid IP found.")
        return (file_name, "Require Manual Check")

    except Exception as e:
        safe_name = os.path.basename(file_path) if isinstance(file_path, str) else "Unknown"
        logging.critical(f"CRITICAL Error in get_ip_address for {safe_name}: {str(e)}")
        return (safe_name, "Require Manual Check")

def get_serial_number(log_data):
    logging.info("Starting serial number search.")
    try:

        m = re.search(r'(?im)^\s*System\s+Serial\s+Number\s*:\s*([A-Z0-9\-]+)\s*$', log_data)
        if m:
            sn = m.group(1)
            # LOGGING ADDED: Successful extraction from show version
            logging.info(f"SN found via 'System Serial Number' field: {sn}")
            return sn
        
        logging.debug("SN not found in 'System Serial Number' field.")

        inv_hdr = re.search(r'(?im)-{5,}\s*show\s+inventory\s*-{5,}', log_data)
        inv_sec = log_data[inv_hdr.end():] if inv_hdr else ""

        if not inv_hdr:
            logging.debug("No 'show inventory' header found. Cannot proceed with inventory searches.")
        else:
            logging.debug("Found 'show inventory' section. Proceeding with inventory checks.")

        # Prefer Switch 1 in stacks if present
        m = re.search(r'(?ims)NAME:\s*"Switch\s*1"[^"]*".*?\bSN:\s*([A-Z0-9]+)', inv_sec)
        if m:
            sn = m.group(1)
            logging.info(f"SN found via 'Switch 1' inventory entry: {sn}")
            return sn
        logging.debug("SN not found for 'Switch 1' inventory entry.")

        # Otherwise prefer Chassis 1 (avoid "Chassis 1 1" line-cards)
        m = re.search(r'(?ims)NAME:\s*"Chassis\s*1\b(?!\s*\d)[^"]*".*?\bSN:\s*([A-Z0-9]+)', inv_sec)
        if m:
            sn = m.group(1)
            logging.info(f"SN found via 'Chassis 1' inventory entry: {sn}")
            return sn
        logging.debug("SN not found for primary 'Chassis 1' inventory entry.")

        # If multiple chassis entries but all have same SN, accept it
        chassis_sns = {x.group(1) for x in re.finditer(r'(?ims)NAME:\s*"Chassis\s*\d+[^"]*".*?\bSN:\s*([A-Z0-9]+)', inv_sec)}
        if len(chassis_sns) == 1:
            sn = next(iter(chassis_sns))
            logging.info(f"SN found as unique SN across all chassis entries: {sn}")
            return sn
        elif len(chassis_sns) > 1:
            logging.warning(f"Multiple differing chassis SNs found: {chassis_sns}. Cannot automatically determine primary SN.")
        else:
            logging.debug("No chassis SNs found in inventory.")

        logging.warning("All automated SN checks failed. Manual check required.")
        return "Require Manual Check"

    except Exception as e:
        logging.error(f"Error in get_serial_number: {str(e)}")
        return "Require Manual Check"

def get_uptime(log_data):
    logging.info("Starting uptime search.")
    try:
        hostname = get_hostname(log_data)
        # If hostname isn't available, don't attempt a bogus regex match
        if not hostname or hostname == "Not available":
            logging.debug("Uptime search skipped due to unavailable hostname.")
            return "Not available"
        
        safe_hostname = re.escape(hostname)
        logging.debug(f"Hostname '{hostname}' escaped for regex use.")

        pattern = rf"{safe_hostname}\s+uptime is\s+(.+)"
        
        match = re.search(pattern, log_data)
        
        logging.debug("Uptime regex search completed.")
        
        # DECISION: Check for match and return
        if match:
            uptime = match.group(1).strip()
            logging.info(f"Uptime successfully extracted: {uptime}")
            return uptime
        else:
            logging.warning("Uptime pattern not found using the extracted hostname.")
            return "Require Manual Check"
            
    except Exception as e:
        logging.error(f"Critical error in get_uptime: {str(e)}")
        return "Require Manual Check"

def get_current_sw_version(log_data):
    """
    Classic IOS banner like:
    Cisco IOS Software, C3750 Software (...), Version 12.2(44)SE4, RELEASE ...
    """
    logging.info("Starting software version search using classic IOS banner pattern.")
    try:
        m = re.search(r'(?mi)^\s*Cisco\s+IOS\s+Software.*?\bVersion\s+([^\s,]+)', log_data)
        if m:
            version = m.group(1).strip()
            logging.info(f"Software version successfully extracted: {version}")
            return version
        else:
            # LOGGING ADDED: Failure to match
            logging.warning("Classic IOS version banner pattern not found.")
            return "Not available"
            
    except Exception as e:
        # LOGGING PRESENT: Error handling
        logging.error(f"Critical error in get_current_sw_version: {str(e)}")
        return "Not available"

def get_last_reboot_reason(log_data):
    logging.info("Starting last reboot reason search.")
    try:
        # First try to match "Last reload reason"
        match = re.search(r"Last reload reason\s*:\s*(.+)", log_data, re.IGNORECASE)
        if match:
            result = match.group(1).strip()
            logging.info(f"Reboot reason found using 'Last reload reason': {result}")
        else:
            logging.debug("'Last reload reason' pattern not found. Falling back.")
            # Fallback: match "System returned to ROM by ..."
            if match:
                # ACTION 2.1: Extract result
                result = match.group(1).strip()
                logging.info(f"Reboot reason found using 'System returned to ROM by': {result}")
            else:
                # ACTION 2.2: Set default result
                result = "Require Manual Check"
                logging.warning("Neither primary nor fallback reboot reason patterns were found.")
        
        logging.debug("Last reboot reason search completed.")
        return result

    except Exception as e:
        logging.error(f"Critical error in get_last_reboot_reason: {str(e)}")
        return "Require Manual Check"

def get_cpu_utilization(log_data):
    logging.info("Starting CPU utilization search.")
    try:
        match = re.search(r"five minutes:\s+(\d+)%", log_data)
        logging.debug("CPU utilization search completed.")
        if match:
            utilization = match.group(1) + "%"
            logging.info(f"CPU utilization successfully extracted (5-min average): {utilization}")
            return utilization
        else:
            logging.warning("CPU utilization pattern ('five minutes') not found.")
            return "Require Manual Check"
            
    except Exception as e:
        logging.error(f"Critical error in get_cpu_utilization: {str(e)}")
        return "Require Manual Check"

def check_stack(log_data):
    try:
        # ACTION 1: Determine the stack size
        stack_size = _stack_size(log_data)
        
        logging.debug(f"Determined stack size is: {stack_size}")
        
        # DECISION 1: Check if the stack size is greater than 1
        if stack_size > 1:
            logging.info("Device is a stack (size > 1). Attempting to parse stack details.")
            
            # ACTION 2: Attempt to parse the stack data
            result = _IOS_STACK.parse_IOS_Stack_Switch(log_data)
            
            logging.info("Successfully parsed stack details.")
            return result
        
        # DECISION 2: Stack size is 1 or less
        logging.info("Device is not a stack (size <= 1). Returning False.")
        return False
        
    except Exception as e:
        logging.error(f"Critical error in check_stack during size check or parsing: {str(e)}")
        return "Require Manual Check"

def get_memory_info(log_data):
    logging.info("Starting memory info extraction.")
    try:
        if not log_data:
            logging.warning("Log data is empty. Cannot extract memory info.")
            return ["Not available", "Not available", "Not available", "Not available"]

        def _parse_num_with_unit(token: str) -> int | None:
            logging.debug(f"Entering _parse_num_with_unit with token: '{token}'")
            if not token:
                logging.debug("Token is empty.")
                return None
            
            s = token.strip().replace(",", "")

            m = re.match(r'^(\d+(?:\.\d+)?)([KkMmGg])?$', s)

            if not m:
                # also accept plain integers with no unit
                if s.isdigit():
                    try:
                        result = int(s)
                        logging.debug(f"Parsed as plain integer: {result}")
                        return result
                    except Exception as e:
                        logging.debug(f"Failed to parse as plain integer: {e}")
                        return None
                logging.debug("Token failed both number/unit regex and integer fallback.")
                return None
            num = float(m.group(1))
            unit = m.group(2).upper() if m.group(2) else None
            mult = 1
            if unit == 'K':
                mult = 1024
            elif unit == 'M':
                mult = 1024 ** 2
            elif unit == 'G':
                mult = 1024 ** 3
            
            result = int(num * mult)
            logging.debug(f"Parsed '{token}' to bytes: {result} (Multiplier: {mult})")
            return result

        m = re.search(
            r'(?mi)^\s*Processor\s+\S+\s+(\d+)\s+(\d+)\s+(\d+)\b',
            log_data
        )
        if m:
            total = int(m.group(1))
            used  = int(m.group(2))
            free  = int(m.group(3))
            if total <= 0:
                logging.error("Total memory is zero (Processor table), cannot calculate utilization")
                return ["Not available", "Not available", "Not available", "Not available"]
            utilization = (used / total) * 100.0
            logging.info(f"Memory info found via Processor table. Total: {total} B, Utilization: {utilization:.2f}%")
            logging.debug("Memory info (Processor table) extraction completed.")
            return [total, used, free, f"{utilization:.2f}%"]

        m2 = re.search(
            r'(?mi)^\s*System\s+memory\s*:\s*'
            r'(?P<total>[0-9,]+[KkMmGg]?)\s+total,\s*'
            r'(?P<used>[0-9,]+[KkMmGg]?)\s+used,\s*'
            r'(?P<free>[0-9,]+[KkMmGg]?)\s+free',
            log_data
        )
        if m2:
            total = _parse_num_with_unit(m2.group('total'))
            used  = _parse_num_with_unit(m2.group('used'))
            free  = _parse_num_with_unit(m2.group('free'))

            if total is None or used is None or free is None or total <= 0:
                logging.error("Could not parse System memory line or total <= 0")
                return ["Not available", "Not available", "Not available", "Not available"]

            utilization = (used / total) * 100.0
            logging.info(f"Memory info found via System memory summary. Total: {total} B, Utilization: {utilization:.2f}%")
            logging.debug("Memory info (System memory summary) extraction completed.")
            return [total, used, free, f"{utilization:.2f}%"]
        
        logging.warning("No memory info found in log data using known patterns.")
        return ["Not available", "Not available", "Not available", "Not available"]

    except Exception as e:
        logging.error(f"Error in get_memory_info: {str(e)}")
        return ["Not available", "Not available", "Not available", "Not available"]

def calculate_flash_utilization(available_bytes, used_bytes):

    logging.info("Starting flash utilization calculation.")
    logging.debug(f"Input: available_bytes={available_bytes}, used_bytes={used_bytes}")

    total = available_bytes + used_bytes
    free = available_bytes
    used = total - free
    if total == 0:
        logging.error("Total flash size is zero, cannot calculate utilization")
        utilization = 0
        logging.warning("Returning 0% utilization due to zero total size.")
    else:
        utilization = (used / total) * 100
        logging.info(f"Flash utilization successfully calculated: {utilization:.2f}%")
    return total, used, free, utilization

def get_flash_info(log_data):
    logging.info("Starting flash info extraction.")
    try:
        flash_information = {}
        flash_id = ''

        # Match header lines like: "------------------ show flash: all ------------------"
        header_iter = list(re.finditer(
            r'^\s*-{2,}\s*show\s+flash(?:[-:]?\s*(\d+))?\s*:?(?:\s*all)?\s*-{2,}\s*$',
            log_data, flags=re.IGNORECASE | re.MULTILINE
        ))
        if not header_iter:
            logging.debug("No flash headers found in log data.")
            return "No flash information found"

        # Find positions of ANY show-section header to bound sections
        all_header_iter = list(re.finditer(
            r'^\s*-{2,}\s*show\b.*?-{2,}\s*$',
            log_data, flags=re.IGNORECASE | re.MULTILINE
        ))
        all_header_positions = [m.start() for m in all_header_iter]
        logging.debug(f"Found {len(header_iter)} 'show flash' headers and {len(all_header_positions)} total headers.")

        for hdr in header_iter:
            start = hdr.end()
            next_pos = next((p for p in all_header_positions if p > start), None)
            end = next_pos if next_pos is not None else len(log_data)
            section = log_data[start:end]

            # Pattern A: "NNN bytes available (MMM bytes used)"
            m_avail_used = re.search(
                r'^\s*(\d+)\s+bytes\s+available\s*\(\s*(\d+)\s+bytes\s+used\s*\)\s*$',
                section, flags=re.IGNORECASE | re.MULTILINE
            )
            # Pattern B: "NNN bytes total (MMM bytes free)"
            m_total_free = re.search(
                r'^\s*(\d+)\s+bytes\s+total\s*\(\s*(\d+)\s+bytes\s+free\s*\)\s*$',
                section, flags=re.IGNORECASE | re.MULTILINE
            )

            if m_avail_used:
                available_bytes = int(m_avail_used.group(1))
                used_bytes = int(m_avail_used.group(2))
                logging.debug(f"Flash {flash_id}: Matched Pattern A (Available/Used).")

            elif m_total_free:
                total_bytes = int(m_total_free.group(1))
                free_bytes = int(m_total_free.group(2))
                available_bytes = free_bytes
                used_bytes = total_bytes - free_bytes
                logging.debug(f"Flash {flash_id}: Matched Pattern B (Total/Free). Derived Available: {available_bytes}, Used: {used_bytes}")

            else:
                logging.warning(f"Flash {flash_id}: No recognizable summary line found in section.")
                continue

            total, used, free, utilization = calculate_flash_utilization(available_bytes, used_bytes)
            logging.info(f"Flash {flash_id} summary: Total={total}, Util={utilization:.2f}%")

            flash_id = hdr.group(1) or '1'
            logging.debug(f"Processing flash section: {flash_id} (Start: {start}, End: {end})")

            flash_information[flash_id] = [total, used, free, utilization]

        # FINAL DECISION & RETURN
        logging.debug("Flash info extraction completed.")
        if flash_information:
            return flash_information
        else:
            logging.warning("Finished iteration but no flash information was successfully extracted.")
            return "No flash information found"

    except Exception as e:
        logging.error(f"Error in get_flash_info: {str(e)}")
        return f"Require Manual Check"

def get_fan_status(log_data: str):
    logging.info("Starting fan status search.")
    try:
        # ACTION 1: Find all FAN status lines
        hits = re.findall(r'(?mi)^\s*FAN\s+is\s+([A-Z ]+)\s*$', log_data)
        
        # DECISION 1: Check if any hits were found
        if not hits:
            logging.warning("No 'FAN is ...' lines found in log data.")
            return ["Not available"]
            
        logging.debug(f"Found {len(hits)} raw fan status hits.")
            
        # ACTION 2: Normalize and convert status strings to uppercase
        vals = [h.strip().upper() for h in hits]
        
        # ACTION 3: Classify each status as "OK" or "Not OK"
        vals = ["OK" if v in ("OK", "GREEN") else "Not OK" for v in vals]
        
        logging.debug(f"Classified fan statuses: {vals}")
        
        # DECISION 2: Determine final overall status
        if vals and all(v == "OK" for v in vals):
            final_status = ["OK"]
            logging.info("All fan statuses are OK.")
        else:
            final_status = ["Not OK"]
            logging.warning("One or more fan statuses are Not OK.")
            
        return final_status
    except Exception as e:
        logging.error(f"Error in get_fan_status_ios: {str(e)}")
        return ["Require Manual Check"]

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

# --- Mock Logger (Replace with a real logging library in production) ---
# class DummyLogger:
#     def info(self, msg): pass
#     def debug(self, msg): pass
#     def error(self, msg): pass
# logging = DummyLogger()

# ====================================================================
# HELPER FUNCTION
# ====================================================================

def extract_env_sections(log_data: str) -> str:
    """
    Extracts content blocks likely from 'show environment' commands.
    This ensures the parser only looks at relevant data.
    """
    logging.info("Starting environment section extraction.")
    sections = []
    
    # 1. Search for commands in a command prompt environment (e.g., 'SWITCH#show env')
    command_blocks = re.split(r'(?m)^[^\r\n#]*#\s*', log_data)
    logging.debug(f"Split log data into {len(command_blocks)} command blocks.")
    for block in command_blocks:
        if re.match(r'(?i)^\s*sh(?:ow)?\s+env(?:ironment)?(?:\s+all)?', block.strip()):
            sections.append(block.strip())
            logging.debug("Found 'show env' section via command prompt split.")

    if not sections:
        logging.info("No 'show env' sections found via command prompt split. Falling back to dash headers.")
        # 2. Fallback for log formats where commands are wrapped in dashes (e.g., 'show tech')
        pattern_dash = r"(-{5,}\s*show environment(?:\s+all)?\s*-{5,}[\s\S]*?-{5,}\s*show)"
        matches_dash = re.findall(pattern_dash, log_data, re.IGNORECASE | re.DOTALL)
        sections.extend(matches_dash)
        logging.debug(f"Found {len(matches_dash)} sections via dash header fallback.")
        
    if not sections:
        logging.info("No sections found via dash header fallback. Attempting final check for raw output.")
        # 3. Final attempt: Return the whole log if it seems like a show env output without header
        if re.search(r'(?mi)temperature|temp|hotspot', log_data):
            logging.warning("No explicit 'show env' header found, but environmental keywords detected. Returning full log.")
            return log_data
        
    if sections:
        logging.info(f"Successfully extracted and combining {len(sections)} environment sections.")
    else:
        logging.warning("Exhausted all methods. No environment data extracted.")

    return "\n".join(sections)

# ====================================================================
# CORE FUNCTION: get_temperature_status
# ====================================================================

# def get_temperature_status(log_data: str) -> list[str]:
#     """
#     Analyzes log data using dynamic regex patterns to determine temperature status.
#     Returns a list of final statuses found (e.g., ['OK'], ['NOT OK'], or ['Not available']).
#     """
#     logging.info("Starting temperature status analysis.")
#     try:
#         search_data = extract_env_sections(log_data)
#         # Clean up common non-breaking spaces and carriage returns
#         search_data = search_data.replace('\xa0', ' ').replace('\r', '')

#         if not search_data:
#             logging.warning("No environment data found after extraction and cleanup.")
#             return ["Not available"]

#         # per_switch_status: Tracks the determined status (True=OK, False=NOT OK)
#         per_switch_status: dict[int, bool] = {} 
#         total_matches_found = False
        
#         logging.info("Starting Phase 1: Applying positive temperature patterns.")

#         # --- PHASE 1: Apply ALL Positive Patterns (Tier 1) ---
#         for pattern_info in TEMPERATURE_PATTERNS["positive_patterns"]:
            
#             # Use finditer for reliable extraction, especially for named groups
#             matches = re.finditer(pattern_info["regex"], search_data, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            
#             for m in matches:
#                 total_matches_found = True
#                 logging.debug(f"Positive Match found using pattern: {pattern_info['regex'][:40]}...")
                
#                 if pattern_info["source_type"] == "Switch":
#                     # For switch/module-specific status
#                     try:
#                         # Use default switch ID 1 if 'ID' group is not available, though it should be.
#                         sw_id = int(m.group('ID')) if 'ID' in m.groupdict() else 1
                        
#                         # Positive match reinforces OK status. Default assumption is True.
#                         per_switch_status[sw_id] = per_switch_status.get(sw_id, True) and True
#                         logging.debug(f"Switch {sw_id} status updated to OK via positive pattern.")
#                     except (IndexError, ValueError):
#                         # Catch if a Switch pattern unexpectedly lacks an ID group
#                         per_switch_status[1] = per_switch_status.get(1, True) and True
#                         logging.warning("Positive Switch pattern matched but ID extraction failed. Defaulting Switch 1 to OK.")
                
#                 elif pattern_info["source_type"] == "Global":
#                     # Global positive matches only signal we have *some* useful status data.
#                     # We assume Switch 1 if no IDs have been seen yet.
#                     if not per_switch_status:
#                         per_switch_status[1] = True
#                         logging.debug("Global positive match noted. Assuming Switch 1 OK.")

#             logging.info("Starting Phase 2: Applying negative temperature patterns.")

#         # --- PHASE 2: Apply ALL Negative Patterns (Tier 2) ---
#         # Negative patterns override any previously set status (Fail-Safe)
#         for pattern_info in TEMPERATURE_PATTERNS["negative_patterns"]:
#             matches = re.finditer(pattern_info["regex"], search_data, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            
#             for m in matches:
#                 total_matches_found = True
#                 logging.debug(f"Negative Match found using pattern: {pattern_info['regex'][:40]}...")

#                 if pattern_info["source_type"] == "Switch":
#                     # Explicitly set status to False (NOT OK) for the matching switch
#                     try:
#                         sw_id = int(m.group('ID')) if 'ID' in m.groupdict() else 1
#                         per_switch_status[sw_id] = False
#                         logging.warning(f"Switch {sw_id} status overridden to NOT OK by negative pattern.")
#                     except (IndexError, ValueError):
#                         per_switch_status[1] = False
#                         logging.warning("Negative Switch pattern matched but ID extraction failed. Defaulting Switch 1 to NOT OK.")
                
#                 elif pattern_info["source_type"] == "Global":
#                     # A single critical word applies globally, forcing all tracked switches to NOT OK.
#                     if per_switch_status:
#                         for sw_id in list(per_switch_status.keys()):
#                             per_switch_status[sw_id] = False
#                         logging.critical("Global critical negative pattern matched! Forcing ALL switches to NOT OK.")
#                     else:
#                          per_switch_status[1] = False # Assume Switch 1 is failing if no switch IDs yet
#                          logging.critical("Global critical negative pattern matched! Assuming Switch 1 NOT OK.")


#         # --- PHASE 3: Final Aggregation and Result (Tier 3 Heuristic) ---
#         logging.info("Starting Phase 3: Final aggregation.")
#         final_results = []
#         has_numeric_temps = re.search(r'(?mi)\b(?:temperature|temp|hotspot)\b[^:\n]*[:\s]\s*\d+\s*(?:C|F|Degree)', search_data)

#         if per_switch_status:
#             # Case 1: We have definitive, structured status data from Tier 1/2 checks
#             for sw in sorted(per_switch_status.keys()):
#                 status = "OK" if per_switch_status[sw] else "NOT OK"
#                 final_results.append(status)
#                 logging.debug(f"Final status for Switch {sw}: {status}")
#             logging.info(f"Final result determined from {len(per_switch_status)} structured switch statuses.")
            
#         # DECISION 9: Case 2 (Safe Fallback): No explicit status found, but numerical temp data exists
#         elif not total_matches_found and has_numeric_temps:
#             final_results = ["OK"]
#             logging.info("Assuming OK: No explicit status found, but numerical temperature data is present.")
        
#         # DECISION 10: Case 3: Log data was extracted but contains no status patterns or temp numbers
#         elif search_data:
#             final_results = ["Not available"]
#             logging.warning("Returning 'Not available': Environment data was found but lacked status patterns or numeric temperatures.")
            
#         # DECISION 11: Case 4: No environment data was found/extracted at all (should be caught by DECISION 1)
#         else:
#             final_results = ["Not available"]
            
#         # ACTION 7: Return unique statuses only
#         unique_results = list(set(final_results))
#         logging.info(f"Final unique temperature status results: {unique_results}")
#         return unique_results

#     except Exception as e:
#         logging.error(f"Critical error in get_temperature_status: {str(e)}")
#         # ACTION 8: Return Manual Check status on exception
#         return [f"Require Manual Check: {type(e).__name__}"]

def get_temperature_status(log_data: str):
    try:
        # 1) Classic formats
        hits1 = re.findall(r'(?mi)^\s*(?:SYSTEM\s+)?TEMPERATURE\s+is\s+([A-Z ]+)\s*$', log_data)
        hits2 = re.findall(r'(?mi)^\s*Temperature\s+State\s*:\s*([A-Z]+)\s*$', log_data)

        def _norm(s: str) -> str:
            s = s.strip().upper()
            return "OK" if s in ("OK", "GREEN") else "Not OK"
        if hits1 or hits2:
            vals = [_norm(v) for v in hits1] + [_norm(v) for v in hits2]
            return ["OK"] if vals and all(v == "OK" for v in vals) else ["Not OK"]
        # 2) 6880-style hierarchical output
        has_numeric_temps = re.search(r'(?mi)^\s*switch\s+\d+.*temperature\s*:\s*\d+\s*C\b', log_data)
        if not has_numeric_temps:
            return ["Not available"]
        for raw in log_data.splitlines():
            line = raw.strip()
            if not line:
                continue
            # benign lines
            if re.search(r'(?i)\bno\s+alarms?\b', line):
                continue
            if re.search(r'(?i)^\s*environmental\s+alarms\s*:\s*$', line):
                continue
            # explicit NOT OK
            if re.search(r'(?i)\bnot\s*ok\b', line):
                return ["Not OK"]
             # over-temp / critical
            if re.search(r'(?i)\bover[\s-]?temp(?:erature)?\b', line):
                return ["Not OK"]
            if re.search(r'(?i)\bcritical\b', line):
                return ["Not OK"]
            # alarm/fault/fail only if the same line DOESN'T say OK
            if re.search(r'(?i)\balarms?\b', line) and not re.search(r'(?i)\bok\b', line):
                # skip section headers like "... alarms:" (no status on the same line)
                if re.search(r':\s*$', line):
                    continue
                return ["Not OK"]
            if re.search(r'(?i)\bfault\b', line) and not re.search(r'(?i)\bok\b', line):
                return ["Not OK"]
            if re.search(r'(?i)\bfail(?:ed)?\b', line) and not re.search(r'(?i)\bok\b', line):
                return ["Not OK"]
            # saw numeric temps and no bad lines
            return ["OK"]
    except Exception as e:
        logging.error(f"Error in get_temperature_status_ios: {e}")
        return ["Require Manual Check"]


def get_power_supply_status(log_data: str):
    logging.info("Starting power supply status search.")
    try:
        statuses = []

        # ---- Table 1: "SW  PID ... Status"
        logging.debug("Starting Table 1 search (SW PID format).")
        for line in log_data.splitlines():
            m = re.match(
                r'^\s*(\d+)\s+[-\w].*?\b(Good|OK|Bad|Fail(?:ed)?|Alarm|Not\s+OK|Not\s+Present)\b',
                line, re.IGNORECASE
            )
            if m:
                st = m.group(2).upper()
                st = {"GOOD": "OK", "FAILED": "FAIL", "NOT  OK": "NOT OK"}.get(st, st)
                statuses.append(st)
                logging.debug(f"Table 1 match found, status: {st}")

        # ---- Table 2: block under "SW  Status  RPS Name ..."
        logging.debug("Starting Table 2 search (SW Status RPS format).")
        m_block = re.search(
            r'(?mi)^\s*SW\s+Status\s+RPS\s+Name.*?$\n(.*?)(?:^\s*-{3,}\s*|\Z)',
            log_data, re.DOTALL
        )
        if m_block:
            logging.debug("Found Table 2 block. Iterating lines.")
            for line in m_block.group(1).splitlines():
                m = re.match(
                    r'^\s*(\d+)\s+(Not\s+Present|OK|Bad|No\s+Input\s+Power|Not\s+OK|Fail(?:ed)?)\b',
                    line, re.IGNORECASE
                )
                if m:
                    st = m.group(2).upper()
                    st = {"FAILED": "FAIL", "NOT  OK": "NOT OK"}.get(st, st)
                    statuses.append(st)
                    logging.debug(f"Table 2 match found, status: {st}")

        # ---- 6880/4500-style key:value lines
        logging.debug("Starting key:value status search (6880/4500 style).")
        status_keys = r'(?:fan-fail|power-output-fail|internal-diagnostics|power-output-under-voltage)'
        pattern_6880 = re.compile(
            rf'(?mi)^\s*switch\s+\d+\s+power-supply\s+\d+\s+{status_keys}\s*:\s*'
            r'(OK|Not\s+OK|Fail(?:ed)?|Bad|Fault|No\s+Input\s+Power|Not\s+Present)\b'
        )
        for m in pattern_6880.finditer(log_data):
            st = m.group(1).upper()
            st = {"FAILED": "FAIL", "NOT  OK": "NOT OK"}.get(st, st)
            statuses.append(st)
            logging.debug(f"Key:value match found, status: {st}")

        logging.debug(f"Total collected raw statuses: {statuses}")

        if not statuses:
            logging.warning("No power supply status lines were found across all patterns.")
            return ["Not available"]

        ok_set = {"OK", "NOT PRESENT"}
        # OK only if all statuses are OK or Not Present
        if all(s in ok_set for s in statuses):
            final_status = ["OK"]
            logging.info("Overall power supply status is OK (all are OK or NOT PRESENT).")
        else:
            final_status = ["NOT OK"]
            logging.warning("Overall power supply status is NOT OK (found failing status).")
        
        return final_status

    except Exception as e:
        logging.error(f"Error in get_power_supply_status_ios: {e}")
        return ["Require Manual Check"]

def get_debug_status(log_data):
    logging.info("Starting debug status extraction.")
    try:
        logging.info("Starting debug status extraction.")
        match = re.search(r"sh|show\w*\s*de\w*", log_data, re.IGNORECASE)
        if match:
            hostname = get_hostname(log_data)
            if hostname == "Not available" or not hostname:
                logging.warning("Hostname is unavailable or 'Not available'. Cannot reliably anchor debug section.")
                return "Not available"
            end_anchor = rf"\n{re.escape(hostname)}#"
            debug_section_match = re.search(
                rf"Ip Address\s+Port\s*-+\|----------\s*([\s\S]*?){end_anchor}",
                log_data[match.end():],
                re.IGNORECASE
            )
            if debug_section_match and debug_section_match.group(1).strip():
                logging.info("Structured debug section found and contains data.")
                return "Require Manual Check"
            else:
                logging.warning("Debug command found, but no structured debug output section found or it was empty.")
                return "Command not found"
        else:
            logging.warning("No command matching 'show debug' or similar found in log data.")
            return "Command not found"
    except Exception as e:
        logging.error(f"Error in get_debug_status: {str(e)}")
        return "Require Manual Check"

def get_available_ports(log_data):
    try:
        logging.info("Starting available ports extraction.")
        start_marker = r"-{18}\s+show\s+interfaces?\s+status\s+-{18}"
        end_marker = r"-{18}\s+show\s+"
        
        # Find the start marker first
        start_match = re.search(start_marker, log_data)
        if not start_match:
            logging.debug("No available ports section found in log data.")
            return [[0]]
        
        # Get position after start marker
        start_pos = start_match.end()
        
        # Search for end marker ONLY in text after start marker
        end_match = re.search(end_marker, log_data[start_pos:])
        
        if end_match:
            # Extract section between start and end
            section = log_data[start_pos:start_pos + end_match.start()]
        else:
            # No end marker found, take everything after start
            section = log_data[start_pos:]
        
        ports = {}
        for line in section.strip().splitlines()[1:]:
            parts = line.split()
            # Keep original selection logic exactly as-is: requires 'notconnect' and '1' present
            if 'notconnect' in parts and '1' in parts:
                try:
                    interface = parts[0]
                    # Keep original normalization (Po excluded, Gi/Te/Ap supported)
                    switch_number = int(interface.split('/')[0].replace('Gi', '').replace('Te', '').replace('Ap', ''))
                    if switch_number not in ports:
                        ports[switch_number] = []
                    ports[switch_number].append(interface)
                except (ValueError, IndexError):
                    continue

        # Build per-switch counts with stable [[int]] shape
        max_switch = max(ports.keys()) if ports else 0
        if max_switch > 0:
            port_list = [[int(len(ports.get(i, [])))] for i in range(1, max_switch + 1)]
            logging.debug("Available ports extraction completed.")
            return port_list

        logging.debug("No available ports found in log data.")
        return [[0]]
    except Exception as e:
        logging.error(f"Error in get_available_ports: {str(e)}")
        # Preserve original error signaling shape
        return [["Require Manual Check"]]

def get_half_duplex_ports(log_data):
    logging.info("Starting half duplex ports extraction.")
    try:
        current_stack_size = _stack_size(log_data)
        logging.debug(f"Determined current stack size: {current_stack_size}")

        match = re.findall(r"^(\S+).*a-half.*$", log_data, re.IGNORECASE | re.MULTILINE)
        if match:
            switch_interfaces = {}
            logging.debug(f"Found {len(match)} potential half duplex interfaces.")
            for interface in match:
                try:
                    switch_number = re.search(r'\D+(\d+)/', interface).group(1)
                except AttributeError:
                    logging.warning(f"Failed to extract switch number from interface: {interface}")
                    continue
                if switch_number not in switch_interfaces:
                    logging.debug(f"Initialized list for Switch {switch_number}")
                switch_interfaces[switch_number].append(interface)
                logging.debug(f"Stored half duplex port {interface} under Switch {switch_number}")

            max_switch_number = max(map(int, switch_interfaces.keys()), default=0)
            # keep original outer shape [[count], ...] (no logic change), but ensure counts are ints
            half_duplex_ports_per_switch = [[int(len(switch_interfaces.get(str(i), [])))] for i in range(1, max_switch_number + 1)]
            logging.info(f"Half duplex ports extracted: {half_duplex_ports_per_switch}")
            return half_duplex_ports_per_switch
        else:
            logging.debug("No half duplex ports found in log data.")
            # keep the original [[...]] shape but use numeric 0 instead of "0"
            return [[0]] * current_stack_size
    except Exception as e:
        logging.error(f"Critical error in get_half_duplex_ports: {str(e)}")
        # preserve original error signaling & shape
        return [["Require Manual Check"]] * current_stack_size

def get_interface_remark(log_data):
    logging.info("Starting half duplex ports extraction.")
    try:
        current_stack_size = _stack_size(log_data)
        logging.debug(f"Determined current stack size: {current_stack_size}")
        match = re.findall(r"^(\S+).*a-half.*$", log_data, re.IGNORECASE | re.MULTILINE)
        if match:
            switch_interfaces = {}
            logging.debug(f"Found {len(match)} interfaces running in half duplex.")
            for interface in match:
                switch_number = re.search(r'\D+(\d+)/', interface)
                if not switch_number:
                    logging.debug(f"Skipping interface {interface}: could not extract switch number.")
                    continue
                switch_number = switch_number.group(1)
                if switch_number not in switch_interfaces:
                    switch_interfaces[switch_number] = []
                    logging.debug(f"Initialized list for Switch {switch_number}")
                switch_interfaces[switch_number].append(interface)
                logging.debug(f"Stored interface remark {interface} under Switch {switch_number}")

            max_switch_number = max(map(int, switch_interfaces.keys()), default=0)
            logging.debug(f"Max switch number found: {max_switch_number}")

            interface_remark = [switch_interfaces.get(str(i), []) for i in range(1, max_switch_number + 1)]
            # typo fixed + consistent sentinel
            interface_remark = [sublist if sublist else ['Not available'] for sublist in interface_remark]
            
            logging.info(f"Interface remarks extracted for switches 1 to {max_switch_number}.")
            return [["Not available"]] * current_stack_size
        else:
            logging.info("No half duplex interface remarks found in log data.")
            return [["Not available"]] * current_stack_size
    except Exception as e:
        logging.error(f"Error in get_interface_remark: {str(e)}")
        return [["Require Manual Check"]] * _stack_size(log_data)

def get_nvram_config_update(log_data):
    logging.info("Starting NVRAM config update extraction.")
    try:
        match = re.search(r"NVRAM\s+config\s+last\s+updated\s+at\s+(.+)", log_data, re.IGNORECASE)
        if match:
            # ACTION 2: Extract the timestamp, cleaning up any 'by user' information
            full_timestamp = match.group(1).strip()
            # Split by 'by' to remove potential username/method information
            timestamp = full_timestamp.split('by')[0].strip()
            
            logging.info(f"NVRAM config update found. Timestamp: {timestamp}")
            return ["Yes", timestamp]
        else:
            # DECISION 2: No match found
            logging.info("No NVRAM config update timestamp found in log data.")
            return ["No", "Not available"]
    except Exception as e:
        logging.error(f"Critical error in get_nvram_config_update: {str(e)}")
        return [f"Require Manual Check", "Not available"]

def get_critical_logs(log_data):
    if not isinstance(log_data, str) or not log_data:
        logging.error("Invalid input type or empty string for log_data")
        return "Require Manual Check"
    try:
        logging.info("Starting critical logs extraction.")
        match = re.search(r'(sh|show)\s+(log|logging)\s*-+\n(.*?)(?=\n-+\s*show|\Z)', log_data, re.DOTALL | re.IGNORECASE)
        if match:
            logging_section = match.group(0)
            logging.debug("Found logging section. Checking for critical severity.")
            if any(f"-{i}-" in logging_section for i in range(3)):
                logging.info("Critical log entries (severity 0, 1, or 2) found.")
                return "YES"
            else:
                logging.info("Logging section found, but no critical log entries (severity 0, 1, or 2) detected.")
                return "NO"
        else:
            logging.warning("No logging section found matching the standard header pattern.")
            return "Require Manual Check"
            
    except Exception as e:
        # LOGGING PRESENT: Error handling
        logging.error(f"Error Occurred while parsing logs!\n{e}")
        return "Require Manual Check"

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

def process_file(file_path: str):
    try:
        logging.info(f"Starting processing of file: {file_path}")
        with open(file_path, 'r', errors= 'ignore') as file:
            log_data = file.read()
        logging.debug(f"File read complete. Log data size: {len(log_data)} bytes.")

        data = {}
        stack = check_stack(log_data)
        logging.debug(f"Stack check returned: {stack}. (Type: {type(stack).__name__})")

        # print("STACK:", stack)
        if not stack:
            logging.info("Processing as a single non-stacked device.")
            memory_info = get_memory_info(log_data)
            flash_info = get_flash_info(log_data)
            logging.debug(f"Memory info extracted: {memory_info}. Flash info extracted: {type(flash_info).__name__}")

            if isinstance(flash_info, dict):
                flash_info = flash_info.get('1', ["Not available", "Not available", "Not available", "Not available"])
                logging.debug("Normalized flash info from dict using key '1'.")
            elif isinstance(flash_info, str):
                flash_info = ["Not available", "Not available", "Not available", "Not available"]
                logging.debug("Normalized flash info from string to 'Not available'.")
            
            data = {
                "File name": [get_ip_address(file_path)[0]],
                "Host name": [get_hostname(log_data)],
                "Model number": [get_model_number(log_data)],
                "Serial number": [get_serial_number(log_data)],
                "Interface ip address": [get_ip_address(file_path)[1]],
                "Uptime": [get_uptime(log_data)],
                "Current s/w version": [get_current_sw_version(log_data)],
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
                # Add default values for the remaining columns
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
            logging.info("Single device data dictionary populated successfully.")
        else:
            logging.info("Processing as a stacked device.")
            data = {}
            file_name, hostname, model_number, serial_number, ip_address, uptime = [], [], [], [], [], []
            current_sw, last_reboot, cpu, memo, flash, critical = [], [], [], [], [], []
            total_memory, used_memory, free_memory, memory_utilization = [], [], [], []
            total_flash, used_flash, free_flash, flash_utilization = [], [], [], []
            avail_free, duplex, interface_remark, config_status, config_date = [], [], [], [], []
            
            current_stack_size = _stack_size(log_data)
            stack_switch_data = _parse_stack_switch(log_data)
            flash_memory_details = get_flash_info(log_data)

            logging.debug(f"Stack size: {current_stack_size}. Parsed switch data keys: {list(stack_switch_data.keys())}")
            
            for item in range(current_stack_size):  # ← FIXED: Use renamed variable
                switch_index = item + 1 # 1-based index
                logging.debug(f"Processing data for Switch {switch_index}/{current_stack_size}.")
                if item == 0:
                    file_name.append(get_ip_address(file_path)[0])
                    model_number.append(get_model_number(log_data))
                    serial_number.append(get_serial_number(log_data))
                    uptime.append(get_uptime(log_data))
                    last_reboot.append(get_last_reboot_reason(log_data))
                    logging.debug(f"Populated core metrics for Switch {switch_index} (main).")
                else:
                    file_name.append(get_ip_address(file_path)[0] + (f"_Stack_{str(item+1)}"))
                    model_number.append(stack_switch_data[f'stack switch {item + 1} Model_Number'])
                    serial_number.append(stack_switch_data[f'stack switch {item + 1} Serial_Number'])
                    uptime.append(stack_switch_data[f'stack switch {item + 1} Uptime'])
                    last_reboot.append(stack_switch_data[f'stack switch {item + 1} Last Reboot'])
                    logging.debug(f"Populated core metrics for Switch {switch_index} (member).")
                
                memo = get_memory_info(log_data)
                total_memory.append(memo[0])
                used_memory.append(memo[1])
                free_memory.append(memo[2])
                memory_utilization.append(memo[3])

                if isinstance(flash_memory_details, dict) and str(item+1) in flash_memory_details:
                    flash = flash_memory_details[str(item+1)]
                    logging.debug(f"Found switch-specific flash info for Switch {switch_index}.")
                elif isinstance(flash_memory_details, dict) and '1' in flash_memory_details:
                    flash = flash_memory_details['1']
                    logging.debug(f"Using default flash '1' info for Switch {switch_index}.")
                else:
                    flash = ["Not available", "Not available", "Not available", "Not available"]
                    logging.debug(f"Flash info unavailable for Switch {switch_index}.")
                total_flash.append(flash[0])
                used_flash.append(flash[1])
                free_flash.append(flash[2])
                flash_utilization.append(f"{flash[3]:.2f}%" if isinstance(flash[3], (int, float)) else flash[3])
                
                hostname.append(get_hostname(log_data))
                ip_address.append(get_ip_address(file_path)[1])
                current_sw.append(get_current_sw_version(log_data))
                cpu.append(get_cpu_utilization(log_data))
                fan = get_fan_status(log_data)
                temp = get_temperature_status(log_data)
                psu = get_power_supply_status(log_data)
                critical.append(get_critical_logs(log_data))
                avail_free = get_available_ports(log_data)
                duplex = get_half_duplex_ports(log_data)
                interface_remark = get_interface_remark(log_data)
                config_status.append(get_nvram_config_update(log_data)[0])
                config_date.append(get_nvram_config_update(log_data)[1])
                
            data["File name"] = file_name
            data["Host name"] = hostname
            data["Model number"] = model_number
            data["Serial number"] = serial_number
            data["Interface ip address"] = ip_address
            data["Uptime"] = uptime
            data["Current s/w version"] = current_sw
            data["Last Reboot Reason"] = last_reboot
            data["Any Debug?"] = [get_debug_status(log_data) for _ in range(current_stack_size)]  # ← FIXED
            data["CPU Utilization"] = cpu
            data["Total memory"] = total_memory
            data["Used memory"] = used_memory
            data["Free memory"] = free_memory
            data["Memory Utilization (%)"] = memory_utilization
            data["Total flash memory"] = total_flash
            data["Used flash memory"] = used_flash
            data["Free flash memory"] = free_flash
            data["Used Flash (%)"] = flash_utilization
            data["Fan status"] = fan
            data["Temperature status"] = temp
            data["PowerSupply status"] = psu
            data["Critical logs"] = critical
            data["Available Free Ports"] = avail_free
            data["Any Half Duplex"] = duplex
            data["Interface/Module Remark"] = interface_remark
            data["Config Status"] = config_status
            data["Config Save Date"] = config_date
            data["Current SW EOS"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["Suggested s/w ver"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["s/w release date"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["Latest S/W version"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["Production s/w is deffered or not?"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["End-of-Sale Date: HW"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["Last Date of Support: HW"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["End of Routine Failure Analysis Date: HW"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["End of Vulnerability/Security Support: HW"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["End of SW Maintenance Releases Date: HW"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["Remark"] = ["Yet to check"] * current_stack_size  # ← FIXED
            logging.info(f"Stacked device data dictionary populated for {current_stack_size} entries.")
        logging.debug(f"File processing completed: {file_path}")
        return data
    except Exception as e:
        logging.error(f"Error in process_file: {str(e)}")
        # print(f"Error in process_file: {str(e)}")

def ios_check(log_data):
    try:
        logging.info("Starting IOS check.")
        if get_current_sw_version(log_data): 
            logging.debug("IOS check completed. Version found.")
            return True
        else:
            logging.debug("IOS check completed. Version not found.")
            return False
    except Exception as e:
        logging.error(f"Error in ios_check: {str(e)}")

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
        for filename in sorted(os.listdir(directory_path), key=str.casefold):
            if not (filename.endswith('.txt') or filename.endswith('.log')):
                logging.debug(f"Skipping non-log file: {filename}")
                continue
            if filename.startswith('~$') or filename.startswith('.'):
                logging.debug(f"Skipping temp/hidden file: {filename}")
                continue
            candidates.append(os.path.join(directory_path, filename))

        logging.info(f"Identified {len(candidates)} eligible files for processing.")

        if not candidates:
            logging.warning("No .txt or .log files found to process.")
            return data  # empty list

        def _process_one(file_path):
            logging.debug(f"Worker started processing: {os.path.basename(file_path)}")
            try:
                with open(file_path, 'r', errors='ignore') as f:
                    log_data = f.read()
                logging.debug(f"Successfully read file: {os.path.basename(file_path)}")
            except Exception as e:
                logging.error(f"Unreadable file {file_path}: {e}")
                return _placeholder_entry(file_path)

            try:
                if ios_check(log_data):
                    logging.debug(f"{os.path.basename(file_path)} is IOS classic. Appending value!")
                    return process_file(file_path)  # your original pipeline
                else:
                    logging.debug(f"{os.path.basename(file_path)} is NOT IOS classic. Producing info row.")
                    return _placeholder_entry(file_path)
            except Exception as e:
                logging.error(f"Error processing {file_path}: {e}")
                return _placeholder_entry(file_path)

        from concurrent.futures import ThreadPoolExecutor, as_completed
        max_workers = min(16, (os.cpu_count() or 4) * 2)
        futures = []
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for fp in candidates:
                futures.append(ex.submit(_process_one, fp))
            for fut in as_completed(futures):
                try:
                    result = fut.result()
                    if isinstance(result, dict) and result:
                        data.append(result)
                        logging.debug(f"Successfully appended processed data to result list.")
                    else:
                        logging.debug(f"Skipping non-dictionary or empty result from worker.")
                except Exception as e:
                    logging.error(f"Worker future raised an unhandled exception: {e}")

        logging.info(f"Directory processing finished. Successfully processed {len(data)} entries.")
        return data

    except Exception as e:
        logging.error(f"Critical error in process_directory: {str(e)}")
        return 500
    
def _placeholder_entry(file_path, reason_text="Non-IOS"):
    try:
        fname, _ = get_ip_address(file_path)
    except Exception:
        fname = os.path.basename(file_path)

    U = "Require Manual Check"

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
        "Remark": ["Non-IOS"],
    }

def main():
    data = []
    # data = process_directory(r"C:\Users\girish.n\Downloads\OneDrive_2_13-10-2025 1")
    data = process_file(file_path = r"C:\Users\girish.n\Downloads\SVR138028674 1\CBJ01-T0-IB-RTR02(10.164.0.41).txt")
    print_data(data)
    # for item in data:
    #     print_data(item['File name'])
    #     print(item['PowerSupply status'])
    #     # print(item['Fan status'])
    #     # print(item['Temperature status'])

if __name__ == "__main__":
    main()