import re
import os
import logging
import datetime
from typing import List, Dict, Union
from . import IOS_XE_Stack_Switch
    
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
        return "Require Manual Check"
    except Exception:
        return None

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
    try:
        logging.info("Starting model number extraction.")
        
        # --- Method 1: Show version Model Number ---
        sv_model = None
        logging.debug("Attempting extraction via 'show version' patterns.")
        try:
            patterns = [
                r"Model\s+Number\s*:\s*([^\s\r\n]+)",
                r"Product\s+ID\s*:\s*([^\s\r\n]+)", 
                r"Model\s*:\s*([^\s\r\n]+)",
                r"Hardware\s*:\s*([^\s\r\n,]+)"
            ]
            
            for i, pattern in enumerate(patterns):
                match = re.search(pattern, log_data, re.IGNORECASE)
                if match:
                    model = match.group(1).strip()
                    if model and model.upper() not in ['N/A', 'NONE', 'UNKNOWN']:
                        sv_model = model
                        logging.debug(f"Found show version model using pattern {i+1}: {sv_model}")
                        break
                    else:
                        logging.debug(f"Pattern {i+1} matched, but value was empty/generic ('{model}').")
                else:
                    logging.debug(f"Pattern {i+1} did not match.")
        except Exception as e:
            logging.debug(f"Error extracting show version model: {e}")
        
        # --- Method 2: Extract inventory section ---
        inventory_section = None
        logging.debug("Attempting to extract 'show inventory' section.")
        try:
            inv_match = re.search(r"-{5,}\s*show\s+inventory\s*-{5,}", log_data, re.IGNORECASE)
            if inv_match:
                start_pos = inv_match.end()
                # Find end of inventory section
                end_match = re.search(r"-{5,}", log_data[start_pos:], re.IGNORECASE)
                if end_match:
                    inventory_section = log_data[start_pos:start_pos + end_match.start()]
                    logging.debug("Extracted 'show inventory' section with clear end marker.")
                else:
                    inventory_section = log_data[start_pos:]
                    logging.debug("Extracted 'show inventory' section to end of log data.")
            else:
                logging.debug("Show inventory section header not found.")
        except Exception as e:
            logging.debug(f"Error extracting inventory section: {e}")
        
        # --- Method 3: Parse inventory for device PIDs ---
        inventory_model = None
        if inventory_section:
            logging.debug("Starting inventory parsing and device prioritization.")
            try:
                # Device priority for model selection
                device_priorities = {
                    'switch_system': 100,     # Switch System - main chassis
                    'switch_stack': 95,       # Stack, c93xx Stack
                    'switch_numbered': 90,    # Switch 1, Switch 2
                    'switch_other': 80,       # Other switch devices  
                    'chassis': 70,            # Chassis devices
                    'supervisor': 60,         # Supervisor modules
                    'linecard': 30,           # Line cards
                    'transceiver': 20,        # SFPs, transceivers
                    'power_fan': 10,          # Power supplies, fans
                    'unknown': 0
                }
                
                inventory_devices = []
                
                # Different inventory patterns to handle various formats
                inventory_patterns = [
                    # Format: NAME: "device name" ... PID: model
                    r'(?ims)NAME:\s*"([^"]+)".*?\bPID:\s*([^\s,\n\r]+)',
                    # Format: NAME device name ... PID model (without quotes)  
                    r'(?ims)NAME:\s*([^,\n]+?).*?\bPID:\s*([^\s,\n\r]+)',
                    # Legacy format variations
                    r'(?ims)NAME:\s*"([^"]+)"[^\n]*\nPID:\s*([^\s,]+)'
                ]
                
                for i, pattern in enumerate(inventory_patterns):
                    matches = re.findall(pattern, inventory_section)
                    logging.debug(f"Pattern {i+1} yielded {len(matches)} inventory matches.")
                    for name, pid in matches:
                        name = name.strip().strip('"')
                        pid = pid.strip()
                        name_lower = name.lower()
                        
                        # Skip invalid PIDs
                        if not pid or pid.upper() in ['UNSPECIFIED', 'N/A', 'NONE', 'UNKNOWN']:
                            logging.debug(f"Skipping inventory item (generic PID): {name} - {pid}")
                            continue
                        
                        # Skip obvious non-model components
                        if any(x in name_lower for x in ['transceiver', 'sfp', 'gbic', 'fan', 'power', 'cable']):
                            logging.debug(f"Skipping inventory item (component): {name} - {pid}")
                            continue
                        
                        # Classify device type and assign priority
                        device_type = 'unknown'
                        priority = 0
                        
                        # Switch devices (highest priority)
                        if 'switch' in name_lower:
                            if 'system' in name_lower:
                                device_type = 'switch_system'
                                priority = device_priorities['switch_system']
                            elif any(x in name_lower for x in ['stack', 'c93xx']):
                                device_type = 'switch_stack'
                                priority = device_priorities['switch_stack']
                            elif re.search(r'switch\s*\d+', name_lower):
                                device_type = 'switch_numbered'
                                priority = device_priorities['switch_numbered']
                                # Boost priority for Switch 1
                                if 'switch 1' in name_lower or 'switch  1' in name_lower:
                                    priority += 5
                            else:
                                device_type = 'switch_other'
                                priority = device_priorities['switch_other']
                        
                        # Chassis devices
                        elif 'chassis' in name_lower:
                            # Avoid line-cards like "Chassis 1 1" 
                            if re.search(r'chassis\s*\d+\b(?!\s*\d)', name_lower):
                                device_type = 'chassis'
                                priority = device_priorities['chassis']
                                # Boost priority for Chassis 1
                                if 'chassis 1' in name_lower or 'chassis  1' in name_lower:
                                    priority += 5
                        
                        # Supervisor modules
                        elif any(x in name_lower for x in ['supervisor', 'sup ']):
                            device_type = 'supervisor'
                            priority = device_priorities['supervisor']
                        
                        # Line cards
                        elif any(x in name_lower for x in ['linecard', 'line card']):
                            device_type = 'linecard'
                            priority = device_priorities['linecard']
                        
                        # Add to devices if it has valid priority
                        if priority > 0:
                            inventory_devices.append({
                                'name': name,
                                'pid': pid,
                                'device_type': device_type,
                                'priority': priority
                            })
                            logging.debug(f"Identified device: {name} (PID: {pid}, Type: {device_type}, Pri: {priority})")
                
                # Select highest priority device model
                if inventory_devices:
                    logging.debug(f"Total relevant inventory devices found: {len(inventory_devices)}. Sorting by priority.")
                    # Sort by priority (highest first), then by name for consistency
                    inventory_devices.sort(key=lambda x: (-x['priority'], x['name']))
                    
                    # Special handling for multiple switches with same PID
                    switch_devices = [d for d in inventory_devices if d['device_type'].startswith('switch')]
                    if len(switch_devices) > 1:
                        switch_pids = set(d['pid'] for d in switch_devices)
                        if len(switch_pids) == 1:
                            # All switches have same PID - use it
                            inventory_model = next(iter(switch_pids))
                            logging.info(f"Inventory: All switches have same PID: {inventory_model}")
                        else:
                            # Mixed PIDs - prefer Switch 1, Switch System, or highest priority
                            switch_1 = next((d for d in switch_devices if '1' in d['name'] or 'system' in d['name'].lower()), None)
                            if switch_1:
                                inventory_model = switch_1['pid']
                                logging.info(f"Inventory: Using primary switch PID: {switch_1['name']} ({inventory_model})")
                            else:
                                # Use highest priority switch
                                inventory_model = switch_devices[0]['pid']
                                logging.info(f"Inventory: Using highest priority switch: {switch_devices[0]['name']} ({inventory_model})")
                    else:
                        # Single switch or no switches - use highest priority device
                        selected_device = inventory_devices[0]
                        inventory_model = selected_device['pid']
                        logging.info(f"Inventory: Selected highest priority device: {selected_device['name']} ({inventory_model})")
                
                # Legacy fallback: Look specifically for Switch N patterns
                if not inventory_model:
                    logging.debug("No model selected via main inventory logic. Trying legacy Switch N pattern.")
                    switch_pattern = r'NAME:\s*"Switch\s*(\d+)"[^\n]*\nPID:\s*([^\s,]+)'
                    switch_matches = re.findall(switch_pattern, inventory_section, re.IGNORECASE)
                    if switch_matches:
                        switch_pids = {int(num): pid.strip() for num, pid in switch_matches}
                        pid_values = set(switch_pids.values())
                        
                        if len(pid_values) == 1:
                            # All Switch N have same PID
                            inventory_model = next(iter(pid_values))
                            logging.info(f"Legacy: All Switch N have same PID: {inventory_model}")
                        elif 1 in switch_pids:
                            # Mixed PIDs - prefer Switch 1
                            inventory_model = switch_pids[1]
                            logging.info(f"Legacy: Using Switch 1 PID: {inventory_model}")
                        else:
                            # Use first available switch
                            first_switch = min(switch_pids.keys())
                            inventory_model = switch_pids[first_switch]
                            logging.info(f"Legacy: Using Switch {first_switch} PID: {inventory_model}")
                        
            except Exception as e:
                logging.debug(f"Error parsing inventory models: {e}")
        
        # --- Determine final model ---
        final_model = None
        
        # Priority: Inventory model > Show version model
        if inventory_model:
            final_model = inventory_model
            logging.info(f"Using inventory model: {final_model}")
            
            # Compare with show version - if different, prefer inventory
            if sv_model and sv_model.strip().upper() != inventory_model.strip().upper():
                logging.info(f"Inventory model ({inventory_model}) differs from show version ({sv_model}), using inventory")
            elif sv_model and sv_model.strip().upper() == inventory_model.strip().upper():
                logging.info(f"Inventory and show version models match: {final_model}")
            else:
                logging.info(f"Using inventory model: {final_model}.")
                
        elif sv_model:
            final_model = sv_model
            logging.info(f"Using show version model: {final_model}")
        
        logging.info(f"Final model: {final_model}")
        return final_model or "Require Manual Check"
        
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

