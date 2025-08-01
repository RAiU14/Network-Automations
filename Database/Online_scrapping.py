# def eox_online_scrapping(model_number, specific_technology):
#     for model in model_number:
#         step_1 = find_device_series_link(model, specific_technology) 
#         step_2 = eox_check(step_1) 
#         if step_2[0] == False:
#             return "Not Announced"
#         elif step_2[0] == True:
#             step_3 = eox_details(step_2[1]["url"])
#             step_4 = (list(step_3.values()))
#             EOX, pid_list = eox_scrapping(step_4[0])
#             new_json(EOX, pid_list)
#             return EOX, pid_list
     
# def new_json(EOX, pid_list):

#     # Load existing EOX PID database
#     with open(r"", "r") as f:
#         eox_pid_db = json.load(f)

#     # Load or initialize scrapped_pid.json
#     scrap_path = "scrapped_pid.json"
#     if os.path.exists(scrap_path):
#         with open(scrap_path, "r") as f:
#             scrapped_db = json.load(f)
#     else:
#         scrapped_db = {}

#     # Append only new entries
#     new_entries = {}
#     for pid in pid_list:
#         if pid not in eox_pid_db and pid not in scrapped_db:
#             new_entries[pid] = EOX

#     # Update and save only if there are new entries
#     if new_entries:
#         scrapped_db.update(new_entries)
#         with open(scrap_path, "w") as f:
#             json.dump(scrapped_db, f, indent=4)
#         print("New PIDs appended to scrapped_pid.json.")
#     else:
#         print("No new PIDs to append.")