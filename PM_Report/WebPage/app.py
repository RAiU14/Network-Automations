import os
import json
import re
import socket
import sys
import time
from flask import Flask, render_template, request, redirect, url_for, flash

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Add Switching directory to path so we can import modules directly
switching_dir = os.path.join(parent_dir, 'Switching')
sys.path.insert(0, switching_dir)

# Now import modules directly (not as packages)
try:
    from file_processing import extract_zip_flatten_structure
    import Cisco_IOS_XE  # Direct import, not from Switching
    import Data_to_Excel  # Direct import, not from Switching
    print("✅ All modules imported successfully")
    print(f"🔧 Available Cisco_IOS_XE functions: {[attr for attr in dir(Cisco_IOS_XE) if not attr.startswith('_')]}")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print(f"Parent directory: {parent_dir}")
    print(f"Switching directory: {switching_dir}")
    print(f"Files in parent: {os.listdir(parent_dir)}")
    print(f"Files in switching: {os.listdir(switching_dir) if os.path.exists(switching_dir) else 'Directory not found'}")
    sys.exit(1)

# Rest of your Flask app configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, '..', '..', 'Database', 'Uploads')
ALLOWED_EXTENSIONS = {'zip'}

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_ticket_number(ticket):
    pattern = r'^SVR\d+$'
    return bool(re.match(pattern, ticket))

@app.route('/')
def index():
    technologies = ['Wireless', 'Switches', 'Security', 'Others']
    return render_template('upload.html', technologies=technologies)

@app.route('/upload', methods=['POST'])
def upload():
    ticket = request.form.get('ticket', '').strip()
    comment = request.form.get('comment')
    technology = request.form.get('technology')
    file = request.files.get('file')

    # Validation checks
    if not ticket:
        flash('Ticket Number is required.', 'warning')
        return redirect(url_for('index'))
    
    if not validate_ticket_number(ticket):
        flash('Ticket number must start with "SVR" followed by numbers (e.g., SVR137572722).', 'warning')
        return redirect(url_for('index'))
    
    if not file or file.filename == '':
        flash('No file selected.', 'warning')
        return redirect(url_for('index'))
    
    if not technology:
        flash('Please select a technology.', 'warning')
        return redirect(url_for('index'))
    
    if not allowed_file(file.filename):
        flash('Only zip files are allowed.', 'warning')
        return redirect(url_for('index'))

    # Create upload folder structure
    ticket_folder = os.path.join(app.config['UPLOAD_FOLDER'], ticket)
    os.makedirs(ticket_folder, exist_ok=True)

    # Save the file
    filename = f"{ticket}.zip"
    file_path = os.path.join(ticket_folder, filename)
    file.save(file_path)

    # Create metadata
    metadata = {
        'ticket_number': ticket,
        'comment': comment,
        'technology': technology,
        'file_path': file_path,
        'filename': filename
    }

    meta_path = os.path.join(ticket_folder, 'metadata.json')
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=4)

    # Extract the uploaded zip file
    try:
        extraction_result = extract_zip_flatten_structure(file_path)
        
        if extraction_result['success']:
            print(f"✅ Extraction successful: {extraction_result['message']}")
            print(f"📁 Files extracted to: {extraction_result['extract_path']}")
            print(f"📄 Number of files extracted: {extraction_result['file_count']}")

            metadata['extraction'] = {
                'extracted': True,
                'extract_path': extraction_result['extract_path'],
                'file_count': extraction_result['file_count'],
                'structure': 'flattened',
                'extracted_files': [os.path.basename(f) for f in extraction_result['extracted_files']]
            }
            
            # Process files
            try:
                print(f"🔄 Processing directory: {extraction_result['extract_path']}")
                
                if hasattr(Cisco_IOS_XE, 'process_directory'):
                    data = Cisco_IOS_XE.process_directory(extraction_result['extract_path'])
                    print(f"✅ Processing completed. Data type: {type(data)}")
                    
                    metadata['processing'] = {
                        'status': 'completed',
                        'data_count': len(data) if isinstance(data, list) else 1,
                        'processed_at': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # Excel processing
                    try:
                        excel_path = os.path.join(ticket_folder, f"{ticket}_analysis.xlsx")
                        Data_to_Excel.append_to_excel(ticket, data, excel_path)
                        metadata['excel_export'] = {'status': 'completed', 'file_path': excel_path}
                        print(f"✅ Excel export completed: {excel_path}")
                    except Exception as excel_error:
                        print(f"❌ Excel processing failed: {excel_error}")
                        metadata['excel_export'] = {'status': 'failed', 'error': str(excel_error)}
                    
                else:
                    error_msg = "process_directory function not found in Cisco_IOS_XE module"
                    print(f"❌ {error_msg}")
                    metadata['processing'] = {'status': 'failed', 'error': error_msg}
                    flash('File uploaded but processing failed. Please check the logs.', 'warning')
                    
            except Exception as processing_error:
                error_msg = f"Error processing files: {str(processing_error)}"
                print(f"❌ {error_msg}")
                metadata['processing'] = {'status': 'failed', 'error': error_msg}
                flash('File uploaded and extracted, but processing failed.', 'warning')
        
        else:
            print(f"❌ Extraction failed: {extraction_result['error']}")
            metadata['extraction'] = {'extracted': False, 'error': extraction_result['error']}
            flash('File uploaded but extraction failed.', 'error')
    
    except Exception as e:
        error_msg = f"Unexpected error during extraction: {str(e)}"
        print(f"❌ {error_msg}")
        metadata['extraction'] = {'extracted': False, 'error': error_msg}
        flash('File upload failed during extraction.', 'error')

    # Update metadata with all results
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=4)

    flash(f'Logs uploaded successfully for ticket {ticket}.', 'success')
    return redirect(url_for('index'))

@app.route('/debug')
def debug():
    debug_info = {
        'upload_folder_exists': os.path.exists(UPLOAD_FOLDER),
        'cisco_ios_xe_functions': [attr for attr in dir(Cisco_IOS_XE) if not attr.startswith('_')],
        'data_to_excel_functions': [attr for attr in dir(Data_to_Excel) if not attr.startswith('_')],
        'current_directory': os.getcwd(),
        'python_path': sys.path[:5]
    }
    return f"<pre>{json.dumps(debug_info, indent=2)}</pre>"

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        print(f"📁 Created upload folder: {UPLOAD_FOLDER}")

    print(f"📂 Upload folder: {UPLOAD_FOLDER}")
    print(f"🔗 Upload folder exists: {os.path.exists(UPLOAD_FOLDER)}")
    
    try:
        available_functions = [attr for attr in dir(Cisco_IOS_XE) if not attr.startswith('_')]
        print(f"🔧 Available Cisco_IOS_XE functions: {available_functions}")
    except Exception as e:
        print(f"❌ Error checking Cisco_IOS_XE module: {e}")

    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        print(f"🚀 Flask app running at: http://{local_ip}:5000")
        print(f"🔍 Debug info available at: http://{local_ip}:5000/debug")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"❌ Failed to start Flask app: {e}")
