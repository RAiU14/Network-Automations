# Cisco_Automations
A set of python program files which can be used smartly and efficiently to make things easier! 

>**Cisco_EOX.py**  
> 🚨 **Cisco Support/EOX API inaccessible? We got you!**
>
> **Goal:** To gather End-of-Life (EOX) details about for all Cisco device by passing the product/model number as input — using only **web scraping techniques** (no API required).
>
> ⚙️ This was developed purely as a **personal/learning project** to help automate tedious manual lookups and speed up engineering workflows.
>
> ⚠️ **Disclaimer:**  
> This tool is **not affiliated with or endorsed by Cisco**. All data is sourced from publicly available information on Cisco’s website.  
> I do **not take any responsibility** for how this tool is used — especially for **commercial purposes**, product sales, or automation in production environments. Use it at your own discretion and risk.  
> Always validate EOX details directly from [Cisco's official website](https://www.cisco.com) before making any business decisions.
> requirements.txt available.
> [WIP. Everything is a function now and not a package.]

>**Connection.py**  
> Has the necessary snippet to connect to the network to run the netmiko commands.

>**Log_Capture.py**  
> Gather logs from a cisco switches (devices) in bulk amount, by passing the IP Address and the required show commands.
> The logs files will be saved by the device hostname.

>**NX_OS.py**  
> Created to analyse and output the logs to excel sheet for quick understanding and reference. It works in one or multiple files with some constraints. 
[WIP]

>**Alive_Checks.py**  
> [Uses inbuilt Python Functions]
> Have a bulk load of devices to verify if they are connected to the network and up?
> Performing a simple OS check before pinging the device or devices. 
> You can use the provided functions to simply check for their remote reachability status with or without the jumphost. 


>**Database folder**
> Created two files, Database.py and EOX.db
> Database.py is coded to take input from the user, the user input is set as primary key.
> Based on the user input, data associated to the primary key is fetched from the databse EOX.db and displayed as output to the user.
> Added few extra lines of code to the same Database.py file to achieve the results which were obtained through database/SQL, but by using CSV file.
> Added few extra lines of code to the same Database.py file to achieve the results which were obtained through database/SQL, but by using json.
> Revisted the SQL section to add the edit functionality to the existing data in a table.
[WIP]

Note: The .gitignore file have been created with the help of gitignore.io website