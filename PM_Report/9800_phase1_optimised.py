# import re
# import pandas as pd

# # def model_serial_number(text_content):
# #     counter = 0
# #     list1 = []
# #     # with open(path) as file:
# #     #     text_content = file.read()
# #     list_of_lines = text_content.rsplit("\n")
# #     for line in list_of_lines:
# #         counter+=1
# #         # Somehow found this common line/string just above WLC's "PID: "
# #         if 'NAME: "Chassis 1"' in line:
# #             list1 = list_of_lines[counter].split(" ")
# #             break
# #     if 'PID:' in list1[0] and 'SN:' in list1[-2]:
# #         return list1[1],list1[-1]
# #     return 0

# def power_fan_status(text_content):
#     # with open(path) as file:
#     #     text_content = file.read()

#     # Regular expression pattern
#     pattern = r'(\w\d+/?\d*)\s+(\w+(?:-\w+)*)\s+(\w+(?:, \w+)*)\s+(\d+[wdmh]?\d*)'

#     # Find all matches
#     matches = re.findall(pattern, ''.join(text_content))
#     # Create a DataFrame

#     df = pd.DataFrame(matches, columns=['Slot', 'Type', 'State', 'Insert time'])
#     # df[df["Slot"].isin(["P0", "P1"])]
#     try:
#         result = df[(df["Slot"].isin(["P0", "P1"]) | (df["State"] == "ok"))]
#         return list(result["State"].iloc[:])
#     except:
#         result = df[df["Slot"].isin(["P0", "P1"]) | (df["State"] != "ok")]
#         return list(result["State"].iloc[:])

# def reload_reason(text_content):
#     # with open(path) as file:
#     #     text_content = file.read()
#     list_of_lines = text_content.rsplit("\n")
#     reload_reason = next((line for line in list_of_lines if line.__contains__("Last reload reason")), None)
#     return (reload_reason.split(":")[1]).strip(" ")

# def version(text_content):
#     counter = 0
#     list1 = []
#     # with open(path) as file:
#     #     text_content = file.read()
#     list_of_lines = text_content.rsplit("\n")
#     version = next((line for line in list_of_lines if line.__contains__("Cisco IOS XE Software, Version ")), None)
#     list1 = version.split(" ")
#     if 'Cisco' in list1[0] and 'Version' in list1[4]:
#         return list1[5].strip(" ")
    
# def hostame(text_content):
#     # with open(path) as file:
#     #     text_content = file.read()
#     list_of_lines = text_content.rsplit("\n")
#     hostame = next((line for line in list_of_lines if line.__contains__(" uptime is ")), None)
#     return hostame[:hostame.find(" ")]

# def uptime(text_content):
#     # with open(path) as file:
#     #     text_content = file.read()
#     list_of_lines = text_content.rsplit("\n")
#     uptime_occurances = next((line for line in list_of_lines if line.__contains__(" uptime is ")), None)
#     return uptime_occurances[uptime_occurances.find("is")+3:]
        
# def cpu_utilization(text_content):
#     # with open(path) as file:
#     #     text_content = file.read()
#     list_of_lines = text_content.rsplit("\n")
#     cpu_utilization = next((line for line in list_of_lines if line.__contains__("CPU utilization for five seconds: ") and line.__contains__("five minutes: ") and "Core " not in line), None)
#     if "CPU" in cpu_utilization.split(' ')[0]:
#         return cpu_utilization.split(' ')[-1]
#     return None

# def memory_info(text_content):
#     # with open(path) as file:
#     #     text_content = file.read()
#     list_of_lines = text_content.rsplit("\n")
#     memory = next((line for line in list_of_lines if line.__contains__("Processor Pool Total: ") and line.__contains__(" Used:  ") and line.__contains__(" Free: ")), None)
#     if "Processor" in memory.split(' ')[0]:
#         total_memory = memory.split(' ')[3]
#         used_memory = memory.split(' ')[6]
#         free_memory = memory.split(' ')[-1]
#         used_percentage = round(int(used_memory)/int(total_memory)*100, 2)
#         return [total_memory,used_memory,free_memory,used_percentage]
#     return None, None, None, None


# def WLC(file_path):
#     with open(file_path, 'r') as file:
#         file_content = file.read()

#     # model_number, serial_number = model_serial_number(file_content)
#     Reload_reason = reload_reason(file_content)
#     Version = version(file_content)
#     Hostname = hostame(file_content)
#     Uptime = uptime(file_content)
#     Cpu_Utilization = cpu_utilization(file_content)
#     power_supply_status, fan_status = power_fan_status(file_content)[0],power_fan_status(file_content)[1]
#     total_memory, used_memory, free_memory, used_percentage = memory_info(file_content)

