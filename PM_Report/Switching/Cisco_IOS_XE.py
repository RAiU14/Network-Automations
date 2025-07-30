import re
import os
from IOS_XE_Stack_Switch import *

def get_hostname(log_data):
    try:
        match = re.search(r"hostname\s+(\S+)", log_data)
        return match.group(1) if match else "NA"
    except Exception as e:
        return f"Error in get_hostname: {str(e)}"

def get_model_number(log_data):
    try:
        match = re.search(r"Model Number\s+:\s+(\S+)", log_data)
        return match.group(1) if match else "NA"
    except Exception as e:
        return f"Error in get_model_number: {str(e)}"

def get_ip_address(file_path):
    try:
        file_name = os.path.basename(file_path)
        match = re.search(r"_(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\.(txt|log)", file_name)
        return [file_name, match.group(1) if match else "NA"]
    except Exception as e:
        return [f"Error in get_ip_address: {str(e)}", "NA"]

def get_serial_number(log_data):
    try:
        match = re.search(r"System Serial Number\s+:\s+(\S+)", log_data)
        return match.group(1) if match else "NA"
    except Exception as e:
        return f"Error in get_serial_number: {str(e)}"

def get_uptime(log_data):
    try:
        match = re.search(r"uptime is\s+(.+)", log_data)
        return match.group(1) if match else "NA"
    except Exception as e:
        return f"Error in get_uptime: {str(e)}"

def get_current_sw_version(log_data):
    try:
        match = re.search(r"Cisco IOS XE Software, Version\s+([\d.]+)", log_data)
        return match.group(1) if match else "NA"
    except Exception as e:
        return f"Error in get_current_sw_version: {str(e)}"

def get_last_reboot_reason(log_data):
    try:
        match = re.search(r"Last reload reason:\s+(.+)", log_data)
        return match.group(1) if match else "NA"
    except Exception as e:
        return f"Error in get_last_reboot_reason: {str(e)}"

def get_cpu_utilization(log_data):
    try:
        match = re.search(r"five minutes:\s+(\d+)%", log_data)
        return match.group(1) + "%" if match else "NA"
    except Exception as e:
        return f"Error in get_cpu_utilization: {str(e)}"

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
        if not start_point:
            return False

        next_start_end_point = re.search(r"Switch\s+(\S+)", req_data[start_point.span()[1]:])
        if not next_start_end_point:
            return False
        else:
            stack_switch_data = Stack_Check()
            return stack_switch_data.parse_ios_xe_stack_switch(log_data)
    except Exception as e:
        return f"Error in check_stack: {str(e)}"

def get_memory_info(log_data):
    try:
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
    except Exception as e:
        return f"Error in get_memory_info: {str(e)}"

def get_flash_info(log_data):
    try:
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
                            flash_information[flash_number[0]] = [total, free, used, utilization]
                        else:
                            total = available_bytes + used_bytes
                            free = available_bytes
                            used = total - free
                            utilization = (used / total) * 100
                            flash_information['1'] = [total, free, used, utilization]
            return flash_information
        else:
            return "No flash information found"
    except Exception as e:
        return f"Error in get_flash_info: {str(e)}"

def get_fan_status(log_data):
    try:
        switches = log_data.split("Sensor List: Environmental Monitoring")[1:]
        fan_status = {}
        for i, switch in enumerate(switches, start=1):
            match = re.search(r'Switch FAN Speed State Airflow direction.*?(?=SW  PID)', switch, re.DOTALL)
            if match:
                fan_section = match.group(0)
                fans = re.findall(r'\d+\s+\d+\s+(OK|[^O][^K])', fan_section)
                status = 'OK' if all(fan == 'OK' for fan in fans) else 'Not OK'
                fan_status[f'Switch {i}'] = status
        return fan_status
    except Exception as e:
        return f"Error in get_fan_status: {str(e)}"

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
        return f"Error in get_temperature_status: {str(e)}"

def get_power_supply_status(log_data):
    try:
        results = []
        sensor_list_starts = [m.start() for m in re.finditer(r"Sensor List: Environmental Monitoring", log_data)]
        if not sensor_list_starts:
            return ["NA: No sensor list found"]

        for i, start_index in enumerate(sensor_list_starts):
            switch_block_start = start_index
            switch_block_end = len(log_data)
            if i + 1 < len(sensor_list_starts):
                switch_block_end = sensor_list_starts[i+1]

            current_switch_data = log_data[switch_block_start:switch_block_end]

            switch_number = i + 1
            alarm_status = "OK"

            sensor_section_match = re.search(r'Sensor List: Environmental Monitoring\s*([\s\S]*?)(?:Switch FAN Speed State Airflow direction|SW\s+PID|$)', current_switch_data, re.DOTALL)
            if sensor_section_match:
                sensor_lines = sensor_section_match.group(1).strip().split('\n')
                for line in sensor_lines:
                    if re.search(r'\s+FAULTY\s+', line):
                        alarm_status = "Not OK"
                        break

            if alarm_status == "OK":
                psu_pid_section_match = re.search(r'SW\s+PID.*?(---\s*|$)', current_switch_data, re.DOTALL)
                if psu_pid_section_match:
                    psu_pid_section = psu_pid_section_match.group(0)
                    if re.search(r'No Input Power|Bad', psu_pid_section):
                        alarm_status = "ALARM"

            results.append(f"Switch {switch_number}: {alarm_status}")

        return results
    except Exception as e:
        return [f"Error in get_power_supply_status: {str(e)}"]

