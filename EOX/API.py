import requests
import json
import logging
from datetime import datetime
import os
import bs4
import re

log_dir = os.path.join(os.path.dirname(__file__), "API_logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir,  f"{datetime.today().strftime('%Y-%m-%d')}.log"), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def get_cisco_access_token():
    try:
        logging.info("Requesting access token.")
        url = "https://id.cisco.com/oauth2/default/v1/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            with open(r'EOX\\Crediability.json', 'r') as json_read:
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
            with open(r'EOX\\Crediability.json', 'w') as json_write:
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
        logging.info(f'Total batches to process: {len(pid_batches)}')
        for pids in pid_batches:
            response = requests.get(f"{url}/{pids}", headers=headers, timeout=30)
            logging.debug(f"Response for PIDs {pids}: {response.status_code}")
            response.raise_for_status()
            sol = response.json()
            for product in sol.get('productList'):
                pid = (product.get('product') or {}).get('basePID')
                suggestions = product.get('suggestions')

                if not pid:
                    logging.info(f'No PID found for product: {product}')
                    continue
                
                normalized = []
                for s in suggestions:
                    if not isinstance(s, dict):
                        continue
                    normalized.append({
                        'Suggested S/W Version': s.get('releaseFormat1'),
                        'Suggested S/W Release Date': s.get('releaseDate')
                    })
                if not normalized:
                    all_results[pid] = []
                elif len(normalized) == 1:
                    all_results[pid] = normalized[0]
                else:
                    all_results[pid] = normalized
                    
    except Exception as e:
        logging.error(f"Error fetching suggested images: {e}")
        return None

    logging.info('Software Suggestion Information fetched successfully.')
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
        last_date_of_support_map = {}

        for record in all_details:
            pb_num = record.get('ProductBulletinNumber')
            if pb_num:
                product_bulletin_set.add(pb_num)
                last_support = record.get('LastDateOfSupport').get('value')
                logging.debug(f'Product Bulletin Number: {pb_num}, Last Date of Support: {last_support}')
                logging.info(f'Performing WebScraping for url: {record.get("LinkToProductBulletinURL")}')
                title = bs4.BeautifulSoup(requests.get(record.get('LinkToProductBulletinURL')).text, 'lxml').find('h1', id='fw-pagetitle').text
                match = re.search(r'\d+\.\d+\.x', title)
                if match:
                    version_number = match.group(0)
                if last_support:
                    last_date_of_support_map[version_number] = last_support
                    
    except Exception as e:
        logging.error(f"Error fetching EoS data: {e}")
        return None
        
    logging.info(f'End of Support (EoS) Information fetched successfully for {devices}')
    return last_date_of_support_map


def get_compatible_software(token, pids):
    try:
        logging.info(f'Fetching compatible software information.')
        # This API URI only works for 1 device at a time. 
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
            response.raise_for_status()
            data = response.json()
            records = data.get('suggestions')
            for image_details in records:
                # The initial few are always suggested.
                if image_details.get('isSuggested') == 'N':
                    device_data[pid] = image_details.get('releaseFormat1')
                    logging.info(f'Compatible software found for PID {pid}: {device_data[pid]}')
                    break
                
    except Exception as e:
        logging.error(f"Error fetching compatible software data: {e}")

    logging.info(f'Compatible software information fetched successfully for {len(pids)} devices!')
    return device_data


def software_deferred_check(token, device_details):
    try:
        logging.info(f'Checking software deferred status.')
        deferred_details = {}
        base_url = 'https://apix.cisco.com/software/v4.0/metadata/pidrelease'
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "outputReleaseVersion": "latest",
            "pageIndex":"1",
            "perPage":"1"
        }
        for devices in device_details:
            payload["pid"] = devices
            for images in device_details[devices]:
                payload['currentReleaseVersion'] = images
                logging.info(f'Checking deferred status for Device: {devices}, Image: {images}')
                response = requests.request("POST", base_url, headers=headers, json=payload)
                if response.status_code == 200:
                    deferred_details[devices] = {images: False}
                    logging.info(f'Software not deferred for Device: {devices}, Image: {images}')
                else:
                    logging.info(f'Software deferred for Device: {devices}, Image: {images}')
                    deferred_details[devices] = {images: True}

    except Exception as e:
        logging.error(f"Error occurred: {e}")
        return None
    
    logging.info('Software deferred status check completed successfully.')
    return deferred_details


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
        all_inputs = list(device_details.keys())

        batches = [all_inputs[i:i + batch_size] for i in range(0, len(all_inputs), batch_size)]
        query_batches = [','.join(batch) for batch in batches]

        eox_data = {}
        
        for devices in query_batches:
            logging.info(f'Fetching EoX milestone information for Device: {devices}')
            response = requests.get(f"{base_url}{devices}", headers=headers, timeout=30)
            logging.debug(f"Response for Device {devices}: {response.status_code}")
            response.raise_for_status()
            data = response.json().get('EOXRecord')
            for information in data:
                eox_data[information.get('EOLProductID')] = {
                    'EndOfSaleDate': information.get('EndOfSaleDate').get('value'),
                    'LastDateOfSupport': information.get('LastDateOfSupport').get('value'),
                    'EndOfRoutineFailureAnalysisDate': information.get('EndOfRoutineFailureAnalysisDate').get('value'),
                    'EndOfSecurityVulSupportDate': information.get('EndOfSecurityVulSupportDate').get('value'),
                    'EndOfSWMaintenanceReleases': information.get('EndOfSWMaintenanceReleases').get('value'),
                }

        logging.info(f'EoX milestone information fetched successfully for {len(device_details)} devices!')

    except Exception as e:
        logging.error(f"Error occurred: {e}")
        return None

    return eox_data


