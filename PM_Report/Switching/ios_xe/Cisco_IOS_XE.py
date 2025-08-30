import re
import os
import logging
import datetime  # ← ADDED: Missing import
import pprint as pp
# from . 
import IOS_XE_Stack_Switch
    
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
    """
    Return a normalized IPv4 (no leading zeros, stripped), or:
      - "Require Manual Check" if clearly malformed
      - "Not available" if empty-ish
    """
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
    """
    Management IP selection priority inside config:
      1) iface name/description contains mgmt|manage|management
      2) LoopbackX
      3) Vlan 1
    Skips DHCP stanzas. Returns normalized IPv4 or None.
    """
    try:
        if not log_data:
            return None

        blocks = _INTERFACE_BLOCK_RE.findall(log_data)
        buckets = {"mgmt": [], "loop": [], "vlan1": []}

        for blk in blocks:
            # Skip DHCP-configured stanzas (no static IP present)
            if re.search(r'(?im)^\s*ip\s+address\s+dhcp\b', blk):
                continue

            # Collect primary, non-secondary IPs
            ips = []
            for m in _IP_LINE_RE.finditer(blk):
                if re.search(r'\bsecondary\b', m.group(0), flags=re.IGNORECASE):
                    continue
                ips.append(m.group('ip'))
            if not ips:
                continue

            # Classify stanza
            header = re.search(r'(?im)^interface\s+([^\r\n]+)', blk)
            iface = header.group(1) if header else ""

            name_has_mgmt = re.search(r'\b(mgmt|manage|management)\b', iface, re.IGNORECASE)
            desc_has_mgmt = re.search(r'(?im)^\s*description\s+.*\b(mgmt|manage|management)\b', blk)

            if name_has_mgmt or desc_has_mgmt:
                buckets["mgmt"].append(ips)
            elif re.search(r'(?im)^interface\s+loopback\d+\b', blk):
                buckets["loop"].append(ips)
            elif re.search(r'(?im)^interface\s+vlan\s*1\b', blk):
                buckets["vlan1"].append(ips)

        # Pick first valid IP from the highest-priority non-empty bucket
        for key in ("mgmt", "loop", "vlan1"):
            for ips in buckets[key]:
                for raw in ips:
                    ip_norm = sanitize_ipv4(raw)
                    if ip_norm not in {"Not available", "Require Manual Check"}:
                        return ip_norm
        return "Require manual check"
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
        return f"Error in get_hostname: {str(e)}"

def get_model_number(log_data):
    try:
        logging.info("Starting model number search.")
        match = re.search(r"Model Number\s+:\s+(\S+)", log_data)
        logging.debug("Model number search completed.")
        return match.group(1) if match else "Require Manual Check"
    except Exception as e:
        logging.error(f"Error in get_model_number: {str(e)}")
        return f"Error in get_model_number: {str(e)}"

def get_ip_address(file_path):
    """
    Enhanced: strict IPv4 validation + content fallback using sanitize_ipv4.
    Returns a tuple: (file_name, ip_or_status_string).
    """
    try:
        logging.info("Starting IP address extraction from file path.")
        file_name = os.path.basename(file_path) if isinstance(file_path, str) else str(file_path)

        # 1) Filename-first: collect candidates, return the first that sanitizes cleanly
        filename_candidates = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?)", file_name)
        for cand in filename_candidates:
            ip_norm = sanitize_ipv4(cand)
            if ip_norm not in {"Not available", "Require Manual Check"}:
                logging.debug(f"IP found in filename: {ip_norm}")
                return (file_name, ip_norm)

        # 2) Content fallback (only if needed)
        try:
            with open(file_path, "r", errors="ignore") as f:
                log_data = f.read()

            # Find all IPv4-ish tokens (allowing optional CIDR), sanitize each, pick first valid
            content_candidates = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?)", log_data)
            for cand in content_candidates:
                ip_norm = sanitize_ipv4(cand)
                if ip_norm not in {"Not available", "Require Manual Check"}:
                    logging.debug(f"IP found in file content: {ip_norm}")
                    return (file_name, ip_norm)

            # --- Last chance: call existing get_ip helper if available ---
            try:
                from_content = get_ip(log_data)
                ip_norm = sanitize_ipv4(from_content)
                if ip_norm not in {"Not available", "Require Manual Check"}:
                    logging.debug(f"IP found via get_ip helper: {ip_norm}")
                    return (file_name, ip_norm)
            except Exception as e:
                logging.warning(f"get_ip helper failed on {file_name}: {e}")

        except Exception as inner:
            logging.warning(f"Content fallback failed while reading {file_name}: {inner}")

        logging.debug("No valid IP found; manual check required.")
        return (file_name, "Require Manual Check")

    except Exception as e:
        logging.error(f"Error in get_ip_address: {str(e)}")
        safe_name = os.path.basename(file_path) if isinstance(file_path, str) else "Unknown"
        return (safe_name, "Require Manual Check")

