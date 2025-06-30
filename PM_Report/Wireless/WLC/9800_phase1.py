import re
import pandas as pd

def model_serial_number(path):
    counter = 0
    list1 = []
    with open(path) as file:
        text_content = file.read()
        list_of_lines = text_content.rsplit("\n")
        for line in list_of_lines:
            counter+=1
            # Somehow found this common line/string just above WLC's "PID: "
            if 'NAME: "Chassis 1"' in line:
                list1 = list_of_lines[counter].split(" ")
                break
    if 'PID:' in list1[0] and 'SN:' in list1[-2]:
        return list1[1],list1[-1]
    return 0

def power_fan_status(path):
    with open(path) as file:
        text_content = file.read()

        # Regular expression pattern
        pattern = r'(\w\d+/?\d*)\s+(\w+(?:-\w+)*)\s+(\w+(?:, \w+)*)\s+(\d+[wdmh]?\d*)'

        # Find all matches
        matches = re.findall(pattern, ''.join(text_content))
        # Create a DataFrame

        df = pd.DataFrame(matches, columns=['Slot', 'Type', 'State', 'Insert time'])
        # df[df["Slot"].isin(["P0", "P1"])]
        try:
            result = df[df["Slot"].isin(["P0", "P1"]) | (df["State"] == "ok")]
            return list(result["State"].iloc[:])
        except :
            result = df[df["Slot"].isin(["P0", "P1"]) | (df["State"] != "ok")]
            return list(result["State"].iloc[:])

def reload_reason(path):
    with open(path) as file:
        text_content = file.read()
        list_of_lines = text_content.rsplit("\n")
        reload_reason = next((line for line in list_of_lines if line.__contains__("Last reload reason")), None)
        return (reload_reason.split(":")[1]).strip(" ")

def version(path):
    counter = 0
    list1 = []
    with open(path) as file:
        text_content = file.read()
        list_of_lines = text_content.rsplit("\n")
        version = next((line for line in list_of_lines if line.__contains__("Cisco IOS XE Software, Version ")), None)
        list1 = version.split(" ")
    if 'Cisco' in list1[0] and 'Version' in list1[4]:
        return list1[5].strip(" ")
    
def hostame(path):
    with open(path) as file:
        text_content = file.read()
        list_of_lines = text_content.rsplit("\n")
        hostame = next((line for line in list_of_lines if line.__contains__(" uptime is ")), None)
    return hostame[:hostame.find(" ")-1]

def uptime(path):
    with open(path) as file:
        text_content = file.read()
        list_of_lines = text_content.rsplit("\n")
        uptime_occurances = next((line for line in list_of_lines if line.__contains__(" uptime is ")), None)
    return uptime_occurances[uptime_occurances.find("is")+3:]
        
def cpu_utilization(path):
    with open(path) as file:
        text_content = file.read()
        list_of_lines = text_content.rsplit("\n")
        cpu_utilization = next((line for line in list_of_lines if line.__contains__("CPU utilization for five seconds: ") and line.__contains__("five minutes: ") and "Core " not in line), None)
        if "CPU" in cpu_utilization.split(' ')[0]:
            return cpu_utilization.split(' ')[-1]
    return 0

def memory_info(path):
    with open(path) as file:
        text_content = file.read()
        list_of_lines = text_content.rsplit("\n")
        memory = next((line for line in list_of_lines if line.__contains__("Processor Pool Total: ") and line.__contains__(" Used:  ") and line.__contains__(" Free: ")), None)
        if "Processor" in memory.split(' ')[0]:
            total_memory = memory.split(' ')[3]
            used_memory = memory.split(' ')[6]
            free_memory = memory.split(' ')[-1]
            used_percentage = round(int(used_memory)/int(total_memory)*100, 2)
            return [total_memory,used_memory,free_memory,used_percentage]
    return 0


def main(file_path):
    with open(file_path, 'r') as file:
        file_content = file.read()

    model_number, serial_number = model_serial_number(file_content)
    reload_reason = reload_reason(file_content)
    version = version(file_content)
    hostname = hostname(file_content)
    uptime = uptime(file_content)
    cpu_utilization = cpu_utilization(file_content)
    power_supply_status, fan_status = power_fan_status(file_content)
    total_memory, used_memory, free_memory, used_percentage = memory_info(file_content)

    print(f"Model Number: {model_number}")
    print(f"Serial Number: {serial_number}")
    print(f"Reload Reason: {reload_reason}")
    print(f"Version: {version}")
    print(f"Hostname: {hostname}")
    print(f"Uptime: {uptime}")
    print(f"CPU Utilization: {cpu_utilization}")
    print(f"Power Supply Status: {', '.join(power_supply_status)}")
    print(f"Fan Status: {', '.join(fan_status)}")
    print(f"Total Memory: {total_memory}")
    print(f"Used Memory: {used_memory}")
    print(f"Free Memory: {free_memory}")
    print(f"Used Percentage: {used_percentage}%")

if __name__ == "__main__":
    file_path = "WIreless\9800\WLC30176.txt"
    main(file_path)

# path = "9800\HQ-03-WLC01.txt"
# print("Model Number : ", model_serial_number(path)[0],'\n'
#       "Serial Number : ", model_serial_number(path)[1])

# print("Reload reason : " ,reload_reason(path))

# print("Version: ", version(path))

# print("Hostname: ", hostame(path))

# print("Uptime: ", uptime(path))

# print("CPU Utilization: ", cpu_utilization(path))

# print("Power Supply : ", power_fan_status(path)[0],'\n'
#       "Fan Status : ", power_fan_status(path)[1])

# print("Total Memory : ", memory_info(path)[0],'\n'
#       "Used Memory : ", memory_info(path)[1],'\n'
#       "Free Memory : ", memory_info(path)[2],'\n'
#       "Used Percentage : ", memory_info(path)[3])