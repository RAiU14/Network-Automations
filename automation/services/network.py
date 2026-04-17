"""
Network tool services — consolidated from Alive_Checks.py and Log_Capture.py.
Provides async ping, batch polling, and SSH-based log capture via Netmiko.
"""
import time
import platform
import asyncio
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------
def _platform_flag():
    """Returns 'n' for Windows and 'c' for Unix-like systems."""
    return 'n' if platform.system().lower() == 'windows' else 'c'


# ---------------------------------------------------------------------------
# Async device polling (absorbed from Alive_Checks.py)
# ---------------------------------------------------------------------------
async def async_ping(device_ip: str) -> dict:
    """Asynchronous ping for a single device."""
    flag = _platform_flag()
    cmd = ["ping", f"-{flag}", "4", device_ip]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode().strip()
        if proc.returncode == 0:
            return {"ip": device_ip, "status": "Online", "output": output}
        return {"ip": device_ip, "status": "Offline", "error": stderr.decode()}
    except Exception as e:
        return {"ip": device_ip, "status": "Error", "error": str(e)}


async def async_batch_poll(device_ips: list) -> list:
    """Polls multiple devices concurrently."""
    return await asyncio.gather(*(async_ping(ip) for ip in device_ips))


def alive_check(device_ip: str) -> dict:
    """Synchronous convenience wrapper."""
    return asyncio.run(async_ping(device_ip))


# ---------------------------------------------------------------------------
# JumpHost ping (requires an active Netmiko connection)
# ---------------------------------------------------------------------------
def jp_device_check(net_connect, device_ip: str) -> dict:
    """Checks if a device is alive via JumpHost using Netmiko."""
    try:
        ping_result = net_connect.send_command_timing(
            command_string=f"ping -c 5 {device_ip}",
            read_timeout=120.0,
            last_read=2.0,
        )
        if 'ping statistics' in ping_result:
            info = ping_result[ping_result.find('ping statistics') + 19:]
            loss = info[info.find('received,') + 10 : info.find('packet loss') - 2]
            logger.info(f"Ping to {device_ip} via JumpHost: {loss}% loss")
            return {"ip": device_ip, "loss_pct": int(loss), "reachable": int(loss) <= 0}

        time.sleep(5)
        long_ping = net_connect.read_channel_timing(max_loops=10, last_read=10, read_timeout=120)
        if 'ping statistics' in long_ping:
            info = long_ping[long_ping.find('ping statistics') + 19:]
            loss = info[info.find('received,') + 10 : info.find('packet loss') - 2]
            return {"ip": device_ip, "loss_pct": int(loss), "reachable": int(loss) <= 0}

        logger.warning(f"Ping to {device_ip} unsuccessful via JumpHost")
        return {"ip": device_ip, "loss_pct": 100, "reachable": False}
    except Exception as e:
        logger.error(f"JumpHost ping failed for {device_ip}: {e}")
        return {"ip": device_ip, "loss_pct": 100, "reachable": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Log capture via JumpHost SSH (absorbed from Log_Capture.py)
# ---------------------------------------------------------------------------
def capture_logs(net_connect, ip_address: str, commands: list, save_dir: str = ".") -> dict:
    """
    SSH into a device via JumpHost, run show commands, save output.
    Returns dict with hostname and file path on success.
    """
    import netmiko
    import os

    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            # Attempt SSH login through jumphost
            net_connect.write_channel(f"ssh {ip_address}\n")
            output = net_connect.read_channel_timing(read_timeout=30.0, last_read=2.0)

            if 'password' in output.lower():
                # Password handled by jumphost session context
                pass

            netmiko.redispatch(net_connect, device_type='cisco_ios')
            output = net_connect.send_multiline(commands)
            hostname = str(net_connect.find_prompt()).rstrip('#>')
            net_connect.write_channel('logout\n')

            # Save
            filepath = os.path.join(save_dir, f"{hostname}.log")
            with open(filepath, 'a+') as f:
                f.write(output)
            logger.info(f"Logs captured for {hostname} -> {filepath}")
            return {"hostname": hostname, "file": filepath, "success": True}

        except Exception as e:
            logger.warning(f"Attempt {attempt}/{max_retries} failed for {ip_address}: {e}")
            time.sleep(2)

    logger.error(f"Log capture for {ip_address} failed after {max_retries} attempts")
    return {"ip": ip_address, "success": False}


# ---------------------------------------------------------------------------
# Django service wrapper
# ---------------------------------------------------------------------------
class NetworkToolService:
    """Thin facade used by Django views."""

    @staticmethod
    def ping(ip: str) -> dict:
        return alive_check(ip)

    @staticmethod
    def batch_ping(ips: list) -> list:
        return asyncio.run(async_batch_poll(ips))