def get_serial_number(log_data):
    try:
        logging.info("Starting serial number search.")
        match = re.search(r"System Serial Number\s+:\s+(\S+)", log_data)
        logging.debug("Serial number search completed.")
        return match.group(1) if match else "Require Manual Check"
    except Exception as e:
        logging.error(f"Error in get_serial_number: {str(e)}")
        return f"Error in get_serial_number: {str(e)}"

def get_uptime(log_data):
    try:
        logging.info("Starting uptime search.")
        hostname = get_hostname(log_data)
        # If hostname isn't available, don't attempt a bogus regex match
        if not hostname or hostname == "Not available":
            logging.debug("Uptime search skipped due to unavailable hostname.")
            return "Not available"
        # Escape hostname to prevent regex meta-characters from breaking the pattern
        pattern = rf"{re.escape(hostname)}\s+uptime is\s+(.+)"
        match = re.search(pattern, log_data)
        logging.debug("Uptime search completed.")
        return match.group(1).strip() if match else "Require Manual Check"
    except Exception as e:
        logging.error(f"Error in get_uptime: {str(e)}")
        return f"Error in get_uptime: {str(e)}"

def get_current_sw_version(log_data):
    """
    Returns the software version string from 'show version' output.
    Supports:
      • IOS-XE 16/17 lines like: "Cisco IOS XE Software, Version 16.09.04"
      • IOS-XE 16/17 classic line: "Cisco IOS Software [...], Version 16.9.4, RELEASE ..."
      • IOS-XE 3.x lines like: "Cisco IOS Software, IOS-XE Software, ..., Version 03.06.06E ..."
    On no match: "Not available".
    """
    try:
        if not log_data:
            return "Not available"

        # 1) Most explicit: "Cisco IOS XE Software, Version X"
        m = re.search(r'(?mi)^\s*Cisco\s+IOS\s+XE\s+Software,\s*Version\s+([^\s,]+)', log_data)
        if m:
            return m.group(1).strip()

        # 2) Common classic banner line that also appears on 16/17 & 3.x:
        #    "Cisco IOS Software ... Version X[, ]"
        m = re.search(r'(?mi)^\s*Cisco\s+IOS\s+Software.*?\bVersion\s+([^\s,]+)', log_data)
        if m:
            return m.group(1).strip()

        # 3) Safety net for variants like "IOS-XE Software, ... Version X"
        m = re.search(r'(?mi)\bIOS[- ]?XE\s+Software.*?\bVersion\s+([^\s,]+)', log_data)
        if m:
            return m.group(1).strip()

        # 4) Last-chance: grab the first "Version X" in the top of the file
        head = "\n".join(log_data.splitlines()[:50])
        m = re.search(r'(?mi)\bVersion\s+([0-9A-Za-z.\(\)]+)', head)
        if m:
            return m.group(1).strip()

        return "Not available"

    except Exception as e:
        logging.error(f"Error in get_current_sw_version: {str(e)}")
        return "Not available"

def get_last_reboot_reason(log_data):
    try:
        logging.info("Starting last reboot reason search.")
        match = re.search(r"Last reload reason:\s+(.+)", log_data)
        logging.debug("Last reboot reason search completed.")
        return match.group(1) if match else "Require Manual Check"
    except Exception as e:
        logging.error(f"Error in get_last_reboot_reason: {str(e)}")
        return f"Error in get_last_reboot_reason: {str(e)}"