def get_serial_number(log_data):
    """
    Extract serial number from network device log data.
    
    Priority order:
    1. System Serial Number from show version
    2. Main switch device from inventory (Switch System, Switch Stack, Switch 1)
    3. Other switch devices from inventory
    4. Chassis/supervisor devices from inventory
    5. Manual check required
    
    Args:
        log_data (str): Raw log data from network device
        
    Returns:
        str: Device serial number or "Require Manual Check"
    """
    try:
        logging.info("Starting serial number extraction.")
        
        # --- Method 1: System Serial Number from show version ---
        system_serial = None
        logging.debug("Attempting extraction via 'show version' patterns.")
        try:
            # Multiple patterns for different IOS versions and platforms
            system_patterns = [
                r"System\s+Serial\s+Number\s*:\s*(\S+)",
                r"Processor\s+board\s+ID\s*(\S+)",
                r"board\s+ID\s*(\S+)",
                r"Serial\s+Number\s*:\s*(\S+)",
                r"System\s+serial\s+number\s*:\s*(\S+)",
                r"Chassis\s+Serial\s+Number\s*:\s*(\S+)"
            ]
            
            for i, pattern in enumerate(system_patterns):
                match = re.search(pattern, log_data, re.IGNORECASE)
                if match:
                    serial = match.group(1).strip()
                    if serial and serial.upper() not in ['N/A', 'NONE', 'UNKNOWN', 'UNSPECIFIED']:
                        system_serial = serial
                        logging.info(f"Found system serial from show version using pattern {i+1}: {system_serial}")
                        break
                    else:
                        logging.debug(f"Pattern {i+1} matched, but value was empty/generic ('{serial}').")
                else:
                    logging.debug(f"Pattern {i+1} did not match.")
        except Exception as e:
            logging.debug(f"Error extracting system serial: {e}")
        
        # --- Method 2: Extract inventory section ---
        inventory_section = None
        logging.debug("Attempting to extract 'show inventory' section.")
        try:
            inv_match = re.search(r"-{5,}\s*show\s+inventory\s*-{5,}", log_data, re.IGNORECASE)
            if inv_match:
                start_pos = inv_match.end()
                # Find end of inventory section
                end_match = re.search(r"-{5,}", log_data[start_pos:], re.IGNORECASE)
                if end_match:
                    inventory_section = log_data[start_pos:start_pos + end_match.start()]
                    logging.debug("Extracted 'show inventory' section with clear end marker.")
                else:
                    inventory_section = log_data[start_pos:]
                    logging.debug("Extracted 'show inventory' section to end of log data.")
            else:
                logging.debug("Show inventory section header not found.")
        except Exception as e:
            logging.debug(f"Error extracting inventory section: {e}")
        
        # --- Method 3: Parse inventory for device serial numbers ---
        inventory_serial = None
        if inventory_section:
            logging.debug("Starting inventory parsing and device prioritization.")
            try:
                # Device priority for serial number selection
                device_priorities = {
                    'switch_system': 100,     # Switch System - main chassis
                    'switch_stack': 95,       # Stack, c93xx Stack
                    'switch_numbered': 90,    # Switch 1, Switch 2
                    'switch_other': 80,       # Other switch devices
                    'chassis': 70,            # Chassis devices
                    'supervisor': 60,         # Supervisor modules
                    'linecard': 30,           # Line cards
                    'transceiver': 20,        # SFPs, transceivers
                    'power_fan': 10,          # Power supplies, fans
                    'unknown': 0
                }
                
                inventory_devices = []
                
                # Different inventory patterns for serial numbers
                inventory_patterns = [
                    # Format: NAME: "device name" ... SN: serial
                    r'(?ims)NAME:\s*"([^"]+)".*?\bSN:\s*([A-Z0-9\-]+)',
                    # Format: NAME device name ... SN serial (without quotes)
                    r'(?ims)NAME:\s*([^,\n]+?).*?\bSN:\s*([A-Z0-9\-]+)',
                    # Format: PID: xxx , VID: xxx , SN: serial
                    r'(?ims)PID:\s*[^\s,]+\s*,\s*VID:\s*[^\s,]+\s*,\s*SN:\s*([A-Z0-9\-]+)',
                    # Legacy format variations
                    r'(?ims)NAME:\s*"([^"]+)"[^\n]*\n.*?SN:\s*([A-Z0-9\-]+)'
                ]
                
                for i, pattern in enumerate(inventory_patterns):
                    if pattern.count('(') == 1:  # Pattern with only SN group
                        matches = re.findall(pattern, inventory_section)
                        for serial in matches:
                            if isinstance(serial, tuple):
                                serial = serial[0] if len(serial) == 1 else serial[1]
                            
                            serial = serial.strip()
                            if not serial or serial.upper() in ['N/A', 'NONE', 'UNKNOWN', 'UNSPECIFIED']:
                                continue
                            
                            inventory_devices.append({
                                'name': 'Device',
                                'serial': serial,
                                'device_type': 'unknown',
                                'priority': device_priorities['unknown']
                            })
                            logging.debug(f"Identified generic serial from pattern {i+1}: {serial}")
                    else:  # Pattern with NAME and SN groups
                        matches = re.findall(pattern, inventory_section)
                        for name, serial in matches:
                            name = name.strip().strip('"')
                            serial = serial.strip()
                            name_lower = name.lower()
                            
                            # Skip invalid serials
                            if not serial or serial.upper() in ['N/A', 'NONE', 'UNKNOWN', 'UNSPECIFIED']:
                                continue
                            
                            # Skip obvious non-main components
                            if any(x in name_lower for x in ['transceiver', 'sfp', 'gbic', 'cable', 'optic']):
                                continue
                            
                            # Classify device type and assign priority
                            device_type = 'unknown'
                            priority = 0
                            
                            # Switch devices (highest priority)
                            if 'switch' in name_lower:
                                if 'system' in name_lower:
                                    device_type = 'switch_system'
                                    priority = device_priorities['switch_system']
                                elif any(x in name_lower for x in ['stack', 'c93xx']):
                                    device_type = 'switch_stack'
                                    priority = device_priorities['switch_stack']
                                elif re.search(r'switch\s*\d+', name_lower):
                                    device_type = 'switch_numbered'
                                    priority = device_priorities['switch_numbered']
                                    # Boost priority for Switch 1
                                    if 'switch 1' in name_lower or 'switch  1' in name_lower:
                                        priority += 5
                                else:
                                    device_type = 'switch_other'
                                    priority = device_priorities['switch_other']
                            
                            # Chassis devices
                            elif 'chassis' in name_lower:
                                # Avoid line-cards like "Chassis 1 1"
                                if re.search(r'chassis\s*\d+\b(?!\s*\d)', name_lower):
                                    device_type = 'chassis'
                                    priority = device_priorities['chassis']
                                    # Boost priority for Chassis 1
                                    if 'chassis 1' in name_lower or 'chassis  1' in name_lower:
                                        priority += 5
                            
                            # Supervisor modules
                            elif any(x in name_lower for x in ['supervisor', 'sup ']):
                                device_type = 'supervisor'
                                priority = device_priorities['supervisor']
                            
                            # Line cards
                            elif any(x in name_lower for x in ['linecard', 'line card']):
                                device_type = 'linecard'
                                priority = device_priorities['linecard']
                            
                            # Power supplies and fans
                            elif any(x in name_lower for x in ['power', 'fan', 'fantray']):
                                device_type = 'power_fan'
                                priority = device_priorities['power_fan']
                            
                            # Add to devices if it has valid priority
                            if priority > 0:
                                inventory_devices.append({
                                    'name': name,
                                    'serial': serial,
                                    'device_type': device_type,
                                    'priority': priority
                                })
                                logging.debug(f"Identified device: {name} (SN: {serial}, Type: {device_type}, Pri: {priority})")
                
                # Select highest priority device serial
                if inventory_devices:
                    logging.debug(f"Total relevant inventory devices found: {len(inventory_devices)}. Sorting by priority.")
                    # Sort by priority (highest first), then by name for consistency
                    inventory_devices.sort(key=lambda x: (-x['priority'], x['name']))
                    
                    # Special handling for multiple switches with same serial
                    switch_devices = [d for d in inventory_devices if d['device_type'].startswith('switch')]
                    if len(switch_devices) > 1:
                        switch_serials = set(d['serial'] for d in switch_devices)
                        if len(switch_serials) == 1:
                            # All switches have same serial - use it
                            inventory_serial = next(iter(switch_serials))
                            logging.info(f"Inventory: All switches have same serial: {inventory_serial}")
                        else:
                            # Mixed serials - prefer Switch 1, Switch System, or highest priority
                            switch_1 = next((d for d in switch_devices if '1' in d['name'] or 'system' in d['name'].lower()), None)
                            if switch_1:
                                inventory_serial = switch_1['serial']
                                logging.info(f"Inventory: Using primary switch serial: {switch_1['name']} ({inventory_serial})")
                            else:
                                # Use highest priority switch
                                inventory_serial = switch_devices[0]['serial']
                                logging.info(f"Inventory: Using highest priority switch serial: {switch_devices[0]['name']} ({inventory_serial})")
                    else:
                        # Single switch or no switches - use highest priority device
                        selected_device = inventory_devices[0]
                        inventory_serial = selected_device['serial']
                        logging.info(f"Inventory: Selected highest priority device: {selected_device['name']} ({inventory_serial})")
                
                # Legacy fallback: Look specifically for Switch N patterns
                if not inventory_serial:
                    logging.debug("No serial selected via main inventory logic. Trying legacy Switch N pattern.")
                    switch_pattern = r'NAME:\s*"Switch\s*(\d+)".*?\bSN:\s*([A-Z0-9\-]+)'
                    switch_matches = re.findall(switch_pattern, inventory_section, re.IGNORECASE | re.DOTALL)
                    if switch_matches:
                        switch_serials = {int(num): serial.strip() for num, serial in switch_matches}
                        serial_values = set(switch_serials.values())
                        
                        if len(serial_values) == 1:
                            # All Switch N have same serial
                            inventory_serial = next(iter(serial_values))
                            logging.info(f"Legacy: All Switch N have same serial: {inventory_serial}")
                        elif 1 in switch_serials:
                            # Mixed serials - prefer Switch 1
                            inventory_serial = switch_serials[1]
                            logging.info(f"Legacy: Using Switch 1 serial: {inventory_serial}")
                        else:
                            # Use first available switch
                            first_switch = min(switch_serials.keys())
                            inventory_serial = switch_serials[first_switch]
                            logging.info(f"Legacy: Using Switch {first_switch} serial: {inventory_serial}")
                
                # Additional fallback: Check for common chassis serials
                if not inventory_serial:
                    logging.debug("Trying additional fallback for Chassis serials.")
                    chassis_pattern = r'NAME:\s*"Chassis\s*\d+[^"]*".*?\bSN:\s*([A-Z0-9\-]+)'
                    chassis_matches = re.findall(chassis_pattern, inventory_section, re.IGNORECASE | re.DOTALL)
                    chassis_serials = {serial for serial in chassis_matches 
                                     if serial and serial.upper() not in ['N/A', 'NONE', 'UNKNOWN', 'UNSPECIFIED']}
                    
                    if len(chassis_serials) == 1:
                        inventory_serial = next(iter(chassis_serials))
                        logging.info(f"Using common chassis serial: {inventory_serial}")
                        
            except Exception as e:
                logging.debug(f"Error parsing inventory serials: {e}")
        
        # --- Determine final serial number ---
        final_serial = None
        
        # Priority: System serial > Inventory serial
        if system_serial:
            final_serial = system_serial
            logging.info(f"Using system serial number: {final_serial}")
            
            # Log comparison with inventory if available
            if inventory_serial and inventory_serial != system_serial:
                logging.info(f"System serial ({system_serial}) differs from inventory ({inventory_serial}), using system")
            elif inventory_serial and inventory_serial == system_serial:
                logging.info(f"System and inventory serials match: {final_serial}")
                
        elif inventory_serial:
            final_serial = inventory_serial
            logging.info(f"Using inventory serial number: {final_serial}")
        
        logging.debug("Serial number search completed.")
        logging.info(f"Final serial: {final_serial}")
        return final_serial or "Require Manual Check"
        
    except Exception as e:
        logging.error(f"Error in get_serial_number: {e}")
        return "Require Manual Check"

