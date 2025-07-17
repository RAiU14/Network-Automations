# Cisco_Automations
A set of python program files which can be used smartly and efficiently to make things easier! 

>**Cisco EOX Package**  
> A series of programs that will help you with your program without the need for API. 
> Cisco EOX: WebScrapping Tool to obtain your details EOX Details for devices easily. (Faster than loading the WebPages!)

> **Goal:** To gather End-of-Life (EOX) details about for all Cisco device by passing the product/model number as input — using only **web scraping techniques** (no API required).

> ⚙️ This was developed purely as a **personal/learning project** to help automate tedious manual lookups and speed up engineering workflows.

> ⚠️ **Disclaimer:**  
> This tool is **not affiliated with or endorsed by Cisco**. All data is sourced from publicly available information on Cisco’s website.  
> I do **not take any responsibility** for how this tool is used — especially for **commercial purposes**, product sales, or automation in production environments. Use it at your own discretion and risk.  
> Always validate EOX details directly from [Cisco's official website](https://www.cisco.com) before making any business decisions.
> Use requirements.txt to install all the dependencies for the program to work.
> Cisco PID: A simple program tool to smartly figure out the device series and to check in the product page. 
> [Complete Automation In Progress]
> Known Failure for Device: Cisco ONS 15454 SONET Multiservice Provisioning Platform (MSPP)
> For some reason, this is the only page which is different in entire Cisco Domain. 
> Something not working? Let me know!
> Sample.py shows how you can use both the program. 
[Broken, WIP on a new Sample under Database\auto_pop.py]


>**Connection.py**  
> Has the necessary snippet to connect to the network to run the netmiko commands.

>**Log_Capture.py**  
> Gather logs from a cisco switches (devices) in bulk amount, by passing the IP Address and the required show commands.
> The logs files will be saved by the device hostname.


>**Alive_Checks.py**  
> [Uses inbuilt Python Functions]
> Have a bulk load of devices to verify if they are connected to the network and up?
> Performing a simple OS check before pinging the device or devices. 
> You can use the provided functions to simply check for their remote reachability status with or without the jumphost. 

>**Database Directory**
> Created two files, Database.py and EOX.db
> Database.py is coded to take input from the user, the user input is set as primary key.
> Based on the user input, data associated to the primary key is fetched from the databse EOX.db and displayed as output to the user.
> Added few extra lines of code to the same Database.py file to achieve the results which were obtained through database/SQL, but by using CSV file.
> Added few extra lines of code to the same Database.py file to achieve the results which were obtained through database/SQL, but by using json.
> Revisted the SQL section to add the edit functionality to the existing data in a table.
> Edited retrieve function of SQL section to accomodate visually appealing and easy to read output format.

> Further edits staged to implement edit functionality in the CSV section.
[WIP]

> auto_pop.py  
A program to automatically retreive all available data from Cisco Portal. 
[Working with 1 known failure. Addressed above!]

**PM_Report folder**
> Contails python scripts to gather Health parameters of Network applaince based on individual technology and vendor.
> Currently, sripts are in phase 1 i.e., need further enhancement.
> Provides basic information by analysing log data, and marks unavailable data as 'NA'
> Further information will be available as the progression contunues - [WIP]
> what si working? known errors? what is pending?



Note: The .gitignore file have been created with the help of gitignore.io website