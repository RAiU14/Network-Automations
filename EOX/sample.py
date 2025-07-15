# This requires additional changes post Bug Fix
# Testing & Bug Fix in progress
# Currently using Database\auto_pop.py as sample.py 
# This is an ideal scenario of how the program works currently. 
from Cisco_EOX import *
from Cisco_PID import *

# A simple function to display obtained items as a menu driven function.
def menu(data):
    if type(data) == dict:
        key_index = 1
        key_save = []
        if len(data) == 1:
            extract = data[list(data.keys())[0]]
            if type(extract) == dict:
                if len(extract) == 1:
                    print(data[list(data.keys())[0]])
                    return data[list(data.keys())[0]]
                for content in data[list(data.keys())[0]]:
                    print(f"{key_index}. {content}")
                    key_save.append(content)
                    key_index += 1
                key_entry = int(input("Enter Index Value: "))
                return data[list(data.keys())[0]][key_save[key_entry-1]]
            else:
                return data[list(data.keys())[0]]
        else:
            for key_value in data.keys():
                print(f"{key_index}. {key_value}")
                key_save.append(key_value)
                key_index += 1
            key_entry = int(input("Enter Index Value: "))
            return data[key_save[key_entry-1]]
    elif type(data) == list:
        list_index = 1
        for list_item in data:
            if type(list_item) == dict:
                for item in list_item.keys():
                    print(f"{list_index}. {item}")
                    list_index += 1
        list_entry = int(input("Enter Option: "))
        return data[list_entry-1]

# A simple menu driven program.
print("Welcome to EOX Retreival!\nAvailable Technology:")
technology = menu(category())
device_list = menu(open_cat(technology))
series_link = menu(device_list)
search_result = eox_check(series_link)
if search_result[0] == True:
    redirection_link = search_result[1]
else:
    print("This product is supported by Cisco, but is no longer sold.\n", search_result[1])
    exit()
eox_urls = eox_details(redirection_link)
eox_link = menu(eox_urls)
eox_data = eox_scrapping(eox_link)
print(eox_data)


# Testing was performed where I as the user know that which technology the PID belongs! 
if __name__ == "__main__":
    All_Devices = open_cat('/c/en/us/support/wireless/index.html')
    
    pid = "AIR-AP2702E-UXBULK"
    # pid = "AIR-AP2602E-UXBULK"
    # pid = "9800"
    # pid = "asdfkasdf"
    
    result = find_device_series_link(pid, All_Devices)
    if result:
        device_name, link = result
        print(f"Matched Device: {device_name}\nURL: {link}")
        eox_devices = eox_retreival(pid, link)
        if eox_devices[0] == False:
            print(f"Device Still in Support!\n{eox_devices[1]}")
        else:
            if pid in eox_devices[1]:
                print("TRUE!")
    else:
        print("No link found for the detected series.")
        