def get_uptime(log_data: str) -> str:
    try:
        logging.info("Starting uptime search.")

        if not isinstance(log_data, str) or not log_data.strip():
            return "Not available"

        hostname = get_hostname(log_data)

        if hostname and hostname not in {"Not available", "Require Manual Check"}:
            escaped_hostname = re.escape(hostname.strip())
            pat_host = rf"(?mi)^\s*{escaped_hostname}\s+uptime\s+is\s+(.+?)\s*$"
            m = re.search(pat_host, log_data)
            if m:
                return m.group(1).strip()

        pat_any_uptime_is = r"(?mi)^\s*(\S+)\s+uptime\s+is\s+(.+?)\s*$"
        candidates = re.findall(pat_any_uptime_is, log_data)
        if candidates:
            for prefix, up in candidates:
                if re.search(r"(?i)\bcontrol\s+processor\b", prefix):
                    continue
                if up.strip():
                    return up.strip()
            if candidates[0][1].strip():
                return candidates[0][1].strip()

        pat_cp = r"(?mi)^\s*Uptime\s+for\s+this\s+control\s+processor\s+is\s+(.+?)\s*$"
        m = re.search(pat_cp, log_data)
        if m and m.group(1).strip():
            return m.group(1).strip()

        return "Require Manual Check"

    except Exception:
        return "Require Manual Check"

