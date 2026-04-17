import os
import re
from PM_Report.pipeline import detect_os_from_file, _scope_show_version

def test_os():
    directory_path = r"C:\Users\girish.n\Downloads\PM logs sets\Ultimate_logs"
    count, ios, iosxe, non = 0, 0, 0, 0
    for file_name in os.listdir(directory_path):
        file_path = os.path.join(directory_path, file_name)
        if os.path.isfile(file_path):
            os_kind = detect_os_from_file(file_path)
            count += 1
            print(f"{file_name}: {os_kind}")
            if os_kind == "ios":
                ios += 1
            elif os_kind == "ios_xe":
                iosxe += 1
            else:
                non += 1
    return count, ios, iosxe, non

def test_show_version():
    directory_path = r"C:\Users\girish.n\Downloads\PM logs sets\Ultimate_logs"
    for file_name in os.listdir(directory_path):
        file_path = os.path.join(directory_path, file_name)
        if os.path.isfile(file_path):
            with open(file_path, "r", errors="ignore") as f:
                content = f.read()
                scoped = _scope_show_version(content)
                print(f"{file_name}: {scoped}")

if __name__ == "__main__":
    test_show_version()