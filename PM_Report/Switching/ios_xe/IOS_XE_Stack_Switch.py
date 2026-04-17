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

def serial_number(data):
    try:
        match = re.search(r"System Serial Number\s+:\s+(\S+)", data)
        return match.group(1) if match else None
    except Exception as e:
        logging.error(f"Error in serial_number: {str(e)}")
        return None

def model_number(data):
    try:
        match = re.search(r"Model Number\s+:\s+(\S+)", data)
        return match.group(1) if match else None
    except Exception as e:
        logging.error(f"Error in model_number: {str(e)}")
        return None

def get_last_reboot_reason(data):
    try:
        match = re.search(r"Last reload reason\s+:\s+(.+)", data)
        return match.group(1) if match else None
    except Exception as e:
        logging.error(f"Error in get_last_reboot_reason: {str(e)}")
        return None

def uptime(data):
    try:
        match = re.search(r"Switch uptime\s+:\s+(.+)", data)
        return match.group(1).strip() if match else None
    except Exception as e:
        logging.error(f"Error in uptime: {str(e)}")
        return None

def stack_size(content):
    try:
        cleared_data_start = re.search('show version', content, re.IGNORECASE)
        if not cleared_data_start:
            logging.debug("Missing 'show version' section")
            return 1  

        cleared_data_end = re.search('show', content[cleared_data_start.span()[1] + 1:], re.IGNORECASE)
        if not cleared_data_end:
            req_data = content[cleared_data_start.span()[1]:]
        else:
            req_data = content[cleared_data_start.span()[1]:cleared_data_start.span()[1] + cleared_data_end.span()[0]]

        start_point = re.search(r"System Serial Number\s+:\s+(\S+)", req_data)
        if not start_point:
            logging.debug("Missing 'System Serial Number' in show version")
            return 1  

        next_start_end_point = re.search(r"Switch\s+(\S+)", req_data[start_point.span()[1]:])
        if not next_start_end_point:
            logging.debug("No 'Switch' found after System Serial Number - likely single switch")
            return 1  

        end_point = re.search(r"Switch\s+(\S+)", req_data[start_point.span()[1] + next_start_end_point.span()[1] + 1:])
        if not end_point:
            logging.debug("No second 'Switch' found - likely single switch")
            return 1  

        stack_data = req_data[
            start_point.span()[1] + next_start_end_point.span()[1] : start_point.span()[1] + next_start_end_point.span()[1] + end_point.span()[0]
        ]

        total_stack_switches = len(stack_data.strip().splitlines()[2:])
        return max(total_stack_switches, 1)  
    except Exception as e:
        logging.error(f"Error in stack_size: {str(e)}")
        return 1  