def get_current_sw_version(log_data):
    try:
        logging.info("Starting software version extraction.")
        if not log_data:
            logging.debug("Log data is empty. Returning 'Not available'.")
            return "Not available"

        # 1) Most explicit: "Cisco IOS XE Software, Version X"
        logging.debug("Attempt 1: Searching for explicit 'Cisco IOS XE Software, Version X'.")
        m = re.search(r'(?mi)^\s*Cisco\s+IOS\s+XE\s+Software,\s*Version\s+([^\s,]+)', log_data)
        if m:
            version = m.group(1).strip()
            logging.info(f"Version found (Attempt 1, IOS XE explicit): {version}")
            return version
        
        # 2) Common classic banner line that also appears on 16/17 & 3.x:
        #    "Cisco IOS Software ... Version X[, ]"
        logging.debug("Attempt 2: Searching for 'Cisco IOS Software ... Version X'.")
        m = re.search(r'(?mi)^\s*Cisco\s+IOS\s+Software.*?\bVersion\s+([^\s,]+)', log_data)
        if m:
            version = m.group(1).strip()
            logging.info(f"Version found (Attempt 2, IOS classic): {version}")
            return version

        # 3) Safety net for variants like "IOS-XE Software, ... Version X"
        logging.debug("Attempt 3: Searching for 'IOS[- ]?XE Software ... Version X'.")
        m = re.search(r'(?mi)\bIOS[- ]?XE\s+Software.*?\bVersion\s+([^\s,]+)', log_data)
        if m:
            version = m.group(1).strip()
            logging.info(f"Version found (Attempt 3, IOS-XE variant): {version}")
            return version

        # 4) Last-chance: grab the first "Version X" in the top of the file
        logging.debug("Attempt 4: Last chance search in the first 50 lines for 'Version X'.")
        head = "\n".join(log_data.splitlines()[:50])
        m = re.search(r'(?mi)\bVersion\s+([0-9A-Za-z.\(\)]+)', head)
        if m:
            version = m.group(1).strip()
            logging.warning(f"Version found (Attempt 4, generic head search): {version}")
            return version
        
        logging.info("No software version found by any pattern. Returning 'Not available'.")
        return "Not available"

    except Exception as e:
        logging.error(f"Error in get_current_sw_version: {str(e)}")
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

