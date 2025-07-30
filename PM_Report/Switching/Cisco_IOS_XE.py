import re
import os
from IOS_XE_Stack_Switch import *

def get_hostname(log_data):
    match = re.search(r"hostname\s+(\S+)", log_data)
    return match.group(1) if match else "NA"

def get_model_number(log_data):
    match = re.search(r"Model Number\s+:\s+(\S+)", log_data)
    return match.group(1) if match else "NA"

def get_ip_address(file_path):
    file_name = os.path.basename(file_path)
    match = re.search(r"_(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\.txt", file_name)
    return match.group(1) if match else "NA"

def get_serial_number(log_data):
    match = re.search(r"System Serial Number\s+:\s+(\S+)", log_data)
    return match.group(1) if match else "NA"

def get_uptime(log_data):
    match = re.search(r"uptime is\s+(.+)", log_data)
    return match.group(1) if match else "NA"

def get_current_sw_version(log_data):
    match = re.search(r"Cisco IOS XE Software, Version\s+([\d.]+)", log_data)
    return match.group(1) if match else "NA"

def get_last_reboot_reason(log_data):
    match = re.search(r"Last reload reason:\s+(.+)", log_data)
    return match.group(1) if match else "NA"

def get_cpu_utilization(log_data):
    match = re.search(r"five minutes:\s+(\d+)%", log_data)
    return match.group(1) + "%" if match else "NA"

def check_stack(log_data):
    try:
            cleared_data_start = re.search('show version', log_data, re.IGNORECASE)
            if not cleared_data_start:
                return False

            cleared_data_end = re.search('show', log_data[cleared_data_start.span()[1] + 1:], re.IGNORECASE)
            if not cleared_data_end:
                req_data = log_data[cleared_data_start.span()[1]:]
            else:
                req_data = log_data[cleared_data_start.span()[1]:cleared_data_start.span()[1] + cleared_data_end.span()[0]]

            start_point = re.search(r"System Serial Number\s+:\s+(\S+)", req_data)
            # This is case sensitive, and it will not work for IOS only on IOS XE.
            if not start_point:
                return False

            next_start_end_point = re.search(r"Switch\s+(\S+)", req_data[start_point.span()[1]:])
            if not next_start_end_point:
                return False
            else: 
                stack_switch_data = Stack_Check()
                return stack_switch_data.parse_ios_xe_stack_switch(log_data)
    
    except Exception as e:
        return 405

def get_memory_info(log_data):
    match = re.search(r"Processor\s+\S+\s+(\d+)\s+(\d+)\s+(\d+)", log_data)
    if match:
        total = int(match.group(1))
        used = int(match.group(2))
        free = int(match.group(3))
        utilization = (used / total) * 100
        return {
            "Total memory": total,
            "Used memory": used,
            "Free memory": free,
            "Memory Utilization (%)": f"{utilization:.2f}%"
        }
    return {
        "Total memory": "NA",
        "Used memory": "NA",
        "Free memory": "NA",
        "Memory Utilization (%)": "NA"
    }

def get_flash_info(log_data):
    total_flashes = re.findall(r"show\s+flash(?:-\d+)?:\s*all", log_data)
    flash_information = {}
    if total_flashes:
        for item in total_flashes: 
            start_index = re.search(item, log_data)
            end_index = re.search(r"show\s", log_data[start_index.span()[1]:])
            flash_data = log_data[start_index.span()[1]:start_index.span()[1] + end_index.span()[0]]
            m = re.findall(r'^\s*(\d+)\s+bytes\s+available\s+\((\d+)\s+bytes\s+used\)', flash_data, re.MULTILINE)
            if m:
                for available_str, used_str in m:
                    available_bytes = int(available_str)
                    used_bytes = int(used_str)
                    flash_number = re.findall(r'\d+', item)
                    if flash_number:
                        total = available_bytes + used_bytes
                        free = available_bytes
                        used = total - free 
                        utilization = (used / total) * 100
                        flash_information [flash_number[0]] = [total, free, used, utilization]
                    else:
                        # This is only for 1 switch
                        total = available_bytes + used_bytes
                        free = available_bytes
                        used = total - free 
                        utilization = (used / total) * 100
                        flash_information ['1'] = [total, free, used, utilization]
        return flash_information
    else:
        False


def get_fan_status(log_data):
    return "OK" if re.search(r"\s+\d+\s+\d+\s+OK\s+Front to Back", log_data) else "Not OK"

def get_temperature_status(log_data):
    try:
        temperature_status = re.findall(r'SYSTEM (INLET|OUTLET|HOTSPOT)\s+(\d+)\s+(\w+)', log_data)
        switch_temps = {}
        for temp in temperature_status:
            switch = temp[1]
            if switch not in switch_temps:
                switch_temps[switch] = []
            switch_temps[switch].append(temp[2])
        result = []
        for switch, temps in switch_temps.items():
            result.append(f"Switch {switch} Temperature: {'OK' if all(temp.upper() == 'GREEN' for temp in temps) else 'Not OK'}")
        return result
    except Exception as e:
        return str(e)