def get_cpu_utilization(log_data):
    try:
        logging.info("Starting CPU utilization search.")
        match = re.search(r"five minutes:\s+(\d+)%", log_data)
        logging.debug("CPU utilization search completed.")
        return match.group(1) + "%" if match else "Require Manual Check"
    except Exception as e:
        logging.error(f"Error in get_cpu_utilization: {str(e)}")
        return f"Error in get_cpu_utilization: {str(e)}"

def check_stack(log_data):
    try:
        logging.info("Starting stack check.")
        cleared_data_start = re.search('show version', log_data, re.IGNORECASE)
        if not cleared_data_start:
            logging.debug("No 'show version' found in log data.")
            return False

        cleared_data_end = re.search('show', log_data[cleared_data_start.span()[1] + 1:], re.IGNORECASE)
        if not cleared_data_end:
            req_data = log_data[cleared_data_start.span()[1]:]
        else:
            req_data = log_data[cleared_data_start.span()[1]:cleared_data_start.span()[1] + cleared_data_end.span()[0]]

        start_point = re.search(r"System Serial Number\s+:\s+(\S+)", req_data)
        if not start_point:
            logging.debug("No system serial number found in log data.")
            return False

        next_start_end_point = re.search(r"Switch\s+(\S+)", req_data[start_point.span()[1]:])
        if not next_start_end_point:
            logging.debug("No switch information found in log data.")
            return False
        else:
            stack_details = IOS_XE_Stack_Switch.parse_ios_xe_stack_switch(log_data)
            logging.debug("Stack check completed.")
            return stack_details
    except Exception as e:
        logging.error(f"Error in check_stack: {str(e)}")
        return f"Error in check_stack: {str(e)}"

def get_memory_info(log_data):
    """
    Works for:
      • IOS-XE 16/17: 'show memory statistics' (Processor ... Total(b) Used(b) Free(b))
      • IOS-XE 3.x :  'show process memory sorted' (System memory : 3931592K total, 1446776K used, 2484816K free, ...)
    Returns: [total_bytes, used_bytes, free_bytes, "util%"] or all "Not available" on failure.
    """
    try:
        logging.info("Starting memory info extraction.")

        if not log_data:
            return ["Not available", "Not available", "Not available", "Not available"]

        import re

        def _parse_num_with_unit(token: str) -> int | None:
            """
            Parse numbers possibly with commas and unit suffix (K/M/G, case-insensitive).
            Returns bytes as int.
            Examples: '531325444' -> 531325444
                      '3,931,592K' -> 3931592 * 1024
                      '2048M' -> 2048 * 1024 * 1024
                      '2G' -> 2 * 1024 ** 3
            """
            if not token:
                return None
            s = token.strip().replace(",", "")
            m = re.match(r'^(\d+(?:\.\d+)?)([KkMmGg])?$', s)
            if not m:
                # also accept plain integers with no unit
                if s.isdigit():
                    try:
                        return int(s)
                    except Exception:
                        return None
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
            return int(num * mult)

        # ----------------------------
        # Path A: IOS-XE 16/17 format
        # Example:
        # Processor  7F661F4010   531325444   120791012   410534432   ...
        # ----------------------------
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
            logging.debug("Memory info (Processor table) extraction completed.")
            return [total, used, free, f"{utilization:.2f}%"]

        # ----------------------------
        # Path B: IOS-XE 3.x format
        # Example:
        # System memory  : 3931592K total, 1446776K used, 2484816K free, 221424K kernel reserved
        # ----------------------------
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
            logging.debug("Memory info (System memory summary) extraction completed.")
            return [total, used, free, f"{utilization:.2f}%"]

        logging.debug("No memory info found in log data.")
        return ["Not available", "Not available", "Not available", "Not available"]

    except Exception as e:
        logging.error(f"Error in get_memory_info: {str(e)}")
        return ["Not available", "Not available", "Not available", "Not available"]

def calculate_flash_utilization(available_bytes, used_bytes):
    total = available_bytes + used_bytes
    free = available_bytes
    used = total - free
    if total == 0:
        logging.error("Total flash size is zero, cannot calculate utilization")
        utilization = 0
    else:
        utilization = (used / total) * 100
    return total, used, free, utilization

