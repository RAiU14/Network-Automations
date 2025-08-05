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
logging.basicConfig(filename=os.path.join(log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def log_type(log_data):
    if not isinstance(log_data, str):
        logging.error("Invalid input type for log_data")
        return f"Not a .txt or.log file"

def get_hostname(log_data):
    try:
        logging.info("Starting hostname search.")
        match = re.search(r"hostname\s+(\S+)", log_data)
        logging.debug("Category Search Completed.")
        return match.group(1) if match else NA
    except Exception as e:
        logging.debug("Category Search failed - hostname not found in log.")
        return f"Error in get_hostname: {str(e)}"

def get_model_number(log_data):
    try:
        logging.info("Starting model number search.")
        match = re.search(r"Model Number\s+:\s+(\S+)", log_data)
        logging.debug("Model number search completed.")
        return match.group(1) if match else NA
    except Exception as e:
        logging.error(f"Error in get_model_number: {str(e)}")
        return f"Error in get_model_number: {str(e)}"

def get_ip_address(file_path):
    try:
        logging.info("Starting IP address extraction from file path.")
        file_name = os.path.basename(file_path)
        match = re.search(r"_(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\.(txt|log)", file_name)
        logging.debug("IP address extraction completed.")
        return [file_name, match.group(1) if match else "Check manually"]
    except Exception as e:
        logging.error(f"Error in get_ip_address: {str(e)}")
        return [f"Error in get_ip_address: {str(e)}", NA]

def get_serial_number(log_data):
    try:
        logging.info("Starting serial number search.")
        match = re.search(r"System Serial Number\s+:\s+(\S+)", log_data)
        logging.debug("Serial number search completed.")
        return match.group(1) if match else "Not available"
    except Exception as e:
        logging.error(f"Error in get_serial_number: {str(e)}")
        return f"Error in get_serial_number: {str(e)}"

def get_uptime(log_data):
    try:
        logging.info("Starting uptime search.")
        match = re.search(r"uptime is\s+(.+)", log_data)
        logging.debug("Uptime search completed.")
        return match.group(1) if match else "Not available"
    except Exception as e:
        logging.error(f"Error in get_uptime: {str(e)}")
        return f"Error in get_uptime: {str(e)}"

def get_current_sw_version(log_data):
    try:
        logging.info("Starting current software version search.")
        match = re.search(r"Cisco IOS XE Software, Version\s+([\d.]+)", log_data)
        logging.debug("Current software version search completed.")
        return match.group(1) if match else False
    except Exception as e:
        logging.error(f"Error in get_current_sw_version: {str(e)}")
        return False

def get_last_reboot_reason(log_data):
    try:
        logging.info("Starting last reboot reason search.")
        match = re.search(r"Last reload reason:\s+(.+)", log_data)
        logging.debug("Last reboot reason search completed.")
        return match.group(1) if match else "Not available"
    except Exception as e:
        logging.error(f"Error in get_last_reboot_reason: {str(e)}")
        return f"Error in get_last_reboot_reason: {str(e)}"

def get_cpu_utilization(log_data):
    try:
        logging.info("Starting CPU utilization search.")
        match = re.search(r"five minutes:\s+(\d+)%", log_data)
        logging.debug("CPU utilization search completed.")
        return match.group(1) + "%" if match else "Not available"
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
    try:
        logging.info("Starting memory info extraction.")
        match = re.search(r"Processor\s+\S+\s+(\d+)\s+(\d+)\s+(\d+)", log_data)
        if match:
            total = int(match.group(1))
            used = int(match.group(2))
            free = int(match.group(3))
            if total == 0:
                logging.error("Total memory is zero, cannot calculate utilization")
                return ["Not available", "Not available", "Not available", "Not available"]
            utilization = (used / total) * 100
            logging.debug("Memory info extraction completed.")
            return [total, used, free, f"{utilization:.2f}%"]
        logging.debug("No memory info found in log data.")
        return ["Not available", "Not available", "Not available", "Not available"]
    except Exception as e:
        logging.error(f"Error in get_memory_info: {str(e)}")
        return f"Error in get_memory_info: {str(e)}"

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
    try:
        logging.info("Starting fan status extraction.")
        version = get_current_sw_version(log_data)
        status = []
        
        if version.startswith('17'):
            switches = log_data.split("Sensor List: Environmental Monitoring")[1:]
            if not switches:
                logging.debug("No fan status information found in log data.")
                return ["Not available"]
            for i, switch in enumerate(switches, start=1):
                match = re.search(r'Switch FAN Speed State Airflow direction.*?(?=SW  PID)', switch, re.DOTALL)
                if match:
                    fan_section = match.group(0)
                    fans = re.findall(r'\d+\s+\d+\s+(OK|[^O][^K])', fan_section)
                    status.append('OK' if all(fan == 'OK' for fan in fans) else 'Not OK')
        elif version.startswith('16'):
            fan_statuses = re.findall(r'Switch (\d+) FAN \d+ is (OK|NOT OK|Faulty|Check)', log_data, re.IGNORECASE)
            if fan_statuses:
                switch_statuses = {}
                for switch, fan_status in fan_statuses:
                    if switch not in switch_statuses:
                        switch_statuses[switch] = []
                    switch_statuses[switch].append(fan_status.upper())
                for switch in sorted(switch_statuses.keys(), key=int):
                    if all(fan_status == 'OK' for fan_status in switch_statuses[switch]):
                        status.append(['OK'])
                    else:
                        non_ok_statuses = [fan_status for fan_status in switch_statuses[switch] if fan_status != 'OK']
                        if non_ok_statuses:
                            status.append([non_ok_statuses[0]])
                        else:
                            status.append(['Not OK'])
        else:
            logging.error("Unsupported version")
            return ["Unsupported version"]
        
        logging.debug("Fan status extraction completed.")
        return status if status else ["Not available"]
    except Exception as e:
        logging.error(f"Error in get_fan_status: {str(e)}")
        return f"Error in get_fan_status: {str(e)}"

def get_temperature_status(log_data):
    try:
        version = get_current_sw_version(log_data)
        logging.info("Starting temperature status extraction.")
        if version.startswith('17'):
            temperature_status = re.findall(r'SYSTEM (INLET|OUTLET|HOTSPOT)\s+(\d+)\s+(\w+)', log_data)
            if not temperature_status:
                logging.debug("No temperature status information found in log data.")
                return ["Not available"]
            switch_temps = {}
            for temp in temperature_status:
                switch = temp[1]
                if switch not in switch_temps:
                    switch_temps[switch] = []
                switch_temps[switch].append(temp[2])
            result = []
            for switch, temps in switch_temps.items():
                result.append('OK' if all(temp.upper() == 'GREEN' for temp in temps) else 'Not OK')
            logging.debug("Temperature status extraction completed.")
            return result if result else ["Not available"]
        elif version.startswith('16'):
            temperature_status = re.findall(r'Switch (\d+): SYSTEM TEMPERATURE is (.+)', log_data)
            if not temperature_status:
                logging.debug("No temperature status information found in log data.")
                return ["Not available"]
            result = []
            for temp in temperature_status:
                result.append('OK' if temp[1].strip().upper() == 'OK' else 'NOT OK')
            logging.debug("Temperature status extraction completed.")
            return result if result else ["Not available"]
        else:
            logging.error("Unsupported version")
            return ["Unsupported version"]
    except Exception as e:
        logging.error(f"Error in get_temperature_status: {str(e)}")
        return f"Error in get_temperature_status: {str(e)}"

def get_power_supply_status(log_data):
    try:
        version = get_current_sw_version(log_data)
        logging.info("Starting power supply status extraction.")
        results = []
        if version.startswith('17'):
            sensor_list_starts = [m.start() for m in re.finditer(r"Sensor List: Environmental Monitoring", log_data)]
            if not sensor_list_starts:
                logging.debug("No sensor list found in log data.")
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
                results.append(alarm_status)
        elif version.startswith('16'):
            results = {}
            lines = log_data.strip().split('\n')
            pdu_line_pattern = re.compile(r'^\s*(\d+)[AB]\s+')
            
            pdu_section_header = re.compile(r'SW\s+PID\s+.*Serial#\s+.*Status')
            
            pdu_lines_start_index = -1
            for i, line in enumerate(lines):
                if pdu_section_header.search(line):
                    pdu_lines_start_index = i + 2 # Header line + separator line
                    break

            if pdu_lines_start_index != -1:
                for line in lines[pdu_lines_start_index:]:
                    if not line.strip() or '------------------' in line:
                        break
                    
                    if pdu_line_pattern.match(line):
                        parts = line.strip().split()
                        
                        try:
                            switch_number = int(parts[0][:-1])
                        except (ValueError, IndexError):
                            continue
                        
                        status = "UNKNOWN"
                        
                        if "Not Present" in line:
                            status = "Not Present"
                        elif len(parts) > 3:
                            status = parts[3].strip()

                        if switch_number not in results:
                            results[switch_number] = []
                        
                        is_ok = (status == "OK" or status == "Not Present")
                        results[switch_number].append(is_ok)

            final_statuses = []
            if results:
                sorted_switch_numbers = sorted(results.keys())
                for switch_num in sorted_switch_numbers:
                    if len(results.get(switch_num, [])) == 2 and all(results.get(switch_num, [])):
                        final_statuses.append("OK")
                    else:
                        final_statuses.append("NOT OK")
            
            return final_statuses if final_statuses else ["Not available"]
        logging.debug("Power supply status extraction completed.")
        return results if results else ["Not available"]
    except Exception as e:
        logging.error(f"Error in get_power_supply_status: {str(e)}")
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
            debug_section_match = re.search(rf"Ip Address\s+Port\s*-+\|----------\s*([\s\S]*?)\n{hostname}#", log_data[match.end():], re.IGNORECASE)
            if debug_section_match and debug_section_match.group(1).strip():
                logging.debug("Debug status extraction completed.")
                return "Require Manual Check."
            else:
                logging.debug("No debug section found in log data.")
                return "Command not found."
        else:
            logging.debug("No debug command found in log data.")
            return "Command not found in logs."
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
                if 'notconnect' in parts and '1' in parts:
                    try:
                        interface = parts[0]
                        switch_number = int(interface.split('/')[0].replace('Gi', '').replace('Te', '').replace('Ap', '').replace('Po', ''))
                        if switch_number not in ports:
                            ports[switch_number] = []
                        ports[switch_number].append(interface)
                    except (ValueError, IndexError):
                        continue
            port_list = [ports.get(i, []) for i in range(1, max(ports.keys()) + 1 if ports else 1)]
            count = sum(len(port) for port in port_list)
            if count:
                logging.debug("Available ports extraction completed.")
                return [[len(port)] for port in port_list]
            else:
                logging.debug("No available ports found in log data.")
                return [[0]]
        else:
            logging.debug("No available ports section found in log data.")
            return [[0]]
    except Exception as e:
        logging.error(f"Error in get_available_ports: {str(e)}")
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
            half_duplex_ports_per_switch = [[len(switch_interfaces.get(str(i), []))] for i in range(1, max_switch_number + 1)]
            logging.debug("Half duplex ports extraction completed.")
            return half_duplex_ports_per_switch
        else:
            logging.debug("No half duplex ports found in log data.")
            return [["NO"]] * current_stack_size  
    except Exception as e:
        logging.error(f"Error in get_half_duplex_ports: {str(e)}")
        return [["Error"]] * current_stack_size

def get_interface_remark(log_data):
    try:
        logging.info("Starting interface remark extraction.")
        current_stack_size = IOS_XE_Stack_Switch.stack_size(log_data)  
        match = re.findall(r"^(\S+).*a-half.*$", log_data, re.IGNORECASE | re.MULTILINE)
        if match:
            switch_interfaces = {}
            for interface in match:
                switch_number = re.search(r'\D+(\d+)/', interface).group(1)
                if switch_number not in switch_interfaces:
                    switch_interfaces[switch_number] = []
                switch_interfaces[switch_number].append(interface)
            max_switch_number = max(map(int, switch_interfaces.keys()), default=0)
            interface_remark = [switch_interfaces.get(str(i), []) for i in range(1, max_switch_number + 1)]
            interface_remark = [sublist if sublist else ['Not avialable'] for sublist in interface_remark]
            logging.debug("Interface remark extraction completed.")
            return interface_remark
        else:
            logging.debug("No interface remark found in log data.")
            return ["Not available"] * current_stack_size  
    except Exception as e:
        logging.error(f"Error in get_interface_remark: {str(e)}")
        return [[f"Error in get_interface_remark: {str(e)}"]] * current_stack_size  

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
    data = []
    try:
        logging.info(f"Starting directory processing: {directory_path}")
        for filename in os.listdir(directory_path):
            if filename.endswith('.txt') or filename.endswith('.log'):
                file_path = os.path.join(directory_path, filename)
                with open(file_path) as file:
                    log_data = file.read()
                ios_xe = ios_xe_check(log_data)
                if ios_xe:
                    logging.debug(f"{filename} is IOS XE File. Appending value!")
                    switch_data = process_file(file_path)
                    data.append(switch_data)
                else:
                    logging.debug(f"{filename} was not IOS XE. Discarding!")
            else:
                logging.debug(f"Skipping non-log file: {filename}")
        logging.debug("Data Extracted Successfully!")
        return data 
    except Exception as e:
        logging.error(f"Error in process_directory: {str(e)}")
        return 500

def main():
    try:
        file_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR135977300\DRC01CORESW01_10.20.253.5.txt"
        directory_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR137436091\9200"
        # pp.pprint(process_file(file_path))
        pp.pprint(process_directory(directory_path))
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()