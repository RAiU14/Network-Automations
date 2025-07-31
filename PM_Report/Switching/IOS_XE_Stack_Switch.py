import re
import logging
import os
import datetime

log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def serial_number(data):
    """Extract serial number from the provided data"""
    match = re.search(r"System Serial Number\s+:\s+(\S+)", data)
    return match.group(1) if match else None

def model_number(data):
    """Extract model number from the provided data"""
    match = re.search(r"Model Number\s+:\s+(\S+)", data)
    return match.group(1) if match else None

def get_last_reboot_reason(data):
    """Extract last reboot reason from the provided data"""
    match = re.search(r"Last reload reason\s+:\s+(.+)", data)
    return match.group(1) if match else None

def uptime(data):
    """Extract uptime from the provided data"""
    match = re.search(r"Switch uptime\s+:\s+(.+)", data)
    return match.group(1).strip() if match else None

def stack_size(content):
    """Calculate stack size from the content"""
    try:
        cleared_data_start = re.search('show version', content, re.IGNORECASE)
        if not cleared_data_start:
            print("Missing 'show version' section")
            return 1  # ← FIXED: Return 1 instead of False for single switch

        cleared_data_end = re.search('show', content[cleared_data_start.span()[1] + 1:], re.IGNORECASE)
        if not cleared_data_end:
            req_data = content[cleared_data_start.span()[1]:]
        else:
            req_data = content[cleared_data_start.span()[1]:cleared_data_start.span()[1] + cleared_data_end.span()[0]]

        start_point = re.search(r"System Serial Number\s+:\s+(\S+)", req_data)
        if not start_point:
            print("Missing 'System Serial Number' in show version")
            return 1  # ← FIXED: Return 1 instead of False

        next_start_end_point = re.search(r"Switch\s+(\S+)", req_data[start_point.span()[1]:])
        if not next_start_end_point:
            print("No 'Switch' found after System Serial Number - likely single switch")
            return 1  # ← FIXED: Return 1 for single switch

        end_point = re.search(r"Switch\s+(\S+)", req_data[start_point.span()[1] + next_start_end_point.span()[1] + 1:])
        if not end_point:
            print("No second 'Switch' found - likely single switch")
            return 1  # ← FIXED: Return 1 for single switch

        stack_data = req_data[
            start_point.span()[1] + next_start_end_point.span()[1] : start_point.span()[1] + next_start_end_point.span()[1] + end_point.span()[0]
        ]

        total_stack_switches = len(stack_data.strip().splitlines()[2:])
        return max(total_stack_switches, 1)  # ← FIXED: Ensure at least 1 is returned
    except Exception as e:
        print(f"Error in stack_size: {e}")
        return 1  # ← FIXED: Return 1 instead of None

def parse_ios_xe_stack_switch(content):
    """Parse IOS XE stack switch information from content"""
    try:
        data = {}
        cleared_data_start = re.search('show version', content, re.IGNORECASE)
        if not cleared_data_start:
            print("Missing 'show version' section")
            return {}  # ← FIXED: Return empty dict instead of False

        cleared_data_end = re.search('show', content[cleared_data_start.span()[1] + 1:], re.IGNORECASE)
        if not cleared_data_end:
            req_data = content[cleared_data_start.span()[1]:]
        else:
            req_data = content[cleared_data_start.span()[1]:cleared_data_start.span()[1] + cleared_data_end.span()[0]]

        start_point = re.search(r"System Serial Number\s+:\s+(\S+)", req_data)
        if not start_point:
            print("Missing 'System Serial Number' in show version")
            return {}  # ← FIXED: Return empty dict instead of False

        next_start_end_point = re.search(r"Switch\s+(\S+)", req_data[start_point.span()[1]:])
        if not next_start_end_point:
            print("No 'Switch' found after System Serial Number")
            return {}  # ← FIXED: Return empty dict instead of False

        end_point = re.search(r"Switch\s+(\S+)", req_data[start_point.span()[1] + next_start_end_point.span()[1] + 1:])
        if not end_point:
            print("No second 'Switch' found after first Switch")
            return {}  # ← FIXED: Return empty dict instead of False

        stack_data = req_data[
            start_point.span()[1] + next_start_end_point.span()[1] : start_point.span()[1] + next_start_end_point.span()[1] + end_point.span()[0]
        ]

        total_stack_switches = len(stack_data.strip().splitlines()[2:])
        if total_stack_switches > 1:
            print("This is a stack switch with multiple switches.")
            stack_switch_data = req_data[start_point.span()[1] + next_start_end_point.span()[1] + end_point.span()[1]:]
            stack_switch_items = re.split(r'-{3,}', stack_switch_data.strip())
            switch_number = 2
            for item in stack_switch_items:
                if len(item) > 1:
                    # Check if any info exists before adding
                    if serial_number(item) or model_number(item) or uptime(item) is not None:
                        data[f'stack switch {switch_number} Serial_Number'] = serial_number(item)
                        data[f'stack switch {switch_number} Model_Number'] = model_number(item)
                        data[f'stack switch {switch_number} Uptime'] = uptime(item)
                        if get_last_reboot_reason(item):
                            data[f'stack switch {switch_number} Last Reboot'] = get_last_reboot_reason(item)
                        else: 
                            data[f'stack switch {switch_number} Last Reboot'] = "N/A"
                        switch_number += 1
            return data
        else:
            return {}  # ← FIXED: Return empty dict instead of False
    except Exception as e:
        print(f"Error parsing IOS XE stack switch: {e}")
        return {}  # ← FIXED: Return empty dict instead of None

# ← ADDED: Helper function to check if it's a stack
def is_stack_switch(content):
    """Check if the content represents a stack switch"""
    return stack_size(content) > 1

if __name__ == "__main__":
    file_name = r""
    if file_name:  # ← ADDED: Check if filename is provided
        with open(file_name) as file:
            content = file.read()
        
        # Call the function directly
        result = parse_ios_xe_stack_switch(content)
        print("Parse result:", result)
        
        # You can also call individual functions
        print("Serial Number:", serial_number(content))
        print("Model Number:", model_number(content))
        print("Uptime:", uptime(content))
        print("Stack Size:", stack_size(content))
        print("Is Stack:", is_stack_switch(content))
    else:
        print("Please provide a file path in the file_name variable")
