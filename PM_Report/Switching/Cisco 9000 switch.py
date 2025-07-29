import re
import os

class CiscoLogParser:
    def __init__(self, file_path):
        with open(file_path, 'r') as file:
            self.log_data = file.read()

    def hostname(self):
        match = re.search(r"hostname\s+(\S+)", self.log_data)
        return match.group(1) if match else "NA"

    def model_number(self):
        match = re.search(r"Model Number\s+:\s+(\S+)", self.log_data)
        return match.group(1) if match else "NA"

    def serial_number(self):
        match = re.search(r"System Serial Number\s+:\s+(\S+)", self.log_data)
        return match.group(1) if match else "NA"

    def uptime(self):
        match = re.search(r"uptime is\s+(.+)", self.log_data)
        return match.group(1) if match else "NA"

    def current_sw_version(self):
        match = re.search(r"Cisco IOS XE Software, Version\s+([\d.]+)", self.log_data)
        return match.group(1) if match else "NA"

    def last_reboot_reason(self):
        match = re.search(r"Last reload reason:\s+(.+)", self.log_data)
        return match.group(1) if match else "NA"

    def cpu_utilization(self):
        match = re.search(r"five minutes:\s+(\d+)%", self.log_data)
        return match.group(1) + "%" if match else "NA"

    def memory_info(self):
        match = re.search(r"Processor\s+\S+\s+(\d+)\s+(\d+)\s+(\d+)", self.log_data)
        if match:
            total = int(match.group(1))
            used = int(match.group(2))
            free = int(match.group(3))
            utilization = (used / total) * 100
            return {
                "Total memory": total,
                "Used memory": used,
                "Free memory": free,
                "Memory Utilization (%)": f"{utilization:.2f}%"
            }
        return {
            "Total memory": "NA",
            "Used memory": "NA",
            "Free memory": "NA",
            "Memory Utilization (%)": "NA"
        }

    def flash_info(self):
        match = re.search(r"(\d+)\s+(\d+)\s+disk\s+rw\s+flash:", self.log_data)
        if match:
            total = int(match.group(1))
            free = int(match.group(2))
            used = total - free 
            utilization = (used / total) * 100
            return {
                "Total flash memory": total,
                "Used flash memory": used,
                "Free flash memory": free,
                "Used Flash (%)": f"{utilization:.2f}%"
            }
        return {
            "Total flash memory": "NA",
            "Used flash memory": "NA",
            "Free flash memory": "NA",
            "Used Flash (%)": "NA"
        }

    def fan_status(self):
        return "OK" if re.search(r"\s+\d+\s+\d+\s+OK\s+Front to Back", self.log_data) else "Not OK"

    def temperature_status(self):
        return "OK" if "GREEN" in self.log_data else "Not OK"

    def power_supply_status(self):
        return "OK" if re.search(r"\s+PWR-C\d+-\d+KWAC\s+\S+\s+OK", self.log_data) else "Not OK"
        
    def debug_status(self):
        match = re.search(r"sh\w*\s*de\w*", self.log_data, re.IGNORECASE)
        if match:
            hostname = self.hostname()
            debug_section_match = re.search(rf"Ip Address\s+Port\s*-+\|----------\s*([\s\S]*?)\n{hostname}#", self.log_data[match.end():], re.IGNORECASE)
            if debug_section_match and debug_section_match.group(1).strip():
                return "Yes"
            else:
                return "No"
        else:
            return "No"
        
    def available_ports(self):
        try:
            match = re.search(r"show interfaces status\s*([\s\S]*?)(?=\n-{20,}|\Z)", self.log_data)
            if match:
                interface_status_output = match.group(1)
                lines = interface_status_output.strip().splitlines()[1:]  # skip header line
                available_ports = 0
                for line in lines:
                    columns = line.split()
                    if len(columns) > 3:
                        try:
                            vlan = columns[3]
                            status = columns[2].lower()
                            if status == "notconnect" and vlan == "1":
                                available_ports += 1
                        except IndexError:
                            continue
                return available_ports
            else:
                return "NA"
        except Exception as e:
            return str(e)
    
    def half_duplex_ports(self):
        try:
            match = re.findall(r"^(\S+).*a-half.*$", self.log_data, re.IGNORECASE | re.MULTILINE)
            return match
        except Exception as e:
            return str(e)
    

class CiscoLogProcessor:
    def __init__(self, directory_path):
        self.directory_path = directory_path

    def get_file_names(self):
        try:
            return [file for file in os.listdir(self.directory_path) if os.path.isfile(os.path.join(self.directory_path, file))]
        except FileNotFoundError:
            print(f"Directory '{self.directory_path}' not found.")
            return []
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return []

    def process_file(self, file_path):
        parser = CiscoLogParser(file_path)
        data = {
            "Hostname": parser.hostname(),
            "Model number": parser.model_number(),
            "Serial number": parser.serial_number(),
            "Uptime": parser.uptime(),
            "Current s/w version": parser.current_sw_version(),
            "Last Reboot Reason": parser.last_reboot_reason(),
            "Debug Status": parser.debug_status(),
            "CPU Utilization": parser.cpu_utilization(),
            "Memory": parser.memory_info(),
            "Flash": parser.flash_info(),
            "Fan status": parser.fan_status(),
            "Temperature status": parser.temperature_status(),
            "PowerSupply status": parser.power_supply_status(),
            "Any debug" : parser.debug_status(),
            "Available Free Ports" : parser.available_ports(),
            "Half Duplex Ports" : parser.half_duplex_ports()
        }
        return data

    def process_directory(self):
        for filename in os.listdir(self.directory_path):
            if filename.endswith('.txt'):
                file_path = os.path.join(self.directory_path, filename)
                data = self.process_file(file_path)
                self.print_data(data)

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
    # For a single file
    file_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR137436091\9200\UOBM-C9200-BBT-OA-L1-01_10.58.72.12.txt"
    processor = CiscoLogProcessor("")
    data = processor.process_file(file_path)
    processor.print_data(data)

    # For a directory
    # directory_path = r"C:\Users\girish.n\Downloads\SVR137436091"
    # processor = CiscoLogProcessor(directory_path)
    # processor.process_directory()


if __name__ == "__main__":
    main()