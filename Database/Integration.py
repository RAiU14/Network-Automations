import pandas as pd

# Your EOX data dictionary
data = {
    'C1000FE-48T-4G-L': {
        'End-of-Life Announcement Date': 'April 30, 2024',
        'End-of-Sale Date: HW': 'April 30, 2025',
        'Last Ship Date: HW': 'July 30, 2025',
        'End of SW Maintenance Releases Date: HW': 'April 30, 2026',
        'End of Vulnerability/Security Support: HW': 'April 30, 2028',
        'End of Routine Failure Analysis Date:  HW': 'April 30, 2026',
        'End of New Service Attachment Date: HW': 'April 30, 2026',
        'End of Service Contract Renewal Date:  HW': 'July 29, 2029',
        'Last Date of Support: HW': 'April 30, 2030'
    },
    'C9200L-48P-4G': {'EOX': 'Not Announced'},
    'C9200L-24P-4G': {'EOX': 'Not Announced'}
}

# Load your Excel file
excel_file_path = r"C:\Users\abhi.bs\OneDrive - NTT Ltd\Desktop\Book1.xlsx"
df = pd.read_excel(excel_file_path, sheet_name='Sheet1', engine='openpyxl')

# Ensure all keys from data dictionary are present as columns
for model_data in data.values():
    if isinstance(model_data, dict):
        for key in model_data.keys():
            if key not in df.columns:
                df[key] = 'NA'
    elif isinstance(model_data, str):
        if 'Remark' not in df.columns:
            df['Remark'] = 'NA'

# Iterate through rows starting from index 1 (Excel row 2)
for idx in range(1, len(df)):
    model = str(df.iloc[idx, 2]).strip()  # Column C = index 2
    if model in data:
        model_data = data[model]
        if isinstance(model_data, dict):
            for key, value in model_data.items():
                if key in df.columns:
                    df.at[idx, key] = value
        elif isinstance(model_data, str):
            df.at[idx, 'Remark'] = model_data

# Save the updated Excel file
df.to_excel(excel_file_path, index=False, sheet_name='Sheet1')
print(f"EOX data updated in {excel_file_path}")
