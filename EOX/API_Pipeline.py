import logging
import json
from . import Cisco_API
from . import Cisco_Scrapping
# import Cisco_Scrapping
# import Cisco_API
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import os
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
 
# Step 2: build path to JSON
LOCAL_DB = ROOT / "Database" / "JSON_Files" / "eox_pid.json"

log_dir = os.path.join(os.path.dirname(__file__), "API_logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir,  f"{datetime.today().strftime('%Y-%m-%d')}.log"), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')



"""I think this is not needed I think"""    
# Function to check if the PID is EOX in the PID Table for the series. 
# Expected input is the PID and the link of the EOX page. 
def pid_eox_check(pid: str, link: str):
    try:
        logging.debug(f"Starting PID_EOX_CHECK for {pid} using link: {link}")
        eox_details = Cisco_Scrapping.eox_scrapping(link)
        if pid in eox_details[1]:
            logging.info(f"{pid} found in {link}. EOX retrieved!")
            return [True, eox_details[0]]
        else:
            logging.info(f"{pid} not found in {link}. No EOX Available for device!")
            return [False, "Check online"]
    except Exception as e:
        logging.error(f"Unknown Error occurred during PID_EOX_CHECK for {pid}: {e}\nLink Used: {link}")
        return [False, "Check online"]
        
# Main Function to obtain hardware EOX details
def hardware_eox_retrieval(unique_pid_list, tech):
    EOX_data = {}
    local_data_loaded = False

    try:
        with open(LOCAL_DB, 'r') as f:
            data = json.load(f)
        local_data_loaded = True
    except Exception as e:
        logging.error(f"Unexpected error reading local DB: {e}")
        data = {}

    missing_pids = []

    for pid in unique_pid_list:
        logging.info(f"Checking PID={pid} in local DB")
        entry = data.get(pid)
        if entry:
            logging.debug(f"Found entry for PID={pid}: {entry}")
            EOX_data[pid] = [True, entry]
        else:
            logging.debug(f"No entry found for PID={pid}")
            missing_pids.append(pid)
            EOX_data[pid] = [False, "Not found"]
            
    if not local_data_loaded or missing_pids:
        logging.info("Calling online EOX data fetch for missing or all PIDs.")
        online_data = request_EOX_data_from_online(unique_pid_list if not local_data_loaded else missing_pids, tech, existing_data=EOX_data)
        return online_data
    else:
        return EOX_data
    
    
# Function to get EOX data from Cisco website.
def request_EOX_data_from_online(unique_pid_list, tech, existing_data=None):
    logging.info(f"Starting EOX pull for PIDs: {unique_pid_list}")
    cleaned_data = existing_data if existing_data else {}

    for pid in unique_pid_list:
        try:
            logging.info(f"Fetching EOX data for PID: {pid}")
            # Pass tech as "Routing and Switching" or "Security" etc.
            result = eox_online_scrapping(pid, tech)  # Expected: {'PID': [True, [{EOX}, [related]]]} or {'PID': [False, 'Not Announced']}
            if isinstance(result, dict) and pid in result:
                value = result[pid]

                # Case 1: [True, [EOX dict, related PIDs]]
                if (
                    isinstance(value, list) and len(value) == 2 and
                    isinstance(value[0], bool) and value[0] is True and
                    isinstance(value[1], list) and len(value[1]) == 2 and
                    isinstance(value[1][0], dict)
                ):
                    eox_details = value[1][0]
                    related_pids = value[1][1]
                    logging.debug(f"Related PIDs for {pid}: {related_pids}")
                    cleaned_data[pid] = [True, eox_details]

                # Case 2: [False, 'Not Announced'] or similar
                elif isinstance(value, list) and len(value) == 2 and isinstance(value[0], bool):
                    data = Cisco_API.eox_milestone(unique_pid_list)
                    print(cleaned_data.update(data))
                    # cleaned_data[pid] = value

                else:
                    logging.warning(f"Unexpected inner format for PID {pid}: {value}")
                    cleaned_data[pid] = [False, "Invalid inner data format"]
            else:
                logging.warning(f"Unexpected format for PID {pid}: {result}")
                cleaned_data[pid] = [False, "Invalid data format"]

        except Exception as e:
            logging.error(f"Failed to fetch EOX data for PID '{pid}': {e}")
            cleaned_data[pid] = [False, f"Error: {str(e)}"]

    logging.info("EOX data pull completed.")
    return cleaned_data

# Function to scrap data from online
def eox_online_scrapping(pid, tech):
    EOX_data = {}
    logging.info(f"Starting processing for PID: {pid}")
    try:
        device_link = Cisco_Scrapping.find_device_series_link(pid, tech)
        
        if device_link:
            logging.debug(f"Device link found for PID={pid}: {device_link}")
            eox_link = Cisco_Scrapping.eox_check(device_link)
            logging.debug(f"EOX link check result for PID={pid}: {eox_link}")
        
            if eox_link[0] is False:
                logging.info(f"EOX not announced for PID={pid}")
                EOX_data[pid] = [False, "Not Announced"]
            else:
                eox_page = Cisco_Scrapping.eox_details(eox_link[1]["url"])

                if eox_page:
                    logging.debug(f"EOX Page result obtained for PID={pid}: {eox_page}")
                    EOX = Cisco_Scrapping.eox_scrapping(list(eox_page.values())[0])
                    logging.info(f"EOX data found for PID={pid}")
                    EOX_data[pid] = [True, EOX]
                else:
                    logging.warning(f"EOX Page not found for PID={pid}")
                    EOX_data[pid] = [False, "EOX Page not found"]

        else:
            logging.warning(f"No device link found for PID={pid}. Skipping EOX check.")
            EOX_data[pid] = [False, "Device link not found"]

    except Exception as e:
        logging.error(f"Error processing PID={pid}: {e}")
        EOX_data[pid] = [False, f"Error occurred: {str(e)}"]

    logging.info("EOX scraping completed.")
    return EOX_data


# This is not working as there is no valid API for this
def validate_serial_batch(serials, headers, base_url):
    try:
        logging.info(f'Validating serial batch: {serials}')
        response = requests.get(f"{base_url}{serials}", headers=headers, timeout=30)
        logging.debug(f"Response for batch {serials}: {response.status_code}")
        response.raise_for_status()
        data = response.json().get('product_list', [])
        
        batch_validation_data = {}
        for product in data:
            serial_no = product.get('sr_no')
            base_pid = product.get('base_pid')
            orderable_pid = product.get('orderable_pid')
            
            batch_validation_data[serial_no] = {
                'base_pid': base_pid,
                'orderable_pid': orderable_pid,
                'product_name': product.get('product_name', ''),
                'valid': True
            }
        
        return batch_validation_data
    
    except Exception as e:
        logging.error(f"Error in batch validation: {e}")
        return {}


# This is not working as there is no valid API for this
def validate_serial_numbers(serial_numbers):
    try:
        logging.info(f'Validating {len(serial_numbers)} serial numbers.')
        base_url = "https://apix.cisco.com/product/v1/information/serial_numbers/"
        headers = {
            "Authorization": f"Bearer {Cisco_API.get_cisco_access_token()}",
            "Accept": "application/json",
        }
        batch_size = 5  # API supports max 5 serial numbers per request
        batches = [serial_numbers[i:i + batch_size] for i in range(0, len(serial_numbers), batch_size)]
        query_batches = [','.join(batch) for batch in batches]

        validation_data = {}
        
        # Use concurrent processing for multiple batches
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            for serials in query_batches:
                future = executor.submit(validate_serial_batch, serials, headers, base_url)
                futures[future] = serials
            
            for future in as_completed(futures):
                batch_serials = futures[future]
                try:
                    batch_result = future.result()
                    validation_data.update(batch_result)
                    logging.debug(f"Batch validation completed for: {batch_serials}")
                except Exception as e:
                    logging.error(f"Batch validation failed for {batch_serials}: {e}")
                    continue

        logging.info(f'Serial number validation completed for {len(validation_data)} devices!')
        return validation_data

    except Exception as e:
        logging.error(f"Error occurred during serial validation: {e}")
        return {}


def sanitizer(data, unique_values):
    try:
        logging.info(f"Beginning data sanitization for {len(data)} data entries and {len(unique_values)} PID-Serial pairs.")
        filtered_data, corrected_pid_serial = [], []
        
        # Define skip values as constants
        SKIP_VALUES = ["Require Manual check", "Require Manual Check", "No IOS or IOS-XE detected"]
        
        # Phase 1: Filter data based on problematic values
        for details in data:
            skip_entry = False
            
            # Check Model number field
            model_number = details.get('Model number')
            if model_number:
                # Handle both list and string formats
                if isinstance(model_number, list):
                    if any(val in SKIP_VALUES for val in model_number):
                        skip_entry = True
                elif isinstance(model_number, str):
                    if model_number in SKIP_VALUES:
                        skip_entry = True
            
            # Check IOS Version field
            ios_version = details.get('IOS Version')
            if ios_version and not skip_entry:
                # Handle both list and string formats
                if isinstance(ios_version, list):
                    if any(val in SKIP_VALUES for val in ios_version):
                        skip_entry = True
                elif isinstance(ios_version, str):
                    if ios_version in SKIP_VALUES:
                        skip_entry = True
            
            if not skip_entry:
                filtered_data.append(details)
            else:
                logging.debug(f"Skipping entry with problematic value: {details.get('Model number')} / {details.get('IOS Version')}")
        
        # Phase 2: Process and correct PID-Serial pairs
        if unique_values:
            # Remove entries with skip values
            clean_pairs = []
            for pid, serial in unique_values:
                if pid not in SKIP_VALUES and serial not in SKIP_VALUES:
                    clean_pairs.append([pid, serial])
                else:
                    logging.debug(f"Skipping entry: [{pid}, {serial}]")
            
            if clean_pairs:
                # Extract unique serial numbers for validation
                serial_numbers = list(set([pair[1] for pair in clean_pairs]))
                
                # Get validation data from Cisco API
                validation_data = validate_serial_numbers(serial_numbers)
                
                # Correct PIDs based on validation results
                for pid, serial in clean_pairs:
                    if serial in validation_data:
                        validated_info = validation_data[serial]
                        correct_pid = validated_info['base_pid']
                        
                        if correct_pid and correct_pid != pid:
                            logging.info(f"PID corrected: {pid} -> {correct_pid} for serial {serial}")
                            corrected_pid_serial.append([correct_pid, serial])
                        else:
                            corrected_pid_serial.append([pid, serial])
                            if not correct_pid:
                                logging.warning(f"No base_pid found for serial {serial}, keeping original PID {pid}")
                    else:
                        logging.warning(f"Serial number {serial} not found in validation data, keeping original PID {pid}")
                        corrected_pid_serial.append([pid, serial])
                
                # Remove duplicates while preserving order
                seen = set()
                deduplicated_pairs = []
                for pair in corrected_pid_serial:
                    pair_tuple = (pair[0], pair[1])
                    if pair_tuple not in seen:
                        seen.add(pair_tuple)
                        deduplicated_pairs.append(pair)
                
                corrected_pid_serial = deduplicated_pairs
            else:
                logging.info("No valid PID-Serial pairs to process after filtering")
        else:
            logging.info("No unique_values provided")
        
        logging.info(f"Filtered {len(filtered_data)} data entries and corrected {len(corrected_pid_serial)} PID-Serial pairs.")
        return [filtered_data, corrected_pid_serial]
        
    except Exception as e:
        logging.error(f"An Error Occurred while sanitizing: {e}")
        return [[], []]

def eox_milestones(data, unique_values, tech):
    try:
        logging.info("Hardware EOX Milestone Retrieval starting.")
        
        # Phase 1: Data sanitization with PID-Serial correction
        sanitized_data = sanitizer(data, unique_values)
        
        # Extract corrected PIDs from sanitized pairs for hardware EOX
        unique_pid = [pair[0] for pair in sanitized_data[1]]
        unique_pid = list(set(unique_pid))  # Remove duplicates for API efficiency
        
        # Phase 2: Build device_pass dictionary
        device_pass = {}
        for i in range(len(sanitized_data[0])):
            model = sanitized_data[0][i]['Model number']
            current_software = sanitized_data[0][i]['Current s/w version']
            for devices, images in zip(model, current_software):
                device_pass.setdefault(devices, [])
                if images not in device_pass[devices]:
                    device_pass[devices].append(images)
        
        # Phase 3: TRUE CONCURRENT API calls
        with ThreadPoolExecutor(max_workers=2) as executor:
            logging.info("Starting CONCURRENT hardware and software API calls...")
            
            # Submit both tasks simultaneously
            hardware_future = executor.submit(hardware_eox_retrieval, unique_pid, tech)
            software_future = executor.submit(Cisco_API.software_milestones, device_pass)
            
            logging.info("Both API calls submitted and running concurrently")
            
            # Wait for BOTH to complete - ensures true simultaneity
            try:
                hardware_eox = hardware_future.result(timeout=120)
                logging.debug("Hardware EOX completed")
            except Exception as e:
                logging.error(f"Hardware EOX failed: {e}")
                hardware_eox = {}
            
            try:
                software_eox = software_future.result(timeout=120)
                logging.debug("Software EOX completed")
            except Exception as e:
                logging.error(f"Software EOX failed: {e}")
                software_eox = None
            
            logging.info(f"CONCURRENT execution completed.")
        
        logging.info("EOX Milestone Retrieval completed successfully")
        # print(hardware_eox, software_eox)
        return [hardware_eox, software_eox]
    except Exception as e:
        logging.error(f"An Error Occurred in EOX Milestone Retrieval: {e}")
        return [{}, {}]