# Function to obtain all software milestones
def software_milestones(device_details):
    try:
        token = get_cisco_access_token()
        software_suggestion_data = get_software_suggestions(token, list(device_details.keys()))
        software_eos_data = get_software_eos(token, device_details)
        latest_software_data = get_compatible_software(token, list(device_details.keys()))
        software_deferred_data = software_deferred_check(token, device_details)

        software_milestone = {}
        
        if software_suggestion_data:
            for pid in software_suggestion_data:
                software_suggestion, software_release_date = [], []
                suggestions = software_suggestion_data[pid]
                for suggestion in suggestions:
                    software_suggestion.append(suggestion['Suggested S/W Version'])
                    software_release_date.append(suggestion['Suggested S/W Release Date'])
                software_milestone[pid] = {
                    'S/W Suggestion': software_suggestion,
                    'S/W Release Date': software_release_date,
                }

        if latest_software_data: 
            for pid in latest_software_data:
                software_milestone[pid].update({'Latest S/W Version': latest_software_data[pid]})
        
        if software_eos_data:
            software_milestone['S/W EoS Dates'] = software_eos_data
            
        if software_deferred_data:
            software_milestone['S/W Milestone'] = software_deferred_data

    except Exception as e:
        logging.error(f"Error fetching software milestone data: {e}")
        return None

    logging.info('Software Milestones fetched Successfully!')
    return software_milestone

if __name__ == "__main__":
    devices = {
        'C9200L-48P-4G-E': ['17.12.5', '16.12.8', '16.11.1', '17.9.6'],
        # 'AIR-CT5508-25-K9': 'Version',
        # 'C9200L-24P-4G': 'Version',
        'C9105AXI-EWC-A': '17.12.5',
        # 'C9130AXI-K': 'Version'
    }
    device = {
        'AIR-CT5508-25-K9' : ['17.12.5', '16.12.8', '16.11.1', '17.9.6']
    }
    # print(eox_milestone(get_cisco_access_token(), device))
    print(software_milestones(devices).json())
    