import re
import os
import logging
import datetime
import pprint as pp

from . import IOS_Stack_Switch  # strict relative import inside package
    
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

# Lines that usually accompany the management SVI
_MGMT_MARKERS = (
    r'no\s+ip\s+redirects',
    r'no\s+ip\s+unreachables',
    r'no\s+ip\s+proxy-arp',
    r'no\s+ip\s+route-cache',
)

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

# Optional extra hints for a management interface
_PREFER_NAME_RE = re.compile(r'(?im)^interface\s+(?:(?:vlan\d+)|(?:loopback0)|(?:bdi\d+))\b')
_DESC_MGMT_RE   = re.compile(r'(?im)^\s*description\s+.*\b(mgmt|manage|management)\b')

def _marker_score(block: str) -> int:
    """Score a stanza by how many management-hardening markers it contains."""
    s = 0
    for pat in _MGMT_MARKERS:
        if re.search(pat, block, flags=re.IGNORECASE):
            s += 1
    return s

def _prefer_rank(block: str) -> int:
    """
    Lower is better.
    0: SVI/Loopback/BDI with 'management' hint in description
    1: SVI/Loopback/BDI without desc hint
    2: Anything else with desc hint
    3: Anything else
    """
    is_pref_if = bool(_PREFER_NAME_RE.search(block))
    has_mgmt_desc = bool(_DESC_MGMT_RE.search(block))
    if is_pref_if and has_mgmt_desc:
        return 0
    if is_pref_if:
        return 1
    if has_mgmt_desc:
        return 2
    return 3

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
        # Match 'Model Number' or 'Model number' (case-insensitive) with variable spaces
        match = re.search(r"Model\s+Number\s*:\s*(\S+)", log_data, re.IGNORECASE)
        logging.debug("Model number search completed.")
        return match.group(1) if match else "Require Manual Check"
    except Exception as e:
        logging.error(f"Error in get_model_number: {str(e)}")
        return f"Error in get_model_number: {str(e)}"
    
def get_ip(log_data: str):
    """
    Find the most likely management IPv4 address from the config text.
    Strategy:
      1) Split into 'interface ...' stanzas.
      2) Score each stanza by presence of hardening lines (no ip redirects/unreachables/proxy-arp/route-cache).
      3) Tie-break by interface type (SVI/Loopback/BDI) and 'management' in description.
      4) Return first sanitized IPv4 from the best stanza.
      5) Fallback: any IPv4-looking token in the whole file (sanitized).
    Returns: '10.x.x.x' (normalized) or None.
    """
    try:
        if not log_data:
            return None

        blocks = _INTERFACE_BLOCK_RE.findall(log_data)
        candidates = []

        for blk in blocks:
            # skip DHCP-assigned mgmt (no concrete IP)
            if re.search(r'(?im)^\s*ip\s+address\s+dhcp\b', blk):
                continue

            # collect primary IPs in the stanza
            ips_in_block = []
            for m in _IP_LINE_RE.finditer(blk):
                ip = m.group('ip')
                line_str = m.group(0)
                # deprioritize "secondary" IPs
                if re.search(r'\bsecondary\b', line_str, flags=re.IGNORECASE):
                    continue
                ips_in_block.append(ip)

            if not ips_in_block:
                continue

            score = _marker_score(blk)
            rank = _prefer_rank(blk)

            # Prefer stanzas that actually include *any* of your mgmt markers
            # We'll sort by: (-score, rank) so more markers is better; then lower rank is better.
            candidates.append((score, rank, ips_in_block, blk))

        if candidates:
            # Sort: highest score first, then lowest rank (preferred names/desc), keep original order stable next
            candidates.sort(key=lambda t: (-t[0], t[1]))
            best = candidates[0]
            _, _, ips, _ = best

            # Return first that sanitizes cleanly
            for raw_ip in ips:
                ip_norm = sanitize_ipv4(raw_ip)
                if ip_norm not in {"Not available", "Require Manual Check"}:
                    return ip_norm

        # --- Fallback: any IPv4-ish token anywhere in the config ---
        any_ip = re.search(r'(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?)', log_data)
        if any_ip:
            ip_norm = sanitize_ipv4(any_ip.group(1))
            if ip_norm not in {"Not available", "Require Manual Check"}:
                return ip_norm

        return None
    except Exception:
        return None

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
    
def _is_valid_ipv4(addr: str) -> bool:
    try:
        parts = addr.split(".")
        if len(parts) != 4:
            return False
        for p in parts:
            if not p.isdigit():
                return False
            n = int(p)
            if n < 0 or n > 255:
                return False
        return True
    except Exception:
        return False