def check_stack(log_data):
    try:
        logging.info("Starting stack check.")

        # Only real stack switches have "Switch <number>" lines in show version output
        real_stack_match = re.search(r'(?mi)^\s*Switch\s+(\d+)\b', log_data)
        if not real_stack_match:
            logging.debug("No valid Catalyst stack pattern found - treating as single switch.")
            return False

        # Use IOS_XE_Stack_Switch logic to safely evaluate
        if not IOS_XE_Stack_Switch.is_stack_switch(log_data):
            logging.debug("IOS_XE_Stack_Switch indicates non-stack device.")
            return False

        stack_details = IOS_XE_Stack_Switch.parse_ios_xe_stack_switch(log_data)
        if not stack_details:
            logging.debug("Stack parser returned empty - treating as single switch.")
            return False

        logging.debug("Stack check completed - valid stack detected.")
        return stack_details

    except Exception as e:
        logging.error(f"Error in check_stack: {str(e)}")
        return False

def get_memory_info(log_data):
    try:
        logging.info("Starting memory info extraction.")

        if not log_data:
            return ["Not available", "Not available", "Not available", "Not available"]

        import re

        def _parse_num_with_unit(token: str) -> int | None:
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
            return "Not available"

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
        return flash_information if flash_information else "Not available"

    except Exception as e:
        logging.error(f"Error in get_flash_info: {str(e)}")
        return f"Require Manual Check"

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

# ====================================================================
# CORE FUNCTION: get_temperature_status
# ====================================================================

# def get_temperature_status(log_data: str) -> List[str]:
#     """
#     Analyzes log data using dynamic regex patterns to determine temperature status.
#     Returns a list of final statuses found (e.g., ['OK'], ['NOT OK'], or ['Not available']).
#     """
#     try:
#         search_data = extract_env_sections(log_data)
#         # Clean up common non-breaking spaces and carriage returns
#         search_data = search_data.replace('\xa0', ' ').replace('\r', '') 

#         # per_switch_status: Tracks the determined status (True=OK, False=NOT OK)
#         per_switch_status: Dict[int, bool] = {} 
#         total_matches_found = False
        
#         # --- PHASE 1: Apply ALL Positive Patterns (Tier 1) ---
#         for pattern_info in TEMPERATURE_PATTERNS["positive_patterns"]:
            
#             # Use finditer for reliable extraction, especially for named groups
#             matches = re.finditer(pattern_info["regex"], search_data, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            
#             for m in matches:
#                 total_matches_found = True
                
#                 if pattern_info["source_type"] == "Switch":
#                     # For switch/module-specific status
#                     try:
#                         # Use default switch ID 1 if 'ID' group is not available, though it should be.
#                         sw_id = int(m.group('ID')) if 'ID' in m.groupdict() else 1
                        
#                         # Positive match reinforces OK status. Default assumption is True.
#                         per_switch_status[sw_id] = per_switch_status.get(sw_id, True) and True
#                     except (IndexError, ValueError):
#                         # Catch if a Switch pattern unexpectedly lacks an ID group
#                         per_switch_status[1] = per_switch_status.get(1, True) and True
                
#                 elif pattern_info["source_type"] == "Global":
#                     # Global positive matches only signal we have *some* useful status data.
#                     # We assume Switch 1 if no IDs have been seen yet.
#                     if not per_switch_status:
#                         per_switch_status[1] = True


#         # --- PHASE 2: Apply ALL Negative Patterns (Tier 2) ---
#         # Negative patterns override any previously set status (Fail-Safe)
#         for pattern_info in TEMPERATURE_PATTERNS["negative_patterns"]:
#             matches = re.finditer(pattern_info["regex"], search_data, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            
#             for m in matches:
#                 total_matches_found = True

#                 if pattern_info["source_type"] == "Switch":
#                     # Explicitly set status to False (NOT OK) for the matching switch
#                     try:
#                         sw_id = int(m.group('ID')) if 'ID' in m.groupdict() else 1
#                         per_switch_status[sw_id] = False
#                     except (IndexError, ValueError):
#                         per_switch_status[1] = False
                
#                 elif pattern_info["source_type"] == "Global":
#                     # A single critical word applies globally, forcing all tracked switches to NOT OK.
#                     if per_switch_status:
#                         for sw_id in list(per_switch_status.keys()):
#                             per_switch_status[sw_id] = False
#                     else:
#                          per_switch_status[1] = False # Assume Switch 1 is failing if no switch IDs yet


#         # --- PHASE 3: Final Aggregation and Result (Tier 3 Heuristic) ---
#         final_results = []
#         has_numeric_temps = re.search(r'(?mi)\b(?:temperature|temp|hotspot)\b[^:\n]*[:\s]\s*\d+\s*(?:C|F|Degree)', search_data)

#         if per_switch_status:
#             # Case 1: We have definitive, structured status data from Tier 1/2 checks
#             for sw in sorted(per_switch_status.keys()):
#                 final_results.append("OK" if per_switch_status[sw] else "NOT OK")
            
#         elif not total_matches_found and has_numeric_temps:
#             # Case 2 (Safe Fallback): No explicit status found, but numerical temp data exists. Assume OK.
#             final_results = ["OK"]
        
#         elif search_data:
#             # Case 3: Log data was extracted but contains no status patterns or temp numbers.
#             final_results = ["Not available"]
            
#         else:
#             # Case 4: No environment data was found/extracted at all.
#             final_results = ["Not available"]

#         return list(set(final_results)) # Return unique statuses only

#     except Exception as e:
#         logging.error(f"Error in get_temperature_status: {str(e)}")
#         # If any unexpected exception occurs, flag for manual review
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

