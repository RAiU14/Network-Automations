# Necessary imports from other modules
import json
from EOX.Cisco_EOX_Scrapper import *
from EOX.Cisco_PID_Retriever import *

# A Temporary function to simulate the retrieval of a PID and device list
def temp():
    category_dict = category()
    user_choice = "Switches" # Example user choice
    if user_choice in category_dict:
        selected_value = category_dict[user_choice]
        all_devices = open_cat(selected_value)
        PID = "C9200L-48P-4G" # Example PID
        return PID, all_devices

# Function to display available technologies and allow user selection
def technology():
    all_technology = category()
    index = 1
    for item in all_technology.keys():
        print(f"{index}. {item}")
        index += 1
    key_input = input("Enter Technology: ")
    if key_input.isdigit() and 1 <= int(key_input) <= len(all_technology):
        selected_tech = list(all_technology.keys())[int(key_input) - 1]
        technology_link = (all_technology[selected_tech])
        return technology_link

# Function to retrieve EOX data based on PID and device link
def eox_data_scrapping():
    step_1 = find_device_series_link(*temp())
    step_2 = eox_check(step_1[1])
    if step_2[0] is False:
        print("Not Announced")  
    else:
        step_3 = eox_details(step_2[1]["url"])
        step_4 = (list(step_3.values()))
        EOX, pid_list = (eox_scrapping(step_4[0]))
        print("EOX: \n", EOX,"\n", "\nPID List: ", pid_list)

    # Load existing JSON database
        path = r""
        with open(path, "r") as f:
            pid_db = json.load(f)

        # Update database
        for pid in pid_list:
            if pid not in pid_db:
                pid_db[pid] = EOX

        # Save updated database
        with open(path, "w") as f:
            json.dump(pid_db, f, indent=4)

eox_data_scrapping()