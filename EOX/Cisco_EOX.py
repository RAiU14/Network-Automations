import bs4
import re
import requests

# Note: This program works as long as the product page from Cisco is not changed~~ 
cisco_url = "https://www.cisco.com"

# This function returns all categories from the product page.
def category():
    tech = {'category': {}}
    title = bs4.BeautifulSoup(requests.get(f"{cisco_url}/c/en/us/support/all-products.html").text, 'lxml').find("h3", string="All Product and Technology Categories").find_next("table").find_all("a")
    for link in title:
        name = link.text.strip().lower()
        links = link.get('href')
        if name and links:
            tech['category'][name] = links
    return tech

# This function is used to obtain device series related links from the category.
# Expected Arguments are - "wireless, switches, routers, security, unified communications" as of now. 
# This will be removed for seamless execution later. 
def open_cat(tech: str):
    try:
        # The checks are mentioned as such based on the webpage layout as of date.
        if tech == 'wireless' or tech == 'unified communications' or tech == 'security':
            device_list = {'series': {}}
            eox_link = {'eox': {}}
            list = bs4.BeautifulSoup(requests.get(f"{cisco_url}{category()['category'][tech]}").text, 'lxml')
            # Obtaining all the devices supported from the technology category
            series = list.find(id="allSupportedProducts").find_all("a")
            for product in series:
                name = product.text.strip()
                links = product.get('href')
                if name and links:
                    device_list['series'][name] = links  # All the devices in the page which has a link.
            # Obtaining all the devices in EOX List from the WebPage
            # It is evidently found out that the EOX List from the WebPage does not redirect to the appropriate EOX details as of date. Hence, the links returned are that of the product Details Page which will sometimes (if existing) will have the EOL Details. 
            eox_list = list.find(id="eos").find_all("tr")
            for devices in eox_list:
                eox_present = devices.find_all('a')
                if eox_present:
                    if len(eox_present) > 1:
                        eox_link['eox'][eox_present[1].text.strip()] = eox_present[1].get('href')
                    else: 
                        eox_link['eox'][eox_present[0].text.strip()] = eox_present[0].get('href')
            return [device_list, eox_link]
        else:
            device_list = {'series': {}}
            eox_link = {'eox': {}}
            list = max(enumerate(bs4.BeautifulSoup(requests.get(f"{cisco_url}{category()['category'][tech]}").text, 'lxml').find_all("div", class_="col full")), key=lambda x: len(x[1]))[1].find_all('ul') # Enumerating and comparing values of series of length to find the appropriate column data
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
            return [device_list, eox_link]
    except Exception as e:
        print(f'Error occurred {e}')
        return None


# Obtaining the next Link for EOX from the Product Page. 
def eox_link_extract(link: str):
    try:
        return bs4.BeautifulSoup(requests.get(f'{link}').text, 'lxml').find('table', class_="birth-cert-table").find("tr", class_="birth-cert-status").find('a').get('href')
    except Exception as e:
        print(f'Error occurred {e}')
        return None 
# Possible integration to open_cat(x)


# Obtaining a list EOX Links
# Different possibilites to filter down URL to be added later.
def eox_details(link: str):
    urls = []
    language = False
    try:
        sections = bs4.BeautifulSoup(requests.get(f'{link}').text, 'lxml').find('ul', class_='listing').find_all('ul')
        for titles in sections:
            title = titles.find('div', class_='heading')
            if title and title.text == 'English':  # Possibility 1
                links = titles.find_all('li')
                for link in links: 
                    urls.append(link.find('a').get('href'))
        return urls
    except Exception as e:
        print(f'Error occured {e}')
        return None

# print(eox_details('https://www.cisco.com/c/en/us/products/switches/catalyst-1000-series-switches/eos-eol-notice-listing.html'))
print(len(eox_details('https://www.cisco.com/c/en/us/products/switches/nexus-5000-series-switches/eos-eol-notice-listing.html')))
exit()


# Below code is unmodified and requires further testing and modifications.
cisco_url = "https://www.cisco.com"

cisco_wireless_url = f"{cisco_url}/c/en/us/support/wireless/index.html"
html_element = requests.get(cisco_wireless_url).text
list_page_soup = bs4.BeautifulSoup(html_element, 'lxml')


def get_device_list():  # Getting the list of devices in the support page
    numbered_device, alpha_device = {}, {}

    numbered_list = list_page_soup.find(id="prodByNumber")
    list_items = numbered_list.find_all("li")
    for n_devices in list_items:
        urls = n_devices.find_all("a")
        for url in urls:
            numbered_device[(int(n_devices.span.text), url.text)] = url['href']

    alpha_list = list_page_soup.find(id="prodByAlpha")
    list_items = alpha_list.find_all("li")
    for a_devices in list_items:
        alpha_device[a_devices.a.text] = a_devices.a['href']

    return [numbered_device, alpha_device]


