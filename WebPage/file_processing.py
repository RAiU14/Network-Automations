import zipfile
import os

def extract_zip_flatten_structure(zip_file_path):
    try:
        # Check if zip file exists
        if not os.path.exists(zip_file_path):
            return {
                'success': False,
                'error': f'Zip file not found: {zip_file_path}',
                'extracted_files': []
            }
        
        # Get the directory where the zip file is located
        zip_directory = os.path.dirname(zip_file_path)
        
        # Create extraction folder name (remove .zip extension)
        zip_filename = os.path.basename(zip_file_path)
        extract_folder_name = zip_filename.rsplit('.', 1)[0] + '_extracted'
        extract_path = os.path.join(zip_directory, extract_folder_name)
        
        # Create extraction directory
        os.makedirs(extract_path, exist_ok=True)
        
        extracted_files = []
        
        # Extract the zip file with flattened structure
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                # Skip directories
                if file_info.is_dir():
                    continue
                
                # Get just the filename without any path
                original_filename = os.path.basename(file_info.filename)
                
                # Skip if filename is empty (can happen with some zip structures)
                if not original_filename:
                    continue
                
                # Handle duplicate filenames by adding a counter
                final_filename = original_filename
                counter = 1
                while os.path.exists(os.path.join(extract_path, final_filename)):
                    name, ext = os.path.splitext(original_filename)
                    final_filename = f"{name}_{counter}{ext}"
                    counter += 1
                
                # Extract the file content
                with zip_ref.open(file_info) as source:
                    target_path = os.path.join(extract_path, final_filename)
                    with open(target_path, 'wb') as target:
                        target.write(source.read())
                
                extracted_files.append(target_path)
        
        return {
            'success': True,
            'message': f'Successfully extracted {len(extracted_files)} files (flattened structure)',
            'extract_path': extract_path,
            'extracted_files': extracted_files,
            'file_count': len(extracted_files),
            'structure': 'flattened'
        }
    
    except zipfile.BadZipFile:
        return {
            'success': False,
            'error': 'Invalid or corrupted zip file',
            'extracted_files': []
        }
    except PermissionError:
        return {
            'success': False,
            'error': 'Permission denied - cannot extract files',
            'extracted_files': []
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Unexpected error during extraction: {str(e)}',
            'extracted_files': []
        }
