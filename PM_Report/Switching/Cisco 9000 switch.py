import re
import os

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
    match = re.search(r"(\d+)\s+(\d+)\s+disk\s+rw\s+flash:", log_data)
    if match:
        total = int(match.group(1))
        free = int(match.group(2))
        used = total - free 
        utilization = (used / total) * 100
        return {
            "Total flash memory": total,
            "Used flash memory": used,
            "Free flash memory": free,
            "Used Flash (%)": f"{utilization:.2f}%"
        }
    return {
        "Total flash memory": "NA",
        "Used flash memory": "NA",
        "Free flash memory": "NA",
        "Used Flash (%)": "NA"
    }

def get_fan_status(log_data):
    return "OK" if re.search(r"\s+\d+\s+\d+\s+OK\s+Front to Back", log_data) else "Not OK"

def get_temperature_status(log_data):
    return "OK" if "GREEN" in log_data else "Not OK"

def get_power_supply_status(log_data):
    return "OK" if re.search(r"\s+PWR-C\d+-\d+KWAC\s+\S+\s+OK", log_data) else "Not OK"

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
        "Half Duplex Ports" : get_half_duplex_ports(log_data)
    }
    print_data(data)

def process_directory(directory_path):
    for filename in os.listdir(directory_path):
        if filename.endswith('.txt'):
            file_path = os.path.join(directory_path, filename)
            process_file(file_path)

def main():
    # For a single file
    file_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR137436091\9200\UOBM-C9200-BBT-OA-L1-01_10.58.72.12.txt"
    process_file(file_path)

    # For a directory
    # directory_path = r"C:\Users\girish.n\Downloads\SVR137436091"
    # process_directory(directory_path)


if __name__ == "__main__":
    main()