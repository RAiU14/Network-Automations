# app.py - Non-Blocking Concurrent Upload System for Production
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
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort, jsonify

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

def check_existing_ticket(ticket: str) -> dict:
    """Check if ticket already exists and return detailed status"""
    ticket_folder = os.path.join(UPLOAD_FOLDER, ticket)
    excel_file = os.path.join(ticket_folder, f"{ticket}_analysis.xlsx")
    zip_file = os.path.join(ticket_folder, f"{ticket}.zip")
    metadata_file = os.path.join(ticket_folder, 'metadata.json')
    
    # Get file information if they exist
    status = {
        'ticket': ticket,
        'folder_exists': os.path.exists(ticket_folder),
        'excel_exists': os.path.exists(excel_file),
        'zip_exists': os.path.exists(zip_file),
        'metadata_exists': os.path.exists(metadata_file),
        'ticket_folder': ticket_folder,
        'excel_file': excel_file,
        'zip_file': zip_file
    }
    
    # Add metadata info if available
    if status['metadata_exists']:
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                status['metadata'] = {
                    'timestamp': metadata.get('timestamp'),
                    'technology': metadata.get('technology'),
                    'comment': metadata.get('comment')
                }
        except Exception as e:
            logging.error(f"Error reading metadata for {ticket}: {e}")
            status['metadata'] = {}
    
    # Add file timestamps and sizes
    if status['excel_exists']:
        try:
            status['excel_size'] = os.path.getsize(excel_file)
            status['excel_modified'] = datetime.datetime.fromtimestamp(os.path.getmtime(excel_file)).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
    
    if status['zip_exists']:
        try:
            status['zip_size'] = os.path.getsize(zip_file)
            status['zip_modified'] = datetime.datetime.fromtimestamp(os.path.getmtime(zip_file)).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
    
    return status

def async_process_upload(form_data, file_path, upload_folder, overwrite_existing=False):
    """Process upload in background thread - non-blocking"""
    try:
        logging.info(f"[CONCURRENT] Starting background processing for ticket: {form_data['ticket']}")
        logging.info(f"[CONCURRENT] Overwrite mode: {overwrite_existing}")
        
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
        
        # Call your existing process_upload function with overwrite flag
        success = process_upload(form_data, file_obj, upload_folder, overwrite_existing)
        
        if success:
            logging.info(f"[CONCURRENT] Background processing completed successfully for ticket: {form_data['ticket']}")
        else:
            logging.error(f"[CONCURRENT] Background processing failed for ticket: {form_data['ticket']}")
            
    except Exception as e:
        logging.exception(f"[CONCURRENT] Background processing error for ticket {form_data['ticket']}: {str(e)}")

# Technology options: UI label vs backend value
TECHNOLOGY_OPTIONS = [
    {"label": "Wireless", "value": "Wireless"},
    {"label": "Routing and Swiching",      "value": "Switches"},  # UI shows RNS, backend still receives "Switches"
    {"label": "Security", "value": "Security"},
    {"label": "Others",   "value": "Others"},
]

VALID_TECH_VALUES = {opt["value"] for opt in TECHNOLOGY_OPTIONS}
TECH_ALIASES = {"Routing and Swiching": "Switches"}  # just in case something posts "RNS" directly

def normalize_technology(value: str) -> str:
    """Ensure technology maps to a known backend value."""
    v = (value or "").strip()
    v = TECH_ALIASES.get(v, v)
    return v if v in VALID_TECH_VALUES else "Others"

@app.route('/')
def index():
    logging.info("Index route accessed")
    try:
        technologies = TECHNOLOGY_OPTIONS
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
        flash('Error occurred while loading the page', 'error')
        # If we can't load the page, at least render the upload form with a warning
        # fall back to the same structure so the template still works
        return render_template('upload.html', technologies=TECHNOLOGY_OPTIONS)

