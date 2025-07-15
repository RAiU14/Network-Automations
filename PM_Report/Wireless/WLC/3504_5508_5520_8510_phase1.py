# import pandas as pd
# import os

import re

# Phase 1 list of functions:
# 1. host Name
# 2. Model number
# 3. serial number
# 4. Ip address
# 5. Uptime
# 6. version
# 7. last reboot reason
# 8. CPU utilization
# 9. Memory - Total, Used, Free
# 10. Fan status
# 11. Temperature status
# 12. Power supply

# Phase 2 list of functions:
# 1. line_matching - which covers, host Name, IP address, uptime, version, cpu utilization, fan status
# 2. 

'''
def escape_parentheses(input_string):
    """
    Escapes parentheses in a given string by adding backslashes before them.
    This allows the resulting string to be used as a regular expression pattern.

    Args:
        input_string (str): The input string containing parentheses.

    Returns:
        str: The modified string with backslashes added before parentheses.
    """
    # Use a regular expression to replace unescaped parentheses with their escaped versions
    pattern = r'([\(\)])'
    escaped_string = re.sub(pattern, r'\\\1', input_string)
    return escaped_string

    Example:
    Original string: Current CPU(s) load
    Escaped string: Current CPU\(s\) load
'''

# common/reused function for single line values
def line_matching(path, simple_value):
    """ 
        Args:
        path (location/directory): The path of text file located.

        Returns:
        str: The expected line.
    """
    try:
        with open(path) as file:
            text_content = file.read()
            for line in text_content.splitlines():

                # re has limitation/exception for open-brackets/parentheses, to overcome, we can use as follows
                pattern = r'([\(\)])'
                line = re.sub(pattern, r'\\\1', line)
                
                # line = escape_parentheses(line) 
                """ 
                # line = escape_parentheses(line) - Globally created function for the same above task,
                i.e, re has limitation/exception for open-brackets/parentheses.
                """

                match = re.search(simple_value, line)
                if match:
                    # To extract only the desired values from lines
                    value = re.split(" ",line)
                    if value[1] == 'Up':
                        merged_string = ""
                        for item in value[3:]:
                            # To merge uptime as string after conerting to list in order to point the final value
                            merged_string += item + " "
                        return merged_string
                    else:
                        return value[-1]
        return 0
    except:
        print(Exception)


# 2. Model & Serial number      
def model_serial_number(path):
    try:
        with open(path) as file:
            text_content = file.read()
        
        list_of_lines = text_content.rsplit("\n")
        counter = 0
        temp = []
        for line in list_of_lines:
            counter+=1
            match1 = re.search("---------------Show udi---------------", line)
            # print(match1.end())
            if match1:
                # print("yes1")
                list_values = list_of_lines[counter+4]
                # print(list_values)
                # The size of SN for 8500 series WLC are small compared to 5500, To remove that testing if SN is capture in the final output/return value
                if "SN: " in list_values[-11:]:
                    # return order - Model number, Serial number
                    return list_values[5:18], list_values[-11:].split(" ")[1]
                else:
                    return list_values[5:18],list_values[-11:]
            
            # There are instences where we we have only "System Inventor" and not "Show udi", "Show uid" usually presents in the "show tech"
            # In those scenarios below match2 will do the neccessary job
            # match2 = re.search("System Inventory", line)
            # if match2:
            #     counter+=3
            #     # print("yes2")
            #     str1 = list_of_lines[counter]
            #     temp.append(str1)

            #     if "SN: " in list_values[-11:]:
            #         return temp[0][5:17], temp[0].split(" ")           
            #     else:
            #         return temp[0][5:17], temp[0][-11:]
                # #     if "PID" in item:
                #         return list_values[5:18], list_values[-11:].split(" ")[1]
                # else:
                #     return list_values[5:18],list_values[-11:]
    except Exception as e:
        print(e)


# 7. last reboot reason
def reboot_reason(path):
    try:
        with open(path) as file:
            text_content = file.read()

        list_of_lines = text_content.rsplit("\n")

        list_with_reset_reason = []

        for line in list_of_lines:
            match1 = re.search("Reset reason : ", line)
            match2 = re.search("Last Reset", line)
            if match1:
                list_with_reset_reason.append(line)
                return list_with_reset_reason[-1].split(" : ")[1]
            if match2:
                return line.split(".")[-2:][-1]
    except:
        print(Exception)


# 9. Memory - Total, Used, Free
def memory(path):
    try:
        with open(path) as file:
            text_content = file.read()

        list_of_lines = text_content.rsplit("\n")

        final_list = []
        result = []
        count = 0

        for line in list_of_lines:
            count+=1
            if "System Memory Statistics:" in line:
                for i in range(count,count+6):
                    final_list.append(list_of_lines[i])
                for string in final_list:
                    if string:
                        pattern = r"([\w.]+|\([\d.]+\s*\w+\)|\d+)"
                        elements = re.findall(pattern, string)
                        result.append(elements)
                    else:
                        result.append('')
                for item in result:
                    for values in item:
                        if "Total" in values:
                            total_memory = item[3]
                        if "Used" in values:
                            used_memory = item[3]
                        if "Free" in values:
                            free_memory = item[3]
            if "Bytes allocated from RTOS" in line:
                break
        
        return [total_memory, used_memory, free_memory, int(used_memory)/int(total_memory)*100]
    
    except:
        print(Exception)
     

