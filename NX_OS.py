import os
import re
import time
import pandas as pd
# openpyxl library required as well to continue. 

# Pending code optimization
start_time = time.time()
all_files = os.listdir()

# for item in all_files:
#     open(item)

with open('filename.txt/log/etc') as current_file:
    data = current_file.read()

# Checking if there is show tech command run in the Nexus Logs
def sh_tech_flag():
    if bool(re.search(r'show\s*tech|sh\s*tech', data)):
        return True
    else:
        return False

# All the below works if the command show tech-support is run and the available commands are executed in the show tech output.
# Extraction - 1
# Obtaining Show Version Details
def show_version(): 
    cut_data = data[re.search(r"show\s*version", data).start() + 1:]
    return cut_data[:re.search(r"show\s*", cut_data).start()]

# Obtaining Installed NX OS Version
def NX_OS(data):
    lgth = len(r"NXOS: ")
    NX_OS_start_index = re.search(r"NXOS:\s*", data).start()
    version_number = ""
    for value in data[NX_OS_start_index + lgth:NX_OS_start_index + lgth + re.search("\n", data[NX_OS_start_index + lgth:]).start()]:
        if value.isdigit() or value in [".", "(", ")"]:
            version_number += value
    return version_number

# Obtaining Serial Number
def serial_number(data):
    lgth = len(r"Processor Board ID ")
    serial_number_start_index = re.search(r"Processor\s*Board\s*ID\s*", data).start()
    return data[serial_number_start_index + lgth:serial_number_start_index + lgth + re.search("\n", data[serial_number_start_index + lgth:]).start()]

# Obtaining Device Name
def device_name(data):
    lgth = len("Device name: ")
    device_name_start_index = re.search(r"Device\s*name:", data).start()
    return data[device_name_start_index + lgth: device_name_start_index + lgth + re.search(r"\n", data[device_name_start_index + lgth:]).start()]

# Obtaining Uptime
def uptime(data):
    lgth = len(r"Kernel uptime is ")
    uptime_start_index = re.search(r"Kernel\s*uptime\s*is\s*", data).start()
    return data[uptime_start_index + lgth: uptime_start_index + lgth + re.search(r"\n", data[uptime_start_index + lgth:]).start()]

# Obtaining Last Reboot Reason
def last_reboot(data):
    lgth = len(r"Reason: ")
    reason_start_index = re.search(r"Reason:\s*", data).start()
    return data[reason_start_index + lgth: reason_start_index + lgth + re.search(r"\n", data[reason_start_index + lgth:]).start()]

# Extraction - 2
# Obtaining Modules
def modules():
    start_index = re.search(r"show\s*module", data).start()
    cut_data = data[start_index + 1:]
    end_index = re.search(r"show\s*", cut_data).start()
    return cut_data[:end_index]

# Obtaining Module Model Numbers
def module_model_numbers(data):
    model_number = {}
    end_index = re.search(r"Mod\s*Sw", data).start()
    for item in data[:end_index].splitlines():
        values = item.split()
        if len(values) > 1:
            try:
                if int(values[0]):
                    if values[-1] == "*":
                        model_number.update({values[0]:[values[-3]]})
                    else:
                        model_number.update({values[0]:[values[-2]]})
            except ValueError:
                pass
    return model_number

# Obtaining Module Serial Numbers
def module_serial_numbers(data):
    serial_number = {}
    start_index = re.search(r"Serial", data).start()
    for item in data[start_index:start_index+re.search(r"Mod\s*", data[start_index:]).start()].splitlines():
            values = item.split()
            if len(values) > 1:
                try:
                    if int(values[0]):
                        serial_number.update({values[0]:[values[-1]]})
                    else: 
                        serial_number.update({values[0]:["Unavailable!"]})
                except ValueError:
                    pass
    return serial_number

# Module data collaboration
def module_info(data1, data2):
    for pid in data1:
        for serial_number in data2.keys():
            if pid == serial_number:
                data1[pid].append(data2[serial_number][0])
    return data1

# Extraction - 3
# Obtaining Environment Details
def env_details():
    cut_data = data[re.search(r"show\s*environment", data).start() + 1:]
    defected_items = {}
    for item in cut_data[:re.search(r"show\s*", cut_data).start()].splitlines():
        if item.find(':') > 2:
            if item[:item.find(':')] in ['Fan', 'Power Supply', 'Temperature']:
                title = item[:item.find(':')]
        if item.find('Not Ok') > 2:
            module_type = item[:item.find(' ')]
            if len(module_type) == 1:
                defected_items.update({title:"PSU " + module_type})
            else:
                defected_items.update({title:module_type})
            return defected_items
    
    if len(defected_items) <= 1:
        defected_items.update({'N/A': 'N/A'})
    
    return defected_items
        