def get_flash_info(log_data):
    try:
        logging.info("Starting flash info extraction.")
        total_flashes = re.findall(r"show\s+flash(?:-\d+)?:\s*all", log_data)
        flash_information = {}
        if total_flashes:
            for item in total_flashes:
                start_index = re.search(item, log_data)
                if start_index:
                    end_index = re.search(r"show\s", log_data[start_index.span()[1]:])
                    if end_index:
                        flash_data = log_data[start_index.span()[1]:start_index.span()[1] + end_index.span()[0]]
                        m = re.findall(r'^\s*(\d+)\s+bytes\s+available\s+\((\d+)\s+bytes\s+used\)', flash_data, re.MULTILINE)
                        if m:
                            for available_str, used_str in m:
                                available_bytes = int(available_str)
                                used_bytes = int(used_str)
                                total, used, free, utilization = calculate_flash_utilization(available_bytes, used_bytes)
                                flash_number = re.findall(r'\d+', item)
                                key = flash_number[0] if flash_number else '1'
                                flash_information[key] = [total, used, free, utilization]
            logging.debug("Flash info extraction completed.")
            return flash_information if flash_information else "No flash information found"
        logging.debug("No flash info found in log data.")
        return "No flash information found"
    except Exception as e:
        logging.error(f"Error in get_flash_info: {str(e)}")
        return f"Error in get_flash_info: {str(e)}"

def get_fan_status(log_data):
    """
    Parse fan lines from 'show environment all' style output (XE 16/17 and XE 3.x).
    Normalizes to: "OK" if all present fans are OK; "Not OK" if any fan reports a fault;
    ignores "NOT PRESENT" entries. If nothing is found, returns "Unsupported version".
    """
    try:
        if not log_data:
            return "Not available"

        # Match lines like:
        #   "Switch 1 FAN 1 is OK"
        #   "FAN PS-2 is NOT PRESENT"
        fan_pat = re.compile(
            r'(?mi)^\s*(?:Switch\s+\d+\s+)?FAN(?:\s+(?:PS-\d+|\d+))?\s+is\s+([A-Z ]+)\s*$'
        )

        statuses = []
        for m in fan_pat.finditer(log_data):
            raw = m.group(1).strip().upper()
            if raw.startswith("OK"):
                statuses.append("OK")
            elif "NOT PRESENT" in raw:
                statuses.append("NOT PRESENT")
            elif raw in {"NOT OK", "FAILED", "FAIL", "FAULTY", "BAD"}:
                statuses.append("NOT OK")
            else:
                # Unknown token – keep but treat as suspicious
                statuses.append(raw)

        if not statuses:
            return "Unsupported version"

        # Compute overall health: ignore NOT PRESENT; any NOT OK => Not OK; else OK if any OK seen
        present_statuses = [s for s in statuses if s != "NOT PRESENT"]
        if any(s == "NOT OK" for s in present_statuses):
            return "Not OK"
        if any(s == "OK" for s in present_statuses):
            return "OK"

        # Only NOT PRESENT seen (no installed fans reported)
        return "Not available"

    except Exception as e:
        logging.error(f"Error in get_fan_status: {str(e)}")
        return "Not available"

