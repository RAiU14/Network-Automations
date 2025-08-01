import re
import logging
import os
import datetime

log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir,  f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


class Stack_Check:
    def __init__(self, log_data=None):
        self.log_data = log_data

    def serial_number(self, data=None):
        target = data if data is not None else self.log_data
        match = re.search(r"System Serial Number\s+:\s+(\S+)", target)
        return match.group(1) if match else None

    def model_number(self, data=None):
        target = data if data is not None else self.log_data
        match = re.search(r"Model Number\s+:\s+(\S+)", target)
        return match.group(1) if match else None
    
    def get_last_reboot_reason(self, data=None):
        target = data if data is not None else self.log_data
        match = re.search(r"Last reload reason\s+:\(.+)", target)
        return match.group(1) if match else "NA"

    def uptime(self, data=None):
        target = data if data is not None else self.log_data
        match = re.search(r"uptime \s+(.+)", target)
        return match.group(1).strip() if match else None

    def parse_ios_xe_stack_switch(self, content):
        try:
            data = {}
            cleared_data_start = re.search('show version', content, re.IGNORECASE)
            if not cleared_data_start:
                print("Missing 'show version' section")
                return False

            cleared_data_end = re.search('show', content[cleared_data_start.span()[1] + 1:], re.IGNORECASE)
            if not cleared_data_end:
                req_data = content[cleared_data_start.span()[1]:]
            else:
                req_data = content[cleared_data_start.span()[1]:cleared_data_start.span()[1] + cleared_data_end.span()[0]]

            start_point = re.search(r"System Serial Number\s+:\s+(\S+)", req_data)
            if not start_point:
                print("Missing 'System Serial Number' in show version")
                return False

            next_start_end_point = re.search(r"Switch\s+(\S+)", req_data[start_point.span()[1]:])
            if not next_start_end_point:
                print("No 'Switch' found after System Serial Number")
                return False

            end_point = re.search(r"Switch\s+(\S+)", req_data[start_point.span()[1] + next_start_end_point.span()[1] + 1:])
            if not end_point:
                print("No second 'Switch' found after first Switch")
                return False

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
                        if self.serial_number(item) or self.model_number(item) or self.uptime(item) or self.get_last_reboot_reason(item):
                            data[f'stack switch {switch_number} Serial_Number'] = self.serial_number(item)
                            data[f'stack switch {switch_number} Model_Number'] = self.model_number(item)
                            data[f'stack switch {switch_number} Uptime'] = self.uptime(item)
                            data[f'stack switch {switch_number} Last Reboot'] = self.get_last_reboot_reason(item)
                            switch_number += 1
                return data
            else:
                return False
        except Exception as e:
            print(f"Error parsing IOS XE stack switch: {e}")
            return None

if __name__ == "__main__":
    file_name = r""
    with open(file_name) as file:
        content = file.read()
    # You can optionally pass `log_data` as None if not used directly
    stack_check = Stack_Check()
    result = stack_check.parse_ios_xe_stack_switch(content)
    print(result)