def get_serial_number(log_data):
    try:
        logging.info("Starting serial number search.")
        # Make it case-insensitive and handle spaces
        match = re.search(r"System\s+Serial\s+Number\s*:\s*(\S+)", log_data, re.IGNORECASE)
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
    try:
        # "Cisco IOS Software, C2960S Software (C2960S-UNIVERSALK9-M), Version 15.0(2)SE10, RELEASE SOFTWARE (fc3)"
        m = re.search(r'(?mi)^\s*Cisco IOS Software.*Version\s+([^\s,]+)', log_data)
        return m.group(1).strip() if m else "Not available"
    except Exception as e:
        logging.error(f"Error in get_current_sw_version: {str(e)}")
        return False

def get_last_reboot_reason(log_data):
    try:
        logging.info("Starting last reboot reason search.")
        
        # First try to match "Last reload reason"
        match = re.search(r"Last reload reason\s*:\s*(.+)", log_data, re.IGNORECASE)
        if match:
            result = match.group(1).strip()
        else:
            # Fallback: match "System returned to ROM by ..."
            match = re.search(r"System returned to ROM by\s+(.+)", log_data, re.IGNORECASE)
            result = match.group(1).strip() if match else "Require Manual Check"
        
        logging.debug("Last reboot reason search completed.")
        return result

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
            stack_details = IOS_Stack_Switch.parse_IOS_Stack_Switch(log_data)
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
        flash_information = {}

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
            elif m_total_free:
                total_bytes = int(m_total_free.group(1))
                free_bytes = int(m_total_free.group(2))
                available_bytes = free_bytes
                used_bytes = total_bytes - free_bytes
            else:
                # No recognizable summary line in this section
                continue

            total, used, free, utilization = calculate_flash_utilization(available_bytes, used_bytes)

            # Figure out flash number from header (flash, flash2, flash-3, etc.)
            num = hdr.group(1)
            key = num if num else '1'  # keep your original '1' default

            flash_information[key] = [total, used, free, utilization]

        logging.debug("Flash info extraction completed.")
        return flash_information if flash_information else "No flash information found"

    except Exception as e:
        logging.error(f"Error in get_flash_info: {str(e)}")
        return f"Error in get_flash_info: {str(e)}"

def get_fan_status(log_data: str):
    try:
        logging.info("Starting fan status extraction (IOS only).")
        # Match either plain "FAN is ..." or numbered "FAN 1 is ..." but exclude PSU fans
        hits = re.findall(
            r'^(?:Switch\s+\d+\s+)?FAN(?:\s+\d+)?\s+is\s+([A-Z ]+)$',
            log_data, re.IGNORECASE | re.MULTILINE
        )
        if not hits:
            logging.debug("No chassis fan lines found.")
            return ["Not available"]

        vals = [h.strip().upper() for h in hits if "PS-" not in h.upper()]
        vals = ["OK" if v == "GREEN" else v for v in vals]

        return ["OK"] if all(v == "OK" for v in vals) else ["Not OK"]
    except Exception as e:
        logging.error(f"Error in get_fan_status_ios: {str(e)}")
        return [f"Error: {str(e)}"]

def get_temperature_status(log_data: str):
    try:
        logging.info("Starting temperature status extraction (IOS only).")

        # 1) Lines like "TEMPERATURE is OK" or "Switch 1: SYSTEM TEMPERATURE is OK"
        hits1 = re.findall(
            r'^(?:Switch\s+\d+\s*:?\s*)?(?:SYSTEM\s+)?TEMPERATURE\s+is\s+([A-Z ]+)\s*$',
            log_data, re.IGNORECASE | re.MULTILINE
        )

        # 2) Lines like "Temperature State: GREEN"
        hits2 = re.findall(
            r'^Temperature\s+State\s*:\s*([A-Z]+)\s*$',
            log_data, re.IGNORECASE | re.MULTILINE
        )

        if not hits1 and not hits2:
            logging.debug("No temperature lines found.")
            return ["Not available"]

        # Normalize to OK/Not OK
        def norm(s):
            s = s.strip().upper()
            if s in ("OK", "GREEN"):
                return "OK"
            # treat common non-OKs
            if s in ("NOT OK", "CRITICAL", "YELLOW", "RED", "FAIL", "FAILED", "ALARM"):
                return "Not OK"
            # default: if it's not obviously OK, consider it Not OK
            return "Not OK"

        vals = [norm(v) for v in hits1] + [norm(v) for v in hits2]

        return ["OK"] if vals and all(v == "OK" for v in vals) else ["Not OK"]

    except Exception as e:
        logging.error(f"Error in get_temperature_status_ios: {e}")
        return [f"Error: {e}"]

