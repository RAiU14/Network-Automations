# Cisco_Automations

A collection of Python utilities designed to automate repetitive Cisco network engineering tasks. The goal of this repository is to provide **smart and efficient scripts** that save time, reduce manual effort, and improve consistency in day-to-day operations.

---

## Cisco EOX Package (Web Scraping)

The **Cisco EOX Package** provides a set of programs to extract End-of-Life (EOX) details for Cisco products **without relying on Cisco’s APIs**.  

Instead, the package uses **web scraping techniques** to retrieve information faster than manually navigating Cisco web pages.

### Key Features
- Input: Cisco **product ID** or **model number**  
- Output: EOX details, including end-of-sale, end-of-support, and lifecycle milestones  
- No API keys or credentials required  
- Faster than loading and searching through Cisco’s web UI  

### Goals
- Automate tedious manual lookups for Cisco lifecycle data  
- Help engineers quickly gather accurate EOX details for devices in bulk  
- Provide a lightweight alternative when APIs are not accessible  

### Disclaimer
This tool is:  
- **Not affiliated with or endorsed by Cisco**  
- Dependent on publicly available information from Cisco’s website  

Users must **validate results directly** from [Cisco’s official website](https://www.cisco.com) before making any business or operational decisions. The author does **not accept responsibility** for misuse, especially in production or commercial settings.

---

## PM_Report Module

The **PM_Report** folder contains scripts for generating **Preventive Maintenance (PM) reports** across multiple vendors and technologies. These reports are designed to provide quick insights into device health and operational readiness.

### Features
- Collects health parameters from network appliances (currently in **Phase 1**)  
- Analyzes log data to produce structured summaries  
- Marks missing or unavailable information clearly as `NA`  
- Modular design allows for vendor-specific or technology-specific expansion  

### Current Status
- **Working:**  
  - Basic log parsing and extraction  
  - Health parameter reporting framework  
  - Error flagging with simple categorization  

- **Known Limitations / Issues:**  
  - Some advanced metrics and vendor-specific parameters are not yet supported  
  - Data enrichment is limited to available log content  

- **Planned Enhancements (WIP):**  
  - Support for more vendor log formats  
  - Richer error categorization and severity levels  
  - Improved output formatting for readability and presentation  
  - Integration with CSV/JSON/Database outputs for archiving and analytics  

---

## Notes
- Use the `requirements.txt` file to install dependencies before running any scripts.  
- Contributions and suggestions for improvements are welcome.  
