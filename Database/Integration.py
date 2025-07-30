# Necessary imports from other modules
import json
import os
import pandas as pd
from openpyxl import Workbook
# from EOX.Cisco_EOX_Scrapper import *
# from EOX.Cisco_PID_Retriever import *
# # from PM_Report.Switching.Cisco 9000 switch import *

# # A Temporary function to simulate the retrieval of a PID and device list
# def temp():
#     category_dict = category()
#     user_choice = "Switches" # Example user choice
#     if user_choice in category_dict:
#         selected_value = category_dict[user_choice]
#         all_devices = open_cat(selected_value)
#         PID = "C9200L-48P-4G" # Example PID
#         return PID, all_devices

# # Function to display available technologies and allow user selection
# def technology():
#     all_technology = category()
#     index = 1
#     for item in all_technology.keys():
#         print(f"{index}. {item}")
#         index += 1
#     key_input = input("Enter Technology: ")
#     if key_input.isdigit() and 1 <= int(key_input) <= len(all_technology):
#         selected_tech = list(all_technology.keys())[int(key_input) - 1]
#         technology_link = (all_technology[selected_tech])
#         print(technology_link)

# # Function to retrieve EOX data based on PID and device link
# def eox_data_scrapping():
#     step_1 = find_device_series_link("C9200L-48P-4G", "Switches")
#     print(f"Step 1: {step_1}")
#     exit()
#     if step_1:
#         step_2 = eox_check(step_1[1])
#     if step_2[0] is False:
#         print("Not Announced")  
#     else:
#         step_3 = eox_details(step_2[1]["url"])
#         step_4 = (list(step_3.values()))
#         EOX, pid_list = (eox_scrapping(step_4[0]))
#         print("EOX: \n", EOX,"\n", "\nPID List: ", pid_list)

#     # Load existing JSON database
#         path = r""
#         with open(path, "r") as f:
#             pid_db = json.load(f)

#         # Update database
#         for pid in pid_list:
#             if pid not in pid_db:
#                 pid_db[pid] = EOX

#         # Save updated database
#         with open(path, "w") as f:
#             json.dump(pid_db, f, indent=4)

# # eox_data_scrapping()
# # technology()

# Appending to Excel
# inputs required :- ticket name, data from pm report and eox details.
# way to achieve, create a new excel file with the ticket name and append data to it.
# accept inputs in dictionary format and convert it to a pandas DataFrame.
# then the dictionary keys should be the column names and the values should be the data to be appended.

import os
import pandas as pd

def append_to_excel(ticket_name, data):
    if not ticket_name.endswith('.xlsx'):
        ticket_name += '.xlsx'

    file_path = ticket_name

    column_data = [
        'File name', 'Host name', 'Model number', 'Serial number', 'Interface ip address',
        'Uptime', 'Current s/w version', 'Current SW EOS', 'Suggested s/w ver', 's/w release date',
        'Latest S/W version', 'Production s/w is deffered or not?', 'Last Reboot Reason', 'Any Debug?',
        'CPU Utilization', 'Total memory', 'Used memory', 'Free memory', 'Memory Utilization (%)',
        'Total flash memory', 'Used flash memory', 'Free flash memory', 'Used Flash (%)',
        'Fan status', 'Temperature status', 'PowerSupply status', 'Available Free Ports',
        'End-of-Sale Date: HW', 'Last Date of Support: HW', 'End of Routine Failure Analysis Date: HW',
        'End of Vulnerability/Security Support: HW', 'End of SW Maintenance Releases Date: HW',
        'Any Half Duplex', 'Interface/Module Remark', 'Config Status', 'Config Save Date',
        'Critical logs', 'Remark'
    ]

    # Prepare the new row with 'NA' for missing columns
    row = {col: data.get(col, 'NA') for col in column_data}
    new_df = pd.DataFrame([row])

    if not os.path.exists(file_path):
        new_df.to_excel(file_path, index=False, sheet_name='Sheet1')
    else:
        existing_df = pd.read_excel(file_path, sheet_name='Sheet1', engine='openpyxl')

        # Ensure all expected columns are present
        for col in column_data:
            if col not in existing_df.columns:
                existing_df[col] = 'NA'

        # Reorder and fill missing values with 'NA'
        existing_df = existing_df[column_data]
        existing_df.fillna('NA', inplace=True)

        # Append and save
        updated_df = pd.concat([existing_df, new_df], ignore_index=True)
        updated_df.to_excel(file_path, index=False, sheet_name='Sheet1')

    print(f"Data appended to {file_path}")


# Example usage
if __name__ == "__main__":  
    ticket_name = "example_ticket.xlsx"
    data = {
        'File name': 'example_file3.txt',
        'Host name': 'Switch3',
        'Model number': 'C9200L-48P-4G',
        'Serial number': 
            {'Abcdefffff',
             'Abcdefffff'
            },
        'Interface ip address': '192.168.1.1.45',
        'Uptime': '11 days',
        'Current s/w version': '16.09.01.af',
        "Last Date of Support: HW": "April 30, 2030"
        }
    append_to_excel(ticket_name, data)