def get_power_supply_status(log_data):
    try:
        results = []
        # Split the log data into sections for each switch based on the "Sensor List:" pattern
        # The first split part before the first "Sensor List:" is usually part of the first switch's data
        # We need to handle the initial data block for Switch 1 separately or ensure the split creates clean blocks.

        # Let's find all occurrences of "Sensor List: Environmental Monitoring" to delineate switch blocks
        # and then extract content between them.
        
        # A more robust way: find starting points of each "Sensor List" and extract content until the next one.
        sensor_list_starts = [m.start() for m in re.finditer(r"Sensor List: Environmental Monitoring", log_data)]
        
        # If no "Sensor List" found, return NA or an empty list depending on expected behavior
        if not sensor_list_starts:
            return ["NA: No sensor list found"]

        for i, start_index in enumerate(sensor_list_starts):
            switch_block_start = start_index
            switch_block_end = len(log_data)
            if i + 1 < len(sensor_list_starts):
                switch_block_end = sensor_list_starts[i+1]
            
            current_switch_data = log_data[switch_block_start:switch_block_end]
            
            switch_number = i + 1
            alarm_status = "OK" # Assume OK unless an alarm is found

            # --- Check sensor states in "Sensor List: Environmental Monitoring" section ---
            # Find the "Sensor List" part of the current switch block
            sensor_section_match = re.search(r'Sensor List: Environmental Monitoring\s*([\s\S]*?)(?:Switch FAN Speed State Airflow direction|SW\s+PID|$)', current_switch_data, re.DOTALL)
            if sensor_section_match:
                sensor_lines = sensor_section_match.group(1).strip().split('\n')
                for line in sensor_lines:
                    # Check for "FAULTY" status in any sensor
                    if re.search(r'\s+FAULTY\s+', line):
                        alarm_status = "Not OK"
                        break # Found an alarm, no need to check further sensors for this switch
            
            # If no sensor alarm, check power supply PIDs status
            if alarm_status == "OK":
                psu_pid_section_match = re.search(r'SW\s+PID.*?(---\s*|$)', current_switch_data, re.DOTALL)
                if psu_pid_section_match:
                    psu_pid_section = psu_pid_section_match.group(0)
                    # Check for "No Input Power" or "Bad" status in PSU PIDs
                    if re.search(r'No Input Power|Bad', psu_pid_section):
                        alarm_status = "ALARM"
            
            results.append(f"Switch {switch_number}: {alarm_status}")
            
        return results
    except Exception as e:
        return [f"Error in get_power_supply_status: {str(e)}"]

def get_debug_status(log_data):
    match = re.search(r"sh\w*\s*de\w*", log_data, re.IGNORECASE)
    if match:
        hostname = get_hostname(log_data)
        debug_section_match = re.search(rf"Ip Address\s+Port\s*-+\|----------\s*([\s\S]*?)\n{hostname}#", log_data[match.end():], re.IGNORECASE)
        if debug_section_match and debug_section_match.group(1).strip():
            return "Yes"
        else:
            return "No"
    else:
        return "No"

def get_available_ports(log_data):
    try:
        match = re.search(r"show interfaces status\s*([\s\S]*?)(?=\n-{20,}|\Z)", log_data)
        if match:
            interface_status_output = match.group(1)
            lines = interface_status_output.strip().splitlines()[1:]  # skip header line
            available_ports = 0
            for line in lines:
                columns = line.split()
                if len(columns) > 3:
                    try:
                        vlan = columns[3]
                        status = columns[2].lower()
                        if status == "notconnect" and vlan == "1":
                            available_ports += 1
                    except IndexError:
                        continue
            return available_ports
        else:
            return "NA"
    except Exception as e:
        return str(e)

def get_half_duplex_ports(log_data):
    try:
        match = re.findall(r"^(\S+).*a-half.*$", log_data, re.IGNORECASE | re.MULTILINE)
        return match
    except Exception as e:
        return str(e)

def print_data(data):
    for key, value in data.items():
        if isinstance(value, dict):
            print(f"{key}:")
            for k, v in value.items():
                print(f"  {k}: {v}")
        else:
            print(f"{key}: {value}")
    print("\n")

def process_file(file_path):
    with open(file_path, 'r') as file:
        log_data = file.read()
    data = {
        "Hostname": get_hostname(log_data),
        "Model number": get_model_number(log_data),
        "Serial number": get_serial_number(log_data),
        "Ip address" : get_ip_address(file_path),
        "Uptime": get_uptime(log_data),
        "Current s/w version": get_current_sw_version(log_data),
        "Last Reboot Reason": get_last_reboot_reason(log_data),
        "Debug Status": get_debug_status(log_data),
        "CPU Utilization": get_cpu_utilization(log_data),
        "Memory": get_memory_info(log_data),
        "Flash": get_flash_info(log_data),
        "Fan status": get_fan_status(log_data),
        "Temperature status": get_temperature_status(log_data),
        "PowerSupply status": get_power_supply_status(log_data),
        "Any debug" : get_debug_status(log_data),
        "Available Free Ports" : get_available_ports(log_data),
        "Half Duplex Ports" : get_half_duplex_ports(log_data), 
        "Stack Switch": check_stack(log_data)
    }
    print_data(data)

def process_directory(directory_path):
    for filename in os.listdir(directory_path):
        if filename.endswith('.txt') or filename.endswith('.log'):
            file_path = os.path.join(directory_path, filename)
            process_file(file_path)
        else: 
            return "No Valid Log Files"

def main():
    # file_path = r"C:\Users\shivanarayan.v\Downloads\DRC01CORESW01_10.20.253.5.txt"
    file_path = r"C:\Users\shivanarayan.v\Downloads\PROD029FLOORSW01_172.16.3.29.txt"
    process_file(file_path)

if __name__ == "__main__":
    main()