def get_fan_status(log_data: str) -> List[str]:
    try:
        if not log_data:
            return ["Not available"]

        # --- PREPROCESSING FIX: Handle non-standard whitespace/CRLF issues ---
        log_data = log_data.replace('\xa0', ' ').replace('\r', '') 
        # ----------------------------------------------------------------------
        
        # Key: Switch Number (int), Value: List of boolean status (True=OK, False=NOT OK)
        fan_status_by_switch: Dict[int, List[bool]] = {}
        # NEW: Dedicated tracking for ONLY chassis/module fans (excluding power supply fans)
        chassis_fan_status_by_switch: Dict[int, List[bool]] = {} 

        def add_status(sw: int, is_ok: bool):
            # Original logic (includes all fan types)
            fan_status_by_switch.setdefault(sw, []).append(is_ok)
            
        def add_chassis_status(sw: int, is_ok: bool):
             # New logic for chassis/module fans only
            chassis_fan_status_by_switch.setdefault(sw, []).append(is_ok)


        env_data = extract_env_sections(log_data)
        search_data = env_data if env_data else log_data
        
        # --- A) Legacy lines: "Switch 1 FAN 2 is OK" (Existing Logic, now calls both)
        for sw_str, state_text in re.findall(
            r'(?mi)^\s*Switch\s+(\d+)\s+FAN\s+\d+\s+is\s+([A-Za-z ]+)\s*$',
            search_data,
        ):
            sw = int(sw_str)
            ok_status = is_fan_ok(state_text)
            add_status(sw, ok_status)
            add_chassis_status(sw, ok_status) # <-- ENHANCEMENT

        # --- A.1) NEW LOGIC: "FAN PS-N is OK" (Existing Logic, PS Fan, so only calls add_status) ---
        for state_text in re.findall(
            r'(?mi)^\s*FAN\s+PS-\d+\s+is\s+([A-Za-z ]+)\s*$',
            search_data,
        ):
            add_status(1, is_fan_ok(state_text)) 

        # --- A.2) ADDED LOGIC: "FAN is OK" (For single-switch/non-stacked outputs, now calls both) ---
        for state_text in re.findall(
            r'(?mi)^\s*FAN\s+is\s+([A-Za-z ]+)\s*$',
            search_data,
        ):
            ok_status = is_fan_ok(state_text)
            add_status(1, ok_status) 
            add_chassis_status(1, ok_status) # <-- ENHANCEMENT
            
        # --- A.3) NEW LOGIC: "Fantray : Good" (For chassis fan trays, now calls both) ---
        for state_text in re.findall(
            r'(?mi)^\s*Fantray\s*:\s*([A-Za-z\s]+)\s*$',
            search_data,
        ):
            ok_status = is_fan_ok(state_text)
            add_status(1, ok_status) 
            add_chassis_status(1, ok_status) # <-- ENHANCEMENT

        # --- A.4) NEW LOGIC: Explicit "fan-fail: OK" lines (Cat6K/Cat6800 style) ---
        # Matches patterns like: "switch 1 fan-tray 1 fan-fail: OK" and "switch 1 power-supply 1 fan-fail: OK"
        fan_fail_pattern = r'(?mi)^\s*switch\s+(\d+)\s+(fan-tray|power-supply)\s+\d+.*fan-fail:\s*([A-Za-z\s]+)\s*$'
        for sw_str, component_type, state_text in re.findall(fan_fail_pattern, search_data):
            sw = int(sw_str)
            ok_status = is_fan_ok(state_text)
            
            add_status(sw, ok_status) 
            
            if component_type.lower() == 'fan-tray':
                add_chassis_status(sw, ok_status) # <-- ENHANCEMENT only for fan-tray


        # --- B) Columnar Table format: "Switch FAN Speed State Airflow direction" (Existing Logic, now calls both)
        blocks = re.split(
            r'(?mi)^\s*Switch\s+FAN\s+Speed\s+State\s+Airflow\s+direction\s*$',
            search_data,
        )
        for blk in blocks[1:]:
             for raw in blk.splitlines():
                 line = raw.strip()
                 if not line or re.match(r'^\s*-{3,}', line) or re.search(r'(?i)^\s*(SW\s+PID|Sensor List:|NAME:|Interface|CPU|show\s+)', line):
                     continue

                 norm = re.sub(r'[\t ]+', ' ', line)
                 cols = norm.split()

                 if len(cols) >= 3 and cols[0].isdigit():
                     sw = int(cols[0])
                     state = None
                     if cols[1].isdigit():
                         state = cols[2].upper()
                     elif len(cols) >= 4 and cols[2].isdigit():
                         state = cols[3].upper()
                     else:
                         state = cols[2].upper()
                         
                     if state is not None and (is_fan_ok(state) or state in ["NOT", "FAULT", "FAILED", "NOT-OK", "SHUTDOWN"]):
                         ok_status = is_fan_ok(state)
                         add_status(sw, ok_status)
                         add_chassis_status(sw, ok_status) # <-- ENHANCEMENT
        
        # --- B.1) NEW LOGIC: Columnar Table format: "Switch FAN Speed State" (No Airflow direction, now calls both) ---
        blocks_no_airflow = re.split(
            r'(?mi)^\s*Switch\s+FAN\s+Speed\s+State\s*$', 
            search_data,
        )
        for blk in blocks_no_airflow[1:]:
             for raw in blk.splitlines():
                 line = raw.strip()
                 if not line or re.match(r'^\s*-{3,}', line) or re.search(r'(?i)^\s*(SW\s+PID|Sensor List:|NAME:|Interface|CPU|show\s+)', line):
                     continue

                 norm = re.sub(r'[\t ]+', ' ', line)
                 cols = norm.split()

                 if len(cols) >= 3 and cols[0].isdigit():
                     sw = int(cols[0])
                     state = None
                     if cols[1].isdigit():
                         state = cols[2].upper()
                     elif len(cols) >= 4 and cols[2].isdigit():
                         state = cols[3].upper()
                     else:
                         state = cols[2].upper()
                         
                     if state is not None and (is_fan_ok(state) or state in ["NOT", "FAULT", "FAILED", "NOT-OK", "SHUTDOWN"]):
                         ok_status = is_fan_ok(state)
                         add_status(sw, ok_status)
                         add_chassis_status(sw, ok_status) # <-- ENHANCEMENT
                         
        # --- C) RPM/PSx Sensor List Parsing (Existing Logic) ---
        sensor_fan_pattern = re.compile(
            r'^\s*PS\d+\s+FAN\s+.*?(\d+)\s+([A-Z\s]+)\s+.*$|' 
            r'^\s*RPM:\s+fan\d+\s+.*?\s+([A-Z\s]+)\s+.*$|'
            r'^\s*SYSTEM\s+(?:INLET|OUTLET|HOTSPOT)\s+(\d+)\s+([A-Z\s]+)\s+.*$'
            , 
            re.IGNORECASE | re.MULTILINE
        )
        
        for match in sensor_fan_pattern.finditer(search_data):
            # PSx FAN match (Only add to standard status)
            if match.group(2) is not None:
                sw = int(match.group(1)) 
                state_text = match.group(2).strip()
                add_status(sw, is_fan_ok(state_text))
            
            # RPM: fanX match (Chassis Fan - add to both)
            elif match.group(3) is not None:
                sw = 1 
                state_text = match.group(3).strip()
                ok_status = is_fan_ok(state_text)
                add_status(sw, ok_status)
                add_chassis_status(sw, ok_status) # <-- ENHANCEMENT
            
            # SYSTEM temp match (Temp status only affects overall if NOT OK)
            elif match.group(5) is not None:
                 sw = int(match.group(4)) 
                 state_text = match.group(5).strip()
                 if not is_fan_ok(state_text): 
                     add_status(sw, is_fan_ok(state_text))
            else:
                continue 
            
        # --- D) Cisco Chassis (Cat9600) Fan/PS Table Parsing (Existing Logic) ---
        switch_blocks = re.split(r'(?i)^\s*Switch:(\d+)\s*$', search_data, re.MULTILINE)
        
        for i in range(1, len(switch_blocks)):
            block = switch_blocks[i] 
            current_sw_id = i 

            # D.1) Parse FAN TRAY (FM) table: (Chassis Fan - add to both)
            fm_pattern = r'(?mi)^\s*FM\d+\s+(ok|not ok|good|not good|fault|failed)\s+([a-z\s]+)\s+([a-z\s]+)\s*([a-z\s]+)\s*([a-z\s]+)\s*$'
            for match in re.findall(fm_pattern, block):
                for state_text in match: 
                    if state_text and state_text.strip():
                        ok_status = is_fan_ok(state_text)
                        add_status(current_sw_id, ok_status)
                        add_chassis_status(current_sw_id, ok_status) # <-- ENHANCEMENT

            # D.2) Parse Power Supply Fan States (PS) table: (PS Fan - only add to standard status)
            ps_fan_pattern = r'(?mi)^\s*PS\d+\s+.*?\s+(ok|fail|not ok|failed)\s+([a-z\s]+)\s*([a-z\s]+)?\s*$'
            for match in re.findall(ps_fan_pattern, block):
                for state_text in match:
                    if state_text and state_text.strip():
                        add_status(current_sw_id, is_fan_ok(state_text))

        # --- E) Switch FAN Speed State Table Parsing (Explicitly for the target format from last turn, now calls both) ---
        fan_table_pattern = re.compile(
            r'(?mi)^\s*Switch\s+FAN\s+Speed\s+State\s+Airflow\s+direction\s*\n\s*-+\s*\n' 
            r'((?:\s+\d+\s+\d+\s+(?:OK|NOT\s+OK|FAULT|GOOD)\s+.*?\s*)+)'
        )
        for block_match in fan_table_pattern.finditer(search_data):
            fan_data_block = block_match.group(1)
            for raw_line in fan_data_block.splitlines():
                line = raw_line.strip()
                if line:
                    norm = re.sub(r'\s{2,}', ' ', line)
                    cols = norm.split(' ', 3)
                    
                    if len(cols) >= 3 and cols[0].isdigit():
                        sw = int(cols[0])
                        state_check = cols[2].split(' ')[0].upper()
                        
                        if is_fan_ok(state_check) or state_check in ["NOT", "FAULT", "FAILED", "NOT-OK", "SHUTDOWN"]:
                            ok_status = is_fan_ok(state_check)
                            add_status(sw, ok_status)
                            add_chassis_status(sw, ok_status) # <-- ENHANCEMENT
                            
        # --- F) NEW CONDITION: Generic Sensor List Parsing (Cat9K style) ---
        sensor_state_pattern_f = re.compile(
            r'(?mi)^\s*[A-Za-z: ]+?\s+(Switch(\d+)[-/\w\s]+?)\s+([A-Z\s]+)\s+.*$',
            re.IGNORECASE | re.MULTILINE
        )
        for match in sensor_state_pattern_f.finditer(search_data):
            try:
                sw = int(match.group(2)) 
                state_text = match.group(3).strip()
                
                # Check for fan sensor (Chassis Fan - add to both, only if not explicitly PS)
                if "FAN" in match.group(1).upper() and "PS" not in match.group(1).upper():
                    ok_status = is_fan_ok(state_text)
                    add_status(sw, ok_status)
                    add_chassis_status(sw, ok_status) # <-- ENHANCEMENT for non-PS fan
                else:
                    # Non-fan/PS status (e.g., temp/other or PS fan)
                    add_status(sw, is_fan_ok(state_text)) 
            except ValueError:
                pass
        # ---------------------------------------------------------------------

        # --- G) Final Report (Aggregation) ---
        
        # 1. Determine which status list to use for each switch.
        #    Prioritize chassis-only status if available (to ignore faulty PS fans)
        
        status_to_report: Dict[int, List[bool]] = {}
        all_switches = set(fan_status_by_switch.keys()) | set(chassis_fan_status_by_switch.keys())
        
        for sw in sorted(all_switches):
            # If any chassis-only fan statuses were found for this switch, use them (This fulfills the user's request)
            if sw in chassis_fan_status_by_switch and chassis_fan_status_by_switch[sw]:
                status_to_report[sw] = chassis_fan_status_by_switch[sw]
            # Otherwise, fall back to the full status list (Preserving old logic for logs without chassis fan details)
            elif sw in fan_status_by_switch:
                status_to_report[sw] = fan_status_by_switch[sw]


        if not status_to_report:
            return ["Not available"]

        final_status: List[str] = []
        
        for sw in sorted(status_to_report.keys()):
            statuses = status_to_report[sw]
            all_fans_ok = all(statuses) 
            final_status.append("OK" if all_fans_ok else "NOT OK")
            
        return final_status

    except Exception as e:
        return [f"Require Manual Check (Error: {e})"]