def get_debug_status(log_data):
    try:
        match = re.search(r"sh|show\w*\s*de\w*", log_data, re.IGNORECASE)
        if match:
            hostname = get_hostname(log_data)
            debug_section_match = re.search(rf"Ip Address\s+Port\s*-+\|----------\s*([\s\S]*?)\n{hostname}#", log_data[match.end():], re.IGNORECASE)
            if debug_section_match and debug_section_match.group(1).strip():
                return "Require Manual Check."
            else:
                return "Command not found."
        else:
            return "Command not found in logs."
    except Exception as e:
        return f"Error in get_debug_status: {str(e)}"

def get_available_ports(log_data):
    try:
        start_marker = "------------------ show interfaces status ------------------"
        end_marker_pattern = r"(?:\n-{20,}\s*show\s+|$)"

        match = re.search(f"{re.escape(start_marker)}(.*?){end_marker_pattern}", log_data, re.DOTALL | re.IGNORECASE)

        if match:
            interface_status_output = match.group(1)
            lines = interface_status_output.strip().splitlines()

            if lines and "Port" in lines[0] and "Status" in lines[0]:
                lines = lines[1:]

            switch_available_ports = {}

            for line in lines:
                line_match = re.match(r'^(Gi|Ap|Te(\d+)/\S+)\s+.*?(\bconnected|\bnotconnect|\berr-disabled)\s+(\S+)\s+.*$', line)

                if line_match:
                    switch_number = int(line_match.group(2))
                    status = line_match.group(3).lower()
                    vlan = line_match.group(4)

                    if status == "notconnect" and vlan == "1":
                        if switch_number not in switch_available_ports:
                            switch_available_ports[switch_number] = 0
                        switch_available_ports[switch_number] += 1

            max_switch_number = max(switch_available_ports.keys(), default=0)
            result = [switch_available_ports.get(i, 0) for i in range(1, max_switch_number + 1)]
            if result == []:
                return 0
            else:
                return result
        else:
            return ["NA: 'show interfaces status' section not found."] * get_stack_size(log_data)
    except Exception as e:
        return [f"Error in get_available_ports: {str(e)}"] * get_stack_size(log_data)

def get_half_duplex_ports(log_data):
    try:
        match = re.findall(r"^(\S+).*a-half.*$", log_data, re.IGNORECASE | re.MULTILINE)
        switch_interfaces = {}
        for interface in match:
            switch_number = re.search(r'\D+(\d+)/', interface).group(1)
            if switch_number not in switch_interfaces:
                switch_interfaces[switch_number] = []
            switch_interfaces[switch_number].append(interface)
        max_switch_number = max(map(int, switch_interfaces.keys()), default=0)
        half_duplex_ports_per_switch = [len(switch_interfaces.get(str(i), [])) for i in range(1, max_switch_number + 1)]
        return half_duplex_ports_per_switch
    except Exception as e:
        return [str(e)] * get_stack_size(log_data)

def get_interface_remark(log_data):
    try:
        match = re.findall(r"^(\S+).*a-half.*$", log_data, re.IGNORECASE | re.MULTILINE)
        switch_interfaces = {}
        for interface in match:
            switch_number = re.search(r'\D+(\d+)/', interface).group(1)
            if switch_number not in switch_interfaces:
                switch_interfaces[switch_number] = []
            switch_interfaces[switch_number].append(interface)
        max_switch_number = max(map(int, switch_interfaces.keys()), default=0)
        interface_remark = [switch_interfaces.get(str(i), []) for i in range(1, max_switch_number + 1)]
        return interface_remark
    except Exception as e:
        return [[f"Error in get_interface_remark: {str(e)}"]] * get_stack_size(log_data)

def get_stack_size(log_data):
    try:
        stack_check = Stack_Check()
        return stack_check.stack_size(log_data)
    except Exception as e:
        return 0
    
def get_critical_logs(log_data):
    try:
        match = re.search(r'(sh|show)\s+(log|logging)\s*-+\n(.*?)(?=\n-+\s*show|\Z)', log_data, re.DOTALL | re.IGNORECASE)
        if match:
            logging_section = match.group(1)
            # Check for -0-, -1-, or -2-
            if any(f"-{i}-" in logging_section for i in range(3)):
                return "YES"
            else:
                return "NO"
        else:
            return "No logging section found!"
    except Exception as e:
        print(f"Error Occurred while parsing logs!\n{e}")
        return False

def print_data(data):
    try:
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            else:
                print(f"{key}: {value}")
        print("\n")
    except Exception as e:
        print(f"Error in print_data: {str(e)}")

