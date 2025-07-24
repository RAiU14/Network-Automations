import re

class FortiGateLogParser:
    def __init__(self, log_content):
        self.log_content = log_content

    def extract_command_output(self, command_start_pattern):
        escaped_command_start = re.escape(command_start_pattern)
        start_match = re.search(r"(?:^|\n)\s*\S+\s*\$\s*" + escaped_command_start + r"\s*$", self.log_content, re.MULTILINE)
        if not start_match:
            start_match = re.search(r"^" + escaped_command_start + r"\s*$", self.log_content, re.MULTILINE)
            if not start_match:
                return None
        start_index = start_match.end()
        end_match = re.search(r"^\s*\S+\s*\$\s*.+", self.log_content[start_index:], re.MULTILINE)
        if end_match:
            end_index = start_index + end_match.start()
            return self.log_content[start_index:end_index].strip()
        else:
            return self.log_content[start_index:].strip()

    def hostname(self):
        sys_status_output = self.extract_command_output("get system status")
        if sys_status_output:
            match = re.search(r"^Hostname:\s*(.+)", sys_status_output, re.MULTILINE | re.I)
            return match.group(1).strip() if match else "NA"
        return "NA"

    def model_number(self):
        hw_status_output = self.extract_command_output("get hardware status")
        if hw_status_output:
            match = re.search(r"^Model name:\s*(FortiGate-\S+)", hw_status_output, re.MULTILINE | re.I)
            return match.group(1).strip() if match else "NA"
        return "NA"

    def serial_number(self):
        sys_status_output = self.extract_command_output("get system status")
        if sys_status_output:
            match = re.search(r"^Serial-Number:\s*(.+)", sys_status_output, re.MULTILINE | re.I)
            return match.group(1).strip() if match else "NA"
        return "NA"

    def current_sw_version(self):
        sys_status_output = self.extract_command_output("get system status")
        if sys_status_output:
            match = re.search(r"v(\d+\.\d+\.\d+),build\d+,\d+", sys_status_output)
            return match.group(1).strip() if match else "NA"
        return "NA"

    def cpu_utilization(self):
        perf_status_output = self.extract_command_output("get system performance status")
        if perf_status_output:
            match = re.search(r"average-cpu-user/nice/system/idle=(\d+)%/(\d+)%/(\d+)%/(\d+)%", perf_status_output)
            if match:
                user_cpu = int(match.group(1))
                system_cpu = int(match.group(3))
                return f"{user_cpu + system_cpu}%" if match else "NA"
            else:
                match = re.search(r"CPU states: (\d+)% user (\d+)% system.*?(\d+)% idle", perf_status_output)
                if match:
                    user_cpu = int(match.group(1))
                    system_cpu = int(match.group(2))
                    return f"{user_cpu + system_cpu}%" if match else "NA"
        return "NA"

    def memory_utilization(self):
        perf_status_output = self.extract_command_output("get system performance status")
        if perf_status_output:
            match = re.search(r"Memory:.*?(\d+\.\d+)%", perf_status_output)
            return f"{match.group(1)}%" if match else "NA"
        return "NA"

    def fan_status(self):
        sensor_list_output = self.extract_command_output("execute sensor list")
        if sensor_list_output:
            match = re.findall(r"Fan \d+ \.+?\s+(\d+\s*RPM)", sensor_list_output)
            if match:
                return "Normal" if all(re.match(r"\d+\s*RPM", f) for f in match) and len(match) > 0 else "Degraded/Not all fans Normal"
            else:
                return "Not Found (No fan readings)"
        return "NA"

    def power_supply_status(self):
        sensor_list_output = self.extract_command_output("execute sensor list")
        if sensor_list_output:
            match = re.findall(r"PS\d Status \.+?\s+(OK|NOT OK)", sensor_list_output, re.I)
            if match:
                return "Normal" if all(status.strip().upper() == 'OK' for status in match) else "Degraded"
            else:
                return "Not Found"
        return "NA"

    def device_uptime(self):
        sys_status_output = self.extract_command_output("get system status")
        if sys_status_output:
            match = re.search(r"Cluster uptime:\s*(.+)", sys_status_output, re.MULTILINE | re.I)
            if match:
                return match.group(1).strip()
            else:
                perf_status_output = self.extract_command_output("get system performance status")
                if perf_status_output:
                    match = re.search(r"^Uptime:\s*(.+)", perf_status_output, re.MULTILINE | re.I)
                    return match.group(1).strip() if match else "NA"
        return "NA"

    def ip_address(self):
        interface_output = self.extract_command_output("get system interface")
        if interface_output:
            match = re.search(r"== \[ mgmt1 \].*?ip: (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", interface_output, re.DOTALL)
            if match:
                return match.group(1).strip()
            else:
                match = re.search(r"ip: (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", interface_output)
                return match.group(1).strip() if match else "NA"
        return "NA"

    def ha_unit_configuration_sync(self):
        ha_status_output = self.extract_command_output("diagnose sys ha status")
        if ha_status_output:
            match = re.findall(r"FG\d+\(.*?\)?: (in-sync|out-of-sync)", ha_status_output)
            if match:
                return "YES" if all(s == 'in-sync' for s in match) and len(match) >= 2 else "NO"
        return "NA"

    def ha_unit_redundancy_state(self):
        ha_status_output = self.extract_command_output("diagnose sys ha status")
        if ha_status_output:
            match = re.search(r"^Primary\s*:\s*\S+,\s*FG\d+", ha_status_output, re.MULTILINE)
            if match:
                return "Primary" if self.hostname() and self.hostname() in match.group(0) else "NA"
            else:
                match = re.search(r"^Secondary\s*:\s*\S+,\s*FG\d+", ha_status_output, re.MULTILINE)
                if match:
                    return "Secondary" if self.hostname() and self.hostname() in match.group(0) else "NA"
        return "NA"


