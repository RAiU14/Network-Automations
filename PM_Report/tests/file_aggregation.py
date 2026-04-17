import shutil
from pathlib import Path

# EDIT THESE TWO PATHS ONLY
source_parent = Path(r"C:\Users\girish.n\Downloads\PM logs sets\Ultimate_log_folders")
destination_dir = Path(r"C:\Users\girish.n\Downloads\PM logs sets\Ultimate_logs")

# Create destination folder if it doesn't exist
destination_dir.mkdir(parents=True, exist_ok=True)

for file in source_parent.rglob("*"):
    if file.is_file() and file.suffix.lower() in (".txt", ".log"):
        # Avoid overwriting files with same names
        new_name = f"{file.parent.name}_{file.stem}{file.suffix}"
        destination = destination_dir / new_name
        shutil.copy2(file, destination)
        print(f"Copied: {file} -> {destination}")