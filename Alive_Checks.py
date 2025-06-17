import time
import platform
import subprocess
from Connection import net_connect


# To check if the IP Address of the given device is alive using a JumpHost
def jp_device_check(device_ip):
    repeater, repeat_counter = False, 2
    try:
        while not repeater:
            ping_result = net_connect.send_command_timing(command_string=f"ping -c 5 {device_ip}", read_timeout=120.0, last_read=2.0)
            # Using Unix like terminal. This uses ping is lower case. Where as Windows uses upper. 
            if 'ping statistics' not in ping_result:
                time.sleep(5)
                long_ping = net_connect.read_channel_timing(max_loops=10, last_read=10, read_timeout=120)
                long_ping_res = long_ping[long_ping.find('ping statistics') + 19:]
                loss_count = long_ping_res[long_ping_res.find('received,') + 10:long_ping_res.find('packet loss') - 2]
                repeater = True
                print(f"Pinging to {device_ip} unsuccessful!")
                if int(loss_count) <= 0:
                    return {True: [int(loss_count)]}
                else:
                    return {False: [int(loss_count)]}
                # Sometimes there will be a delay in ping start/response. Maybe the packet loss is less than 100%.
            else:
                ping_info = ping_result[ping_result.find('ping statistics') + 19:]  # 19 is so that the slicing will start from the next line.
                loss_count = ping_info[ping_info.find('received,') + 10:ping_info.find('packet loss') - 2]
                print(f"Pinging to {device_ip} successful!")
                repeat_counter -= 1
                if int(loss_count) <= 0:
                    return {True: [int(loss_count)]}
                else:
                    return {False: [int(loss_count)]}
    except Exception as e:
        print(f"Ping Failed for {device_ip}\nError! {e}")


# To check if devices in the network is responding. 
def alive_check(device_ip):
    repeater, repeat_counter, command = False, 2, platform_check()
    try:
        if command == 'n':
            while not repeater:
                ping_result = subprocess.check_output(f"ping -{platform_check} 4 {device_ip}", universal_newlines=True)
                ping_info = ping_result[ping_result.find('Ping statistics') + 19:]
                loss_count = ping_info[ping_info.find('Lost') + 7: ping_info.find('Lost') + ping_info[ping_info.find('Lost') + 1:].find('(')]
                if int(loss_count) <= 0:
                    return f"Ping Passed for {device_ip}"
                else: 
                    repeater = True
                    repeat_counter -= 1
                    if repeat_counter == 0:
                        return f"Ping Failed for {device_ip}"
    # [Tested on Windows]
        else: 
            while not repeater:
                ping_result = subprocess.check_output(['bash', '-c', f"ping -{platform_check} 5 {device_ip}"], universal_newlines=True)
                ping_info = ping_result[ping_result.find('ping statistics') + 19:]
                loss_count = ping_info[ping_info.find('received,') + 10:ping_info.find('packet loss') - 2]
                if int(loss_count) <= 0:
                    return f"Ping Passed for {device_ip}"
                else: 
                    repeater = True
                    repeat_counter -= 1
                    if repeat_counter == 0:
                        return f"Ping Failed for {device_ip}"
    # [Tested on WSL]
    except subprocess.CalledProcesseError as e:
        print(f'Ping failed: {e} for device {device_ip}')


# Tested the following in Windows and WSL
def platform_check():
    if platform.system().lower == 'windows':
        return 'n' 
    else:   
        return 'c'