class FortiGateLogProcessor:
    def __init__(self, log_content):
        self.log_content = log_content
        self.parser = FortiGateLogParser(log_content)

    def process_log(self):
        data = {
            "IP Address": self.parser.ip_address(),
            "Hostname": self.parser.hostname(),
            "Vendor": "Fortinet",
            "Hardware Model": self.parser.model_number(),
            "Type": "Firewall",
            "Serial Number": self.parser.serial_number(),
            "Current Version": self.parser.current_sw_version(),
            "CPU Utilization in % (Used)": self.parser.cpu_utilization(),
            "Memory Utilization in % (Used)": self.parser.memory_utilization(),
            "Fan Status": self.parser.fan_status(),
            "Power Source Single/Dual": "NA",
            "Power Supply Status": self.parser.power_supply_status(),
            "Device Uptime": self.parser.device_uptime(),
            "HA Unit Configuration Sync? YES or NO": self.parser.ha_unit_configuration_sync(),
            "HA Unit - Redundancy State?": self.parser.ha_unit_redundancy_state(),
            "SW end of engineering support": "NA",
            "SW End of support": "NA",
            "HW End of sale date": "NA",
            "HW End of support": "NA",
            "Backup Status(Is the back up readly available with client)": "NA",
            "Overall Remarks / Recommendation": "NA"
        }
        return data

    def print_data(self, data):
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            else:
                print(f"{key}: {value}")
        print("\n")


def main():
    try:
        with open('Log_samples\FortiGate-1801F.txt', 'r') as f:
            full_log_content = f.read()
    except FileNotFoundError:
        print("Error: 'BR-DR-EXT-3PT01(10.11.90.21).txt' not found.")
        full_log_content = ""

    if full_log_content:
        processor = FortiGateLogProcessor(full_log_content)
        data = processor.process_log()
        processor.print_data(data)
    else:
        print("No log content to analyze. Please ensure the file exists and is accessible.")


if __name__ == "__main__":
    main()