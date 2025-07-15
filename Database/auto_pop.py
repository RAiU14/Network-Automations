# Auto Populate Program to Create a JSON Database
# WIP

from EOX.Cisco_EOX import *
from .json_fun import *


def obtain():
    all_available_devices, all_devices, eox_devices, eox_links, eox_data = {}, {}, {}, {}, {}
    categories = category()
    for link in categories.keys():
        all_available_devices[link] = open_cat(categories[link])
    
    device_names = []
    for devices in all_available_devices.values():
        for device in devices:
            if device['series'] not in device_names:
                device_names.append(device['series'])
    saver(all_available_devices, "devices_technology.json")
    # Saving all the available device information. 
    exit()
    
    for key in all_available_devices.keys():
        if len(all_available_devices[key]) == 1:
            # Only Device List Available:
            all_devices[key] = all_available_devices[key][0]['series']
        else:
            # Both Device List and EOX Link are available. 
            all_devices[key] = all_available_devices[key][0]['series']
            eox_devices[key] = all_available_devices[key][1]['eox']
    
    for technology in eox_devices.keys():
        available_eox_devices = eox_devices[technology]
        for device in available_eox_devices.keys():
            eox_details = eox_check(link_check(available_eox_devices[device]))
            if eox_details is None:
                print("ERROR: EOX Details not found for device:", device)
                break
            if eox_details[0]:
                eox_links[device] = eox_details[1]
            else:
                eox_data[device] = eox_details[1]
                
    print("\n\n\nEOX Links:\n", eox_links, "\n\n\nEOX Data:\n", eox_data)

# Code block to retreieve all the devices by Cisco which has URL details
def device_list():
    all_available_devices, all_devices, eox_devices = {}, {}, {}
    categories = category()
    for link in categories.keys():
        all_available_devices[link] = open_cat(categories[link])
    
    for key in all_available_devices.keys():
        if len(all_available_devices[key]) == 1:
            # Only Device List Available:
            all_devices[key] = list(all_available_devices[key][0]['series'].keys())
        else:
            # Both Device List and EOX are available. 
            all_devices[key] = list(all_available_devices[key][0]['series'].keys())
            eox_devices[key] = list(all_available_devices[key][1]['eox'].keys())
        
    device_names = {}
    for key in set(all_devices.keys()).union(eox_devices.keys()):
        values = []
        if key in all_devices:
            values.extend(all_devices[key])
        if key in eox_devices:
            values.extend(eox_devices[key])
        device_names[key] = values
    
    saver(device_names, "all_available_devices.json")

device_list()
