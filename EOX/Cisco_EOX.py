import json
from .Cisco_EOX_Scrapper import *
from .Cisco_PID_Retriever import *

def local_db_check(pid):
    with open("", "r") as file:
        data = json.load(file)
    if pid in data.keys():
        return data[pid]
    else:
        return False

print(local_db_check("C1000-16FP-2G-L"))
print(local_db_check("9800"))
