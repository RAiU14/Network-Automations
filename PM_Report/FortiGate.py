import re
import os

def extract_fortigate_info(log_content, log_filename=None):
    """
    Extracts specific performance and status information from Fortigate log content.

    Args:
        log_content (str): The full content of the Fortigate log file.
        log_filename (str, optional): The name of the log file. Used to extract IP address.

    Returns:
        dict: A dictionary containing the extracted attributes.
    """
    data = {
        "IP Address": "N/A",
        "Hostname": "N/A",
        "Vendor": "Fortinet", # Fixed value for Fortigate
        "Hardware Model": "N/A",
        "Type": "FortiGate Appliance", # Fixed value for Fortigate
        "Serial Number": "N/A",
        "Current Version": "N/A",
        "CPU Utilization in % (Used)": "N/A",
        "Memory Utilization in % (Used)": "N/A",
        "Fan Status": "N/A",
        "Power Source Single/Dual": "N/A",
        "Power Supply Status": "N/A",
        "Device Uptime": "N/A (Not found in provided log content)", # Explained why N/A
        "HA Unit Configuration Sync? YES or NO": "N/A",
        "HA Unit - Redundancy State?": "N/A"
    }

    # IP Address from filename (e.g., BR-DR-EXT-01(10.11.90.11).txt)
    if log_filename:
        ip_from_filename_match = re.search(r'\(((\d{1,3}\.){3}\d{1,3})\)', log_filename)
        if ip_from_filename_match:
            data["IP Address"] = ip_from_filename_match.group(1)
        else:
            # Fallback to primary_ip if IP not in filename and no other explicit IP found
            ip_match = re.search(r"primary_ip=(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", log_content)
            if ip_match:
                data["IP Address"] = ip_match.group(1)
    else: # If no filename is provided, try to get IP from HA info
        ip_match = re.search(r"primary_ip=(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", log_content)
        if ip_match:
            data["IP Address"] = ip_match.group(1)


    # Hostname
    hostname_match = re.search(r"Hostname:\s*([^\n\r]+)", log_filename)
    if hostname_match:
        data["Hostname"] = hostname_match.group(1)

    # Hardware Model (e.g., FG1800F)
    model_match_from_version = re.search(r"Version: (FortiGate-(\S+)-?\S+)\s", log_content)
    if model_match_from_version:
        # Extract "1800F" then prepend "FG"
        model_part = model_match_from_version.group(2).replace("FortiGate-", "")
        data["Hardware Model"] = f"FG{model_part}"
    else:
        model_match_from_ha = re.search(r"Model=(\S+),", log_content)
        if model_match_from_ha:
             data["Hardware Model"] = f"FG{model_match_from_ha.group(1)}"


    # Serial Number (Primary)
    sn_match = re.search(r"Factory SN:\s*(\S+)", log_content)
    if sn_match:
        data["Serial Number"] = sn_match.group(1)

    # Current Version (e.g., v7.0.14, build1688 (GA))
    version_match = re.search(r"Version: FortiGate-\S+\s*(v\S+),build(\d+),\d+\s*\(GA\)", log_content)
    if version_match:
        data["Current Version"] = f"{version_match.group(1)}, build{version_match.group(2)} (GA)"
    else: # Fallback for slightly different version formats
        version_alt_match = re.search(r"Version: (FortiGate-\S+ v\S+,\S+,\S+)", log_content)
        if version_alt_match:
            data["Current Version"] = version_alt_match.group(1).split(' ')[1] # Get 'v7.0.14,build1688,240813' part

    # CPU Utilization
    cpu_match = re.search(r"CPU:\s*(\d+)% used", log_content)
    if cpu_match:
        data["CPU Utilization in % (Used)"] = f"{cpu_match.group(1)}%"

    # Memory Utilization (Prioritize direct percentage from `get hardware status`)
    mem_used_percent_match = re.search(r"Memory: (\d+)% used", log_content)
    if mem_used_percent_match:
        data["Memory Utilization in % (Used)"] = f"{mem_used_percent_match.group(1)}%"
    else: # Fallback to calculation if direct percentage not found
        mem_total_match = re.search(r"MemTotal:\s*(\d+)\s*kB", log_content)
        mem_free_match = re.search(r"MemFree:\s*(\d+)\s*kB", log_content)
        if mem_total_match and mem_free_match:
            mem_total = int(mem_total_match.group(1))
            mem_free = int(mem_free_match.group(1))
            mem_used = mem_total - mem_free
            if mem_total > 0:
                mem_utilization = (mem_used / mem_total) * 100
                data["Memory Utilization in % (Used)"] = f"{mem_utilization:.2f}%"

    # Fan Status
    fan_status_matches = re.findall(r"Fan:\s*\d+\.\s*(OK|Faulty)", log_content)
    if fan_status_matches:
        if all(status == "OK" for status in fan_status_matches):
            data["Fan Status"] = f"All OK ({len(fan_status_matches)} fans)"
        else:
            fan_details = []
            rpm_matches = re.findall(r"Fan:\s*\d+\.\s*(?:OK|Faulty)\s*(\d+)\s*RPM", log_content)
            for i, status in enumerate(fan_status_matches, 1):
                rpm = rpm_matches[i-1] if i-1 < len(rpm_matches) else "N/A"
                fan_details.append(f"Fan {i}: {status} ({rpm} RPM)")
            data["Fan Status"] = ", ".join(fan_details)

    # Power Supply Status and Power Source
    power_supply_matches = re.findall(r"Power Supply:\s*\d+\.\s*(OK|Faulty)", log_content)
    if power_supply_matches:
        if len(power_supply_matches) > 1:
            data["Power Source Single/Dual"] = "Dual"
        else:
            data["Power Source Single/Dual"] = "Single"

        if all(status == "OK" for status in power_supply_matches):
            data["Power Supply Status"] = f"All OK ({len(power_supply_matches)} PSUs)"
        else:
            ps_statuses = [status for status in power_supply_matches]
            data["Power Supply Status"] = ", ".join([f"PS {i}: {status}" for i, status in enumerate(ps_statuses, 1)])

    # HA Unit Configuration Sync?
    # Using 'all' checksum from both units
    checksums_primary_all_match = re.search(r"FG181FTK21901986\s*=+\s*checksum\n.*?all:\s*(\S+)", log_content, re.DOTALL)
    checksums_secondary_all_match = re.search(r"FG181FTK23901571\s*=+\s*checksum\n.*?all:\s*(\S+)", log_content, re.DOTALL)

    if checksums_primary_all_match and checksums_secondary_all_match:
        primary_checksum = checksums_primary_all_match.group(1).strip()
        secondary_checksum = checksums_secondary_all_match.group(1).strip()
        if primary_checksum == secondary_checksum:
            data["HA Unit Configuration Sync? YES or NO"] = "YES"
        else:
            data["HA Unit Configuration Sync? YES or NO"] = "NO"

    # HA Unit - Redundancy State?
    ha_primary_state_match = re.search(r"FG181FTK21901986:\s*(Primary)", log_content)
    ha_secondary_state_match = re.search(r"FG181FTK23901571:\s*(Secondary)", log_content)

    if ha_primary_state_match and ha_secondary_state_match:
        data["HA Unit - Redundancy State?"] = f"{ha_primary_state_match.group(1)}/{ha_secondary_state_match.group(1)}"
    elif ha_primary_state_match:
        data["HA Unit - Redundancy State?"] = ha_primary_state_match.group(1)
    elif ha_secondary_state_match:
        data["HA Unit - Redundancy State?"] = ha_secondary_state_match.group(1)

    return data

# --- Example Usage ---
# Assume the log content is read from the file 'BR-DR-EXT-01(10.11.90.11).txt'
log_file_path = "log_file.txt"

try:
    with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
        log_content = f.read()
    log_filename = os.path.basename(log_file_path) # Extract filename for IP

    extracted_data = extract_fortigate_info(log_content, log_filename)

    # Prepare the output
    output = []
    output.append("| Attribute | Value |")
    output.append("|---|---|")
    for key, value in extracted_data.items():
        output.append(f"| {key} | {value} |")

    print("\n".join(output))

except FileNotFoundError:
    print(f"Error: The file '{log_file_path}' was not found.")
except Exception as e:
    print(f"An error occurred: {e}")