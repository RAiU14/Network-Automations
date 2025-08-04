# Necessary imports
import json
import logging
import os
import datetime
import pandas as pd
import bs4
import requests
from langdetect import detect
import re

# Default paths
default_database_path = r"Database\JSON_Files\eox_pid.json"

# Program to perform efficient Web-Scrapping
# Note: This program works as long as the product page from Cisco is not changed~~ 

# Used for logging. 
log_dir = os.path.join(os.path.dirname(__file__), "EOX_logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir,  f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


cisco_url = "https://www.cisco.com"

# This function is used to check the links if permissible and if any necessary changes are required. 
def link_check(link: str) -> str:
    new_link = link
    for url in [cisco_url, "https://www.cisco.com", "//www.cisco.com", "https://cisco.com"]:
        if url in link: 
            new_link = link.replace(url, '')
            logging.debug(f"Link {link} is valid and changed to {new_link}.")
    for bad_url in ["https://help.", "https://supportforums."]:
        if bad_url in link:
            new_link = False
            logging.warning(f"Link {link} is invalid, hence not passed.")
    return new_link

# The flow is linear and similar as to how you open the device details from Cisco Support Page
# This function returns all the available categories from the product page.
def category():
    logging.info("Starting category search process.")
    tech = {}
    for link in bs4.BeautifulSoup(requests.get(f"{cisco_url}/c/en/us/support/all-products.html").text, 'lxml').find("h3", string="All Product and Technology Categories").find_next("table").find_all("a"):
        name = link.text.strip()
        links = link.get('href')
        if name and links:
            tech[name] = links
    logging.debug("Category Search Completed.")
    return tech

# This function is used to open the speific category and obtain device series links for the selected category.
def open_cat(link: str) -> list[dict[str, dict[str, str]]]:
    logging.info(f"Starting Device Gathering Process for category for URL: {cisco_url}{link}.")
    try:
        # The checks are mentioned as such based on the webpage layout as of date.
        list = bs4.BeautifulSoup(requests.get(f"{cisco_url}{link}").text, 'lxml')
        device_list = {'series': {}}
        eox_link = {'eox': {}}
        if list.find(id="allSupportedProducts"):
            # Obtaining all the devices supported from the technology category
            for product in list.find(id="allSupportedProducts").find_all("a"):
                name = product.text.strip()
                links = product.get('href')
                links = link_check(links)
                if name and links:
                    device_list['series'][name] = links  # All the devices in the page which has a link.
            # Obtaining all the devices in EOX List from the WebPage
            # It is evidently found out that the EOX List from the WebPage does not redirect to the appropriate EOX details as of date. Hence, the links returned are that of the product Details Page which will sometimes (if existing) will have the EOL Details. 
            if list.find(id="eos"):
                for devices in list.find(id="eos").find_all("tr"):
                    eox_present = devices.find_all('a')
                    if eox_present:
                        if len(eox_present) > 1:
                            eox_link['eox'][eox_present[0].text.strip()] = eox_present[0].get('href')
                        else:
                            eox_link['eox'][eox_present[0].text.strip()] = eox_present[0].get('href')
                logging.debug("Category Search Completed for Technology with seperate EOX list.")
                return [device_list, eox_link]
            else:
                pass
            logging.debug("Category Search Completed for Technology without available EOX list in the WebPage. Category 1")
            return [device_list]
        elif list.find(id="allDevices"):
            devices_present = list.find(id="allDevices").find(id="alphabetical")
            if devices_present:
                for product in devices_present.find_all('a'):
                    name = product.text.strip()
                    links = product.get('href')
                    links = link_check(links)
                    if name and links:
                        device_list['series'][name] = links
            else:
                divs = list.find_all('div', attrs = {"class": True}, recursive=True, limit=None)
                exact_col_divs = [div for div in divs if div.get('class') == ['col']]
                if len(exact_col_divs) == 1:
                    for product in exact_col_divs[0].find_all('a'):
                        name = product.text.strip()
                        links = product.get('href')
                        links = link_check(links)
                        if name and links:
                            device_list['series'][name] = links
                else:
                    each_item, data = [], []
                    for tags in exact_col_divs:
                        each_item.append(tags.find_all('a'))
                    for item in each_item:
                        data.append(len(item))
                    for things in each_item:
                        if len(things) == max(data):
                            for stuffs in things:
                                name = stuffs.text.strip()
                                links = stuffs.get('href')
                                links = link_check(links)
                                if name and links:
                                    device_list['series'][name] = links 
            logging.debug("Category Search Completed for Technology without available EOX list in WebPage. Category 1 - This might get additional overview details as well.")
            return [device_list]
        elif max(enumerate(list.find_all("div", class_="col full")), key=lambda x: len(x[1]))[1].find_all('ul'):
            if list.find_all('div', class_='productContainers'):
                for product in list.find_all('div', class_='productContainers'):
                    for devices in product.find_all('a'):
                        name = re.sub(r'\s+', ' ', devices.text.strip()).strip()
                        links = devices.get('href')
                        links = link_check(links)
                        if name and links:
                            device_list['series'][name] = links
                logging.debug("Category Search Completed for Technology without available EOX list in WebPage. Category 2 - Which have images.")
                return [device_list]
            # Enumerating and comparing values of series of length to find the appropriate column data. [Above line was shortened using AI for faster execution.]
            elif list.find('div', class_='tech-container'):
                for product in list.find('div', class_='tech-container').find('div', class_="col").find_all('a'):
                    name = product.text.strip()
                    links = product.get('href')
                    links = link_check(links)
                    if name and links:
                        device_list['series'][name] = links
                logging.debug("Category Search Completed for Technology without available EOX list in WebPage. Category 3 - Simple list of multiple devices.")
                return [device_list]
            else:
                for devices in max(enumerate(list.find_all("div", class_="col full")), key=lambda x: len(x[1]))[1].find_all('ul'):  
                    for device in devices.find_all('li'):
                        eol = device.find("img")
                        alt_text = eol.get("alt") if eol else None
                        a_tag = device.find("a")
                        if a_tag:
                            if alt_text == "End of Support" or alt_text == "End of Sale":
                                link = link_check(a_tag.get("href"))
                                eox_link['eox'][a_tag.text.strip()] = link
                            else:
                                link = link_check(a_tag.get("href"))
                                device_list['series'][a_tag.text.strip()] = link
                logging.debug("Category Search Completed for Technology with EOS icons.")
                return [device_list, eox_link]
        else: 
            divs = list.find_all('div', attrs = {"class": True}, recursive=True, limit=None)
            exact_col_divs = [div for div in divs if div.get('class') == ['col']]
            if len(exact_col_divs) == 1:
                for product in exact_col_divs[0].find_all('a'):
                    name = product.text.strip()
                    links = product.get('href')
                    links = link_check(links)
                    if name and links:
                        device_list['series'][name] = links
            else:
                each_item, data = [], []
                for tags in exact_col_divs:
                    each_item.append(tags.find_all('a'))
                for item in each_item:
                    data.append(len(item))
                for things in each_item:
                    if len(things) == max(data):
                        for stuffs in things:
                            name = stuffs.text.strip()
                            links = stuffs.get('href')
                            links = link_check(links)
                            if name and links:
                                device_list['series'][name] = links 
            logging.debug("Category Search Completed for Technology without available EOX list in WebPage. Category 4 - This might get additional overview details as well.")
            return [device_list]
    except Exception as e:
        logging.error(f"An Error Occurred for opening Category URL: {cisco_url}{link}!\n{e}")
        return None

# Checking if EOX is available for selective device in the Product Pages.
def eox_check(link: str) -> list[bool, dict[str, str]]:
    logging.info(f"Starting EOX Redirection Link retreival process for URL: {cisco_url}{link}")
    try:
        logging.debug(f"EOX Redirection Link Completed Successfully!\nURL: {cisco_url}{link}!")
        product_data_table = bs4.BeautifulSoup(requests.get(f'{cisco_url}{link}').text, 'lxml').find_all('table', class_="birth-cert-table")
        if product_data_table:
            if len(product_data_table) >= 2:
                index_value = 1
                if len(product_data_table[index_value].find_all('th')) == 0:
                    index_value = 0
            else:
                index_value = 0
            if product_data_table[index_value].find(class_='eol'):
                EOL_data = {}
                url = product_data_table[index_value].find("tr", class_="birth-cert-status").find('a')
                for item in product_data_table[index_value].find_all('tr'):
                    th = item.find("th")
                    td = item.find("td")
                    if not th or not td:
                            continue
                    label = th.text.strip()
                    if label in ("Series Release Date", "End-of-Sale Date", "End-of-Support Date"):
                        EOL_data[label] = td.text.strip()
                logging.debug(f"Device is still in support\nURL: {cisco_url}{link}")
                if url:
                    link = link_check(url.get('href'))
                    EOL_data['url'] = link
                    logging.debug(f"EOX Link available for EOL device and extracted with URL: {cisco_url}{link}")
                    return [True, EOL_data]
                else:   
                    logging.debug(f"EOX Link unavailable for EOL device hence extracted dates from URL: {cisco_url}{link}")
                    return [False, EOL_data]
            elif product_data_table[index_value].find(class_='eos'):
                url = product_data_table[index_value].find("tr", class_="birth-cert-status").find('a')
                if url:
                    link = link_check(url.get('href'))
                    if link:
                        logging.debug(f"EOX Link available and extracted with URL: {cisco_url}{link}")
                        return [True, {'url': link}]
                    else:
                        EOL_data = {}
                        for item in product_data_table[index_value].find_all('tr'):
                            th = item.find("th")
                            td = item.find("td")
                            if not th or not td:
                                    continue
                            label = th.text.strip()
                            if label in ("Series Release Date", "End-of-Sale Date", "End-of-Support Date"):
                                EOL_data[label] = td.text.strip()
                        logging.debug(f"Device is out of support and EOX link is unavailable! Category 1\nURL: {cisco_url}{link}")
                        return [False, EOL_data]
                else:
                    EOL_data = {}
                    for item in product_data_table[index_value].find_all('tr'):
                        th = item.find("th")
                        td = item.find("td")
                        if not th or not td:
                                continue
                        label = th.text.strip()
                        if label in ("Series Release Date", "End-of-Sale Date", "End-of-Support Date"):
                            EOL_data[label] = td.text.strip()
                    logging.debug(f"Device is out of support and EOX link is unavailable! Category 2\nURL: {cisco_url}{link}")
                    return [False, EOL_data]
            else:
                EOL_data = {}
                if product_data_table[0].find("div", id="microLifecycleBlade"):
                    status = product_data_table[0].find("div", id="microLifecycleBlade").get("class")
                else:
                    status_data = []
                    labels = product_data_table[index_value].find_all('tr')
                    for item in labels:
                        th = item.find("th")
                        td = item.find("td")
                        if not th or not td:
                            continue
                        label = th.text.strip()
                        if ("Status") in label:
                            status_data.append(td.text.strip())
                        else:
                            status_data.append("Unknown")
                for labels in status_data:
                    if "Available" in labels:
                        status = "Available"
                        break
                    else:
                        status = "Unavailable"
                url = product_data_table[index_value].find("tr", class_="birth-cert-status").find('a')
                for item in product_data_table[index_value].find_all('tr'):
                    th = item.find("th")
                    td = item.find("td")
                    if not th or not td:
                            continue
                    label = th.text.strip()
                    if label in ("Series Release Date", "End-of-Sale Date", "End-of-Support Date"):
                        EOL_data[label] = td.text.strip()
                if status == "Available":
                    logging.debug(f"Device status is {str(status).upper()}!\nURL: {cisco_url}{link}")
                    if label in ("Series Release Date", "End-of-Sale Date", "End-of-Support Date"):
                        EOL_data[label] = td.text.strip()
                    return [False, EOL_data]
                if url:
                    link = link_check(url.get('href'))
                    EOL_data['url'] = link
                    logging.debug(f"EOX Link available for {str(status).upper()} device and extracted with URL: {cisco_url}{link}")
                    return [True, EOL_data]
                else:   
                    logging.debug(f"EOX Link unavailable for {str(status).upper()} device hence extracted dates from URL: {cisco_url}{link}")
                    return [False, EOL_data]
        else:
            logging.debug(f"EOX Link is not appropriate!\nURL: {cisco_url}{link}")
            return None
    except Exception as e:
        logging.error(f"An Error Occurred for while retreiving EOX redirection Links!\n{e}")
        return None 

# Obtaining a EOX Links from redirect page.
def eox_details(link: str):
    logging.info("Starting EOX Link retreival process.")
    urls = {}
    try:
        url_check = bs4.BeautifulSoup(requests.get(f'{cisco_url}{link}').text, 'lxml')
        if url_check.find('ul', class_='listing'):
            for links in url_check.find('ul', class_='listing').find_all('li'):
                text = links.find('a').text 
                if detect(text) == 'en':
                    if any(keyword in text for keyword in ["Software", "Release", "IOS"]):
                        continue
                    else:
                        logging.debug(f"EOX Link Retreived successfully!\nURL: {cisco_url}{link}")
                        urls[text.replace("End-of-Sale and End-of-Life Announcement for the Cisco ", "")] = links.find('a').get('href') 
            return urls
        else:
            return False
    except Exception as e:
        logging.error(f"An Error Occurred for while retreiving EOX Link!\n{e}")
        return None

# Obtaining EOX Details and Devices listed for EOX
def eox_scrapping(link: str) -> list[dict[str, str], list[str]]:
    logging.info("Starting EOX data retreival process.")
    eox = {}
    devices = []
    try:
        tables = bs4.BeautifulSoup(requests.get(f'{cisco_url}{link}').text, 'lxml').find_all('table')
        if len(tables) <= 2:
            # Generally, only 2 tables are available in the EOX page.
            index_value = 0
        else:
            index_value = 0
            for values in tables[index_value].find('tbody').find_all('tr'):
                if values.find('td').text.lower().strip() == 'milestone':
                    index_value = index_value
                    break
                else:
                    index_value += 1
        for section in tables[index_value].find('tbody').find_all('tr'):
            column = section.find_all('td')
            eox[column[0].text.strip()] = column[2].text.strip()
        for key in list(eox.keys()):
            if key.lower() == 'milestone':
                del eox[key]
        for device_list in tables[index_value + 1].find('tbody').find_all('tr'):
            devices.append(device_list.find('td').text.strip())
        if devices[0].lower().startswith('end-of-sale product'):
            del devices[0]
        return [eox, devices]
    except Exception as e:
        logging.error(f"An Error Occurred for while retreiving EOX data!\n{e}")
        return None


# Below functions are used to obtain EOX of PIDs
# To get a possible series from PID
def get_possible_series(pid: str) -> list:
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

# Below method is used to search for the PID online. 
# To compare it with the device list from the device category link. 
def find_device_series_link(pid: str, tech: str):
    try:
        data = {}
        available_category = category()
        # Tech has to be the same STR available in category().keys()
        tech_link = available_category[tech]
        all_devices = open_cat(tech_link)
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
            logging.debug(f"Cleaned the PID for matching: {pid} is now {clean_pid}")
            logging.debug(f"Available PIDs: {list(data.keys())}")
            
            # Checking for exact match first
            if pid in data:
                logging.debug(f"Exact match found for PID '{pid}': {data[pid]}")
                return data[pid]

            logging.info("Starting Best Match Logic")
            best_match = max(
                data.keys(), 
                key=lambda k: len(k.replace('-', '').replace(' ', '').upper()) if k.replace('-', '').replace(' ', '').upper() in clean_pid else 0, 
                default=None
            )
            
            if best_match:
                logging.debug(f"Closest best match found for PID '{pid}': {data[best_match]}")
                return data[best_match]
            else:
                logging.debug(f"No good match, returning first available: {list(data.values())[0]}")
                return list(data.values())[0]

        else:
            logging.info(f"No match found for PID '{pid}'")
            return False
    except Exception as e:
        logging.error(f"An Error Occurred while retreving link for {pid}!\n{e}")
        return None  
    
# Function to check if the PID is EOX in the PID Table for the series. 
# Expected input is the PID and the link of the EOX page. 
def pid_eox_check(pid: str, link: str):
    try:
        logging.debug(f"Starting PID_EOX_CHECK for {pid} using link: {link}")
        eox_details = eox_scrapping(link)
        if pid in eox_details[1]:
            logging.info(f"{pid} found in {link}. EOX retrieved!")
            return [True, eox_details[0]]
        else:
            logging.info(f"{pid} not found in {link}. No EOX Available for device!")
            return [False, "Check online"]
    except Exception as e:
        logging.error(f"Unknown Error occurred during PID_EOX_CHECK for {pid}: {e}\nLink Used: {link}")
        
# Function to check EOX details on local database
def request_EOX_data_from_local_db(unique_pid_list, tech, db_path=default_database_path):
    EOX_data = {}
    local_data_loaded = False

    try:
        logging.info(f"Reading local DB: {db_path}")
        with open(db_path, 'r') as f:
            data = json.load(f)
        local_data_loaded = True
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error reading local DB: {e}")
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

    if not local_data_loaded or missing_pids:
        logging.info("Calling online EOX data fetch for missing or all PIDs.")
        online_data = request_EOX_data_from_online(
            unique_pid_list if not local_data_loaded else missing_pids,
            tech,
            existing_data=EOX_data
        )
        return online_data
    else:
        return EOX_data

# Function to scrap data from online
def eox_online_scrapping(pid, tech):
    EOX_data = {}

    logging.info(f"Starting processing for PID: {pid}")

    try:
        step_1 = find_device_series_link(pid, tech)
        logging.debug(f"Step 1 result for PID={pid}: {step_1}")

        step_2 = eox_check(step_1)
        logging.debug(f"Step 2 result for PID={pid}: {step_2}")

        if step_2[0] is False:
            logging.info(f"EOX not announced for PID={pid}")
            EOX_data[pid] = [False, "Not Announced"]
        else:
            step_3 = eox_details(step_2[1]["url"])
            logging.debug(f"Step 3 result for PID={pid}: {step_3}")

            step_4 = list(step_3.values())
            EOX = eox_scrapping(step_4[0])
            logging.info(f"EOX data found for PID={pid}")
            EOX_data[pid] = [True, EOX]

    except Exception as e:
        logging.error(f"Error processing PID={pid}: {e}")
        EOX_data[pid] = [False, f"Error occurred: {str(e)}"]

    logging.info("EOX scraping completed.")
    return EOX_data

# Function to get EOX data from Cisco website.
def request_EOX_data_from_online(unique_pid_list, tech, existing_data=None):
    logging.info(f"Starting EOX pull for PIDs: {unique_pid_list}")
    cleaned_data = existing_data if existing_data else {}

    for pid in unique_pid_list:
        try:
            logging.info(f"Fetching EOX data for PID: {pid}")
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
                    cleaned_data[pid] = value

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
    
# Function to update EOX to raw data with just logs.    
def update_lifecycle_data(data_list, lifecycle_info):
    # Define regex patterns for each canonical field (HW is optional)
    field_patterns = {
        'End-of-Sale Date: HW': r'end\s*[\-:]?\s*of\s*[\-:]?\s*sale\s*[\-:]?\s*date\s*[\-:]?\s*(hw)?',
        'Last Date of Support: HW': r'last\s*[\-:]?\s*date\s*[\-:]?\s*of\s*[\-:]?\s*support\s*[\-:]?\s*(hw)?',
        'End of Routine Failure Analysis Date:  HW': r'end\s*[\-:]?\s*of\s*[\-:]?\s*routine\s*[\-:]?\s*failure\s*[\-:]?\s*analysis\s*[\-:]?\s*date\s*[\-:]?\s*(hw)?',
        'End of Vulnerability/Security Support: HW': r'end\s*[\-:]?\s*of\s*[\-:]?\s*(vulnerability|security)\s*[\-:/]?\s*(security|vulnerability)?\s*[\-:]?\s*support\s*[\-:]?\s*(hw)?',
        'End of SW Maintenance Releases Date: HW': r'end\s*[\-:]?\s*of\s*[\-:]?\s*sw\s*[\-:]?\s*maintenance\s*[\-:]?\s*releases\s*[\-:]?\s*date\s*[\-:]?\s*(hw)?'
    }

    fresh_data = []

    try:
        for index, device_dict in enumerate(data_list):
            logging.info(f"Processing device group {index + 1}")
            updated_dict = {key: list(value) for key, value in device_dict.items()}

            for i, model in enumerate(updated_dict.get('Model number', [])):
                if model in lifecycle_info:
                    logging.info(f"Updating model '{model}' at index {i}")
                    lifecycle_entry = lifecycle_info[model]

                    if isinstance(lifecycle_entry, list):
                        if lifecycle_entry[0] is False:
                            # Not Announced case
                            for canonical_field in field_patterns:
                                if canonical_field in updated_dict and i < len(updated_dict[canonical_field]):
                                    updated_dict[canonical_field][i] = 'Not Announced'
                        elif lifecycle_entry[0] is True and isinstance(lifecycle_entry[1], dict):
                            # Normalize lifecycle data keys
                            normalized_lifecycle_data = {
                                re.sub(r'\s+', ' ', key.strip().lower()): value
                                for key, value in lifecycle_entry[1].items()
                            }

                            for canonical_field, pattern in field_patterns.items():
                                if canonical_field in updated_dict and i < len(updated_dict[canonical_field]):
                                    matched_value = 'Unavailable'
                                    for key in normalized_lifecycle_data:
                                        if re.fullmatch(pattern, key):
                                            matched_value = normalized_lifecycle_data[key]
                                            break
                                    updated_dict[canonical_field][i] = matched_value
                else:
                    logging.warning(f"Model '{model}' not found in lifecycle_info")
                    # If model not found, mark all lifecycle fields as Unavailable
                    for canonical_field in field_patterns:
                        if canonical_field in updated_dict and i < len(updated_dict[canonical_field]):
                            updated_dict[canonical_field][i] = 'Unavailable'

            fresh_data.append(updated_dict)

    except Exception as e:
        logging.error(f"Error during lifecycle update: {e}")

    return fresh_data

 # Controller function to run the whole py file.   
def sub_controller(raw_data, unique_pid, tech):
    lifecycle_info = request_EOX_data_from_local_db(unique_pid, tech)
    complete_data = update_lifecycle_data(raw_data, lifecycle_info)
    print(complete_data)
    return complete_data