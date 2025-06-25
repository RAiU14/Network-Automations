# required imports
import sqlite3

# connection to database
conn = sqlite3.connect('EOX.db')
cursor = conn.cursor()

# table creation and defining of its attributes
cursor.execute("""
CREATE TABLE IF NOT EXISTS EOX (
    Device_Model TEXT PRIMARY KEY,
    End_of_Life_Announcement_Date TEXT,
    End_of_Sale_Date_HW TEXT,
    Last_Ship_Date_HW TEXT,
    End_of_SW_Maintenance_Releases_Date_HW TEXT,
    End_of_Vulnerability_Security_Support_HW TEXT,
    End_of_Routine_Failure_Analysis_Date_HW TEXT,
    End_of_New_Service_Attachment_Date_HW TEXT,
    End_of_Service_Contract_Renewal_Date_HW TEXT,
    Last_Date_of_Support_HW TEXT
)
""")

# input to EOX table
def enter_data():
    rows = [
        ('a', 'B', 'C', 'D', 'sdE', '3R', '4F', '3D', '##', 'ef'), #dummy input
        ('b', 'X', 'C', 'D', 'sdE', 'R', 'F', 'D', '3', '2f') #dummy input
    ]
    cursor.executemany("INSERT OR IGNORE INTO EOX VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)

# retriving data from the database    
def table_data():   
    model_number = input("Enter model number = ")
    cursor.execute(("SELECT * FROM EOX WHERE Device_Model = ?"), (model_number))
    data = cursor.fetchall()
    column_names = [description[0] for description in cursor.description]
    for row in data:
        print("\n--Retrived Data--")
        for col_name, value in zip(column_names, row):
            print(f"{col_name}: {value}")

# update existing data    
def update_data():
    model_number = input("Enter model number: ")
    update = input("""Which field do you want to edit?:
        1 - Device_Model
        2 - End_of_Life_Announcement_Date
        3 - End_of_Sale_Date_HW
        4 - Last_Ship_Date_HW
        5 - End_of_SW_Maintenance_Releases_Date_HW
        6 - End_of_Vulnerability_Security_Support_HW
        7 - End_of_Routine_Failure_Analysis_Date_HW
        8 - End_of_New_Service_Attachment_Date_HW
        9 - End_of_Service_Contract_Renewal_Date_HW
        10 - Last_Date_of_Support_HW
        Enter your choice (1-10): """)

    fields = {
        "1": "Device_Model",
        "2": "End_of_Life_Announcement_Date",
        "3": "End_of_Sale_Date_HW",
        "4": "Last_Ship_Date_HW",
        "5": "End_of_SW_Maintenance_Releases_Date_HW",
        "6": "End_of_Vulnerability_Security_Support_HW",
        "7": "End_of_Routine_Failure_Analysis_Date_HW",
        "8": "End_of_New_Service_Attachment_Date_HW",
        "9": "End_of_Service_Contract_Renewal_Date_HW",
        "10": "Last_Date_of_Support_HW"
    }

    if update in fields:
        new_value = input(f"Enter new value for {fields[update]}: ")
        query = f'UPDATE EOX SET "{fields[update]}" = ? WHERE Device_Model = ?'
        cursor.execute(query, (new_value, model_number))
        conn.commit()
        print("Record updated successfully.")
    else:
        print("Invalid choice.")

# function call for entering input and retriving data
enter_data()
table_data()
update_data()

# commit to database and closing the connection to database
conn.commit()
conn.close()

#############################################################################################################################################################################################################

## Trying the same in CSV method.
import csv

csv_file = 'EXO_details.csv'

# Add details to existing CSV
def add_details():
    with open(csv_file, mode="a", newline='') as file:
        writer = csv.writer(file)

        Device_Model = input("Enter Device Model = ")
        End_of_Life_Announcement_Date = input("Enter End of Life Announcement Date = ")
        End_of_Sale_Date_HW = input("Enter End of Sale Date = ")
        Last_Ship_Date_HW = input("Enter Last Ship Date = ")
        End_of_SW_Maintenance_Releases_Date_HW = input("Enter End of SW Maintenance Release Date HW = ")
        End_of_Vulnerability_Security_Support_HW = input("Enter End of Vulnerability support HW = ")
        End_of_Routine_Failure_Analysis_Date_HW = input("Enter Routine Failure Analysis Date HW = ")
        End_of_New_Service_Attachment_Date_HW = input("Enter New Service Attachment Date HW = ")
        End_of_Service_Contract_Renewal_Date_HW = input("Enter End of Service Contract Renewal Date HW = ")
        Last_Date_of_Support_HW = input("Enter Last Date of Support HW = ")

        writer.writerow([
            Device_Model,
            End_of_Life_Announcement_Date,
            End_of_Sale_Date_HW,
            Last_Ship_Date_HW,
            End_of_SW_Maintenance_Releases_Date_HW,
            End_of_Vulnerability_Security_Support_HW,
            End_of_Routine_Failure_Analysis_Date_HW,
            End_of_New_Service_Attachment_Date_HW,
            End_of_Service_Contract_Renewal_Date_HW,
            Last_Date_of_Support_HW
        ])

# Retrieve details by model number
def get_details():
    with open(csv_file, mode="r") as file:
        reader = csv.reader(file)
        headers = next(reader)  # Read the header row

        search_key = input("Enter model number: ").strip()
        found = False

        for row in reader:
            if row[0].strip() == search_key:
                print("\nDevice Details:")
                for header, value in zip(headers, row):
                    print(f"{header}: {value}")
                found = True
                break

        if not found:
            print("No details found")


# Run the functions
choice = input("Press A if you want to add and Press B is you want to retrieve : ")
if choice == "A":
    add_details()
elif choice == "B":
    get_details()
else : 
    print("Wrong input")
    

#############################################################################################################################################################################################################

## Trying the same in json method.
import json
import os

# File to store device lifecycle data
filename = "EOX_details.json"

# Load existing data or initialize empty dictionary
if os.path.exists(filename) and os.path.getsize(filename) > 0:
    with open(filename, "r") as file:
        data = json.load(file)
else:
    data = {}

# Predefined column names
columns = [
    "End_of_Life_Announcement_Date",
    "End_of_Sale_Date_HW",
    "Last_Ship_Date_HW",
    "End_of_SW_Maintenance_Releases_Date_HW",
    "End_of_Vulnerability_Security_Support_HW",
    "End_of_Routine_Failure_Analysis_Date_HW",
    "End_of_New_Service_Attachment_Date_HW",
    "End_of_Service_Contract_Renewal_Date_HW",
    "Last_Date_of_Support_HW"
]

# Add new device details
def add_device_details(Device_Model, *details):
    if Device_Model in data:
        print(f"Model '{Device_Model}' already exists. Model details exist.")
        return

    if len(details) != len(columns):
        print("Error: Incorrect number of details provided.")
        return

    data[Device_Model] = dict(zip(columns, details))
    with open(filename, "w") as file:
        json.dump(data, file, indent=4)
    print(f"Details for '{Device_Model}' added successfully.")

# Retrieve device details
def get_device_details(Device_Model):
    if Device_Model in data:
        print(f"\nModel: {Device_Model}")
        for key, value in data[Device_Model].items():
            print(f"{key}: {value}")
    else:
        print("Model not found.")

# Edit a specific field for a given device model
def edit_device_detail(Device_Model, column_name, new_value):
    if Device_Model not in data:
        print(f"Model '{Device_Model}' not found. Cannot update.")
        return

    if column_name not in columns:
        print(f"Invalid column name: '{column_name}'.")
        print("Valid columns are:")
        for col in columns:
            print(f"- {col}")
        return

    data[Device_Model][column_name] = new_value
    with open(filename, "w") as file:
        json.dump(data, file, indent=4)
    print(f"Updated '{column_name}' for model '{Device_Model}' to '{new_value}'.")
    

# add_device_details("xyz", "1", "2", "3", "4", "5", "6", "7", "8", "9")
# get_device_details("xyz")
# edit_device_detail("xyz", "Last_Date_of_Support_HW", "09")