# app.py - View/Route Layer (MVC)
import os
import sys
import json
import re
import socket
import logging
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort

# Import controller functions
from controller import process_upload

# Setup logging
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
log_dir = os.path.join(root_dir, "Logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(log_dir, f"App_Logs_{datetime.datetime.today().strftime('%Y-%m-%d')}.log"),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'Database', 'Uploads')
ALLOWED_EXTENSIONS = {'zip'}

logging.info("=== Flask Application Initialization ===")
logging.info(f"Base directory: {BASE_DIR}")
logging.info(f"Project root: {PROJECT_ROOT}")
logging.info(f"Upload folder: {UPLOAD_FOLDER}")

# Flask app setup
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

logging.info("Flask app created successfully")

# Add validation function (moved from controller since it was removed)
def validate_ticket_number(ticket: str) -> bool:
    """Validate ticket number format"""
    if not ticket:
        return False
    pattern = r'^SVR\d+$'
    return bool(re.match(pattern, ticket))

@app.route('/')
def index():
    logging.info("Index route accessed")
    try:
        technologies = ['Wireless', 'Switches', 'Security', 'Others']
        logging.debug(f"Available technologies: {technologies}")
        
        upload_exists = os.path.exists(UPLOAD_FOLDER)
        logging.debug(f"Upload folder exists: {upload_exists}")
        
        if not upload_exists:
            logging.warning(f"Upload folder does not exist: {UPLOAD_FOLDER}")
        
        logging.info("Index page rendered successfully")
        return render_template('upload.html', technologies=technologies)
        
    except Exception as e:
        logging.error(f"Error in index route: {str(e)}")
        logging.exception("Full traceback for index route error:")
        flash('An error occurred while loading the page', 'error')
        return render_template('upload.html', technologies=['Wireless', 'Switches', 'Security', 'Others'])

@app.route('/upload', methods=['POST'])
def upload():
    logging.info("Upload route accessed")

    try:
        # Extract request data
        form_data = {
            'ticket': request.form.get('ticket', '').strip(),
            'comment': request.form.get('comment', ''),
            'technology': request.form.get('technology', '')
        }
        
        file_obj = request.files.get('file')
        
        # Log request details
        logging.info(f"Upload request details:")
        logging.info(f"Ticket: {form_data['ticket']}")
        logging.info(f"Technology: {form_data['technology']}")
        logging.info(f"Comment length: {len(form_data['comment'])} characters")
        
        if file_obj and hasattr(file_obj, 'filename'):
            logging.info(f"File: {file_obj.filename}")
            logging.debug(f"File content type: {getattr(file_obj, 'content_type', 'Unknown')}")
        else:
            logging.warning("No file provided in request")
        
        # FIXED - Call controller function which now returns boolean
        logging.info("Processing upload with controller...")
        success = process_upload(form_data, file_obj, UPLOAD_FOLDER)
        
        # FIXED - Handle boolean response instead of dictionary
        if success:
            flash('Logs uploaded and processed successfully.', 'success')
            logging.info("Upload processing completed successfully")
        else:
            flash('Upload processing failed. Please check logs for details.', 'error')
            logging.warning("Upload processing failed")
        
        return redirect(url_for('index'))
        
    except Exception as e:
        error_msg = f"Unexpected error in upload route: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback for upload route error:")
        flash('An unexpected error occurred during upload processing', 'error')
        return redirect(url_for('index'))

@app.route('/debug')
def debug():
    """Debug information endpoint"""
    logging.info("Debug route accessed")
    
    try:
        # SIMPLIFIED - Basic debug info without module checking
        debug_info = {
            'base_directory': BASE_DIR,
            'project_root': PROJECT_ROOT,
            'upload_folder': UPLOAD_FOLDER,
            'upload_folder_exists': os.path.exists(UPLOAD_FOLDER),
            'current_directory': os.getcwd(),
            'python_path_count': len(sys.path),
            'flask_config': dict(app.config),
            'request_info': {
                'remote_addr': request.remote_addr if request else 'No request context',
                'user_agent': str(request.user_agent) if request else 'No request context'
            }
        }
        
        logging.info("Debug information compiled successfully")
        
        # Check for missing critical paths
        critical_paths = [BASE_DIR, PROJECT_ROOT, UPLOAD_FOLDER]
        missing_paths = [path for path in critical_paths if not os.path.exists(path)]
        
        if missing_paths:
            logging.warning(f"Missing critical paths: {missing_paths}")
            debug_info['missing_paths'] = missing_paths
        
        return f"<pre>{json.dumps(debug_info, indent=2, default=str)}</pre>"
        
    except Exception as e:
        error_msg = f"Error in debug route: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback for debug route error:")
        return f"<pre>Debug Error: {error_msg}</pre>"

