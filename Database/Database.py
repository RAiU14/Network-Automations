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
    print("Table data =", data)

# function call for entering input and retriving data
enter_data()
table_data()

# commit to database and closing the connection to database
conn.commit()
conn.close()