import re

def extract_command_output(log_content, command_start_pattern):
    """
    Extracts the output block for a specific command from the full log content.
    Assumes commands are delimited by lines starting with a hostname followed by '$ '.
    """
    # Escape special characters in the command_start_pattern for regex
    escaped_command_start = re.escape(command_start_pattern)

    # Find the start of the desired command's output, preceded by a prompt (e.g., BR-DR-EXT-3PT01 $)
    start_match = re.search(r"(?:^|\n)\s*\S+\s*\$\s*" + escaped_command_start + r"\s*$", log_content, re.MULTILINE)
    if not start_match:
        # Fallback if the command is at the very beginning or not preceded by a prompt, but still exists
        start_match = re.search(r"^" + escaped_command_start + r"\s*$", log_content, re.MULTILINE)
        if not start_match:
            return None

    start_index = start_match.end()

    # Find the start of the next command prompt to delineate the end of the current command's output.
    # This regex looks for a line starting with non-whitespace, followed by $, then any characters.
    end_match = re.search(r"^\s*\S+\s*\$\s*.+", log_content[start_index:], re.MULTILINE)

    if end_match:
        end_index = start_index + end_match.start()
        return log_content[start_index:end_index].strip()
    else:
        # If no next command is found, it's the end of the log
        return log_content[start_index:].strip()