def process_file(file_path):
    try:
        with open(file_path, 'r') as file:
            log_data = file.read()
        data = {}
        stack = check_stack(log_data)
        if not stack:
            data = {
                "Filename": [get_ip_address(file_path)[0]],
                "Hostname": [get_hostname(log_data)],
                "Model number": [get_model_number(log_data)],
                "Serial number": [get_serial_number(log_data)],
                "Ip address" : [get_ip_address(file_path)[1]],
                "Uptime": [get_uptime(log_data)],
                "Current s/w version": [get_current_sw_version(log_data)],
                "Last Reboot Reason": [get_last_reboot_reason(log_data)],
                "Debug Status": [get_debug_status(log_data)],
                "CPU Utilization": [get_cpu_utilization(log_data)],
                "Memory": [get_memory_info(log_data)],
                "Flash": [get_flash_info(log_data)],
                "Fan status": [get_fan_status(log_data)],
                "Temperature status": [get_temperature_status(log_data)],
                "PowerSupply status": [get_power_supply_status(log_data)],
                "Available Free Ports" : get_available_ports(log_data),
                "Half Duplex Ports" : get_half_duplex_ports(log_data),
                "Interface/Module Remark" : get_interface_remark,
                "Any debug" : [get_debug_status(log_data)],
                "Critical Logs": [get_critical_logs(log_data)], 
                "Config Status": None, 
                "Config Date": None
            }
        else:
            data = {}
            file_name, hostname, model_number, serial_number, ip_address, uptime = [], [], [], [], [], []
            current_sw, last_reboot, cpu, memo, flash, critical = [], [], [], [], [], []
            avail_free, duplex, interface_remark, config_status, config_data = [], [], [], [], []
            stack_switch = Stack_Check()
            stack_size = stack_switch.stack_size(log_data)
            stack_switch_data = stack_switch.parse_ios_xe_stack_switch(log_data)
            flash_memory_details = get_flash_info(log_data)
            for item in range(stack_size):
                if item == 0:
                    file_name.append(get_ip_address(file_path)[0])
                    model_number.append(get_model_number(log_data))
                    serial_number.append(get_serial_number(log_data))
                    uptime.append(get_uptime(log_data))
                    last_reboot.append(get_last_reboot_reason(log_data))
                    flash.append(flash_memory_details['1'])

                else:
                    file_name.append(get_ip_address(file_path)[0] + (f"_Stack_{str(item+1)}"))
                    model_number.append(stack_switch_data[f'stack switch {item + 1} Model_Number'])
                    serial_number.append(stack_switch_data[f'stack switch {item + 1} Serial_Number'])
                    uptime.append(stack_switch_data[f'stack switch {item + 1} Uptime'])
                    last_reboot.append(stack_switch_data[f'stack switch {item + 1} Last Reboot'])
                    if flash_memory_details[str(item)]:
                        flash.append(flash_memory_details[str(item)])
                
                
                hostname.append(get_hostname(log_data))
                ip_address.append(get_ip_address(file_path)[1])
                current_sw.append(get_current_sw_version(log_data))
                cpu.append(get_cpu_utilization(log_data))
                memo.append(get_memory_info(log_data))
                fan = get_fan_status(log_data)
                temp = get_temperature_status(log_data)
                psu = get_power_supply_status(log_data)
                critical.append(get_critical_logs(log_data))
                avail_free.append(get_available_ports(log_data))
                duplex.append(get_half_duplex_ports(log_data))
                interface_remark.append(get_interface_remark(log_data))
                
            data["Filename"] = file_name
            data["Hostname"] = hostname
            data["Model Number"] = model_number
            data["IP Address"] = ip_address
            data["Uptime"] = uptime
            data["Current S/W Version"] = current_sw
            data["Uptime"] = uptime
            data["Last Reboot Reason"] = last_reboot
            data["CPU"] = cpu
            data["Memory"] = memo
            data["flash"] = flash
            data["Fan Status"] = fan
            data["Temperature Status"] = temp
            data["PSU Status"] = psu
            data["Critial Logs"] = critical
            data["Available Free Ports"] = avail_free
            data["Any Half Duplex"] = duplex
            data["Interface/Module Remark"] = interface_remark
            print_data(data)
            
        return data
    except Exception as e:
        print(f"Error in process_file: {str(e)}")

def process_directory(directory_path):
    try:
        for filename in os.listdir(directory_path):
            if filename.endswith('.txt') or filename.endswith('.log'):
                file_path = os.path.join(directory_path, filename)
                process_file(file_path)
            else:
                print("No Valid Log Files")
    except Exception as e:
        print(f"Error in process_directory: {str(e)}")

def main():
    try:
        # file_path = r"C:\Users\shivanarayan.v\Downloads\UOBM-C9200-AST-OA-03_10.58.40.12.txt"
        file_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR135977300\PROD28FLOORSW01_172.16.3.28.txt"
        # file_path = r"C:\Users\shivanarayan.v\Downloads\UOBM-C9200-JOT-L01-01_10.31.99.100.txt"
        process_file(file_path)
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()