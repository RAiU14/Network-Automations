import re
import os
import logging
import pprint as pp
from IOS_XE_Stack_Switch import *

log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir,  f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


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
        return [file_name, match.group(1) if match else "Check manually"]
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
        return match.group(1) if match else False
    except Exception as e:
        logging.error(f"Error in get_current_sw_version: {str(e)}")
        return False

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
            return [
                total,
                used,
                free,
                f"{utilization:.2f}%"
            ]
        return [
            "NA",
            "NA",
            "NA",
            "NA"
        ]
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
                            flash_information[flash_number[0]] = [total, used, free, utilization]
                        else:
                            total = available_bytes + used_bytes
                            free = available_bytes
                            used = total - free
                            utilization = (used / total) * 100
                            flash_information['1'] = [total, used, free, utilization]
            return flash_information
        else:
            return "No flash information found"
    except Exception as e:
        return f"Error in get_flash_info: {str(e)}"

def get_fan_status(log_data):
    try:
        switches = log_data.split("Sensor List: Environmental Monitoring")[1:]
        status = []
        for i, switch in enumerate(switches, start=1):
            match = re.search(r'Switch FAN Speed State Airflow direction.*?(?=SW  PID)', switch, re.DOTALL)
            if match:
                fan_section = match.group(0)
                fans = re.findall(r'\d+\s+\d+\s+(OK|[^O][^K])', fan_section)
                status.append('OK' if all(fan == 'OK' for fan in fans) else 'Not OK')
                # fan_status[f'Switch {i}'] = status
        return status
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
            result.append('OK' if all(temp.upper() == 'GREEN' for temp in temps) else 'Not OK')
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
            results.append(alarm_status)

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
        end_marker = "------------------ show "
        
        match = re.search(f"{re.escape(start_marker)}(.*?){re.escape(end_marker)}", log_data, re.DOTALL)
        if match:
            section = match.group(1)
            ports = {}
            for line in section.strip().splitlines()[1:]:  # Skip the header line
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
                return [[len(port)] for port in port_list]
            else:
                return 0
    except Exception as e:
        return [[str(e)]]

def get_half_duplex_ports(log_data):
    try:
        stack_switch = Stack_Check(log_data)
        get_stack_size = stack_switch.stack_size(log_data)
        match = re.findall(r"^(\S+).*a-half.*$", log_data, re.IGNORECASE | re.MULTILINE)
        if match:
            switch_interfaces = {}
            for interface in match:
                switch_number = re.search(r'\D+(\d+)/', interface).group(1)
                if switch_number not in switch_interfaces:
                    switch_interfaces[switch_number] = []
                switch_interfaces[switch_number].append(interface)
            max_switch_number = max(map(int, switch_interfaces.keys()), default=0)
            half_duplex_ports_per_switch = [[len(switch_interfaces.get(str(i), []))] for i in range(1, max_switch_number + 1)]
            return half_duplex_ports_per_switch
        else:
            return ["NO"] * get_stack_size
    except Exception as e:
        return [[str(e)]] * get_stack_size

def get_interface_remark(log_data):
    try:
        stack_switch = Stack_Check(log_data)
        get_stack_size = stack_switch.stack_size(log_data)
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
            interface_remark = [sublist if sublist else ['N/A'] for sublist in interface_remark]
            return interface_remark
        else:
            return ["N/A"] * get_stack_size
    except Exception as e:
        return [[f"Error in get_interface_remark: {str(e)}"]] * get_stack_size

def get_nvram_config_update(log_data):
    try:
        match = re.search(r"NVRAM\s+config\s+last\s+updated\s+at\s+(.+)", log_data, re.IGNORECASE)
        if match:
            return ["Yes", match.group(1).strip().split('by')[0].strip()]
        else:
            return ["No", "NA"]
    except Exception as e:
        return [f"Error: {str(e)}", "NA"]
    
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
            memory_info = get_memory_info(log_data)
            flash_info = get_flash_info(log_data)
            if isinstance(flash_info, dict):
                flash_info = flash_info.get('1', ["NA", "NA", "NA", "NA"])
            elif isinstance(flash_info, str):
                flash_info = ["NA", "NA", "NA", "NA"]
            
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
                        "Current SW EOS": ["NA"],
                        "Suggested s/w ver": ["NA"],
                        "s/w release date": ["NA"],
                        "Latest S/W version": ["NA"],
                        "Production s/w is deffered or not?": ["NA"],
                        "End-of-Sale Date: HW": ["NA"],
                        "Last Date of Support: HW": ["NA"],
                        "End of Routine Failure Analysis Date: HW": ["NA"],
                        "End of Vulnerability/Security Support: HW": ["NA"],
                        "End of SW Maintenance Releases Date: HW": ["NA"],
                        "Remark": ["NA"]
                    }
        else:
            data = {}
            file_name, hostname, model_number, serial_number, ip_address, uptime = [], [], [], [], [], []
            current_sw, last_reboot, cpu, memo, flash, critical = [], [], [], [], [], []
            total_memory, used_memory, free_memory, memory_utilization = [], [], [], []
            total_flash, used_flash, free_flash, flash_utilization = [], [], [], []
            avail_free, duplex, interface_remark, config_status, config_date = [], [], [], [], []
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
                    flash = ["NA", "NA", "NA", "NA"]
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
            data["Any Debug?"] = [get_debug_status(log_data) for _ in range(stack_size)]
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
            data["Current SW EOS"] = ["Yet to check"] * stack_size
            data["Suggested s/w ver"] = ["Yet to check"] * stack_size
            data["s/w release date"] = ["Yet to check"] * stack_size
            data["Latest S/W version"] = ["Yet to check"] * stack_size
            data["Production s/w is deffered or not?"] = ["Yet to check"] * stack_size
            data["End-of-Sale Date: HW"] = ["Yet to check"] * stack_size
            data["Last Date of Support: HW"] = ["Yet to check"] * stack_size
            data["End of Routine Failure Analysis Date: HW"] = ["Yet to check"] * stack_size
            data["End of Vulnerability/Security Support: HW"] = ["Yet to check"] * stack_size
            data["End of SW Maintenance Releases Date: HW"] = ["Yet to check"] * stack_size
            data["Remark"] = ["Yet to check"] * stack_size
        return data
    except Exception as e:
        print(f"Error in process_file: {str(e)}")

def ios_xe_check(log_data):
    if get_current_sw_version(log_data): 
        return True
    else:
        return False

def process_directory(directory_path):
    data = []
    try:
        for filename in os.listdir(directory_path):
            if filename.endswith('.txt') or filename.endswith('.log'):
                file_path = os.path.join(directory_path, filename)
                with open(os.path.join(directory_path, filename)) as file:
                    log_data = file.read()
                ios_xe = ios_xe_check(log_data)
                if ios_xe:
                    logging.debug(f"{filename} is IOS XE File. Appending value!")
                    switch_data = process_file(file_path)
                    data.append(switch_data)
                else:
                    logging.debug(f"{filename} was not IOS XE. Discarding!")
            else:
                logging.warning("No Valid Log Files")
        logging.debug("Data Extracted Successfully!")
        return data
    except Exception as e:
        logging.error(f"Error in process_directory: {str(e)}")
        return 500


def main():
    try:
        # file_path = r"C:\Users\shivanarayan.v\Downloads\PROD28FLOORSW01_172.16.3.28 1.txt"
        file_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR137436091\9200\UOBAM-C9300-PLA-L20-DSW-01_10.52.254.5.txt"
        pp.pprint(process_file(file_path))
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()