@app.route('/download/<ticket_number>')
def download_report(ticket_number):
    """Download completed report for a ticket"""
    logging.info(f"Download request for ticket: {ticket_number}")
    
    try:
        # Validate ticket format
        if not validate_ticket_number(ticket_number):
            logging.warning(f"Invalid ticket format for download: {ticket_number}")
            flash('Invalid ticket number format', 'error')
            return redirect(url_for('index'))
        
        # Construct file path
        ticket_folder = os.path.join(UPLOAD_FOLDER, ticket_number)
        excel_file = os.path.join(ticket_folder, f"{ticket_number}_analysis.xlsx")
        
        logging.debug(f"Looking for file: {excel_file}")
        
        # Check if file exists
        if not os.path.exists(excel_file):
            logging.warning(f"Report file not found: {excel_file}")
            flash(f'Report not found for ticket {ticket_number}', 'error')
            return redirect(url_for('index'))
        
        # Check file size and log
        file_size = os.path.getsize(excel_file)
        logging.info(f"Serving download: {excel_file} (Size: {file_size} bytes)")
        
        # Send file
        return send_file(
            excel_file,
            as_attachment=True,
            download_name=f"{ticket_number}_analysis.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        error_msg = f"Error downloading report for {ticket_number}: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback for download error:")
        flash('Error occurred while downloading the report', 'error')
        return redirect(url_for('index'))

@app.route('/check_status/<ticket_number>')
def check_status(ticket_number):
    """Check processing status and file availability for a ticket"""
    logging.info(f"Status check for ticket: {ticket_number}")
    
    try:
        if not validate_ticket_number(ticket_number):
            return {'status': 'error', 'message': 'Invalid ticket format'}
        
        ticket_folder = os.path.join(UPLOAD_FOLDER, ticket_number)
        excel_file = os.path.join(ticket_folder, f"{ticket_number}_analysis.xlsx")
        
        status_info = {
            'ticket_exists': os.path.exists(ticket_folder),
            'excel_exists': os.path.exists(excel_file),
            'download_ready': os.path.exists(excel_file)
        }
        
        logging.debug(f"Status for {ticket_number}: {status_info}")
        return status_info
        
    except Exception as e:
        logging.error(f"Error checking status for {ticket_number}: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@app.route('/reset')
def reset_form():
    """Reset form and clear any flash messages"""
    logging.info("Form reset requested")
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    logging.warning(f"404 Error: {request.url} not found")
    flash('Page not found', 'error')
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logging.error(f"500 Internal Server Error: {str(error)}")
    logging.exception("Full traceback for 500 error:")
    flash('An internal server error occurred', 'error')
    return redirect(url_for('index'))

if __name__ == '__main__':
    logging.info("=== Flask Application Startup ===")
    
    try:
        # Ensure upload folder exists
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            logging.info(f"Created upload folder: {UPLOAD_FOLDER}")
            print(f"Created upload folder: {UPLOAD_FOLDER}")
        else:
            logging.info(f"Upload folder already exists: {UPLOAD_FOLDER}")

        logging.info(f"Upload folder: {UPLOAD_FOLDER}")
        logging.info(f"Upload folder exists: {os.path.exists(UPLOAD_FOLDER)}")
        print(f"Upload folder: {UPLOAD_FOLDER}")
        print(f"Upload folder exists: {os.path.exists(UPLOAD_FOLDER)}")
        
        # Get local IP for access information
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            logging.info(f"Local IP detected: {local_ip}")
        except Exception as ip_error:
            local_ip = 'localhost'
            logging.warning(f"Could not detect local IP, using localhost: {str(ip_error)}")

        # Start Flask app
        logging.info("Starting Flask development server...")
        print(f"Flask app running at: http://{local_ip}:5000")
        print(f"Debug info available at: http://{local_ip}:5000/debug")
        print(f"Download reports at: http://{local_ip}:5000/download/<ticket_number>")
        
        logging.info(f"Flask server starting on {local_ip}:5000")
        logging.info("Debug mode: True")
        
        app.run(host='0.0.0.0', port=5000, debug=True)
        
    except KeyboardInterrupt:
        logging.info("Flask application stopped by user (Ctrl+C)")
        print("\nFlask application stopped by user")
        
    except Exception as e:
        error_msg = f"Failed to start Flask app: {str(e)}"
        logging.critical(error_msg)
        logging.exception("Full traceback for Flask startup error:")
        print(error_msg)
        raise
        
    finally:
        logging.info("=== Flask Application Shutdown ===")
