import time
import platform
import asyncio
import subprocess
import logging
from Connection import net_connect

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# To check if the IP Address of the given device is alive using a JumpHost
def jp_device_check(device_ip):
    """Checks if a device is alive via JumpHost using Netmiko."""
    repeater, repeat_counter = False, 2
    try:
        while not repeater:
            ping_result = net_connect.send_command_timing(
                command_string=f"ping -c 5 {device_ip}", 
                read_timeout=120.0, 
                last_read=2.0
            )
            if 'ping statistics' not in ping_result:
                time.sleep(5)
                long_ping = net_connect.read_channel_timing(max_loops=10, last_read=10, read_timeout=120)
                if 'ping statistics' in long_ping:
                    long_ping_res = long_ping[long_ping.find('ping statistics') + 19:]
                    loss_count = long_ping_res[long_ping_res.find('received,') + 10:long_ping_res.find('packet loss') - 2]
                    logger.info(f"Pinging to {device_ip} successful after retry!")
                    return {int(loss_count) <= 0: [int(loss_count)]}
                
                logger.warning(f"Pinging to {device_ip} unsuccessful!")
                repeater = True
                return {False: [100]} # Assume 100% loss if statistics missing
            else:
                ping_info = ping_result[ping_result.find('ping statistics') + 19:]
                loss_count = ping_info[ping_info.find('received,') + 10:ping_info.find('packet loss') - 2]
                logger.info(f"Pinging to {device_ip} successful!")
                return {int(loss_count) <= 0: [int(loss_count)]}
    except Exception as e:
        logger.error(f"Ping Failed for {device_ip} via JumpHost: {e}")
        return {False: [e]}


# To check if devices in the network is responding using system ping
async def async_ping(device_ip):
    """Asynchronous ping for a single device."""
    command_flag = platform_check()
    count_flag = f"-{command_flag}"
    
    # Construct command for Windows vs Unix
    if command_flag == 'n': # Windows
        cmd = ["ping", count_flag, "4", device_ip]
    else: # Unix/WSL
        cmd = ["ping", count_flag, "4", device_ip]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode().strip()

        if process.returncode == 0:
            return {"ip": device_ip, "status": "Online", "output": output}
        else:
            return {"ip": device_ip, "status": "Offline", "error": stderr.decode()}
    except Exception as e:
        return {"ip": device_ip, "status": "Error", "error": str(e)}

async def async_batch_poll(device_ips):
    """Polls multiple devices concurrently."""
    tasks = [async_ping(ip) for ip in device_ips]
    results = await asyncio.gather(*tasks)
    return results

def alive_check(device_ip):
    """Synchronous wrapper for legacy compatibility."""
    return asyncio.run(async_ping(device_ip))


# Tested the following in Windows and WSL
def platform_check():
    """Returns 'n' for Windows and 'c' for Unix-like systems."""
    if platform.system().lower() == 'windows':
        return 'n'
    else:
        return 'c'