# Auto Populate Program to Create a JSON Database
from EOX.Cisco_EOX import *
from .json_fun import *

# Code block to directly obtain EOX for EOX Link available devices. 
def obtain():
    all_available_devices, all_devices, eox_devices, eox_links, eox_data = {}, {}, {}, {}, {}
    categories = category()
    for link in categories.keys():
        all_available_devices[link] = open_cat(categories[link])
    
    for technology in all_available_devices:
        for key in all_available_devices[technology][0]['series']:
            if len(all_available_devices[technology]) == 1:
                for key in all_available_devices[technology][0]['series']:
                # Only Series List is Available:
                    all_devices[key] = all_available_devices[technology][0]['series'][key]
            else:
                # Both Device List and EOX are available. 
                for key in all_available_devices[technology][0]['series']:
                    all_devices[key] = all_available_devices[technology][0]['series'][key]
                for key in all_available_devices[technology][1]['eox']:
                    eox_devices[key] = all_available_devices[technology][1]['eox'][key]

    eox_data = {}
    for devices in eox_devices:
        url = link_check(eox_devices[devices])
        if not url:
            continue
        else:
            eox_links = eox_check(url)
            if not eox_links[0]:
                eox_data[devices] = eox_links[1]
            else:
                urls = eox_details(eox_links[1]['url'])
                if urls:
                    for links in urls:
                        eox = eox_scrapping(urls[links])
                        if eox: 
                            for dev in eox[1]:
                                eox_data[dev] = eox[0]

    with open('eox_pid.json', 'w') as f:
        json.dump(eox_data, f, ensure_ascii=False, indent=4)

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
    
    saver(device_names, "device_family_per_technology.json")