def get_eol_status(new_url):
    try:
        dev_details_page = requests.get(new_url).text
        detail_page_soup = bs4.BeautifulSoup(dev_details_page, 'lxml')
        required_box = detail_page_soup.find("div", "data-wrapper")
        status = required_box.find("tr", "birth-cert-status").td.text.strip()
        if "End of Sale" in status:
            eol_link = required_box.find("tr", "birth-cert-status").a['href']
        else:
            print("Device EOL not announced yet, product is still Available!")
            eol_link = False
    except AttributeError:
        print("EOL Data unavailable!\nExiting...")
        eol_link = False

    return eol_link


def getting_eox_link(eol_link):
    data_sheet_link = ""

    try:
        next_page = requests.get(cisco_url + eol_link).text
        next_page_soup = bs4.BeautifulSoup(next_page, 'lxml')
        searching_eol = next_page_soup.find("div", "lll-cq base-blowout")
        # The above is not always available!
        all_list = searching_eol.find_all("li")
        for item in all_list:
            if "End-of-Sale" in item.text:
                data_sheet_link = item.a['href']
                break
            else:
                print("No forwarding link found!\nExiting...")
                data_sheet_link = False

    except AttributeError:
        print(f"Data unavailable in {cisco_url + eol_link}\nContinuing...")
        data_sheet_link = False

    finally:
        if data_sheet_link:
            eox_url = cisco_url + data_sheet_link
            if "-fr" in eox_url:
                eox_url = eox_url[:-8] + ".html"
            else:
                pass
        else:
            # print("No EOS link found!\n")
            eox_url = False

    return eox_url


def get_eox_data(eox_url, search_input):
    eox_data = {}
    available_title, data, device_list = [], [], []

    final_page = requests.get(eox_url).text
    detail_page_soup = bs4.BeautifulSoup(final_page, 'lxml')
    table_data = detail_page_soup.find_all("table")

    for item in table_data:
        available_title.append(item.find("thead").text.strip().split())

    for item in table_data:
        curr_table = []
        for tr in item.find("tbody").find_all("tr"):
            row_data = []
            for td in tr.find_all("td"):
                row_data.append(td.p.text)
            curr_table.append(row_data)
        data.append(curr_table)

    for item in data[0]:
        eox_data[item[0]] = item[2]

    for item in data[1]:
        device_list.append(item[0])

    if search_input in device_list:
        return eox_data
    else:
        print(f"Device not found in the list on site: {eox_url}")
        eox_data = False
        return eox_data


def get_eox(url, search_input):
    data = {}
    eol_link = get_eol_status(url)
    if eol_link:
        eox_url = getting_eox_link(eol_link)
        if eox_url:
            eox_data = get_eox_data(eox_url, search_input)
            if eox_data:
                data['status'] = True
                data['eox'] = eox_data
            else:
                data['status'] = False
                data['eox'] = {'Message': 'No EOX Data found in the data sheet!'}
            return data
        else:
            data['status'] = False
            data['eox'] = {'Message': 'No EOX URL found!'}
        return data
    else:
        data['status'] = False
        data['eox'] = {'Message': 'No EOL Data found'}
    return data


def main():
    device_number, search_inp, new_url, data_sheet_link = "", "", "", ""
    next_url, numbered = [], []
    found_any = False
    numbered_device = get_device_list()[0]
    alpha_device = get_device_list()[1]

    search_input = input("Device Name:")

    if search_input:
        try:
            numbers = re.findall(r'\d+', search_input)
            [numbered.append(int(devices)) for devices in numbers]
            device_number = max(numbered)
        except ValueError:
            exit()
    elif search_input == '':
        exit()
    else:
        try:
            device_number = int(search_input)
        except ValueError:
            pass

    # Test
    if device_number:
        try:
            search_inp = int(device_number)
        except ValueError:
            pass

        for key in numbered_device.keys():
            if type(search_inp) is int:
                if key[0] == search_inp:
                    found_any = True
                    next_url.append([key[1], numbered_device[key]])
                    # print(f"{key[1]}: {numbered_device[key]}")

            elif type(search_inp) is str:
                if key[1].find(search_inp) >= 0:
                    found_any = True
                    next_url.append([key[1], numbered_device[key]])
                    # print(f"{key[1]}: {numbered_device[key]}")

        if not found_any:
            search_inp = str(search_inp)[:2]
            for key in numbered_device.keys():
                if str(key[0]).find(search_inp) >= 0:
                    found_any = True
                    next_url.append([key[1], numbered_device[key]])
                    # print(f"{key[1]}: {numbered_device[key]}")

    else:
        for key in alpha_device.keys():
            if str(key).find(search_inp) >= 0:
                found_any = True
                next_url.append([key, alpha_device[key]])
                # print(f"{key}: {alpha_device[key]}")

    # Obtain the next URL to check the EOL details
    if not found_any:
        print("Device is not found in the support list!\nExiting...")
        exit()
    else:
        if len(next_url) > 1:
            for devices in next_url:
                new_url = cisco_url + devices[1]
                eox_data = get_eox(new_url, search_input)
                if eox_data['status']:
                    print(eox_data['eox'])
                else:
                    pass
        else:
            # print(f"Checking for device details in {next_url[0][0]} list!")
            new_url = cisco_url + next_url[0][1]
            eox_data = get_eox(new_url, search_input)
            if eox_data['status']:
                print(eox_data['eox'])
            else:
                pass


if __name__ == '__main__':
    main()
