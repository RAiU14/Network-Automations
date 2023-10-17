import netmiko
import credentials  # This is a custom python file which has a dictionary of device with jump-host details and necessary credentials
import time

device = credentials.device
# device = {
#     'device_type': '',
#     'ip': '',  # Jump-host IP Address
#     'username': '',
#     'password': '',
#     'port': 22
# }
tacas = credentials.Credentials
net_connect = netmiko.ConnectHandler(**device)  # Connecting to the Jump-host


# To save the output in the file
def save_data(filename, output):
    with open(f'{filename}.log', 'a+') as f:
        f.write(output)


# To check if the IP Address of the given device is alive
def device_a_check(device_ip):
    print(f"Pinging {device_ip}")
    repeater, repeat_counter, packet_loss, long_ping_packet_res, e_msg = False, 2, "0", "0", None
    try:
        while not repeater:
            ping_result = net_connect.send_command_timing(command_string=f"ping -c 5 {device_ip}", read_timeout=120.0, last_read=2.0)
            if 'ping statistics' not in ping_result:
                time.sleep(15)
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


# Gathering device details
def exec_command(ip_address, commands):
    try:
        flag = False
        while not flag:
            net_connect.write_channel(f"ssh -l {tacas['TACAS Username']} {ip_address}\n")  # Logging into the switch
            output = net_connect.read_channel_timing(read_timeout=10.0, max_loops=2, last_read=2.0)
            # Logging into a device for the first time.
            if 'RSA key' in output:
                net_connect.write_channel("yes\n")  # Saving new RSA Key
                new_output = net_connect.read_channel_timing(read_timeout=10.0, max_loops=2, last_read=2.0)
                if 'password' in new_output:
                    net_connect.write_channel(f"{tacas['TACAS Password']}\n")
                    flag = True

            elif 'password' in output:  # Checking if the string is present in the output displayed
                net_connect.write_channel(f"{tacas['TACAS Password']}\n")  # Entering password
                if 'password' in net_connect.read_channel_timing(read_timeout=10.0, max_loops=2, last_read=2.0):  # I did not check this
                    net_connect.disconnect()  # Disconnecting due to wrong password entry
                    print(f'Error occurred while trying to log into device, wrong credentials entered for device with IP Address {ip_address}!')
                    flag = False
                else:
                    flag = True

            elif 'NASTY!' in output:
                # This is such that, if the RSA key of that device or from the current PC is changed, then it has to be regenerated.
                net_connect.write_channel(f'ssh-keygen - R {ip_address}\n')
                flag = False

            else:
                print(f'Unknown occurred while trying to log into device {ip_address}!')
                net_connect.write_channel("\x03")
                time.sleep(2)
                flag = True

        netmiko.redispatch(net_connect, device_type='cisco_ios')  # Necessary to communicate with Cisco IOS devices.
        output = net_connect.send_multiline(commands)
        switch_hostname = str(net_connect.find_prompt())[:-1]  # Obtaining the device hostname.
        net_connect.write_channel('logout\n')
        save_data(switch_hostname, output)
        print(f'Logs collected for - {switch_hostname}')
        time.sleep(2)

    except Exception as e:
        print(f'Error occurred!\n{e}')


def main():
    cmd_input, invalid_commands, commands, ip_addresses, list_of_healthy_ip, list_of_unhealthy_ip = [], [], [], [], [], []
    print("Enter a list of commands to be executed (hit enter after each commands), hit enter key after final command and press CTRL + D (CTRL + Z and enter key) to finish your input.\n[Only show commands]")
    # For VS Code, give CTRL + Z and then hit entre.
    var = input()
    while var != '':
        cmd_input.append(var)
        var = input()

    for item in cmd_input:
        if not item.startswith("show"):
            invalid_commands.append(item)
        else:
            commands.append(item)
    if len(invalid_commands) != 0:
        print(f"The following commands are invalid and will not be executed: {invalid_commands}")
    print(f"Executing the following commands: {commands}")

    # List of commands to be executed on the switch/cisco device.
    print("Enter a list of IPs, hit enter key after final command and press CTRL + D (CTRL + Z and enter key) to finish your input.")

    ip_input = input()
    while ip_input != '':
        ip_addresses.append(ip_input)
        ip_input = input()

    for item in ip_addresses:
        boole = device_a_check(item)
        if True in boole:
            list_of_healthy_ip.append(item)
        else:
            list_of_unhealthy_ip.append(item)

    if list_of_unhealthy_ip:
        print(f'These IP are unreachable:\n{list_of_unhealthy_ip}')

    for item in list_of_healthy_ip:
        exec_command(item, commands)


main()
