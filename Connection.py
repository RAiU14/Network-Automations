import netmiko
from credentials import device


net_connect = netmiko.ConnectHandler(**device)  # Connecting to the Jump-host
# device = {
#     'device_type': '',
#     'ip': '',  # Jump-host IP Address
#     'username': '',
#     'password': '',
#     'port': 22
# }