def get_power_supply_status(log_data: str):
    """
    IOS classic 'show env all' power-supply parser.
    Returns a per-switch list like ["OK", "NOT OK"] ordered by switch number.
    Rules:
      - Parse the PSU table under the 'SW  PID ... Status ...' header.
      - Slot labels look like '1A', '1B', etc.
      - 'OK' = healthy. 'Not Present' is neutral/acceptable.
      - Any of: Bad, No Input Power, Not OK, Faulty, Fail/Failed => NOT OK.
      - If no PSU lines found => ["Not available"].
    """
    try:
        logging.info("Starting power supply status extraction (IOS only).")

        # Isolate the PSU table after the header 'SW  PID ... Status'
        m = re.search(
            r'^\s*SW\s+PID\s+.*?Status.*?\n(-{2,}.*?\n)?(.*?)(?:\n\s*SW\s+Status|^-{10,}\s*show|\Z)',
            log_data, re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        section = m.group(2) if m else ""

        if not section.strip():
            logging.debug("No PSU table section found.")
            return ["Not available"]

        # Collect slot -> status
        # 1) Minimal "Not Present" rows
        rows = re.findall(r'^\s*([0-9]+[A-Z])\s+Not\s+Present\s*$', section,
                          re.IGNORECASE | re.MULTILINE)
        slot_status = {slot.upper(): "NOT PRESENT" for slot in rows}

        # 2) Full rows with a status token somewhere in the line
        for line in section.splitlines():
            line_s = line.strip()
            if not line_s:
                continue
            mslot = re.match(r'^([0-9]+[A-Z])\b', line_s, re.IGNORECASE)
            if not mslot:
                continue
            slot = mslot.group(1).upper()

            # Find a status token in the row
            mstatus = re.search(
                r'\b(OK|Not\s+Present|No\s+Input\s+Power|Bad|Not\s+OK|Faulty|Fail(?:ed)?)\b',
                line_s, re.IGNORECASE
            )
            if mstatus:
                status = mstatus.group(1).upper().replace("  ", " ")
                # Normalize a couple forms
                status = status.replace("FAILED", "FAIL").replace("NOT  OK", "NOT OK")
                slot_status[slot] = status

        if not slot_status:
            logging.debug("No PSU rows parsed.")
            return ["Not available"]

        # Aggregate per switch number
        per_switch = {}
        for slot, status in slot_status.items():
            sw = int(slot[:-1])  # '1A' -> 1
            per_switch.setdefault(sw, []).append(status)

        crit = {"BAD", "NO INPUT POWER", "NOT OK", "FAULTY", "FAIL"}
        final = []
        for sw in sorted(per_switch.keys()):
            statuses = per_switch[sw]
            if any(s in crit for s in statuses):
                final.append("NOT OK")
            else:
                # Accept 'NOT PRESENT' as neutral; OK if at least one OK and no criticals
                final.append("OK" if any(s == "OK" for s in statuses) else "NOT OK")

        return final if final else ["Not available"]

    except Exception as e:
        logging.error(f"Error in get_power_supply_status_ios: {e}")
        return [f"Error: {e}"]

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
        current_stack_size = IOS_Stack_Switch.stack_size(log_data)
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
        current_stack_size = IOS_Stack_Switch.stack_size(log_data)
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
            return [["Require Manual Check"]] * current_stack_size
    except Exception as e:
        logging.error(f"Error in get_interface_remark: {str(e)}")
        # Preserve original error signaling shape (list-of-lists)
        return [[f"Error in get_interface_remark: {str(e)}"]] * IOS_Stack_Switch.stack_size(log_data)

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

def process_file(file_path: str):
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
            
            current_stack_size = IOS_Stack_Switch.stack_size(log_data)  # ← FIXED: Renamed variable to avoid shadowing
            stack_switch_data = IOS_Stack_Switch.parse_IOS_Stack_Switch(log_data)
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
        file_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR137436091\3750\UOBM-C3750-JOT-L03-03_10.31.99.12.txt"
        directory_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR137436091\3750"
        data = process_file(file_path)
        print_data(data)
        # for item in data:
        #     print(item["File name"])
        #     print(item["Temperature status"])
            # print_data(item)
        # pp.pprint(data["Interface ip address"])
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()