#     try:
#         # print(f"Model Number: {model_number}")
#         # print(f"Serial Number: {serial_number}")
#         print(f"Reload Reason: {Reload_reason}")
#         print(f"Version: {Version}")
#         print(f"Hostname: {Hostname}")
#         print(f"Uptime: {Uptime}")
#         print(f"CPU Utilization: {Cpu_Utilization}")
#         print(f"Power Supply Status: {power_supply_status}")
#         print(f"Fan Status: {fan_status}")
#         print(f"Total Memory: {total_memory}")
#         print(f"Used Memory: {used_memory}")
#         print(f"Free Memory: {free_memory}")
#         print(f"Used Percentage: {used_percentage}%")
#     except Exception as e:
#         print(e)

# if __name__ == "__main__":
#     file_path = "SVR135977300\DRC01MGMTSW01_10.20.253.6.txt"
#     WLC(file_path)
    

# # path = "9800\HQ-03-WLC01.txt"
# # print("Model Number : ", model_serial_number(path)[0],'\n'
# #       "Serial Number : ", model_serial_number(path)[1])

# # print("Reload reason : " ,reload_reason(path))

# # print("Version: ", version(path))

# # print("Hostname: ", hostame(path))

# # print("Uptime: ", uptime(path))

# # print("CPU Utilization: ", cpu_utilization(path))

# # print("Power Supply : ", power_fan_status(path)[0],'\n'
# #       "Fan Status : ", power_fan_status(path)[1])

# # print("Total Memory : ", memory_info(path)[0],'\n'
# #       "Used Memory : ", memory_info(path)[1],'\n'
# #       "Free Memory : ", memory_info(path)[2],'\n'
# #       "Used Percentage : ", memory_info(path)[3])

# Meta optimised
import re
import pandas as pd

class CiscoParser:
    def __init__(self, file_path):
        with open(file_path, 'r') as file:
            self.file_content = file.read()

    def reload_reason(self):
        return next((line.split(":")[1].strip() for line in self.file_content.split("\n") if "Last reload reason" in line), None)

    def version(self):
        return next((line.split("Version ")[1].strip() for line in self.file_content.split("\n") if "Cisco IOS XE Software, Version" in line), None)

    def hostname(self):
        return next((line.split(" uptime is ")[0] for line in self.file_content.split("\n") if " uptime is " in line), None)

    def uptime(self):
        return next((line.split("is ")[1] for line in self.file_content.split("\n") if " uptime is " in line), None)

    def cpu_utilization(self):
        cpu_line = next((line for line in self.file_content.split("\n") if "CPU utilization for five seconds: " in line and "five minutes: " in line and "Core " not in line), None)
        return cpu_line.split(' ')[-1] if cpu_line else None

    def memory_info(self):
        memory_line = next((line for line in self.file_content.split("\n") if "Processor Pool Total: " in line and " Used:  " in line and " Free: " in line), None)
        if memory_line:
            values = memory_line.split(' ')
            total_memory, used_memory, free_memory = values[3], values[6], values[-1]
            used_percentage = round(int(used_memory)/int(total_memory)*100, 2)
            return total_memory, used_memory, free_memory, used_percentage
        return None, None, None, None

    def power_fan_status(self):
        pattern = r'(\w\d+/?\d*)\s+(\w+(?:-\w+)*)\s+(\w+(?:, \w+)*)\s+(\d+[wdmh]?\d*)'
        matches = re.findall(pattern, self.file_content)
        df = pd.DataFrame(matches, columns=['Slot', 'Type', 'State', 'Insert time'])
        result = df[(df["Slot"].isin(["P0", "P1"]) | (df["State"] == "ok"))]
        return result["State"].iloc[:].tolist()


def main():
    file_path = "Log_samples\9800 WLC.txt"
    parser = CiscoParser(file_path)
    
    try:
        print(f"Reload Reason: {parser.reload_reason()}")
        print(f"Version: {parser.version()}")
        print(f"Hostname: {parser.hostname()}")
        print(f"Uptime: {parser.uptime()}")
        print(f"CPU Utilization: {parser.cpu_utilization()}")
        power_fan_status = parser.power_fan_status()
        print(f"Power Supply Status: {power_fan_status[0]}")
        print(f"Fan Status: {power_fan_status[1]}")
        total_memory, used_memory, free_memory, used_percentage = parser.memory_info()
        print(f"Total Memory: {total_memory}")
        print(f"Used Memory: {used_memory}")
        print(f"Free Memory: {free_memory}")
        print(f"Used Percentage: {used_percentage}%")
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()