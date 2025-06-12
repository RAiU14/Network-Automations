# Cisco_Automations
A set of python program files which can be used smartly and efficiently to make things easier! 

>**Cisco_EOX.py**  
> A web-scrapping python program to gather EOX details about a device if product/model number of the device is passed as an input.
> Output is not stored anywhere, just displayed. (As of now)
[Broken!]

>**Connection.py**
> Has the necessary snippet to connect to the network to run the netmiko commands.

>**Log_Capture.py**  
> Gather logs from a cisco switches (devices) in bulk amount, by passing the IP Address and the required show commands.
> The logs files will be saved by the device hostname.

>**NX_OS.py**
> Created to analyse and output the logs to excel sheet for quick understanding and reference. It works in one or multiple files with some constraints. 
[WIP]

>**Manual_Alive_Checks.py**
> [Uses inbuilt Python Functions]
> Have a bulk load of devices to verify if they are connected to the network and up?
> Performing a simple OS check before pinging the device. 
> You can use the provided functions to simply check for their remote reachability status with or without the jumphost. 
> Streamlined the code by eliminating two redundant variables.
[WIP]

>**Database folder**
>Created two files, Database.py and EOX.db
>Database.py is coded to take input from the user, the user input is set as primary key.
>Based on the user input, data associated to the primary key is fetched from the databse EOX.db and displayed as output to the user.
[WIP]

[Requirement files will be added later!]

Note: The .gitignore file have been created with the help of gitignore.io website