def get_temperature_status(log_data: str):
    """
    Returns a list with one status per switch: ["OK", "Not OK", ...]
    Supports:
      - 16.x / 3.x: "Switch N: SYSTEM TEMPERATURE is OK"
      - 17.x:       "SYSTEM INLET|OUTLET|HOTSPOT   N   GREEN|YELLOW|RED ..."
    If nothing found: ["Not available"]
    """
    try:
        logging.info("Starting temperature status extraction.")
        per_switch_ok = {}

        # --- 17.x style: SYSTEM INLET/OUTLET/HOTSPOT <sw> <GREEN|...>
        # e.g. "SYSTEM INLET    2               GREEN                 25 Celsius ..."
        m_sys = re.findall(r'(?mi)^\s*SYSTEM\s+(?:INLET|OUTLET|HOTSPOT)\s+(\d+)\s+([A-Z]+)', log_data)
        if m_sys:
            tmp = {}
            for sw_str, state in m_sys:
                sw = int(sw_str)
                state_up = state.strip().upper()
                # all GREEN => OK; any non-GREEN => Not OK
                prev = tmp.get(sw, True)
                tmp[sw] = prev and (state_up == "GREEN")
            per_switch_ok.update(tmp)

        # --- 16.x / 3.x style: "Switch N: SYSTEM TEMPERATURE is OK"
        m_legacy = re.findall(r'(?mi)^\s*Switch\s+(\d+):\s*SYSTEM\s+TEMPERATURE\s+is\s+([A-Za-z ]+)\s*$', log_data)
        if m_legacy:
            tmp = {}
            for sw_str, status_text in m_legacy:
                sw = int(sw_str)
                ok = (status_text.strip().upper() == "OK")
                prev = tmp.get(sw, True)
                tmp[sw] = prev and ok
            # Merge — if we already had 17.x signals, AND them
            for sw, ok in tmp.items():
                per_switch_ok[sw] = per_switch_ok.get(sw, True) and ok

        if not per_switch_ok:
            logging.debug("No temperature patterns matched.")
            return ["Not available"]

        result = ["OK" if per_switch_ok[sw] else "Not OK" for sw in sorted(per_switch_ok.keys())]
        logging.debug("Temperature status extraction completed.")
        return result if result else ["Not available"]

    except Exception as e:
        logging.error(f"Error in get_temperature_status: {str(e)}")
        return [f"Error in get_temperature_status: {str(e)}"]


def get_fan_status(log_data: str):
    """
    Returns a list with one status per switch: ["OK", "Not OK", ...]
    Supports:
      - 16.x / 3.x: "Switch N FAN X is OK|NOT OK|NOT PRESENT"
      - 17.x:       fan table under "Switch FAN Speed State Airflow direction"
                    lines like: "<sw>  <rpm>  OK|NOT OK  <dir>"
    Rules:
      - NOT PRESENT is treated as OK for fan presence.
      - If any fan line for a switch is NOT OK -> switch is Not OK.
    If nothing found: ["Not available"]
    """
    try:
        logging.info("Starting fan status extraction.")
        per_switch_ok = {}

        # --- 16.x / 3.x style: "Switch 1 FAN 2 is OK"
        m_legacy = re.findall(r'(?mi)^\s*Switch\s+(\d+)\s+FAN\s+\d+\s+is\s+([A-Za-z ]+)\s*$', log_data)
        if m_legacy:
            tmp = {}
            for sw_str, state_text in m_legacy:
                sw = int(sw_str)
                st = state_text.strip().upper()
                # NOT PRESENT -> acceptable
                is_ok = (st == "OK" or st == "NOT PRESENT")
                prev = tmp.get(sw, True)
                tmp[sw] = prev and is_ok
            per_switch_ok.update(tmp)

        # --- 17.x style: "Switch FAN Speed State Airflow direction" block
        # Lines look like: "  2    15458   OK Front to Back"
        # We'll find the blocks and parse lines that start with a switch number.
        if re.search(r'(?mi)^\s*Switch\s+FAN\s+Speed\s+State\s+Airflow\s+direction\s*$', log_data):
            blocks = re.split(r'(?mi)^\s*Switch\s+FAN\s+Speed\s+State\s+Airflow\s+direction\s*$', log_data)
            tmp = {}
            for blk in blocks[1:]:
                for raw in blk.splitlines():
                    line = raw.strip()
                    if not line or line.startswith('-'):
                        continue
                    cols = line.split()
                    # Expect: <sw> <rpm> <state> <...>
                    if len(cols) >= 3 and cols[0].isdigit() and cols[1].isdigit():
                        sw = int(cols[0])
                        st = cols[2].upper()  # <-- only the state token (e.g., "OK")
                        is_ok = (st == "OK" or st == "NOT" or st == "PRESENT")  # keep lenient if vendors vary
                        # Better: exact allow-list
                        is_ok = (st == "OK")
                        prev = tmp.get(sw, True)
                        tmp[sw] = prev and is_ok
            for sw, ok in tmp.items():
                per_switch_ok[sw] = per_switch_ok.get(sw, True) and ok

        if not per_switch_ok:
            logging.debug("No fan patterns matched.")
            return ["Not available"]

        result = ["OK" if per_switch_ok[sw] else "Not OK" for sw in sorted(per_switch_ok.keys())]
        logging.debug("Fan status extraction completed.")
        return result if result else ["Not available"]

    except Exception as e:
        logging.error(f"Error in get_fan_status: {str(e)}")
        return [f"Error in get_fan_status: {str(e)}"]