def analyze_fortigate_logs(log_content):
    """
    Analyzes the complete FortiGate log content to gather specified information.

    Args:
        log_content (str): The entire multiline string of the FortiGate log file.

    Returns:
        dict: A dictionary containing the extracted device information.
    """
    device_info = {
        'IP Address': 'N/A',
        'Hostname': 'N/A',
        'Vendor': 'Fortinet',
        'Hardware Model': 'N/A',
        'Type': 'Firewall', # Changed to Firewall as per your request
        'Serial Number': 'N/A',
        'Current Version': 'N/A',
        'CPU Utilization in % (Used)': 'N/A',
        'Memory Utilization in % (Used)': 'N/A',
        'Fan Status': 'N/A',
        'Power Source Single/Dual': 'N/A',
        'Power Supply Status': 'N/A',
        'Device Uptime': 'N/A',
        'HA Unit Configuration Sync? YES or NO': 'N/A',
        'HA Unit - Redundancy State?': 'N/A',
        'SW end of engineering support': 'N/A', # Not in logs
        'SW End of support': 'N/A',           # Not in logs
        'HW End of sale date': 'N/A',         # Not in logs
        'HW End of support': 'N/A',           # Not in logs
        'Backup Status(Is the back up readly available with client)': 'N/A', # Not in logs
        'Overall Remarks / Recommendation': 'N/A' # Not in logs
    }

    # --- Extracting information from 'get system status' ---
    sys_status_output = extract_command_output(log_content, "get system status")
    if sys_status_output:
        # Hostname
        hostname_match = re.search(r"^Hostname:\s*(.+)", sys_status_output, re.MULTILINE | re.I)
        if hostname_match:
            device_info['Hostname'] = hostname_match.group(1).strip()

        # Serial Number
        serial_match = re.search(r"^Serial-Number:\s*(.+)", sys_status_output, re.MULTILINE | re.I)
        if serial_match:
            device_info['Serial Number'] = serial_match.group(1).strip()

        # Current Version - Extract just the numeric version part (e.g., 7.2.9)
        version_match = re.search(r"v(\d+\.\d+\.\d+),build\d+,\d+", sys_status_output)
        if version_match:
            device_info['Current Version'] = version_match.group(1).strip()

        # Device Uptime (from 'get system status' if more specific 'get system performance status' is not found)
        cluster_uptime_match = re.search(r"Cluster uptime:\s*(.+)", sys_status_output, re.MULTILINE | re.I)
        if cluster_uptime_match:
            device_info['Device Uptime'] = cluster_uptime_match.group(1).strip()

    # --- Extracting information from 'get hardware status' ---
    hw_status_output = extract_command_output(log_content, "get hardware status")
    if hw_status_output:
        # Hardware Model - Capture the full model name
        model_name_match = re.search(r"^Model name:\s*(FortiGate-\S+)", hw_status_output, re.MULTILINE | re.I)
        if model_name_match:
            device_info['Hardware Model'] = model_name_match.group(1).strip()

    # --- Extracting information from 'get system performance status' ---
    perf_status_output = extract_command_output(log_content, "get system performance status")
    if perf_status_output:
        # CPU Utilization in % (Used)
        # Prioritize CPU from HA status if available and indicating non-zero user/system
        # Otherwise, use the overall CPU states or fallback to log display
        cpu_performance_match = re.search(r"average-cpu-user/nice/system/idle=(\d+)%/(\d+)%/(\d+)%/(\d+)%", perf_status_output)
        if cpu_performance_match:
            user_cpu = int(cpu_performance_match.group(1))
            system_cpu = int(cpu_performance_match.group(3))
            device_info['CPU Utilization in % (Used)'] = f"{user_cpu + system_cpu}%"
        else: # Fallback to CPU states line if HA performance stats not found
            cpu_states_match = re.search(r"CPU states: (\d+)% user (\d+)% system.*?(\d+)% idle", perf_status_output)
            if cpu_states_match:
                user_cpu = int(cpu_states_match.group(1))
                system_cpu = int(cpu_states_match.group(2))
                device_info['CPU Utilization in % (Used)'] = f"{user_cpu + system_cpu}%"

        # Memory Utilization in % (Used)
        mem_match = re.search(r"Memory:.*?(\d+\.\d+)%", perf_status_output)
        if mem_match:
            device_info['Memory Utilization in % (Used)'] = f"{mem_match.group(1)}%"
        else: # Fallback to log display if not found in performance status
            log_display_mem_match = re.search(r"mem=(\d+)", log_content) # Search anywhere in logs for mem=XX
            if log_display_mem_match:
                device_info['Memory Utilization in % (Used)'] = f"{log_display_mem_match.group(1)}%"

        # Device Uptime (from 'get system performance status' as it's often more detailed)
        uptime_match_perf = re.search(r"^Uptime:\s*(.+)", perf_status_output, re.MULTILINE | re.I)
        if uptime_match_perf:
            device_info['Device Uptime'] = uptime_match_perf.group(1).strip()


    # --- Extracting information from 'get system interface' for IP Address ---
    interface_output = extract_command_output(log_content, "get system interface")
    if interface_output:
        # IP Address (looking for the mgmt1 interface IP)
        ip_match = re.search(r"== \[ mgmt1 \].*?ip: (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", interface_output, re.DOTALL)
        if ip_match:
            device_info['IP Address'] = ip_match.group(1).strip()
        else:
            # Fallback to any interface IP if mgmt1 not found but an IP exists
            any_ip_match = re.search(r"ip: (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", interface_output)
            if any_ip_match:
                 device_info['IP Address'] = any_ip_match.group(1).strip()

    # --- Extracting information from 'diagnose sys ha status' ---
    ha_status_output = extract_command_output(log_content, "diagnose sys ha status")
    if ha_status_output:
        # HA Unit Configuration Sync? YES or NO
        sync_matches = re.findall(r"FG\d+\(.*?\)?: (in-sync|out-of-sync)", ha_status_output)
        if all(s == 'in-sync' for s in sync_matches) and len(sync_matches) >= 2:
            device_info['HA Unit Configuration Sync? YES or NO'] = 'YES'
        elif any(s == 'out-of-sync' for s in sync_matches):
            device_info['HA Unit Configuration Sync? YES or NO'] = 'NO'

        # HA Unit - Redundancy State? (Primary)
        # Check for the line specifically stating "Primary     :" or "Secondary   :"
        primary_line_match = re.search(r"^Primary\s*:\s*\S+,\s*FG\d+", ha_status_output, re.MULTILINE)
        if primary_line_match:
            # If the current device's hostname matches the Primary hostname, then it's Primary
            # The log provided is from BR-DR-EXT-3PT01, which is the Primary
            if device_info['Hostname'] and device_info['Hostname'] in primary_line_match.group(0):
                 device_info['HA Unit - Redundancy State?'] = "Primary"
            else:
                 # This branch would typically hit if the log was from the secondary, but it mentions primary
                 # For the exact match of "Primary" in the table, we'll keep it simple for now
                 pass # Keep as N/A or if it's the secondary, it's Secondary.
        else:
            secondary_line_match = re.search(r"^Secondary\s*:\s*\S+,\s*FG\d+", ha_status_output, re.MULTILINE)
            if secondary_line_match and device_info['Hostname'] and device_info['Hostname'] in secondary_line_match.group(0):
                device_info['HA Unit - Redundancy State?'] = "Secondary"


    # --- Extracting information from 'execute sensor list' for Fans and Power Supplies ---
    sensor_list_output = extract_command_output(log_content, "execute sensor list")
    if sensor_list_output:
        # Fan Status
        fan_matches = re.findall(r"Fan \d+ \.+?\s+(\d+\s*RPM)", sensor_list_output)
        if fan_matches:
            if all(re.match(r"\d+\s*RPM", f) for f in fan_matches) and len(fan_matches) > 0:
                device_info['Fan Status'] = "Normal" # Changed from "OK (All fans detected and spinning)"
            else:
                device_info['Fan Status'] = "Degraded/Not all fans Normal"
        else:
            device_info['Fan Status'] = "Not Found (No fan readings)"

        # Power Supply Status and Power Source Single/Dual
        psu_status_matches = re.findall(r"PS\d Status \.+?\s+(OK|NOT OK)", sensor_list_output, re.I)
        if psu_status_matches:
            if all(status.strip().upper() == 'OK' for status in psu_status_matches):
                device_info['Power Supply Status'] = "Normal" # Changed from "OK"
                if len(psu_status_matches) == 1:
                    device_info['Power Source Single/Dual'] = "Single"
                elif len(psu_status_matches) >= 2:
                    device_info['Power Source Single/Dual'] = "Dual"
            else:
                device_info['Power Supply Status'] = "Degraded" # At least one is not OK
                if len(psu_status_matches) == 1:
                    device_info['Power Source Single/Dual'] = "Single"
                elif len(psu_status_matches) >= 2:
                    device_info['Power Source Single/Dual'] = "Dual"
        else:
            device_info['Power Supply Status'] = "Not Found"
            device_info['Power Source Single/Dual'] = "Not Found"

    return device_info

# --- Main execution block ---
if __name__ == "__main__":
    # Load the complete log file content
    try:
        with open('PM_Report\Log_samples\BR-DR-EXT-3PT01(10.11.90.21).txt', 'r') as f:
            full_log_content = f.read()
    except FileNotFoundError:
        print("Error: 'BR-DR-EXT-3PT01(10.11.90.21).txt' not found.")
        full_log_content = "" # Set to empty to avoid errors

    if full_log_content:
        extracted_data = analyze_fortigate_logs(full_log_content)

        print("--- Extracted Device Information ---")
        # Format and print the output in a table-like structure
        print(f"{'Attribute':<55} | {'Value':<50}")
        print(f"{'-'*55} | {'-'*50}")
        for attribute, value in extracted_data.items():
            print(f"{attribute:<55} | {value:<50}")
    else:
        print("No log content to analyze. Please ensure the file exists and is accessible.")
