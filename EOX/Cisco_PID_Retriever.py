import re
import logging
from typing import List, Dict
from .Cisco_EOX_Scrapper import *
# This is a simple program to 
# Note: This only works for PIDs with series or numerical value. 


log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir,  f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# To get a possible series
def get_possible_series(pid: str):
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

# Below method is used to search online. 
# To compare it with the device list from the device category link. 
def find_device_series_link(pid: str, tech: str):
    try:
        data = {}
        all_devices = open_cat(tech)
        series_candidates = get_possible_series(pid)
        logging.debug(f"Series candidates for '{pid}': {series_candidates}")

        for cand in series_candidates:
            for tech_block in all_devices:
                for devices in tech_block.values():
                    for device_name, url in devices.items():
                        if cand in device_name:
                            logging.info(f"Matched '{cand}' in '{device_name}'")
                            data[device_name] = url
        if data:
            clean_pid = pid.replace("-", "").upper()
            print(f"Search Clean: {clean_pid}")
            print(f"All available PIDs: {data.keys()}")
            best_match = max(data.keys(), key=lambda k: len(k.replace('-', '').replace(' ', '').upper()) if k.replace('-', '').replace(' ', '').upper() in clean_pid else 0, default=None)
            print(best_match, data[best_match])
            if pid in data.keys():
                logging.debug(f"Exact match found for PID '{pid}': {data[pid]}")
                return data[pid]
            else:
                logging.debug(f"Match found for PID '{pid}': {data[pid]}")
                return list(data.values())[0]  # Return the first match if no exact match
        else:
            logging.info(f"No match found for PID '{pid}'")
            return False
    except Exception as e:
        logging.error(f"An Error Occurred while retreving link for {pid}!\n{e}")
        return None

# Once PID and Link is obtained, complete EOX is retreived. 
def eox_retreival(pid, link):
    try:
        eox_link = eox_details(link)
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
        
        