def get_power_supply_status(log_data: str):
    """
    Returns a list of statuses per switch.
      - "OK" if all present PSUs are OK.
      - "Not Present" if any PSU is missing (but no failures).
      - "NOT OK" if any PSU reports a bad state.
      - "UNKNOWN" if unrecognized states.
      - ["Not available"] if no PSU table found.
    """
    try:
        logging.info("Starting power supply status extraction")
        lines = log_data.splitlines()
        per_switch_slots = {}   # sw -> list of status strings
        in_psu_table = False

        header_re = re.compile(r'(?mi)^\s*SW\s+PID\s+.*Serial#\s+.*Status')
        row_slot_re = re.compile(r'^\s*(\d+[A-Z])\b', re.IGNORECASE)

        for idx, line in enumerate(lines):
            if not in_psu_table:
                if header_re.search(line):
                    in_psu_table = True
                    logging.debug(f"Found PSU table header at line {idx}: {line.strip()}")
                    continue
            else:
                if not line.strip() or re.search(r'-{3,}', line) or line.strip().startswith(('Sensor List:', 'Switch FAN')):
                    continue

                m = row_slot_re.match(line)
                if not m:
                    continue

                slot = m.group(1).upper()
                sw = int(slot[:-1])
                norm = line.strip()
                status = ""

                if re.search(r'(?i)\bNot\s+Present\b', norm):
                    status = "Not Present"
                elif re.search(r'(?i)\bOK\b', norm):
                    status = "OK"
                elif re.search(r'(?i)\b(BAD|FAIL|NO\s+INPUT\s+POWER|ALARM)\b', norm):
                    status = "NOT OK"
                else:
                    status = "UNKNOWN"

                logging.debug(f"Parsed line {idx}: slot={slot}, sw={sw}, status={status}")
                per_switch_slots.setdefault(sw, []).append((slot, status))

        if not per_switch_slots:
            logging.warning("No PSU table rows matched")
            return ["Not available"]

        result = []
        for sw in sorted(per_switch_slots.keys()):
            slots = per_switch_slots[sw]
            logging.debug(f"Evaluating Switch {sw} with slots: {slots}")

            if any(status == "NOT OK" for _, status in slots):
                bad_slot = next(slot for slot, status in slots if status == "NOT OK")
                result.append(f"{bad_slot}: NOT OK")
                logging.info(f"Switch {sw} -> {bad_slot}: NOT OK")
            elif any(status == "Not Present" for _, status in slots):
                missing_slot = next(slot for slot, status in slots if status == "Not Present")
                result.append(f"{missing_slot}: Not Present")
                logging.info(f"Switch {sw} -> {missing_slot}: Not Present")
            elif all(status == "OK" for _, status in slots):
                ok_slot = ", ".join(slot for slot, _ in slots)
                result.append("OK")
                logging.info(f"Switch {sw} -> All OK ({ok_slot})")
            else:
                result.append("UNKNOWN")
                logging.info(f"Switch {sw} -> UNKNOWN")

        logging.info("Completed power supply status extraction")
        return result

    except Exception as e:
        logging.error(f"Error in get_power_supply_status: {str(e)}", exc_info=True)
        return [f"Error in get_power_supply_status: {str(e)}"]

def get_debug_status(log_data):
    try:
        logging.info("Starting debug status extraction.")
        match = re.search(r"sh|show\w*\s*de\w*", log_data, re.IGNORECASE)
        if match:
            hostname = get_hostname(log_data)
            if hostname == "Not available" or not hostname:
                logging.debug("Hostname not found in log data.")
                return "Hostname not found"
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
        return f"Error in get_debug_status: {str(e)}"

