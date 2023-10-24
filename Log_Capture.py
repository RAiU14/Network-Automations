import netmiko
import traceback
import time
import credentials  # This is a custom python file which has a dictionary of device with jump-host details and necessary credentials [Can be a JSON]
import Ping_Checks
from Connection import net_connect


tacas = credentials.Credentials


# To save the output in the file
def save_data(filename, output):
    with open(f'{filename}.log', 'a+') as f:
        f.write(output)


# Gathering device details
def exec_command(ip_address, commands):
    counter = 1
    while counter < 11:  # Max retries for one IP to retry log capture.
        try:
            flag = False
            while not flag:
                net_connect.write_channel(f"ssh -l {tacas['TACAS Username']} {ip_address}\n")  # Logging into the switch
                output = net_connect.read_channel_timing(read_timeout=1500.0, max_loops=3, last_read=2.0)
                # Logging into a device for the first time.
                if 'RSA key' in output:
                    net_connect.write_channel("yes\n")  # Saving new RSA Key
                    new_output = net_connect.read_channel_timing(read_timeout=1500.0, max_loops=3, last_read=2.0)
                    if 'password' in new_output:
                        net_connect.write_channel(f"{tacas['TACAS Password']}\n")
                        flag = True

                elif 'password' in output:  # Checking if the string is present in the output displayed
                    net_connect.write_channel(f"{tacas['TACAS Password']}\n")  # Entering password
                    if 'password' in net_connect.read_channel_timing(read_timeout=1500.0, max_loops=3, last_read=2.0):  # I did not check this
                        net_connect.disconnect()  # Disconnecting due to wrong password entry
                        print(f'Error occurred while trying to log into device, wrong credentials entered for device with IP Address {ip_address}!')
                        flag = False
                        counter += 1
                    else:
                        flag = True

                elif 'NASTY!' in output:
                    # This is such that, if the RSA key of that device or from the current PC is changed, then it has to be regenerated.
                    net_connect.write_channel(f'ssh-keygen - R {ip_address}\n')
                    counter += 1
                    flag = False

                else:
                    print(f'Unknown occurred while trying to log into device {ip_address}!')
                    net_connect.write_channel("\x03\n\x03")
                    print(traceback.format_exc())
                    time.sleep(2)
                    flag = False
                    counter += 1

            netmiko.redispatch(net_connect, device_type='cisco_ios')  # Necessary to communicate with Cisco IOS devices.
            output = net_connect.send_multiline(commands)
            switch_hostname = str(net_connect.find_prompt())[:-1]  # Obtaining the device hostname.
            net_connect.write_channel('logout\n')
            save_data(switch_hostname, output)
            print(f'Logs collected for - {switch_hostname}')
            time.sleep(2)
            return

        except Exception as e:
            print(f'Error occurred!\n{e}')
            print(traceback.format_exc())

        counter += 1

    print(f"Gathering log for {ip_address} unsuccessful after {counter} attempts, proceeding further...\n")
    return


def main():
    cmd_input, invalid_commands, commands, ip_addresses, list_of_healthy_ip, list_of_unhealthy_ip = [], [], [], [], [], []
    print("Enter a list of IPs, hit enter key twice after final command to finish your input.\n[Only show commands]")
    var = input()
    while var != '':
        cmd_input.append(var)
        var = input().lower()
    for item in cmd_input:
        if not item.startswith("show"):
            invalid_commands.append(item)
        else:
            commands.append(item)
    if len(invalid_commands) != 0:
        print(f"The following commands are invalid and will not be executed: {invalid_commands}")
    print(f"Executing the following commands: {commands}")

    # List of commands to be executed on the switch/cisco device.
    print("Enter a list of commands, hit enter key twice after final command to finish your input.")
    ip_input = input()
    while ip_input != '':
        ip_addresses.append(ip_input)
        ip_input = input()

    # Menu-driven only to ping if necessary.
    print("Do you want to perform ping test for the given IPs? [Yes/y/No/n]")
    response = input().lower()
    while response is not ["yes", "y", "no", "n"]:
        if response in ["yes", "y"]:
            print(f"Pinging {len(ip_addresses)} devices!\n")
            for item in ip_addresses:
                boole = Ping_Checks.ping_test(item)
                if True in boole:
                    list_of_healthy_ip.append(item)
                else:
                    list_of_unhealthy_ip.append(item)

            if list_of_unhealthy_ip:
                print(f'These IP are unreachable:\n{list_of_unhealthy_ip}')

        elif response in ["no", "n"]:
            counter = 1
            for item in ip_addresses:
                exec_command(item, commands)
                print(f"[{counter}/{len(ip_addresses)}]")
                counter += 1
        else:
            print("Please enter a valid choice from the given option which is either 'yes' or 'no'.")
        response = input().lower()


if __name__ == '__main__':
    main()
