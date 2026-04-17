import requests
import json
import logging
from datetime import datetime
import os
import bs4
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
 
# Step 2: build path to JSON
CRED = ROOT / "EOX" / "Crediability.json"

log_dir = os.path.join(os.path.dirname(__file__), "API_logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir,  f"{datetime.today().strftime('%Y-%m-%d')}.log"), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def get_cisco_access_token():
    try:
        logging.info("Requesting access token.")
        url = "https://id.cisco.com/oauth2/default/v1/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            with open(CRED, 'r') as json_read:
                data = json.load(json_read)
        except FileNotFoundError:
            logging.error('Crediability.json file not found')
            data = {"data": {}, "token_details": {}}

        token = data.get("token_details", {})
        now = datetime.now().timestamp()

        lifetime = float(token.get("expiry") or 0)  
        expires_at = float(token.get("time_stamp") or 0) + lifetime
        cached_token = token.get("token")

        needs_refresh = (not cached_token) or (lifetime <= 0) or (now >= (expires_at - 60))

        if needs_refresh:
            logging.info("Generating new access token.")
            api_resp = requests.post(url, headers=headers, data=data.get("data"), timeout=30)
            api_resp.raise_for_status()
            api_data = api_resp.json()

            access_token = api_data["access_token"]
            expires_in = int(api_data["expires_in"])  

            now = datetime.now().timestamp()
            data["token_details"] = {
                "token": access_token,
                "expiry": expires_in,                 
                "time_stamp": now,                    
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S%z"),
            }
            with open(CRED, 'w') as json_write:
                json.dump(data, json_write, indent=4)
                logging.info("Writing new token details to JSON Database successful.")
            return access_token
    except Exception as e:
        logging.error(f"Error fetching access token: {e}")
        return None

    logging.info("Using cached access token.")
    return cached_token


# Functions for software milestones
def get_software_suggestions(token, pid_list):
    try:
        logging.info(f'Fetching for Software Suggestion Information for {pid_list}')
        url = "https://apix.cisco.com/software/suggestion/v2/suggestions/software/productIds"
        headers = {"Authorization": f"Bearer {token}"}
        batch_size = 10
        pid_batches = []
        
        for i in range(0, len(pid_list), batch_size):
            batch = pid_list[i:i+batch_size]
            pids = ""
            for pid in batch:
                pids += pid + ","
            pid_batches.append(pids.rstrip(","))
            
        all_results = {}
        failed_pid = []
        logging.info(f'Total batches to process: {len(pid_batches)}')
        
        for pids in pid_batches:
            response = requests.get(f"{url}/{pids}", headers=headers, timeout=30)
            logging.debug(f"Response for PIDs {pids}: {response.status_code}")
            response.raise_for_status()
            sol = response.json()
            
            for product in sol.get('productList'):
                pid = (product.get('product') or {}).get('basePID')
                suggestions = product.get('suggestions')
                if sol.get('errorDetailsResponse') is not None:
                    logging.error(f"Error in response for product {product}: {sol.get('errorDetailsResponse')}")
                    continue
                                
                normalized = []
                for s in suggestions:
                    if not isinstance(s, dict):
                        continue
                    normalized.append({
                        'Suggested S/W Version': s.get('releaseFormat1'),
                        'Suggested S/W Release Date': s.get('releaseDate')
                    })
                
                # Always return a list for consistency
                all_results[pid] = normalized
                
                if pid in pid_list:
                    pid_list.remove(pid)
                    failed_pid = pid_list
                    logging.warning(f"Received unexpected PID {pid} not in requested list.")
                    continue
                    
    except Exception as e:
        logging.error(f"Error fetching suggested images: {e}")
        return None

    if failed_pid:
        logging.warning(f"Failed to fetch suggestions for PIDs: {failed_pid}")
        for pid in failed_pid:
            all_results[pid] = ['Require Manual Check'] * 2
    else:
        logging.info(f'Software Suggestion Information fetched successfully for devices: {len(all_results)}')

    return all_results


def get_software_eos(token, devices):
    try:
        logging.info(f'Fetching End of Support (EoS) Information for {devices}')
        base_url = "https://apix.cisco.com/supporttools/eox/rest/5/EOXBySWReleaseString/1"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        
        batch_size = 20
        all_inputs = []
        input_number = 1
        for versions in devices.values():
            for version in versions:
                all_inputs.append(f"input{input_number}={version}")
                input_number += 1

        batches = [all_inputs[i:i + batch_size] for i in range(0, len(all_inputs), batch_size)]
        query_batches = ['&'.join(batch) for batch in batches]
        logging.info(f'Query batches created: {query_batches}')
        
        all_details = []
        
        for images in query_batches: 
            logging.info(f'Processing batch: {images}')
            response = requests.get(f"{base_url}?{images}", headers=headers, timeout=30)
            logging.debug(f"Response for batch {images}: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            records = data.get('EOXRecord')
            all_details.extend(records)


        product_bulletin_set = set()
        product_url = set()
        
        for record in all_details:
            pb_num = record.get('ProductBulletinNumber')
            if pb_num:
                product_bulletin_set.add(pb_num)
                last_support = record.get('LastDateOfSupport').get('value')
                if not record.get('LinkToProductBulletinURL'):
                    logging.warning(f'No link provided by Cisco API for Product Bulletin Number: {pb_num}')
                    continue
                else: 
                    product_url.add(record.get('LinkToProductBulletinURL'))
        
        last_date_of_support_map = {}
        for links in product_url:
            logging.info(f'Performing WebScraping for url: {links}')
            load = bs4.BeautifulSoup(requests.get(links).text, 'lxml')
            title = load.find('h1').text
            if "software" in title.lower():
                match = re.search(r'\d+\.\d+(?:\.x)?', title)
            else:
                match = re.search(r'\d+\.\d+(?:\.\d+)?', title)
            if match:
                version_number = match.group(0)
                if last_support:
                    last_date_of_support_map[version_number] = last_support
                    logging.debug(f'Product Bulletin Number: {pb_num}, Last Date of Support: {last_support}')

    except Exception as e:
        logging.error(f"Error fetching EoS data: {e}")
        return None
    
    logging.info(f'End of Support (EoS) Information fetched successfully for {devices}')
    return last_date_of_support_map


def get_compatible_software(token, pids):
    try:
        logging.info(f'Fetching compatible software information.')
        base_url = "https://apix.cisco.com/software/suggestion/v2/suggestions/compatible/productId/"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        device_data = {}
        logging.info(f'Total PID List Size: {len(pids)}')
        for pid in pids:
            logging.info(f'Fetching compatible software information for PID: {pid}')
            response = requests.get(f"{base_url}{pid}", headers=headers, timeout=30)
            logging.debug(f"Response for PID {pid}: {response.status_code}")
            if response.status_code == 200:
                response.raise_for_status()
                data = response.json()
                records = data.get('suggestions', [])
                valid_records = [r for r in records if r.get('releaseDate')]
                if valid_records:
                    latest_record = max(valid_records, key=lambda x: datetime.strptime(x['releaseDate'], '%d-%b-%Y'))
                    device_data[pid] = latest_record.get('releaseFormat1')
                    logging.info(f'Compatible software found for PID {pid}: {device_data[pid]} (Released: {latest_record.get("releaseDate")})')
                else:
                    device_data[pid] = 'Require Manual Check'
            else:
                logging.warning(f"Response for PID {pid}: {response.status_code}")
                device_data[pid] = 'Require Manual Check'
                continue
    except Exception as e:
        logging.error(f"Error fetching compatible software data: {e}")
    logging.info(f'Compatible software information fetched successfully for {len(pids)} devices!')
    return device_data


def software_deferred_check(token, device_details):
    try:
        logging.info("Checking software deferred status.")
        base_url = "https://apix.cisco.com/software/v4.0/metadata/pidrelease"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        result = {}

        for device, images in device_details.items():
            if isinstance(images, str):
                images = [images]

            for image in images:
                image = re.sub(r'(^|\.)0+(\d)', r'\1\2', image)
                payload = {
                    "outputReleaseVersion": "latest",
                    "pageIndex": "1",
                    "perPage": "1",
                    "pid": device,
                    "currentReleaseVersion": image,
                }

                try:
                    response = requests.post(base_url, headers=headers, json=payload, timeout=30)
                    if response.status_code == 200:
                        deferred = False
                        logging.info(f"Software not deferred for Device: {device}, Image: {image}")
                    # Temporary changes as Cisco API is not working at the moment.
                    elif response.status_code == 404:
                        deferred = True
                        logging.info(f"API unable to obtain information for: {device}, Image: {image} (status {response.status_code})")
                    else:
                        deferred = "Required Manual Check"
                        logging.warning(f"Software deferred for Device: {device}, Image: {image} (status {response.status_code})")
                except Exception as e:
                    deferred = "Require Manual Check"
                    logging.warning(f"Error Occurred for Device: {device}, Image: {image}: {e}")

                result.setdefault(device, {})[image] = deferred

        logging.info("Software deferred status check completed successfully.")
        return result

    except Exception as e:
        logging.error(f"Error occurred in software_deferred_check: {e}")
        return None


# Function to obtain all hardware EOX information
def eox_milestone(device_details):
    try:
        logging.info(f'Fetching EoX milestone information.')
        base_url = "https://apix.cisco.com/supporttools/eox/rest/5/EOXByProductID/1/"
        headers = {
            "Authorization": f"Bearer {get_cisco_access_token()}",
            "Accept": "application/json",
        }
        batch_size = 20
        batches = [device_details[i:i + batch_size] for i in range(0, len(device_details), batch_size)]
        query_batches = [','.join(batch) for batch in batches]

        eox_data = {}
        
        for devices in query_batches:
            logging.info(f'Fetching EoX milestone information for Device: {devices}')
            response = requests.get(f"{base_url}{devices}", headers=headers, timeout=30)
            logging.debug(f"Response for Device {devices}: {response.status_code}")
            response.raise_for_status()
            data = response.json().get('EOXRecord')
            for information in data:
                if information.get('EndOfSaleDate').get('value') == "":
                    eox_data[information.get('EOXInputValue')] = [False, 'Not Announced']
                else:
                    eox_data[information.get('EOLProductID')] = [True, {
                        'End-of-Sale Date: HW': information.get('EndOfSaleDate').get('value'),
                        'Last Date of Support: HW': information.get('LastDateOfSupport').get('value'),
                        'End of Routine Failure Analysis Date:  HW': information.get('EndOfRoutineFailureAnalysisDate').get('value'),
                        'End of Vulnerability/Security Support: HW': information.get('EndOfSecurityVulSupportDate').get('value'),
                        'End of SW Maintenance Releases Date: HW': information.get('EndOfSWMaintenanceReleases').get('value'),
                    }]

        logging.info(f'EoX milestone information fetched successfully for {len(device_details)} devices!')

    except Exception as e:
        logging.error(f"Error occurred: {e}")
        return None

    return eox_data


# Function to obtain all software milestones
def software_milestones(device_details):
    """Your existing function - already optimized with concurrent calls"""
    try:
        # Get token first (required for other calls)
        token = get_cisco_access_token()
        
        if not token:
            logging.error("Failed to get Cisco access token")
            return None
        
        # Prepare parameters for concurrent calls
        device_keys = list(device_details.keys())
        
        # Execute API calls concurrently using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:  # Cisco API rate limits
            # Submit all API calls concurrently
            future_to_call = {
                executor.submit(get_software_suggestions, token, device_keys): 'suggestions',
                executor.submit(get_software_eos, token, device_details): 'eos', 
                executor.submit(get_compatible_software, token, device_keys): 'compatible',
                executor.submit(software_deferred_check, token, device_details): 'deferred'
            }
            
            # Collect results as they complete
            results = {}
            for future in as_completed(future_to_call):
                call_type = future_to_call[future]
                try:
                    result = future.result(timeout=30)  # 30 second timeout per call
                    results[call_type] = result
                    logging.debug(f"{call_type} API call completed successfully")
                except Exception as e:
                    logging.error(f"{call_type} API call failed: {e}")
                    results[call_type] = None
        
        # Build software_milestone dictionary from results
        software_milestone = {}
        
        # Process suggestions data
        if results.get('suggestions'):
            for pid, suggestions in results['suggestions'].items():
                software_milestone[pid] = {
                    'S/W Suggestion': [s['Suggested S/W Version'] for s in suggestions],
                    'S/W Release Date': [s['Suggested S/W Release Date'] for s in suggestions]
                }
        
        # Process compatible software data
        if results.get('compatible'):
            for pid in results['compatible']:
                if pid in software_milestone:
                    software_milestone[pid].update({'Latest S/W Version': results['compatible'][pid]})
                else:
                    software_milestone[pid] = {'Latest S/W Version': results['compatible'][pid]}
        
        # Process EOS data
        if results.get('eos'):
            software_milestone['S/W EoS Dates'] = results['eos']
        
        # Process deferred data    
        if results.get('deferred'):
            software_milestone['S/W Milestone'] = results['deferred']
        
        logging.info('Software Milestones fetched Successfully with concurrent processing!')
        return software_milestone
        
    except Exception as e:
        logging.error(f"Error fetching software milestone data: {e}")
        return None
    