def get_available_ports(log_data):
    try:
        logging.info("Starting available ports extraction.")
        start_marker = "------------------ show interfaces status ------------------"
        end_marker = "------------------ show "
        
        match = re.search(f"{re.escape(start_marker)}(.*?){re.escape(end_marker)}", log_data, re.DOTALL)
        if match:
            section = match.group(1)
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
        else:
            logging.debug("No available ports section found in log data.")
            return [[0]]
    except Exception as e:
        logging.error(f"Error in get_available_ports: {str(e)}")
        # Preserve original error signaling shape
        return [[str(e)]]

def get_half_duplex_ports(log_data):
    try:
        logging.info("Starting half duplex ports extraction.")
        current_stack_size = IOS_XE_Stack_Switch.stack_size(log_data)
        match = re.findall(r"^(\S+).*a-half.*$", log_data, re.IGNORECASE | re.MULTILINE)
        if match:
            switch_interfaces = {}
            for interface in match:
                try:
                    switch_number = re.search(r'\D+(\d+)/', interface).group(1)
                except AttributeError:
                    continue
                if switch_number not in switch_interfaces:
                    switch_interfaces[switch_number] = []
                switch_interfaces[switch_number].append(interface)

            max_switch_number = max(map(int, switch_interfaces.keys()), default=0)
            # keep original outer shape [[count], ...] (no logic change), but ensure counts are ints
            half_duplex_ports_per_switch = [[int(len(switch_interfaces.get(str(i), [])))] for i in range(1, max_switch_number + 1)]
            logging.debug("Half duplex ports extraction completed.")
            return half_duplex_ports_per_switch
        else:
            logging.debug("No half duplex ports found in log data.")
            # keep the original [[...]] shape but use numeric 0 instead of "0"
            return [[0]] * current_stack_size
    except Exception as e:
        logging.error(f"Error in get_half_duplex_ports: {str(e)}")
        # preserve original error signaling & shape
        return [["Error"]] * current_stack_size

def get_interface_remark(log_data):
    try:
        logging.info("Starting interface remark extraction.")
        current_stack_size = IOS_XE_Stack_Switch.stack_size(log_data)
        match = re.findall(r"^(\S+).*a-half.*$", log_data, re.IGNORECASE | re.MULTILINE)
        if match:
            switch_interfaces = {}
            for interface in match:
                switch_number = re.search(r'\D+(\d+)/', interface)
                if not switch_number:
                    continue
                switch_number = switch_number.group(1)
                if switch_number not in switch_interfaces:
                    switch_interfaces[switch_number] = []
                switch_interfaces[switch_number].append(interface)

            max_switch_number = max(map(int, switch_interfaces.keys()), default=0)
            # Preserve original inner default 'Not avialable' where a switch has no entries,
            # but ensure the OUTER shape is always list-of-lists (per switch)
            interface_remark = [switch_interfaces.get(str(i), []) for i in range(1, max_switch_number + 1)]
            interface_remark = [sublist if sublist else ['Not avialable'] for sublist in interface_remark]
            logging.debug("Interface remark extraction completed.")
            return interface_remark
        else:
            logging.debug("No interface remark found in log data.")
            # IMPORTANT: keep OUTER shape as list-of-lists, one per switch
            return [["Not available"]] * current_stack_size
    except Exception as e:
        logging.error(f"Error in get_interface_remark: {str(e)}")
        # Preserve original error signaling shape (list-of-lists)
        return [[f"Error in get_interface_remark: {str(e)}"]] * IOS_XE_Stack_Switch.stack_size(log_data)

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
        return [f"Error: {str(e)}", "Not available"]

def get_critical_logs(log_data):
    if not isinstance(log_data, str) or not log_data:
        logging.error("Invalid input type or empty string for log_data")
        return f"Error in get_critical_logs: Invalid input"
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
            return "No logging section found!"
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

