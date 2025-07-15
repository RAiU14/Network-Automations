import bs4
import requests
from langdetect import detect
import logging
import datetime
import os
import re
# Program to perform efficient Web-Scrapping
# Note: This program works as long as the product page from Cisco is not changed~~ 

# Used for logging. 
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir,  f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


cisco_url = "https://www.cisco.com"

# This function returns all categories from the product page.
def category() -> dict[str, str]:
    logging.info("Starting category search process.")
    tech = {}
    for link in bs4.BeautifulSoup(requests.get(f"{cisco_url}/c/en/us/support/all-products.html").text, 'lxml').find("h3", string="All Product and Technology Categories").find_next("table").find_all("a"):
        name = link.text.strip()
        links = link.get('href')
        if name and links:
            tech[name] = links
    logging.debug("Category Search Completed.")
    return tech

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
            logging.warning(f"Link {link} is not valid, hence not passed.")
    return new_link


# This function is used to obtain device series related links from the category.
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


# Checking if EOX is available for selective URL pages.
def eox_check(link: str) -> list[bool, dict[str, str]]:
    logging.info(f"Starting EOX Redirection Link retreival process for URL: {cisco_url}{link}")
    try:
        logging.debug(f"EOX Redirection Link Completed Successfully!\nURL: {cisco_url}{link}!")
        product_data_table = bs4.BeautifulSoup(requests.get(f'{cisco_url}{link}').text, 'lxml').find('table', class_="birth-cert-table")
        if product_data_table.find(class_='eol'):
            EOL_data = {}
            for item in product_data_table.find_all('tr'):
                th = item.find("th")
                td = item.find("td")
                if not th or not td:
                        continue
                label = th.text.strip()
                if label in ("Series Release Date", "End-of-Sale Date", "End-of-Support Date"):
                    EOL_data[label] = td.text.strip()
            logging.debug(f"Device is still in support\nURL: {cisco_url}{link}")
            return [False, EOL_data]
        elif product_data_table.find(class_='eos'):
            url = product_data_table.find("tr", class_="birth-cert-status").find('a')
            if url:
                link = link_check(url.get('href'))
                logging.debug(f"EOX Link available and extracted with URL: {cisco_url}{link}")
                return [True, link]
            else:
                EOL_data = {}
                for item in product_data_table.find_all('tr'):
                    th = item.find("th")
                    td = item.find("td")
                    if not th or not td:
                            continue
                    label = th.text.strip()
                    if label in ("Series Release Date", "End-of-Sale Date", "End-of-Support Date"):
                        EOL_data[label] = td.text.strip()
                logging.debug(f"Device is out of support and EOX link is unavailable!\nURL: {cisco_url}{link}")
                return [False, EOL_data]
        else:
            EOL_data = {}
            for item in product_data_table.find_all('tr'):
                th = item.find("th")
                td = item.find("td")
                if not th or not td:
                        continue
                label = th.text.strip()
                if label in ("Series Release Date", "End-of-Sale Date", "End-of-Support Date"):
                    EOL_data[label] = td.text.strip()
            logging.debug(f"Device is still in support and EOX is not accounced.\nURL: {cisco_url}{link}")
            return [False, EOL_data]
    except Exception as e:
        logging.error(f"An Error Occurred for while retreiving EOX redirection Links!\n{e}")
        return None 

# Known Failure for Device: Cisco Nexus 1000V Switch for VMware vSphere
# For some reason, this is the only page which is different in entire Cisco Domain. 

# Obtaining a EOX Links
def eox_details(link: str) -> dict:
    logging.info("Starting EOX Link retreival process.")
    urls = {}
    try:
        for links in bs4.BeautifulSoup(requests.get(f'{cisco_url}{link}').text, 'lxml').find('ul', class_='listing').find_all('li'):
            text = links.find('a').text 
            if detect(text) == 'en':
                if "Software" in text:
                    continue
                else:
                    logging.debug(f"EOX Link Retreived successfully!\nURL: {cisco_url}{link}")
                    urls[text.replace("End-of-Sale and End-of-Life Announcement for the Cisco ", "")] = links.find('a').get('href') 
        return urls
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
        for section in tables[0].find('tbody').find_all('tr'):
            column = section.find_all('td')
            eox[column[0].text.strip()] = column[2].text.strip()
        for key in list(eox.keys()):
            if key.lower() == 'milestone':
                del eox[key]
        for device_list in tables[1].find('tbody').find_all('tr'):
            devices.append(device_list.find('td').text.strip())
        return [eox, devices]
    except Exception as e:
        logging.error(f"An Error Occurred for while retreiving EOX data!\n{e}")
        return None
