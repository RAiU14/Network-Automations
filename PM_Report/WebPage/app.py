import os
import json
import re
import socket
from flask import Flask, render_template, request, redirect, url_for, flash
import sys
from file_processing import *

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from Switching import Cisco_IOS_XE

# Correct path to stay inside the project folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR,'..', '..', 'Database', 'Uploads')
ALLOWED_EXTENSIONS = {'zip'}

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_ticket_number(ticket):
    pattern = r'^SVR\\d+$'
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

    ticket_folder = os.path.join(app.config['UPLOAD_FOLDER'], ticket)
    os.makedirs(ticket_folder, exist_ok=True)

    filename = f"{ticket}.zip"
    file_path = os.path.join(ticket_folder, filename)
    file.save(file_path)

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
    else:
        print(f"❌ Extraction failed: {extraction_result['error']}")
        metadata['extraction'] = {'extracted': False, 'error': extraction_result['error']}

    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=4)

    flash(f'Logs uploaded successfully for ticket {ticket}.', 'success')
    dir_path = extraction_result['extract_path']
    Cisco_IOS_XE.process_directory(dir_path)
    return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    local_ip = socket.gethostbyname(socket.gethostname())
    print(f"🚀 Flask app running at: http://{local_ip}:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)