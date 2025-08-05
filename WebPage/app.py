# app.py - Enhanced with True Parallel Processing
import os
import sys
import json
import re
import socket
import logging
import datetime
import threading
import atexit
from concurrent.futures import ThreadPoolExecutor
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

# CREATE THREAD POOL FOR CONCURRENT PROCESSING
executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="UploadProcessor")
logging.info("ThreadPoolExecutor initialized with 10 workers for concurrent processing")

logging.info("Flask app created successfully")

# Add validation function
def validate_ticket_number(ticket: str) -> bool:
    """Validate ticket number format"""
    if not ticket:
        return False
    pattern = r'^SVR\d+$'
    return bool(re.match(pattern, ticket))

def async_process_upload(form_data, file_path, upload_folder):
    """Process upload in background thread"""
    try:
        logging.info(f"[CONCURRENT] Starting background processing for ticket: {form_data['ticket']}")
        
        # Create a mock file object for the controller
        class FileObj:
            def __init__(self, file_path, original_filename):
                self.file_path = file_path
                self.filename = original_filename
            
            def save(self, path):
                # File already saved, just copy if needed
                if path != self.file_path:
                    import shutil
                    shutil.copy2(self.file_path, path)
        
        # Create file object
        file_obj = FileObj(file_path, f"{form_data['ticket']}.zip")
        
        # Call your existing process_upload function
        success = process_upload(form_data, file_obj, upload_folder)
        
        if success:
            logging.info(f"[CONCURRENT] Background processing completed successfully for ticket: {form_data['ticket']}")
        else:
            logging.error(f"[CONCURRENT] Background processing failed for ticket: {form_data['ticket']}")
            
    except Exception as e:
        logging.exception(f"[CONCURRENT] Background processing error for ticket {form_data['ticket']}: {str(e)}")

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
    """Enhanced upload with concurrent processing"""
    logging.info("Upload route accessed")

    try:
        # Extract request data quickly
        form_data = {
            'ticket': request.form.get('ticket', '').strip(),
            'comment': request.form.get('comment', ''),
            'technology': request.form.get('technology', '')
        }
        file_obj = request.files.get('file')
        
        # Basic validation
        if not form_data['ticket'] or not file_obj:
            flash('Ticket number and file are required', 'error')
            return redirect(url_for('index'))
        
        if not validate_ticket_number(form_data['ticket']):
            flash('Invalid ticket number format. Use SVR followed by numbers.', 'error')
            return redirect(url_for('index'))
        
        # Log request details
        logging.info(f"Processing upload for ticket: {form_data['ticket']}")
        logging.info(f"Technology: {form_data['technology']}")
        logging.info(f"File: {file_obj.filename}")
        
        # Save file immediately and start background processing
        ticket_folder = os.path.join(UPLOAD_FOLDER, form_data['ticket'])
        os.makedirs(ticket_folder, exist_ok=True)
        file_path = os.path.join(ticket_folder, f"{form_data['ticket']}.zip")
        
        # Save file (this is the only potentially slow operation)
        file_obj.save(file_path)
        logging.info(f"File saved: {file_path}")
        
        # Submit to thread pool for concurrent processing
        future = executor.submit(async_process_upload, form_data, file_path, UPLOAD_FOLDER)
        active_threads = threading.active_count()
        logging.info(f"[CONCURRENT] Task submitted to thread pool. Active threads: {active_threads}")
        
        # Return success immediately
        flash(f'Upload successful for ticket {form_data["ticket"]}! Processing started in background (concurrent mode).', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        error_msg = f"Upload error: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback for upload error:")
        flash('Upload failed. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/debug')
