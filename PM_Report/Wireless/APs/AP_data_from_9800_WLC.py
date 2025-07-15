import re
import pandas as pd

# Read the log file
with open("Log_samples\9800 WLC3.txt", "r") as f:
    log_contents = f.read()

# Split the log contents into individual sections
sections = re.split(r"ATM01WLC02#show", log_contents)[1:]

# Initialize dictionaries to store the extracted data
ap_summary_data = {}
ap_uptime_data = {}
ap_config_data = {}

# Extract data from each section
for section in sections:
    section = section.strip()
    if section.startswith(" ap summary"):
        # Extract AP summary data
        ap_summary_lines = section.splitlines()[4:]  # Skip the header lines
        for line in ap_summary_lines:
            if line.strip():  # Ignore empty lines
                columns = line.split()
                ap_name = columns[0]
                ap_model = columns[2]
                ip_address = columns[6]
                ap_summary_data[ap_name] = {
                    "Model number": ap_model,
                    "Interface IP addr": ip_address,
                }
    elif section.startswith(" ap uptime"):
        # Extract AP uptime data
        ap_uptime_lines = section.splitlines()[3:]  # Skip the header lines
        for line in ap_uptime_lines:
            if line.strip():  # Ignore empty lines
                columns = line.split()
                ap_name = columns[0]
                uptime = columns[3] + " " + columns[4] + " " + columns[5] + " " + columns[6]
                ap_uptime_data[ap_name] = {
                    "Uptime": uptime,
                }
    elif section.startswith(" ap config general"):
        # Extract AP config general data
        ap_configs = re.split(r"Cisco AP Name", section)[1:]  # Split into individual AP configs
        for ap_config in ap_configs:
            ap_name_match = re.search(r": (.+)", ap_config)
            serial_number_match = re.search(r"AP Serial Number\s+: (.+)", ap_config)
            software_version_match = re.search(r"Software Version\s+: (.+)", ap_config)
            if ap_name_match and serial_number_match and software_version_match:
                ap_name = ap_name_match.group(1).strip()
                serial_number = serial_number_match.group(1)
                software_version = software_version_match.group(1)
                ap_config_data[ap_name] = {
                    "Serial number": serial_number,
                    "Current s/w ver": software_version,
                }

# Combine the extracted data
data = []
for ap_name in set(list(ap_summary_data.keys()) + list(ap_uptime_data.keys()) + list(ap_config_data.keys())):
    ap_data = {}
    ap_data.update(ap_summary_data.get(ap_name, {}))
    ap_data.update(ap_uptime_data.get(ap_name, {}))
    ap_data.update(ap_config_data.get(ap_name, {}))
    ap_data["Hostname"] = ap_name
    data.append(ap_data)
# Create a pandas DataFrame from the extracted data
df = pd.DataFrame(data)

# Print the DataFrame
print(df)