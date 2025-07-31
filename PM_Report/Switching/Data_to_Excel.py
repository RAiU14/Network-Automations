import os
import shutil
import pandas as pd
import Cisco_IOS_XE

def append_to_excel(ticket_number, data_list, file_path, column_order=None):
    column_order = [
                'File name', 'Host name', 'Model number', 'Serial number', 'Interface ip address',
                'Uptime', 'Current s/w version', 'Current SW EOS', 'Suggested s/w ver', 's/w release date',
                'Latest S/W version', 'Production s/w is deffered or not?', 'Last Reboot Reason', 'Any Debug?',
                'CPU Utilization', 'Total memory', 'Used memory', 'Free memory', 'Memory Utilization (%)',
                'Total flash memory', 'Used flash memory', 'Free flash memory', 'Used Flash (%)',
                'Fan status', 'Temperature status', 'PowerSupply status', 'Available Free Ports',
                'End-of-Sale Date: HW', 'Last Date of Support: HW', 'End of Routine Failure Analysis Date: HW',
                'End of Vulnerability/Security Support: HW', 'End of SW Maintenance Releases Date: HW',
                'Any Half Duplex', 'Interface/Module Remark', 'Config Status', 'Config Save Date',
                'Critical logs', 'Remark'
            ]

    # Create a list to store the formatted data
    formatted_data = []

    # Iterate over the data list
    for data in data_list:
        # Determine the length of the data
        data_length = len(next(iter(data.values())))

        # Iterate over the data
        for i in range(data_length):
            row_data = {}
            for key in column_order:
                if key in data:
                    value = data[key]
                    if isinstance(value, list):
                        row_data[key] = value[i]
                    else:
                        row_data[key] = value
                else:
                    row_data[key] = 'NA'
            formatted_data.append(row_data)

    # Create a DataFrame
    df = pd.DataFrame(formatted_data)

    # Reorder the columns
    df = df[column_order]

    # Write to Excel
    try:
        existing_df = pd.read_excel(file_path)
        combined_df = pd.concat([existing_df, df])
        combined_df.to_excel(file_path, index=False)
    except FileNotFoundError:
        df.to_excel(file_path, index=False)


def unique_model_numbers(data_list):
    try:
        model_numbers = set()
        model_numbers.update(data_list["Model number"])
        return list(model_numbers)
    except Exception as e:
        print(f"Error in main: {str(e)}")

def main():
    try:
        SVR = "SVR3333333333"
        file_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR137436091\9200\Temp\UOBM-9200L-JOT-L03-05_10.31.99.14.txt"
        data_list = Cisco_IOS_XE.process_file(file_path)
        # print(data_list)
        model_numbers = unique_model_numbers(data_list)
        print(model_numbers)
    except Exception as e:
        print(f"Error in main: {str(e)}")
if __name__ == "__main__":
    main()