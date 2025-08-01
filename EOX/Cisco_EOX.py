import json
import logging
import os
import datetime
import pandas as pd
from EOX.Cisco_EOX_Scrapper import *
from EOX.Cisco_PID_Retriever import *

# Setup logging
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def local_db_check(pid, db_path):
    try:
        with open(db_path, 'r') as f:
            data = json.load(f)
        entry = data.get(pid, False)
        if entry:
            logging.debug(f"Found entry for PID={pid} in local DB.")
            return entry
        else:
            logging.debug(f"No entry for PID={pid} in local DB.")
            technology = "Switches"
            data, pid_list = eox_online_scrapping([pid], technology)

            # Wrap "Not Announced" as a dictionary
            if isinstance(data, str) and data == "Not Announced":
                data = {"EOX": "Not Announced"}

            if isinstance(data, dict):
                new_json({pid: data}, db_path)

            return data
    except (IOError, json.JSONDecodeError) as e:
        logging.error(f"Error reading local DB for PID={pid}: {e}")
        return False

def get_eox_data(pid, db_path):
    return local_db_check(pid, db_path)

def eox_online_scrapping(model_number, specific_technology):
    for model in model_number:
        step_1 = find_device_series_link(model, specific_technology)
        step_2 = eox_check(step_1)
        if step_2[0] is False:
            return "Not Announced", [model]
        elif step_2[0] is True:
            step_3 = eox_details(step_2[1]["url"])
            step_4 = list(step_3.values())
            EOX, pid_list = eox_scrapping(step_4[0])
            return EOX, pid_list

def new_json(new_data_dict, db_path):
    scrap_path = "scrapped_pid.json"

    # Load existing scrapped data
    if os.path.exists(scrap_path):
        with open(scrap_path, "r") as f:
            scrapped_db = json.load(f)
    else:
        scrapped_db = {}

    # Load existing EOX PID DB
    with open(db_path, "r") as f:
        eox_pid_db = json.load(f)

    # Filter out already existing PIDs
    filtered_data = {
        pid: data for pid, data in new_data_dict.items()
        if pid not in eox_pid_db and pid not in scrapped_db
    }

    if filtered_data:
        scrapped_db.update(filtered_data)
        with open(scrap_path, "w") as f:
            json.dump(scrapped_db, f, indent=4)
        logging.info("New PIDs appended to scrapped_pid.json.")
    else:
        logging.info("No new PIDs to append.")

def unique_pid(excel_file_path):
    unextracted = pd.read_excel(excel_file_path, engine="openpyxl")
    column_c_values = unextracted.iloc[0:, 2]
    column_c_values = column_c_values.dropna().astype(str).str.strip()
    unique_values = column_c_values.unique()
    return unique_values.tolist()

def eox_pull(excel_file_path, db_path=None):
    # pid_list = unique_pid(excel_file_path)
    pid_list = ["C1000-16FP-2G-L"]
    results = {}
    for pid in pid_list:
        results[pid] = get_eox_data(pid, db_path)
    return results

# Example usage
if __name__ == "__main__":
    excel_file_path = r"C:\Users\abhi.bs\OneDrive - NTT Ltd\Desktop\Book1.xlsx"
    db_path = r"C:\\Users\\abhi.bs\\OneDrive - NTT Ltd\\Desktop\\(!)\\Repo\\Network-Automations\\Database\\JSON_Files\\eox_pid.json"
    final_result = eox_pull(excel_file_path, db_path)
    print(final_result)
    json.dumps(final_result, indent=4)