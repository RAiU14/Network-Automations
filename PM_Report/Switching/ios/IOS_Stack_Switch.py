import re
import logging
import os
import datetime

log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
# Configure logging only once to avoid collisions when imported alongside Cisco_IOS_XE
if not logging.getLogger().handlers:
    logging.basicConfig(
        filename=os.path.join(log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"),
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


# Strict row shape: [*] <id> <ports> <model> <swver> <image> ...
ROW_RE = re.compile(
    r'(?m)^[ *]\s*'                 # optional asterisk, spaces
    r'(?P<id>[1-9]\d?)\s+'          # member id 1..99 (we'll cap later)
    r'(?P<ports>\d{1,3})\s+'        # ports column (1..3 digits)
    r'(?P<model>[A-Z0-9-]+)\s+'     # model token (e.g., WS-C2960X-48FPS-L)
    r'(?P<swver>\S+)\s+'            # SW Version token (e.g., 15.2(7)E5)
    r'(?P<image>\S+)'               # SW Image token (e.g., C2960X-UNIVERSALK9-M)
)

HEADER_RE = re.compile(
    r'(?mi)^\s*Switch\s+Ports\s+Model\s+SW\s+Version\s+SW\s+Image\s*$'
)

def stack_size(log_text: str, *, max_members: int = 12) -> int:
    """
    Read one or more 'Switch Ports Model ...' tables from log_text and
    return the maximum stack size found. Stops each table at the first
    non-row line. Ignores spurious matches.
    """
    if not log_text:
        return 1

    # normalize newlines
    lines = log_text.replace('\r', '').split('\n')
    n = len(lines)
    i = 0
    best = 1

    while i < n:
        # find the next header line
        m = HEADER_RE.search(lines[i])
        if not m:
            i += 1
            continue

        # move to the line after the header; optionally skip an underline line of dashes/spaces
        j = i + 1
        if j < n and re.match(r'^\s*[-\s]+$', lines[j]):
            j += 1

        member_ids = set()

        # consume contiguous valid row lines only
        while j < n:
            rowm = ROW_RE.match(lines[j])
            if not rowm:
                break  # end of this table
            mid = int(rowm.group('id'))
            if 1 <= mid <= max_members:
                member_ids.add(mid)
            j += 1

        # compute this table's count
        if member_ids:
            # use both the number of unique ids and the highest id to survive gaps
            count = max(len(member_ids), max(member_ids))
            if 1 <= count <= max_members:
                best = max(best, count)

        # continue scanning after the table we just processed
        i = j + 1

    return best

def serial_number(data):
    try:
        m = re.search(r"System\s+Serial\s+Number\s*:\s*(\S+)", data, re.IGNORECASE)
        return m.group(1) if m else None
    except Exception as e:
        logging.error(f"Error in serial_number: {str(e)}")
        return None

def model_number(data):
    try:
        m = re.search(r"Model\s+Number\s*:\s*(\S+)", data, re.IGNORECASE)
        return m.group(1) if m else None
    except Exception as e:
        logging.error(f"Error in model_number: {str(e)}")
        return None

def get_last_reboot_reason(data):
    """Extract last reboot reason from the provided data"""
    try:
        match = re.search(r"Last reload reason\s+:\s+(.+)", data)
        return match.group(1) if match else None
    except Exception as e:
        logging.error(f"Error in get_last_reboot_reason: {str(e)}")
        return None

def uptime(data):
    """Extract uptime from the provided data"""
    try:
        match = re.search(r"Switch uptime\s+:\s+(.+)", data)
        return match.group(1).strip() if match else None
    except Exception as e:
        logging.error(f"Error in uptime: {str(e)}")
        return None

def parse_IOS_Stack_Switch(content: str):
    """
    Parse IOS/IOS-XE per-switch details from 'show version' style output.
    Robust to case, spacing, and mixed logs. Prefers per-switch inventory PID when present.
    Returns a dict like:
      {
        'stack switch 2 Serial_Number': 'FOC2239T1J0',
        'stack switch 2 Model_Number' : 'WS-C2960X-48FPS-L',
        'stack switch 2 Uptime'       : '47 weeks, 4 days, 2 hours, 0 minutes',
        'stack switch 2 Last Reboot'  : 'Not available',
        ...
      }
    """
    try:
        if not isinstance(content, str) or not content.strip():
            return {}

        text = content.replace('\r', '')  # normalize newlines

        data = {}

        # ---------- 1) Build optional Inventory map: Switch-N -> PID ----------
        # Matches blocks like:
        #   NAME: "Switch 03", DESCR: ...
        #   PID: WS-C2960X-48FPS-L , VID: V07, SN: FOC2239T1H5
        inv_map = {}
        try:
            inv_blocks = re.finditer(
                r'(?mis)^NAME:\s*"[^\n"]*Switch\s*(\d+)"[^\n]*\n\s*PID:\s*([^\s,]+)',
                text, re.IGNORECASE
            )
            for m in inv_blocks:
                sw = int(m.group(1))
                pid = m.group(2).strip()
                inv_map[sw] = pid
        except Exception as _:
            pass  # inventory is optional

        # ---------- 2) Find "Switch NN" sections in show version ----------
        # Sections look like:
        #   Switch 02
        #   ---------
        #   Switch Uptime                  : 1 year, ...
        #   Base ethernet MAC Address      : ...
        #   Model number                   : WS-C2960X-48FPS-L
        #   System serial number           : FOC2239T1J0
        #
        # We capture the NN and the following block up to the next "Switch XX" header or a blank line run.
        sec_iter = re.finditer(
            r'(?mis)^\s*Switch\s+(\d{1,2})\s*$\n[-=]{3,}\n(.*?)(?=^\s*Switch\s+\d{1,2}\s*$\n[-=]{3,}\n|\Z)',
            text, re.IGNORECASE
        )

        # helpers to pick fields from a section body (case-insensitive, tolerant colons/spaces)
        def _pick_serial(s: str):
            m = re.search(r'(?mi)^\s*System\s+Serial\s+Number\s*[:=]?\s*(\S+)', s)
            return m.group(1).strip() if m else None

        def _pick_model(s: str):
            m = re.search(r'(?mi)^\s*Model\s+Number\s*[:=]?\s*([^\s\r\n]+)', s)
            return m.group(1).strip() if m else None

        def _pick_uptime(s: str):
            # "Switch Uptime                   : 47 weeks, 4 days, ..."
            m = re.search(r'(?mi)^\s*Switch\s+Uptime\s*[:=]?\s*(.+?)\s*$', s)
            return m.group(1).strip() if m else None

        def _pick_last_reboot(s: str):
            # Often not present in per-switch blocks; fill if available else "Not available"
            m = re.search(r'(?mi)^\s*Last\s+reload\s+reason\s*[:=]?\s*(.+?)\s*$', s)
            return m.group(1).strip() if m else None

        any_section = False
        for sec in sec_iter:
            any_section = True
            sw = int(sec.group(1))
            body = sec.group(2)

            sv_model = _pick_model(body)
            sv_sn    = _pick_serial(body)
            sv_up    = _pick_uptime(body)
            sv_last  = _pick_last_reboot(body) or "Not available"

            # prefer inventory PID over show-ver model when present
            chosen_model = inv_map.get(sw) or sv_model

            if sv_sn or chosen_model or sv_up:
                data[f'stack switch {sw} Serial_Number'] = sv_sn
                data[f'stack switch {sw} Model_Number']  = chosen_model
                data[f'stack switch {sw} Uptime']        = sv_up
                data[f'stack switch {sw} Last Reboot']   = sv_last

        if any_section:
            return data

        # ---------- 3) Fallback: try to parse the "Switch Ports Model ..." table ----------
        # If no per-switch sections exist (single-unit or some images), derive at least #1 model/SN if we can.
        # Table header:
        #   Switch Ports Model                     SW Version            SW Image
        #   ------ ----- -----                     ----------            ----------
        #   *    1 54    WS-C2960X-48FPS-L         15.2(7)E5             C2960X-UNIVERSALK9-M
        table_match = re.search(
            r'(?mis)^\s*Switch\s+Ports\s+Model\s+SW\s+Version\s+SW\s+Image\s*\n[-\s]+\n'
            r'(?P<table>(?:[ *]\s*\d+\s+\d+\s+\S+.*\n)+)',
            text
        )
        if table_match:
            # grab row for switch 1 (asterisk or not), in case we want to expose minimal info
            table = table_match.group('table')
            m1 = re.search(r'(?mi)^[ *]\s*1\s+\d+\s+([A-Z0-9-]+)\s+', table)
            if m1:
                data['stack switch 1 Model_Number'] = inv_map.get(1) or m1.group(1).strip()
            # Serial number for switch 1 usually appears earlier in show ver (outside sections)
            # Try generic 'System serial number' near the top:
            m_sn = re.search(r'(?mi)^\s*System\s+Serial\s+Number\s*[:=]?\s*(\S+)?\s*$', text)
            if m_sn:
                data['stack switch 1 Serial_Number'] = m_sn.group(1).strip()
            # Uptime for single device (not per-switch)
            m_up = re.search(r'(?mi)^\s*\S+\s+uptime\s+is\s+(.+)$', text)
            if m_up:
                data['stack switch 1 Uptime'] = m_up.group(1).strip()
            data.setdefault('stack switch 1 Last Reboot', 'Not available')

        return data

    except Exception as e:
        logging.error(f"Error parsing IOS/IOS-XE stack switch: {e}")
        return {}

# ← ADDED: Helper function to check if it's a stack
def is_stack_switch(content):
    """Check if the content represents a stack switch"""
    try:
        return stack_size(content) > 1
    except Exception as e:
        logging.error(f"Error in is_stack_switch: {str(e)}")
        return False

if __name__ == "__main__":
    file_name = r""
    if file_name:  # ← ADDED: Check if filename is provided
        with open(file_name) as file:
            content = file.read()
        
        # Call the function directly
        result = parse_IOS_Stack_Switch(content)
        print("Parse result:", result)
        
        # You can also call individual functions
        print("Serial Number:", serial_number(content))
        print("Model Number:", model_number(content))
        print("Uptime:", uptime(content))
        print("Stack Size:", stack_size(content))
        print("Is Stack:", is_stack_switch(content))
    else:
        print("Please provide a file path in the file_name variable")