import time
import platform
from Connection import net_connect


# To check if the IP Address of the given device is alive
def jump_host_alive_test(device_ip):
    repeater, repeat_counter, packet_loss = False, 2, "0"
    try:
        while not repeater:
            ping_result = net_connect.send_command_timing(command_string=f"ping -c 5 {device_ip}", read_timeout=120.0, last_read=2.0)
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
        print(f"Error! {e}")
        return {False: [int(packet_loss)]}

# WIP
def alive_check(device_ip):
    return

# WIP
def platform_check():
    OS = platform.system()
    return