# 11. Temperature status
def temperature(path):
    try:
        alarm_limits = None
        internal_temp = None
        external_temp = None
        
        with open(path, 'r') as file:
            for line in file:
                if "Internal Temp Alarm Limits" in line:
                    alarm_limits = re.findall(r'\d+', line)[0:2]
                elif "Internal Temperature" in line:
                    internal_temp = re.findall(r'[\+\-]?\d+', line)[0]
                elif "External Temperature" in line:
                    external_temp = re.findall(r'[\+\-]?\d+', line)[0]
        
        if alarm_limits:
            min_limit, max_limit = int(alarm_limits[0]), int(alarm_limits[1])
            print(f"Internal Temp Alarm Limits: {min_limit} to {max_limit} C")
            
            if internal_temp:
                internal_temp = int(internal_temp)
                print(f"Internal Temperature: {internal_temp} C")
                if internal_temp < min_limit or internal_temp > max_limit:
                    print("Internal temperature is outside the alarm limits!")
                else:
                    print("Internal temperature is within the alarm limits.")
            else:
                print("Internal Temperature not found.")
            
            if external_temp:
                external_temp = int(external_temp)
                print(f"External Temperature: {external_temp} C")
                if external_temp < min_limit or external_temp > max_limit:
                    print("External temperature is outside the alarm limits!")
                else:
                    print("External temperature is within the alarm limits.")
            else:
                print("External Temperature not found.")
        else:
            print("Internal Temp Alarm Limits not found.")
        return 0
    
    except:
        print(Exception)

            
# 12. Power supply
def power_supply(path):
    result = 0
    try:
        with open(path) as file:
            text_content = file.read()

        list_of_lines = text_content.rsplit("\n")

        power_dependends = ['Power Supply 1', 'Power Supply 2']

        temp_list = []

        for line in list_of_lines:
            for item in power_dependends:
                match = re.search(item, line)
                if match:
                    temp_list.append(line)
                    final_power = list(set(temp_list))
                    power_1 = ''.join(char for char in final_power[0][-11:] if char.isalpha())
                    power_2 = ''.join(char for char in final_power[-1][-11:] if char.isalpha())
                    result = power_1, power_2 
        return result
    
    except:
        print(Exception)


def test(path):
    with open(path) as file:
        text_content = file.read()
    
    list1 = []

    list_of_lines = text_content.rsplit("\n")

    for line in list_of_lines:
        match = re.search("Current CPU\(s\) load", line)       
        if match:
            list1.append(line) 
            return line
    return list1


def WLC(path):
    # print(hostname(path)) -- done
    # print(model_number(path)) -- done
    # print(serial_number(path)) -- done
    # print(ip_address(path)) -- done
    # print(uptime(path)) -- done
    # print(version(path)) -- done
    # print(reboot_reason(path)) -- done
    # print(cpu_utilization(path)) -- done
    # print(memory(path))
    # print(fan_status(path)) -- done
    # print(temperature(path))
    # print(power_supply(path)) -- done

    
    print(f'Model Number : ', model_serial_number(path)[0],'\n'
          f'Serial Number : ', model_serial_number(path)[1])

    print(f'Power supply 1 : ', power_supply(path)[0],'\n'
          f'Power supply 2 : ', power_supply(path)[1])
    
    print(f'Total memory : ', memory(path)[0],'\n'
          f'Used memory : ', memory(path)[1],'\n'
          f'Free memory : ', memory(path)[2],'\n'
          f'Used memory Percentage : ', memory(path)[3])

    print("Reload/Reboot reason : ", reboot_reason(path))

    simple_values = ["System Name", "IP Address", "System Up Time", 
                     "Product Version", "Current CPU", 
                     "Fan Status"]
    for item in simple_values:
        print(f'{item} : ', line_matching(path, item))

    print(temperature(path))
 
if __name__ == '__main__':
    path = "Test WLC 5508/10.119.138.3.txt"

    # Problems : model & serial number, memory , power
    # no issue with memory for 3500
    # complete problem with CBJ01WLC01 (1).txt - 5500

    # print(f'Model Number : ', model_serial_number(path)[0],'\n'
    #       f'Serial Number : ', model_serial_number(path)[1])

    # print(f'Power supply 1 : ', power_supply(path)[0],'\n'
    #       f'Power supply 2 : ', power_supply(path)[1])
    
    # print(f'Total memory : ', memory(path)[0],'\n'
    #       f'Used memory : ', memory(path)[1],'\n'
    #       f'Free memory : ', memory(path)[2],'\n'
    #       f'Used memory Percentage : ', memory(path)[3])

    # print("Reload/Reboot reason : ", reboot_reason(path))

    # simple_values = ["System Name", "IP Address", "System Up Time", 
    #                  "Product Version", "Current CPU", 
    #                  "Fan Status"]
    # for item in simple_values:
    #     print(f'{item} : ', line_matching(path, item))

    # print(temperature(path))
    WLC(path)