# Real-World Hardware Integration Guide

This document provides step-by-step instructions for testing the **EN-NMS** prototype with physical networking hardware (Cisco, Huawei, Juniper, etc.).

## 1. Prerequisites
- A physical switch/router with at least one IP-reachable interface (SVI orRouted Port).
- Management PC running the EN-NMS backend with network connectivity to the switch.
- SNMP v2c or v3 support on the hardware.

## 2. Hardware Configuration (Cisco IOS Example)

Log in to your switch and apply the following configuration to enable the SNMP agent:

```bash
# Enter global configuration mode
Switch# configure terminal

# 1. Define the SNMP Read-Only Community String
# Replace 'public' with your preferred string (must match config.yaml)
Switch(config)# snmp-server community public RO

# 2. (Optional) Set Location and Contact info for validation
Switch(config)# snmp-server location Lab_Rack_01
Switch(config)# snmp-server contact Admin_Name

# 3. Ensure the Management Interface has an IP
# For a Layer 2 switch, use an SVI:
Switch(config)# interface vlan 1
Switch(config)# ip address 192.168.1.10 255.255.255.0
Switch(config)# no shutdown

# 4. Exit and save
Switch(config)# end
Switch# write memory
```

## 3. Connectivity Verification
From the terminal where you run the EN-NMS backend, ensure you can ping the switch:

```powershell
ping 192.168.1.10
```

## 4. EN-NMS Configuration
Update your `config.yaml` to include the physical device:

```yaml
database:
  path: "db/nms.db"
polling:
  interval: 60
  max_concurrent: 10
devices:
  - name: "Core-Switch-01"
    ip: "192.168.1.10"
    snmp_community: "public"
```

## 5. Execution
1.  **Initialize**: Run `python init_devices.py` to sync the new device into the database.
2.  **Start Poller**: Run `python poller.py` or use the `auto_start.ps1` script.
3.  **Monitor**: Open the Dashboard, find "Core-Switch-01", and click **"Force Heavy Poll"** to verify the MAC address and sysUpTime are retrieved correctly from the physical ASIC.

---

> [!important]
> **SNMP OIDs**: This prototype uses standard MIB-II OIDs. If your hardware uses non-standard indexes for bandwidth (e.g., `1.3.6.1.2.1.2.2.1.10.X`), ensure your physical interface index matches the poller's loop (defaulting to .1).

> [!tip]
> **Troubleshooting**: If the dashboard shows "Down", check if a firewall on your PC is blocking UDP port 161.
