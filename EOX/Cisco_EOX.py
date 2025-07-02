import bs4
import requests
from langdetect import detect
import logging
import datetime
from typing import List, Dict
import os
# Program to perform efficient Web-Scrapping
# Note: This program works as long as the product page from Cisco is not changed~~ 

# Used for logging. 
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir,  f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


cisco_url = "https://www.cisco.com"

# This function returns all categories from the product page.
def category():
    logging.info("Starting category search process.")
    tech = {}
    title = bs4.BeautifulSoup(requests.get(f"{cisco_url}/c/en/us/support/all-products.html").text, 'lxml').find("h3", string="All Product and Technology Categories").find_next("table").find_all("a")
    for link in title:
        name = link.text.strip()
        links = link.get('href')
        if name and links:
            tech[name] = links
    logging.debug("Category Search Completed.")
    return tech


# This function is used to obtain device series related links from the category.
def open_cat(link: str):
    logging.info(f"Starting Device Gathering Process for category for URL: {cisco_url}{link}.")
    try:
        # The checks are mentioned as such based on the webpage layout as of date.
        link_check = bs4.BeautifulSoup(requests.get(f"{cisco_url}{link}").text, 'lxml').find(id="allSupportedProducts")
        if link_check:
            device_list = {'series': {}}
            eox_link = {'eox': {}}
            list = bs4.BeautifulSoup(requests.get(f"{cisco_url}{link}").text, 'lxml')
            # Obtaining all the devices supported from the technology category
            for product in list.find(id="allSupportedProducts").find_all("a"):
                name = product.text.strip()
                links = product.get('href')
                if name and links:
                    device_list['series'][name] = links  # All the devices in the page which has a link.
            # Obtaining all the devices in EOX List from the WebPage
            # It is evidently found out that the EOX List from the WebPage does not redirect to the appropriate EOX details as of date. Hence, the links returned are that of the product Details Page which will sometimes (if existing) will have the EOL Details. 
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
            device_list = {'series': {}}
            eox_link = {'eox': {}}
            list = max(enumerate(bs4.BeautifulSoup(requests.get(f"{cisco_url}{link}").text, 'lxml').find_all("div", class_="col full")), key=lambda x: len(x[1]))[1].find_all('ul') # Enumerating and comparing values of series of length to find the appropriate column data
            for devices in list:
                for device in devices.find_all('li'):
                    eol = device.find("img")
                    alt_text = eol.get("alt") if eol else None
                    a_tag = device.find("a")
                    if a_tag:
                        if alt_text == "End of Support" or alt_text == "End of Sale":
                            eox_link['eox'][a_tag.text.strip()] = a_tag.get("href")
                        else:
                            device_list['series'][a_tag.text.strip()] = a_tag.get("href")    
            logging.debug("Category Search Completed for Technology with EOS icons.")
            return [device_list, eox_link]
    except Exception as e:
        logging.error(f"An Error Occurred for opening Category URL: {cisco_url}{link}!\n{e}")
        return None


# Obtaining the next Link for EOX from the Product Page. 
def eox_link_extract(link: str):
    logging.info(f"Starting EOX Redirection Link retreival process for URL: {cisco_url}{link}")
    try:
        logging.debug(f"EOX Redirection Link Completed Successfully!\nURL: {cisco_url}{link}!")
        product_data_table = bs4.BeautifulSoup(requests.get(f'{cisco_url}{link}').text, 'lxml').find('table', class_="birth-cert-table")
        if product_data_table.find('div', class_='eol'):
            EOL_data = {}
            for item in product_data_table.find_all('tr'):
                th = item.find("th")
                td = item.find("td")
                if not th or not td:
                        continue
                label = th.text.strip()
                if label in ("End-of-Sale Date", "End-of-Support Date"):
                    EOL_data[label] = td.text.strip()
            logging.debug(f"Device is still in support\nURL: {cisco_url}{link}")
            return [False, EOL_data]
        elif product_data_table.find('div', class_='eos'):
            EOX_Link = product_data_table.find("tr", class_="birth-cert-status").find('a').get('href')
            logging.debug(f"Link Extracted for URL: {cisco_url}{link}")
            return [True, EOX_Link]
        else:
            EOL_data = {}
            for item in product_data_table.find_all('tr'):
                th = item.find("th")
                td = item.find("td")
                if not th or not td:
                        continue
                label = th.text.strip()
                if label in ("Series Release Date"):
                    EOL_data[label] = td.text.strip()
            logging.debug(f"Device is still in support\nURL: {cisco_url}{link}")
            return [False, EOL_data]
    except Exception as e:
        logging.error(f"An Error Occurred for while retreiving EOX redirection Links!\n{e}")
        return None 


# Obtaining a EOX Links
def eox_details(link: str):
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
def eox_scrapping(link: str):
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
