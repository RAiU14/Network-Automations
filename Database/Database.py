import sqlite3

conn = sqlite3.connect('EOX.db')
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS EOX (
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

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Table names =", tables)

conn.commit()
conn.close()