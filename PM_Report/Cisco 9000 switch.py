import re

def extract_data(log_file):
    try:
        with open(log_file, 'r') as file:
            log_data = file.read()

        data = {
            "Hostname": re.search(r"hostname\s+(\S+)", log_data).group(1) if re.search(r"hostname\s+(\S+)", log_data) else None,
            "Model number": re.search(r"Model Number\s+:\s+(\S+)", log_data).group(1) if re.search(r"Model Number\s+:\s+(\S+)", log_data) else None,
            "Serial number": re.search(r"System Serial Number\s+:\s+(\S+)", log_data).group(1) if re.search(r"System Serial Number\s+:\s+(\S+)", log_data) else None,
            "Uptime": re.search(r"uptime is\s+(.+)", log_data).group(1) if re.search(r"uptime is\s+(.+)", log_data) else None,
            "Current s/w version": re.search(r"Cisco IOS XE Software, Version\s+([\d.]+)", log_data).group(1) if re.search(r"Cisco IOS XE Software, Version\s+([\d.]+)", log_data) else None,
            "Last Reboot Reason": re.search(r"Last reload reason:\s+(.+)", log_data).group(1) if re.search(r"Last reload reason:\s+(.+)", log_data) else None,
            "CPU Utilization": re.search(r"CPU utilization for five seconds:\s+(\d+)%", log_data).group(1) + "%" if re.search(r"CPU utilization for five seconds:\s+(\d+)%", log_data) else None,
        }

        memory_match = re.search(r"Total\(b\)\s+(\d+)\s+Used\(b\)\s+(\d+)\s+Free\(b\)\s+(\d+)", log_data)
        if memory_match:
            total = int(memory_match.group(1))
            used = int(memory_match.group(2))
            free = int(memory_match.group(3))
            utilization = (used / total) * 100
            data["Memory"] = {
                "Total memory": total,
                "Used memory": used,
                "Free memory": free,
                "Memory Utilization (%)": f"{utilization:.2f}%"
            }

        flash_match = re.search(r"(\d+)\s+(\d+)\s+disk\s+rw\s+flash:", log_data)
        if flash_match:
            total = int(flash_match.group(1))
            free = int(flash_match.group(2))
            used = total - free
            utilization = (used / total) * 100
            data["Flash"] = {
                "Total flash memory": total,
                "Used flash memory": used,
                "Free flash memory": free,
                "Used Flash (%)": f"{utilization:.2f}%"
            }

        data["Fan status"] = "OK" if re.search(r"\s+\d+\s+\d+\s+OK\s+Front to Back", log_data) else "Not OK"
        data["Temperature status"] = "OK" if "GREEN" in log_data else "Not OK"
        data["PowerSupply status"] = "OK" if re.search(r"\s+PWR-C\d+-\d+KWAC\s+\S+\s+OK", log_data) else "Not OK"

        return data

    except FileNotFoundError:
        print("File not found.")
        return None

def main():
    log_file = r"Log_samples\3650 switch.txt"
    data = extract_data(log_file)

    if data:
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            else:
                print(f"{key}: {value}")

if __name__ == "__main__":
    main()