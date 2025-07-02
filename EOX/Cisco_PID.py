import re
import logging
from typing import List, Dict, Optional
from Cisco_EOX import *  
# This is a simple program to 
# Note: This only works for PIDs with series or numerical value. 


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# To get a possible series
def get_possible_series(pid: str) -> List[str]:
    try:
        numbers = re.search(r'(\d+)', pid)  # Getting only digits
        if not numbers:
            logging.warning(f"No digits in PID '{pid}'")
            return [pid]
        num = int(numbers.group(1))
        candidates = []
        candidates.append(str(num))  # full number first
        if num >= 100:
            candidates.append(str((num // 100) * 100))  # rounded to nearest hundred
        if num >= 1000:
            candidates.append(str((num // 1000) * 1000))  # rounded to nearest thousand

        seen = set()
        unique_candidates = []
        seen = set()
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique_candidates.append(c)
        return unique_candidates  
    except Exception as e:
        logging.error(f"An Error Occurred while figuring out the possibile device series for {pid}!\n{e}")
        return None

# This is going to be advanced method.
# To compare it with the device list from the device category link. 
def find_device_series_link(pid: str,all_devices: List[Dict[str, Dict[str, str]]]):
    try:
        series_candidates = get_possible_series(pid)
        logging.debug(f"Series candidates for '{pid}': {series_candidates}")
        for cand in series_candidates:
            for tech_block in all_devices:
                for devices in tech_block.values():
                    for device_name, url in devices.items():
                        if cand in device_name:
                            logging.info(f"Matched '{cand}' in '{device_name}'")
                            return [device_name, url]
        logging.info(f"No match found for PID '{pid}'")
        return None
    except Exception as e:
        logging.error(f"An Error Occurred while retreving link for {pid}!\n{e}")
        return None

# Once PID and Link is obtained, complete EOX is retreived. 
def eox_retreival(pid, link):
    try:
        eox_link = eox_link_extract(link)
        if eox_link[0] == True:
            eox_listing_links = eox_details(eox_link[1])
            if len(eox_listing_links) == 1:
                eox = eox_scrapping(eox_listing_links[list(eox_listing_links.keys())[0]])
                if pid in eox[1]:
                    return eox
            else:
                logging.debug(f"Multiple Entreis found. Requesting Manual input to proceed further. PID Details:'{pid}'")
                print("Multiple Enteries Found!\nRequire Mannual Intervention!")
                index = 1
                copy_val = []
                for link_title in eox_listing_links.keys():
                    print(f"{index}. {link_title}")
                    copy_val.append(link_title)
                    index += 1
                index_entry = int(input("Enter Correct Series Bunlde: "))
                logging.debug(f"Input Received\n{index_entry}->{copy_val[index_entry-1]}")
                return eox_scrapping(eox_listing_links[copy_val[index_entry-1]])
        else:
            logging.debug(f"Successfully retreived data for: {pid}")
            return eox_link
    except Exception as e:
        logging.error(f"An Error Occurred while retreving EOX for {pid}!\n{e}")
        return None
        

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
                print(eox_devices[0])
                print("TRUE!")
    else:
        print("No link found for the detected series.")
        