def process_file(file_path):
    try:
        logging.info(f"Starting processing of file: {file_path}")
        with open(file_path, 'r') as file:
            log_data = file.read()
        data = {}
        stack = check_stack(log_data)
        # print("STACK:", stack)
        if not stack:
            memory_info = get_memory_info(log_data)
            flash_info = get_flash_info(log_data)
            if isinstance(flash_info, dict):
                flash_info = flash_info.get('1', ["Not available", "Not available", "Not available", "Not available"])
            elif isinstance(flash_info, str):
                flash_info = ["Not available", "Not available", "Not available", "Not available"]
            
            # ... (rest of single switch processing remains the same)
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
                "End of Routine Failure Analysis Date:  HW": ["Yet to check"],
                "End of Vulnerability/Security Support: HW": ["Yet to check"],
                "End of SW Maintenance Releases Date: HW": ["Yet to check"],
                "Remark": ["Yet to check"]
            }
        else:
            data = {}
            file_name, hostname, model_number, serial_number, ip_address, uptime = [], [], [], [], [], []
            current_sw, last_reboot, cpu, memo, flash, critical = [], [], [], [], [], []
            total_memory, used_memory, free_memory, memory_utilization = [], [], [], []
            total_flash, used_flash, free_flash, flash_utilization = [], [], [], []
            avail_free, duplex, interface_remark, config_status, config_date = [], [], [], [], []
            
            current_stack_size = IOS_XE_Stack_Switch.stack_size(log_data)  # ← FIXED: Renamed variable to avoid shadowing
            stack_switch_data = IOS_XE_Stack_Switch.parse_ios_xe_stack_switch(log_data)
            flash_memory_details = get_flash_info(log_data)
            
            for item in range(current_stack_size):  # ← FIXED: Use renamed variable
                if item == 0:
                    file_name.append(get_ip_address(file_path)[0])
                    model_number.append(get_model_number(log_data))
                    serial_number.append(get_serial_number(log_data))
                    uptime.append(get_uptime(log_data))
                    last_reboot.append(get_last_reboot_reason(log_data))
                else:
                    file_name.append(get_ip_address(file_path)[0] + (f"_Stack_{str(item+1)}"))
                    model_number.append(stack_switch_data[f'stack switch {item + 1} Model_Number'])
                    serial_number.append(stack_switch_data[f'stack switch {item + 1} Serial_Number'])
                    uptime.append(stack_switch_data[f'stack switch {item + 1} Uptime'])
                    last_reboot.append(stack_switch_data[f'stack switch {item + 1} Last Reboot'])
                
                memo = get_memory_info(log_data)
                total_memory.append(memo[0])
                used_memory.append(memo[1])
                free_memory.append(memo[2])
                memory_utilization.append(memo[3])

                if isinstance(flash_memory_details, dict) and str(item+1) in flash_memory_details:
                    flash = flash_memory_details[str(item+1)]
                elif isinstance(flash_memory_details, dict) and '1' in flash_memory_details:
                    flash = flash_memory_details['1']
                else:
                    flash = ["Not available", "Not available", "Not available", "Not available"]
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
            data["End of Routine Failure Analysis Date:  HW"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["End of Vulnerability/Security Support: HW"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["End of SW Maintenance Releases Date: HW"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["Remark"] = ["Yet to check"] * current_stack_size  # ← FIXED
            logging.debug(f"File processing completed: {file_path}")
        return data
    except Exception as e:
        logging.error(f"Error in process_file: {str(e)}")
        # print(f"Error in process_file: {str(e)}")

def ios_xe_check(log_data):
    try:
        logging.info("Starting IOS XE check.")
        if get_current_sw_version(log_data): 
            logging.debug("IOS XE check completed. Version found.")
            return True
        else:
            logging.debug("IOS XE check completed. Version not found.")
            return False
    except Exception as e:
        logging.error(f"Error in ios_xe_check: {str(e)}")

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
                if ios_xe_check(log_data):
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
        return 500
    
def _placeholder_entry(file_path, reason_text="Non-IOS_XE"):
    """
    One-row data dict for files that were skipped or failed.
    For Non-IOS-XE rows we fill ALL attributes with 'Unsupported IOS'.
    """
    import os
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
        "End of Routine Failure Analysis Date:  HW": [U],
        "End of Vulnerability/Security Support: HW": [U],
        "End of SW Maintenance Releases Date: HW": [U],
        "Remark": ["Non-IOS_XE"],
    }

def main():
    try:
        # file_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR137436091\9200\UOBM-C9200-APG-OA-01_10.59.80.10.txt"
        directory_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR137436091\9200"
        data = process_directory(directory_path)
        # print_data(data)
        for item in data:
            # print(item["Interface ip address"])
            print_data(item)
        # pp.pprint(data["Interface ip address"])
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()