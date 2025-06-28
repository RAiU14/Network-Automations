import re
import logging
from typing import List, Dict, Optional, Tuple
from Cisco_EOX import *  
# Note: This only works for PIDs with series or numerical value. 


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_possible_series(pid: str) -> List[str]:
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
    # dedupe but preserve order
    seen = set()
    return [c for c in candidates if not (c in seen or seen.add(c))]  # Shortened using AI tool. Will elaborate this line for further modification. 

def find_device_series_link(pid: str,all_devices: List[Dict[str, Dict[str, str]]]) -> Optional[Tuple[str, str]]:
    series_candidates = get_possible_series(pid)
    logging.debug(f"Series candidates for '{pid}': {series_candidates}")
    for cand in series_candidates:
        for tech_block in all_devices:
            # tech_block is a dict: { tech_category: { device_name: url, ... } }
            for devices in tech_block.values():
                for device_name, url in devices.items():
                    if cand in device_name:
                        logging.info(f"Matched '{cand}' in '{device_name}'")
                        return device_name, url
    logging.info(f"No match found for PID '{pid}'")
    return None