# Extracion - 4
# Obtaining interface details
def interface_brief():
    cut_data = data[re.search(r"show\s*interface\s*brief", data).start() + 1:]
    lines = cut_data[:re.search(r"show\s*", cut_data).start()].splitlines()
    
    open_ports = []
    for item in lines:
        if re.search(r"not\s*connected", item):
            all_vals = item.split()
            if all_vals[1] == "1" and all_vals[4] == "down":
                open_ports.append(all_vals[0])
            counter = len(open_ports)
        else: 
            counter = 0

    port_details = []
    for item in lines:
        if re.search(r"half|Half", item):
            all_vals = item.split()
            port_details.append(all_vals[0])

    if len(port_details) > 1:
        half_duplex = {'Yes': port_details}
    else:
        half_duplex = {'No': 'N/A'}

    for item in lines:
        start_index = re.search(r"mgmt0", item)
        if start_index:
            if re.search(r"up", item[start_index.start():re.search(r"\n", item[start_index.start():])]):
                ip_address = item.split()[3]
            else: 
                ip_address = "Unavailable"

    return {'Management IP': ip_address,'Open Ports': counter, 'Half Duplex': half_duplex}

# WIP
# Extraction - 5
# Obtaining debug details
def debugging():
    cut_data = data[re.search(r"show\s*debug", data).start() + 1:]
    return cut_data[:re.search(r"show\s*", cut_data).start()]

# Extraction - 6
# Obtaining system resources 
def sys_resource():
    start_index = re.search(r"show\s*system\s*resources\s*module\s*all", data).start()
    title = []
    cpu_values = []
    memory_values = []
    for item in data[start_index: start_index + re.search(r"show\s*", data[start_index + 1:]).start()].splitlines(): 
        strip_values = item.split()
        if item.find(':') > 2:
            if len(item.split()) > 5:
                title.append(item[:item.find(':')].strip())
        if title:
            if len(title) > 1:
                if len(strip_values) == 4:
                    memory_values.append({strip_values[0]:[strip_values[1],strip_values[2],strip_values[3]]})
            else:
                if len(strip_values) == 4:
                    cpu_values.append({strip_values[0]:strip_values[3]})
    return cpu_values, memory_values

# Extraction - 7
# Obtaining Flash Memory
def flash_details():
    start_index = re.search(r"show\s*hardware\s*capacity\s*module", data).start()
    cut_data = data[start_index:start_index + re.search(r"show\s*", data[start_index + 1:]).start()]
    line_data = cut_data[re.search(r'Flash', cut_data).start():].splitlines()
    # Total, Free, Used%
    for item in line_data:
        content = item.split()
        for context in content:
            if context == "bootflash":
                flash_mem = [content[-1], content[-2], content[-3]]
    return flash_mem

# Extraction - 8
# Obtaining Critical Logs
def critical_logs():
    start_index = re.search(r"show\s*logging\s*log", data).start()
    match_hit = {}
    match_sequence = ['-0-', '-1-', '-2-']
    for pattern in match_sequence:
        counter = re.findall(pattern, data[start_index:start_index + re.search(r"show\s*", data[start_index + 1:]).start()])
        if counter:
            match_hit.update({pattern:len(counter)})
    return match_hit

# Extraction - 9
# Obtaining Config Status
def config_status():
    return

# Extraction - 10
# Obtaining IP Address
def ip_address():
    return

# Use this code to write obtained value to Excel. 
def report_generation(file_path):
    data = {
        'File name':['abc'],
        'Host name':['xse'],
        'Serial number':['scdcsdc'],
        'Uptime':['123'],
        'Current s/w version':['2.2.2'],
        'Last Reboot Reason':['abd'], 
        'Interface Name': ['1/1/1', '1/1/2']
    }

    df = pd.DataFrame(data)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    df.to_excel(file_path, index=False)

end_time = time.time()

sh_ver_data = show_version()
print(NX_OS(sh_ver_data))
print(serial_number(sh_ver_data))
print(device_name(sh_ver_data))
print(uptime(sh_ver_data))
print(last_reboot(sh_ver_data))
print(env_details())
print(interface_brief())
print(module_info(module_model_numbers(modules()), module_serial_numbers(modules())))
print(sys_resource())
print(flash_details())
print(critical_logs())
print(f"Elapsed Time: {end_time - start_time} seconds")

# This code is a WIP
