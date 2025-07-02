from EOX import Cisco_PID  
from EOX import Cisco_EOX


def get_series(technology: str, pid: str):
    series = Cisco_PID.get_possible_series(pid)
    print(f"Possible Series are: {series}")
    if technology == "wireless":
        series_link = Cisco_PID.find_device_series_link(pid, Cisco_EOX.open_cat('/c/en/us/support/wireless/index.html'))
        print("Yes, it is wireless", series_link)
    return

get_series("wireless", "AIR-AP9117AXI-E")

