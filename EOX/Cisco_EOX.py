import json
import logging
import os
import datetime
from Database.Integration import *
from Database import *

path = r"C:\Users\abhi.bs\OneDrive - NTT Ltd\Desktop\(!)\Repo\Network-Automations\Database\Uploads\SVR137436530\metadata.json"

log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir,  f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Class to fetch Cisco EOX data for a given Product ID (PID) by checking the EOX_PID JSON database. No scraping or additional retrievers.
class Cisco_EOX:
    def __init__(self, pid: str, db_path: str = None):
        self.pid = pid
        self.db_path = db_path or r"Mention Path Here"
        logging.debug(f"Initialized Cisco_EOX for PID={self.pid}.")

    def local_db_check(self):
        try:
            with open(self.db_path, 'r') as f:
                data = json.load(f)
            entry = data.get(self.pid, False)
            if entry:
                logging.debug(f"Found entry for PID={self.pid} in local DB.")
                return entry
            else:
                logging.debug(f"No entry for PID={self.pid} in local DB.")
                model_number = self.pid
                # technology = metadata(ticket_number)
                # eox_online_scrapping([model_number], technology) #WIP
                return False
        except (IOError, json.JSONDecodeError) as e:
            logging.error(f"Error reading local DB for PID={self.pid}: {e}")
            return False

    def get_eox_data(self) -> dict:
        return self.local_db_check()
    