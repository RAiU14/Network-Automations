import re
import os


def check_show_module_exists(log_text):
    # Pattern handles: show/sh/sho with optional dashes
    command_pattern = r'[-]*\s*(?:show|sho|sh)\s+modules?'
    
    command_match = re.search(command_pattern, log_text, re.IGNORECASE)
    if not command_match:
        return False
    
    # Extract section until next show command
    start_pos = command_match.end()
    next_show_pattern = r'(?:#|(?<=\n))[-]*\s*(?:show|sho|sh)\s+(?!module)'
    next_show_match = re.search(next_show_pattern, log_text[start_pos:], re.IGNORECASE)
    
    if next_show_match:
        section = log_text[start_pos:start_pos + next_show_match.start()]
    else:
        section = log_text[start_pos:]
    
    # Verify actual module data exists
    header_pattern = r'Mod\s+Ports\s+Card Type'
    has_header = re.search(header_pattern, section, re.IGNORECASE)
    
    if not has_header:
        return False
    
    # Check for module entries (lines with mod number and ports)
    module_entry_pattern = r'\n\s*\d+\s+\d+\s+\S'
    has_modules = re.search(module_entry_pattern, section)
    
    return bool(has_modules)

def extract_show_module_section(log_text):
    command_pattern = r'(.*?(?:show|sho|sh)\s+modules?.*?)(?=\n)'
    command_match = re.search(command_pattern, log_text, re.IGNORECASE)
    
    if not command_match:
        return ""
    
    start_pos = command_match.start()
    search_start = command_match.end()
    
    # Find next show command
    next_show_pattern = r'(?:#|(?<=\n))[-]*\s*(?:show|sho|sh)\s+(?!module)'
    next_show_match = re.search(next_show_pattern, log_text[search_start:], re.IGNORECASE)
    
    if next_show_match:
        end_pos = search_start + next_show_match.start()
        section = log_text[start_pos:end_pos]
    else:
        section = log_text[start_pos:]
    
    return section.strip()

def parse_module_details(section_text):
    modules = []
    lines = section_text.split('\n')
    current_switch = None
    in_module_section = False
    
    header_pattern = r'Mod\s+Ports\s+Card Type'
    separator_pattern = r'---\+-----\+'
    
    for i, line in enumerate(lines):
        # Track switch number for stacks/VSS
        switch_match = re.search(r'Switch Number:\s*(\d+)', line)
        if switch_match:
            current_switch = switch_match.group(1)
        
        # Find table header
        if re.search(header_pattern, line, re.IGNORECASE):
            if i + 1 < len(lines) and re.search(separator_pattern, lines[i + 1]):
                in_module_section = True
                continue
        
        # Stop at next table
        if in_module_section:
            if (re.match(r'^[M-]\s+\w+', line) or 
                re.match(r'^Mod\s+Redundancy', line)):
                in_module_section = False
                continue
            
            # Parse: <mod> <ports> <card_type> <model> <serial>
            # Key: 2+ spaces separate card_type from model
            module_pattern = r'^\s*(\d+)\s+(\d+)\s+(.+?)\s{2,}(\S+)\s+(\S+)\s*$'
            match = re.match(module_pattern, line)
            
            if match:
                module_info = {
                    'card_type': match.group(3).strip(),
                    'model': match.group(4).strip(),
                    'serial_no': match.group(5).strip()
                }
                if current_switch:
                    module_info['switch_number'] = current_switch
                modules.append(module_info)
    
    return modules

if __name__ == "__main__":
    dir = r""
    # This is tested and working for version 15 and 16 of IOS_XE
    for file in os.listdir(dir):
        file_path = os.path.join(dir, file)
        if os.path.isfile(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = f.read()
                if check_show_module_exists(data):
                    section = extract_show_module_section(data)
                    modules = parse_module_details(section)
                    for mod in modules:
                        print(mod)
                else:
                    print("No valid 'show module' output found.")
        