def debug():
    """Enhanced debug information with thread pool stats"""
    logging.info("Debug route accessed")
    
    try:
        # Get thread pool statistics
        executor_info = {
            'max_workers': executor._max_workers,
            'active_threads': threading.active_count(),
            'pool_shutdown': executor._shutdown,
            'concurrent_processing_enabled': True
        }
        
        debug_info = {
            'base_directory': BASE_DIR,
            'project_root': PROJECT_ROOT,
            'upload_folder': UPLOAD_FOLDER,
            'upload_folder_exists': os.path.exists(UPLOAD_FOLDER),
            'current_directory': os.getcwd(),
            'python_path_count': len(sys.path),
            'thread_pool_info': executor_info,
            'flask_config': dict(app.config),
            'request_info': {
                'remote_addr': request.remote_addr if request else 'No request context',
                'user_agent': str(request.user_agent) if request else 'No request context'
            }
        }
        
        logging.info("Debug information compiled successfully")
        
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
        if not validate_ticket_number(ticket_number):
            logging.warning(f"Invalid ticket format for download: {ticket_number}")
            flash('Invalid ticket number format', 'error')
            return redirect(url_for('index'))
        
        ticket_folder = os.path.join(UPLOAD_FOLDER, ticket_number)
        excel_file = os.path.join(ticket_folder, f"{ticket_number}_analysis.xlsx")
        
        logging.debug(f"Looking for file: {excel_file}")
        
        if not os.path.exists(excel_file):
            logging.warning(f"Report file not found: {excel_file}")
            flash(f'Report not found for ticket {ticket_number}', 'error')
            return redirect(url_for('index'))
        
        file_size = os.path.getsize(excel_file)
        logging.info(f"Serving download: {excel_file} (Size: {file_size} bytes)")
        
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
    """Enhanced status checking with concurrent processing info"""
    logging.info(f"Status check for ticket: {ticket_number}")
    
    try:
        if not validate_ticket_number(ticket_number):
            return {'status': 'error', 'message': 'Invalid ticket format'}
        
        ticket_folder = os.path.join(UPLOAD_FOLDER, ticket_number)
        zip_file = os.path.join(ticket_folder, f"{ticket_number}.zip")
        excel_file = os.path.join(ticket_folder, f"{ticket_number}_analysis.xlsx")
        metadata_file = os.path.join(ticket_folder, 'metadata.json')
        
        status_info = {
            'ticket_exists': os.path.exists(ticket_folder),
            'uploaded': os.path.exists(zip_file),
            'processing_complete': os.path.exists(excel_file),
            'download_ready': os.path.exists(excel_file),
            'concurrent_processing': True,
            'max_concurrent_uploads': executor._max_workers
        }
        
        # Determine overall status
        if status_info['download_ready']:
            status_info['status'] = 'completed'
            status_info['message'] = 'Processing completed. File ready for download.'
        elif status_info['uploaded']:
            status_info['status'] = 'processing'
            status_info['message'] = 'File uploaded. Processing in progress (concurrent mode)...'
        else:
            status_info['status'] = 'not_found'
            status_info['message'] = 'Ticket not found.'
        
        logging.debug(f"Status for {ticket_number}: {status_info}")
        return status_info
        
    except Exception as e:
        logging.error(f"Error checking status for {ticket_number}: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@app.route('/stats')
def processing_stats():
    """Show current processing statistics"""
    try:
        stats = {
            'max_workers': executor._max_workers,
            'active_threads': threading.active_count(),
            'pool_shutdown': executor._shutdown,
            'concurrent_processing_enabled': True,
            'thread_pool_class': 'ThreadPoolExecutor'
        }
        return f"<pre>{json.dumps(stats, indent=2)}</pre>"
    except Exception as e:
        return f"<pre>Stats Error: {str(e)}</pre>"

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

# Cleanup thread pool on app shutdown
def cleanup_executor():
    """Cleanup thread pool on shutdown"""
    logging.info("Shutting down thread pool executor...")
    executor.shutdown(wait=True)
    logging.info("Thread pool executor shut down complete")

atexit.register(cleanup_executor)

if __name__ == '__main__':
    logging.info("=== Flask Application Startup ===")
    
    try:
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
        
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            logging.info(f"Local IP detected: {local_ip}")
        except Exception as ip_error:
            local_ip = 'localhost'
            logging.warning(f"Could not detect local IP, using localhost: {str(ip_error)}")

        logging.info("Starting Flask development server...")
        print(f"Flask app running at: http://{local_ip}:5000")
        print(f"Debug info available at: http://{local_ip}:5000/debug")
        print(f"Processing stats: http://{local_ip}:5000/stats")
        print(f"Download reports at: http://{local_ip}:5000/download/<ticket_number>")
        print(f"Check status at: http://{local_ip}:5000/check_status/<ticket_number>")
        print(f"Concurrent processing enabled: {executor._max_workers} workers")
        
        logging.info(f"Flask server starting on {local_ip}:5000")
        logging.info("Debug mode: True")
        logging.info(f"Concurrent processing: {executor._max_workers} workers")
        
        app.run(host='0.0.0.0', port=5000, debug=True)
        
    except KeyboardInterrupt:
        logging.info("Flask application stopped by user (Ctrl+C)")
        print("\nShutting down Flask application...")
        cleanup_executor()
        
    except Exception as e:
        error_msg = f"Failed to start Flask app: {str(e)}"
        logging.critical(error_msg)
        logging.exception("Full traceback for Flask startup error:")
        print(error_msg)
        raise
        
    finally:
        logging.info("=== Flask Application Shutdown ===")