def parse_ios_xe_stack_switch(content):
    try:
        data = {}
        cleared_data_start = re.search('show version', content, re.IGNORECASE)
        if not cleared_data_start:
            logging.debug("Missing 'show version' section")
            return {}

        cleared_data_end = re.search('show', content[cleared_data_start.span()[1] + 1:], re.IGNORECASE)
        if not cleared_data_end:
            req_data = content[cleared_data_start.span()[1]:]
        else:
            req_data = content[cleared_data_start.span()[1]:cleared_data_start.span()[1] + cleared_data_end.span()[0]]

        start_point = re.search(r"System Serial Number\s+:\s+(\S+)", req_data)
        if not start_point:
            logging.debug("Missing 'System Serial Number' in show version")
            return {}

        # The subsequent checks for Switch\s+(\S+) are part of the original, complex logic 
        # that we will bypass if the 3850/9000 format is detected.
        next_start_end_point = re.search(r"Switch\s+(\S+)", req_data[start_point.span()[1]:])
        if not next_start_end_point:
            logging.debug("No 'Switch' found after System Serial Number")
            return {}

        end_point = re.search(r"Switch\s+(\S+)", req_data[start_point.span()[1] + next_start_end_point.span()[1] + 1:])
        if not end_point:
            logging.debug("No second 'Switch' found after first Switch")
            return {}

        stack_data = req_data[
            start_point.span()[1] + next_start_end_point.span()[1] :
            start_point.span()[1] + next_start_end_point.span()[1] + end_point.span()[0]
        ]

        total_stack_switches = len(stack_data.strip().splitlines()[2:])
        if total_stack_switches <= 1:
            return {}

        # --- [MOD] Build inventory Switch-N → PID map (prefer Switch 1 on conflict) ---
        inv_hdr = re.search(r"-{5,}\s*show\s+inventory\s*-{5,}", content, re.IGNORECASE)      # [MOD]
        inv_sec = content[inv_hdr.end():] if inv_hdr else ""                                   # [MOD]
        inv_map = {
            int(m.group(1)): m.group(2).strip()
            for m in re.finditer(r'NAME:\s*"Switch\s*(\d+)"[^\n]*\nPID:\s*([^\s,]+)',         # [MOD]
                                 inv_sec, re.IGNORECASE)
        }

        # Original Segmentation Logic (kept for compatibility)
        stack_switch_data = req_data[start_point.span()[1] + next_start_end_point.span()[1] + 1 + end_point.span()[0]:]
        stack_switch_items = re.split(r'(?m)(?=^\s*Switch\s+\d+\b)', stack_switch_data.strip())
        
        # -----------------------------------------------------------------
        # [NEW ENHANCEMENT: IOS XE Explicit Member Block Segmentation]
        # This handles the Catalyst 3850/9000 format where Switch 02, 03, etc. 
        # details are in full, separate blocks after the main switch table.
        # -----------------------------------------------------------------
        
        # Check for the explicit header pattern used by 3850/9000 member blocks
        is_explicit_member_block_format = re.search(r'(?m)^Switch\s+\d{2,}\n-+', req_data)
        
        if is_explicit_member_block_format:
            # 1. Extract Switch 1 (Master) block: everything up to the start of the first explicit member block
            start_of_member_blocks = re.search(r'(?m)^Switch\s+\d{2,}\n-+', req_data)
            
            if start_of_member_blocks:
                # The Master Switch (Switch 1) information is everything up to the first 'Switch 02' block
                master_switch_block = req_data[:start_of_member_blocks.start()].strip()
                
                # Extract all content from the start of the first member block onwards.
                all_member_data = req_data[start_of_member_blocks.start():]
                
                # Robustly find all blocks starting with "Switch XX\n---" up to the next block or end.
                member_blocks = re.findall(r'(?ms)^(Switch\s+\d{2,}\n-+\s*.*?)(?=^Switch\s+\d{2,}\n-+\s*|\Z)', all_member_data.strip())
                
                # 2. Overwrite the original segmentation result with the new, correct list of blocks.
                # Start with the Master Switch (Switch 1) block.
                stack_switch_items = [master_switch_block] + member_blocks
        
        # -----------------------------------------------------------------
        # [END OF ENHANCEMENT]
        # -----------------------------------------------------------------
        
        # Use switch_number = 1 for the enhanced path (where Switch 1 is the first item)
        # Use switch_number = 2 for the original path (where Switch 1 details are assumed to be handled outside)
        switch_number = 1 if is_explicit_member_block_format else 2

        def _sv_model_only(block: str):
            m = re.search(r"Model\s+Number\s*:\s*([^\s\r\n]+)", block, re.IGNORECASE)
            return m.group(1) if m else None

        for item in stack_switch_items:
            if len(item) > 1:
                sv_mod = _sv_model_only(item)
                chosen_model = sv_mod

                # --- [MOD] Prefer inventory PID for this switch when available ---
                if switch_number in inv_map:
                    inv_pid = inv_map[switch_number]
                    if sv_mod and sv_mod.strip().upper() != inv_pid.strip().upper():
                        chosen_model = inv_pid
                    elif not sv_mod:
                        chosen_model = inv_pid

                # This is the "business logic" section which remains unchanged
                if serial_number(item) or chosen_model or uptime(item) is not None:
                    data[f'stack switch {switch_number} Serial_Number'] = serial_number(item)
                    data[f'stack switch {switch_number} Model_Number'] = chosen_model
                    data[f'stack switch {switch_number} Uptime'] = uptime(item)
                    data[f'stack switch {switch_number} Last Reboot'] = get_last_reboot_reason(item) or "Not available"

                switch_number += 1

        return data

    except Exception as e:
        logging.error(f"Error parsing IOS XE stack switch: {str(e)}")
        return {}

# ← ADDED: Helper function to check if it's a stack
def is_stack_switch(content):
    try:
        return stack_size(content) > 1
    except Exception as e:
        logging.error(f"Error in is_stack_switch: {str(e)}")
        return False