def show_env(log_data):
    show_env_start_index = re.search("show environment", log_data).group(1)
    show_env_end_index = re.search("show", log_data[show_env_start_index:])
    required_section = log_data[show_env_start_index:show_env_start_index + show_env_end_index]
    return required_section
 
def get_power_supply_status(log_data: str) -> list[str]:
    logging.info("Starting power supply status extraction")

    lines = log_data.splitlines()
    header_re = re.compile(r'(?i)^\s*SW\s+PID\s+.*Serial#\s+.*Status\b')
    # Require 1–2 digit stack id, slot A|B, and at least one space before the rest of columns
    row_re = re.compile(r'^\s*(?P<sw>\d{1,2})(?P<bay>[AB])\s+(?P<rest>.+)$')

    severity = {"OK": 0, "Not Present": 1, "NOT OK": 2, "UNKNOWN": -1}

    in_table = False
    rows_started = False
    per_switch = {}  # sw -> list[(slot, status)]

    for idx, line in enumerate(lines):
        if not in_table:
            if header_re.search(line):
                in_table = True
                rows_started = False
                logging.debug(f"Found PSU table header at line {idx}: {line.strip()}")
            continue

        # Skip divider lines inside the table
        if re.match(r'^\s*-{3,}\s*$', line):
            continue

        if not rows_started:
            m = row_re.match(line)
            if m:
                rows_started = True
            else:
                # header area noise; a blank line before rows ends the table
                if not line.strip():
                    logging.debug(f"Blank line before first row at {idx}; exiting table")
                    in_table = False
                continue

        # If rows have started, stop at blank line or first non-row
        if not line.strip():
            logging.debug(f"Blank line after rows at {idx}; exiting table")
            break
        m = row_re.match(line)
        if not m:
            logging.debug(f"Non-row encountered at {idx}; exiting table: {line.strip()}")
            break

        sw = int(m.group('sw'))          # guard: only 1–2 digits allowed
        bay = m.group('bay').upper()
        slot = f"{sw}{bay}"
        norm = m.group('rest').strip()

        if re.search(r'(?i)\bNot\s+Present\b', norm):
            status = "Not Present"
        elif re.search(r'(?i)\b(BAD|FAIL|NO\s+INPUT\s+POWER|ALARM)\b', norm):
            status = "NOT OK"
        elif re.search(r'(?i)\bOK\b', norm):
            status = "OK"
        else:
            status = "UNKNOWN"

        logging.debug(f"Parsed line {idx}: slot={slot}, sw={sw}, status={status}")
        per_switch.setdefault(sw, []).append((slot, status))

    if not per_switch:
        logging.warning("No PSU table rows matched")
        logging.info("Completed power supply status extraction")
        return ["Not available"]

    # Consolidate per switch: take the worst status; include slot for non-OK
    result: list[str] = []
    for sw in sorted(per_switch.keys()):
        slots = per_switch[sw]
        worst_slot, worst_status = max(slots, key=lambda ss: severity.get(ss[1], -1))

        if worst_status == "OK":
            if all(s == "OK" for _, s in slots):
                result.append("OK")
                logging.info(f"Switch {sw} -> All OK ({', '.join(sl for sl, _ in slots)})")
            else:
                # OK mixed with UNKNOWN -> OK; otherwise worst already covers it
                if any(s not in ("OK", "UNKNOWN") for _, s in slots):
                    result.append(f"{worst_slot}: {worst_status}")
                    logging.info(f"Switch {sw} -> {worst_slot}: {worst_status}")
                else:
                    result.append("OK")
                    logging.info(f"Switch {sw} -> OK (with UNKNOWN present)")
        else:
            result.append(f"{worst_slot}: {worst_status}")
            logging.info(f"Switch {sw} -> {worst_slot}: {worst_status}")

    logging.info("Completed power supply status extraction")
    return result

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
        return [["Require Manual Check"]] * current_stack_size

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
        return [[f"Require Manual Check"]] * IOS_XE_Stack_Switch.stack_size(log_data)

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
    try:
        logging.info(f"Starting processing of file: {file_path}")
        # read only if text not provided
        if text is None:
            with open(file_path, 'r', errors='ignore') as file:
                log_data = file.read()
        else:
            log_data = text
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
                "End of Routine Failure Analysis Date: HW": ["Yet to check"],
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
            data["End of Routine Failure Analysis Date: HW"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["End of Vulnerability/Security Support: HW"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["End of SW Maintenance Releases Date: HW"] = ["Yet to check"] * current_stack_size  # ← FIXED
            data["Remark"] = ["Yet to check"] * current_stack_size  # ← FIXED
            logging.debug(f"File processing completed: {file_path}")
        return data
    except Exception as e:
        logging.error(f"Error in process_file: {str(e)}")
        return {
            "File name": [get_ip_address(file_path)[0] if file_path else "Unknown"],
            "Host name": ["Require Manual Check"],
            "Model number": ["Require Manual Check"],
            "Serial number": ["Require Manual Check"],
            "Interface ip address": [get_ip_address(file_path)[1] if file_path else "Unknown"],
            "Uptime": ["Require Manual Check"],
            "Current s/w version": ["Require Manual Check"],
            "Last Reboot Reason": ["Require Manual Check"],
            "Any Debug?": ["Require Manual Check"],
            "CPU Utilization": ["Require Manual Check"],
            "Total memory": ["Require Manual Check"],
            "Used memory": ["Require Manual Check"],
            "Free memory": ["Require Manual Check"],
            "Memory Utilization (%)": ["Require Manual Check"],
            "Total flash memory": ["Require Manual Check"],
            "Used flash memory": ["Require Manual Check"],
            "Free flash memory": ["Require Manual Check"],
            "Used Flash (%)": ["Require Manual Check"],
            "Fan status": ["Require Manual Check"],
            "Temperature status": ["Require Manual Check"],
            "PowerSupply status": ["Require Manual Check"],
            "Available Free Ports": ["Require Manual Check"],
            "Any Half Duplex": ["Require Manual Check"],
            "Interface/Module Remark": ["Require Manual Check"],
            "Config Status": ["Require Manual Check"],
            "Config Save Date": ["Require Manual Check"],
            "Critical logs": [f"process_file failed: {e}"],
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
            "Remark": [f"Require Manual Check (IOSXE parser exception: {e})"],
        }
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
    # data = process_directory(r"C:\Users\girish.n\Downloads\OneDrive_2_13-10-2025 1")
    # with open (r"C:\Users\girish.n\Downloads\OneDrive_2025-11-18 1\Cisco R&S\TH-MUDA-WHC9407R-01.txt", 'r', errors='ignore') as f:
    #     log_data = f.read()
    #     hostname = get_hostname(log_data)
    #     model_number = get_model_number(log_data)
    #     serial_number = get_serial_number(log_data)
    # print(hostname)
    # print(model_number)
    # print(serial_number)
    data = process_file(file_path = r"C:\Users\girish.n\Downloads\OneDrive_2025-11-18 1\Cisco R&S\TH-MUDA-WHC9407R-01.txt")
    print_data(data)
    # for item in data:
    #     print_data(item['File name'])
    #     print(item['PowerSupply status'])
    #     # print(item['Fan status'])
    #     # print(item['Temperature status'])

if __name__ == "__main__":
    main()