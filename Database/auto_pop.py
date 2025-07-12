# Auto Populate Program to Create a JSON Database
# WIP

from EOX.Cisco_EOX import *
import datetime

start = print(f"Started: {datetime.datetime.now()}")

def obtain():
    all_available_devices, all_devices, eox_devices, eox_links, eox_data = {}, {}, {}, {}, {}
    categories = category()
    for link in categories.keys():
        all_available_devices[link] = open_cat(categories[link])
    # All available device details are stored in form of dictionary. 
    for key in all_available_devices.keys():
        if len(all_available_devices[key]) == 1:
            # Only Device List Available:
            all_devices[key] = all_available_devices[key][0]['series']
        else:
            # Both Device List and EOX are available. 
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


print(obtain())
end = print(f"Finished Execution at {datetime.datetime.now()}")
print(f"Total Time Taken: {start - end}")
