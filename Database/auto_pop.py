# Auto Populate Program to Create a JSON Database
from EOX.Cisco_EOX_Scrapper import *
from .json_fun import *
import logging

log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir,  f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class Auto_Pop:
    def __init__(self):
        self.all_available_devices = {}
        self.all_devices = {}
        self.eox_devices = {}
        self.eox_links = {}
        self.eox_data = {}
        self.categories = category()
        
    def load_categories(self):
        for link in self.categories.keys():
            self.all_available_devices[link] = open_cat(self.categories[link])
        logging.debug("Categories loaded successfully.")
        
    def process_devices(self):
        for technology in self.all_available_devices:
            if len(self.all_available_devices[technology]) == 1:
                # Only Series List is Available
                for key in self.all_available_devices[technology][0]['series']:
                    self.all_devices[key] = self.all_available_devices[technology][0]['series'][key]
            else:
                # Both Device List and EOX are available
                for key in self.all_available_devices[technology][0]['series']:
                    self.all_devices[key] = self.all_available_devices[technology][0]['series'][key]
                for key in self.all_available_devices[technology][1]['eox']:
                        self.eox_devices[key] = self.all_available_devices[technology][1]['eox'][key]
        logging.debug(f"Processed {len(self.eox_devices)} EOX devices.")
        
    def scrap_eox_data(self):
        logging.info(f"Starting EOX Scrapping Process for {len(self.eox_devices)} devices.")
        for devices in self.eox_devices:
            url = link_check(self.eox_devices[devices])
            if not url:
                continue
            else:
                eox_links = eox_check(url)
                if eox_links:
                    if not eox_links[0]:
                        self.eox_data[devices] = eox_links[1]
                    else:
                        urls = eox_details(eox_links[1]['url'])
                        if urls:
                            for links in urls:
                                eox = eox_scrapping(urls[links])
                                if eox: 
                                    for dev in eox[1]:
                                        self.eox_data[dev] = eox[0]
        logging.info(f"Total EOX Data Retrieved: {len(self.eox_data)}.")
        
    def obtain(self, output_file='eox_pid.json'):
        logging.info("Starting the EOX Device List Retrieval Process.")
        self.load_categories()
        self.process_devices()
        self.scrap_eox_data()
        
        with open(output_file, 'w') as f:
            logging.info("Writing EOX Data to JSON file.")
            json.dump(self.eox_data, f, ensure_ascii=False, indent=4)
            logging.info("EOX Data written successfully.")
        logging.info("EOX Device List Retrieval Process Completed Successfully.")