@app.route('/api/check_ticket', methods=['POST'])
def api_check_ticket():
    """API endpoint to check if ticket exists (for JavaScript duplicate detection)"""
    try:
        data = request.get_json()
        ticket = data.get('ticket', '').strip()
        
        if not validate_ticket_number(ticket):
            return jsonify({
                'success': False,
                'error': 'Invalid ticket format'
            }), 400
        
        status = check_existing_ticket(ticket)
        logging.info(f"API check for ticket {ticket}: folder_exists={status['folder_exists']}, excel_exists={status['excel_exists']}")
        
        return jsonify({
            'success': True,
            'exists': status['folder_exists'] and status['excel_exists'],
            'ticket': ticket,
            'details': status
        })
        
    except Exception as e:
        logging.error(f"Error in API check ticket: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/upload', methods=['POST'])
def upload():
    """Non-blocking upload route for concurrent file processing"""
    logging.info("Upload route accessed - non-blocking mode")

    try:
        # Extract request data quickly
        form_data = {
            'ticket': request.form.get('ticket', '').strip(),
            'comment': request.form.get('comment', ''),
            'technology': request.form.get('technology', '')
        }
        form_data['technology'] = normalize_technology(form_data['technology'])
        file_obj = request.files.get('file')
        overwrite_confirmed = request.form.get('overwrite_confirmed', 'false') == 'true'
        
        # Basic validation
        if not form_data['ticket'] or not file_obj:
            return jsonify({
                'success': False,
                'error': 'Ticket number and file are required'
            }), 400
        
        if not validate_ticket_number(form_data['ticket']):
            return jsonify({
                'success': False,
                'error': 'Invalid ticket number format. Use SVR followed by numbers.'
            }), 400
        
        # Log request details
        logging.info(f"Processing upload for ticket: {form_data['ticket']} (overwrite: {overwrite_confirmed})")
        logging.info(f"Technology: {form_data['technology']}")
        logging.info(f"File: {file_obj.filename}")
        logging.info(f"File size: {file_obj.content_length if hasattr(file_obj, 'content_length') else 'Unknown'}")
        
        # Save file immediately and start background processing
        ticket_folder = os.path.join(UPLOAD_FOLDER, form_data['ticket'])
        os.makedirs(ticket_folder, exist_ok=True)
        file_path = os.path.join(ticket_folder, f"{form_data['ticket']}.zip")
        
        # Save file (this is the only potentially blocking operation)
        file_obj.save(file_path)
        logging.info(f"File saved: {file_path}")
        
        # Submit to thread pool for concurrent processing (non-blocking)
        future = executor.submit(async_process_upload, form_data, file_path, UPLOAD_FOLDER, overwrite_confirmed)
        active_threads = threading.active_count()
        logging.info(f"[CONCURRENT] Task submitted to thread pool. Active threads: {active_threads}")
        
        # Return success immediately - don't wait for processing
        message = f'Upload successful for ticket {form_data["ticket"]}! Processing started in background.'
        if overwrite_confirmed:
            message += ' (Overwrite mode)'
        
        return jsonify({
            'success': True,
            'message': message,
            'ticket': form_data['ticket'],
            'overwrite_mode': overwrite_confirmed,
            'processing_started': True
        })
        
    except Exception as e:
        error_msg = f"Upload error: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback for upload error:")
        return jsonify({
            'success': False,
            'error': 'Upload failed. Please try again.'
        }), 500

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
    """Check processing status for a ticket"""
    logging.info(f"Status check for ticket: {ticket_number}")
    
    try:
        if not validate_ticket_number(ticket_number):
            return {'status': 'error', 'message': 'Invalid ticket format'}
        
        existing_status = check_existing_ticket(ticket_number)
        
        status_info = {
            'ticket_exists': existing_status['folder_exists'],
            'uploaded': existing_status['zip_exists'],
            'processing_complete': existing_status['excel_exists'],
            'download_ready': existing_status['excel_exists'],
            'concurrent_processing': True,
            'max_concurrent_uploads': executor._max_workers,
            'ticket': ticket_number
        }
        
        # Add file info if available
        if existing_status.get('excel_size'):
            status_info['excel_size'] = existing_status['excel_size']
        if existing_status.get('excel_modified'):
            status_info['excel_modified'] = existing_status['excel_modified']
        
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
        return jsonify(status_info)
        
    except Exception as e:
        logging.error(f"Error checking status for {ticket_number}: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/stats')
def processing_stats():
    """Show current processing statistics"""
    try:
        stats = {
            'max_workers': executor._max_workers,
            'active_threads': threading.active_count(),
            'pool_shutdown': executor._shutdown,
            'concurrent_processing_enabled': True,
            'thread_pool_class': 'ThreadPoolExecutor',
            'upload_folder': UPLOAD_FOLDER,
            'upload_folder_exists': os.path.exists(UPLOAD_FOLDER),
            'current_time': datetime.datetime.now().isoformat(),
            'system_info': {
                'platform': os.name,
                'python_version': sys.version.split()[0]
            }
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug')
def debug():
    """Enhanced debug information with system details"""
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
            'environment': {
                'platform': os.name,
                'python_version': sys.version,
                'flask_version': getattr(__import__('flask'), '__version__', 'Unknown')
            },
            'request_info': {
                'remote_addr': request.remote_addr if request else 'No request context',
                'user_agent': str(request.user_agent) if request else 'No request context'
            },
            'timestamp': datetime.datetime.now().isoformat()
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

@app.route('/reset')
def reset_form():
    """Reset form and clear any flash messages"""
    logging.info("Form reset requested")
    return redirect(url_for('index'))

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.datetime.now().isoformat(),
            'upload_folder_accessible': os.path.exists(UPLOAD_FOLDER) and os.access(UPLOAD_FOLDER, os.W_OK),
            'thread_pool_active': not executor._shutdown,
            'active_threads': threading.active_count(),
            'version': '1.0.0'
        }
        return jsonify(health_status)
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.datetime.now().isoformat()
        }), 500

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    logging.warning(f"404 Error: {request.url} not found")
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found'}), 404
    flash('Page not found', 'error')
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logging.error(f"500 Internal Server Error: {str(error)}")
    logging.exception("Full traceback for 500 error:")
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    flash('An internal server error occurred', 'error')
    return redirect(url_for('index'))

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large errors"""
    logging.warning(f"File too large error: {str(error)}")
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({'error': 'File too large'}), 413
    flash('File is too large. Please upload a smaller file.', 'error')
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
        
        # Get local IP
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            logging.info(f"Local IP detected: {local_ip}")
        except Exception as ip_error:
            local_ip = 'localhost'
            logging.warning(f"Could not detect local IP, using localhost: {str(ip_error)}")

        # Startup information
        logging.info("Starting Flask development server...")
        print(f"\n🚀 Flask Upload System Starting...")
        print(f"📍 Server: http://{local_ip}:5000")
        print(f"🔍 Debug: http://{local_ip}:5000/debug")
        print(f"📊 Stats: http://{local_ip}:5000/stats")
        print(f"❤️  Health: http://{local_ip}:5000/health")
        print(f"📥 Downloads: http://{local_ip}:5000/download/<ticket_number>")
        print(f"📋 Status: http://{local_ip}:5000/check_status/<ticket_number>")
        print(f"⚡ Concurrent processing: {executor._max_workers} workers")
        print(f"🎯 Non-blocking uploads: ENABLED")
        print("=" * 60)
        
        logging.info(f"Flask server starting on {local_ip}:5000")
        logging.info("Debug mode: True")
        logging.info(f"Concurrent processing: {executor._max_workers} workers")
        logging.info("Non-blocking upload mode: ENABLED")
        
        # Start Flask app
        app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
        
    except KeyboardInterrupt:
        logging.info("Flask application stopped by user (Ctrl+C)")
        print("\n🛑 Shutting down Flask application...")
        cleanup_executor()
        
    except Exception as e:
        error_msg = f"Failed to start Flask app: {str(e)}"
        logging.critical(error_msg)
        logging.exception("Full traceback for Flask startup error:")
        print(f"❌ {error_msg}")
        raise
        
    finally:
        logging.info("=== Flask Application Shutdown ===")
