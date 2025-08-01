# app.py - View/Route Layer (MVC)
import os
import sys
import json
import socket
import logging
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash

# Import controller
from controller import get_controller

# Setup logging
log_dir = os.path.join(os.path.dirname(__file__), "app_run_logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"),
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
logging.info(f"Allowed extensions: {ALLOWED_EXTENSIONS}")

# Flask app setup
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

logging.info("✅ Flask app created successfully")
logging.debug(f"Flask app config: UPLOAD_FOLDER={app.config['UPLOAD_FOLDER']}")

# Initialize controller
try:
    controller = get_controller(UPLOAD_FOLDER, ALLOWED_EXTENSIONS)
    logging.info("✅ Controller initialized successfully")
except Exception as e:
    logging.critical(f" Failed to initialize controller: {str(e)}")
    raise

@app.route('/')
def index():
    """Home page with upload form"""
    logging.info("📄 Index route accessed")
    try:
        technologies = ['Wireless', 'Switches', 'Security', 'Others']
        logging.debug(f"Available technologies: {technologies}")
        
        # Check if upload folder exists
        upload_exists = os.path.exists(UPLOAD_FOLDER)
        logging.debug(f"Upload folder exists: {upload_exists}")
        
        if not upload_exists:
            logging.warning(f"Upload folder does not exist: {UPLOAD_FOLDER}")
        
        logging.info("✅ Index page rendered successfully")
        return render_template('upload.html', technologies=technologies)
        
    except Exception as e:
        logging.error(f" Error in index route: {str(e)}")
        logging.exception("Full traceback for index route error:")
        flash('An error occurred while loading the page', 'error')
        return render_template('upload.html', technologies=['Wireless', 'Switches', 'Security', 'Others'])

@app.route('/upload', methods=['POST'])
def upload():
    """Handle file upload - delegates to controller"""
    logging.info("📤 Upload route accessed")
    
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
        logging.info(f"  Ticket: {form_data['ticket']}")
        logging.info(f"  Technology: {form_data['technology']}")
        logging.info(f"  Comment length: {len(form_data['comment'])} characters")
        
        if file_obj and hasattr(file_obj, 'filename'):
            logging.info(f"  File: {file_obj.filename}")
            logging.debug(f"  File content type: {getattr(file_obj, 'content_type', 'Unknown')}")
        else:
            logging.warning("  No file provided in request")
        
        # Delegate to controller
        logging.info("🔄 Delegating to controller for processing...")
        result = controller.process_upload(form_data, file_obj)
        
        # Log controller result
        logging.info(f"Controller processing result: {result['success']}")
        if result['success']:
            logging.info(f"✅ Upload successful: {result['message']}")
        else:
            logging.warning(f"⚠️ Upload failed: {result['message']}")
            logging.debug(f"Errors: {result['errors']}")
        
        # Handle controller response
        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(result['message'], 'error')
            # Log flash message for debugging
            logging.debug(f"Flash message set: {result['message']}")
        
        redirect_target = result.get('redirect_to', 'index')
        logging.info(f"🔀 Redirecting to: {redirect_target}")
        return redirect(url_for(redirect_target))
        
    except Exception as e:
        error_msg = f"Unexpected error in upload route: {str(e)}"
        logging.error(f" {error_msg}")
        logging.exception("Full traceback for upload route error:")
        flash('An unexpected error occurred during upload processing', 'error')
        return redirect(url_for('index'))

@app.route('/debug')
def debug():
    """Debug information endpoint"""
    logging.info("🔍 Debug route accessed")
    
    try:
        # Check module availability
        logging.debug("Checking module availability...")
        modules = controller.check_module_availability()
        
        # Gather debug information
        debug_info = {
            'base_directory': BASE_DIR,
            'project_root': PROJECT_ROOT,
            'upload_folder': UPLOAD_FOLDER,
            'upload_folder_exists': os.path.exists(UPLOAD_FOLDER),
            'module_availability': modules,
            'current_directory': os.getcwd(),
            'python_path_count': len(sys.path) if 'sys' in globals() else 'sys not imported',
            'flask_config': dict(app.config),
            'request_info': {
                'remote_addr': request.remote_addr if request else 'No request context',
                'user_agent': str(request.user_agent) if request else 'No request context'
            }
        }
        
        # Log debug access
        logging.info("Debug information compiled successfully")
        logging.debug(f"Modules available: {sum(modules.values())}/{len(modules)}")
        
        # Check for any missing critical paths or modules
        critical_paths = [BASE_DIR, PROJECT_ROOT, UPLOAD_FOLDER]
        missing_paths = [path for path in critical_paths if not os.path.exists(path)]
        
        if missing_paths:
            logging.warning(f"Missing critical paths: {missing_paths}")
            debug_info['missing_paths'] = missing_paths
        
        return f"<pre>{json.dumps(debug_info, indent=2, default=str)}</pre>"
        
    except Exception as e:
        error_msg = f"Error in debug route: {str(e)}"
        logging.error(f" {error_msg}")
        logging.exception("Full traceback for debug route error:")
        return f"<pre>Debug Error: {error_msg}</pre>"

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
            logging.info(f"📁 Created upload folder: {UPLOAD_FOLDER}")
            print(f"📁 Created upload folder: {UPLOAD_FOLDER}")
        else:
            logging.info(f"📁 Upload folder already exists: {UPLOAD_FOLDER}")

        logging.info(f"📂 Upload folder: {UPLOAD_FOLDER}")
        logging.info(f"🔗 Upload folder exists: {os.path.exists(UPLOAD_FOLDER)}")
        print(f"📂 Upload folder: {UPLOAD_FOLDER}")
        print(f"🔗 Upload folder exists: {os.path.exists(UPLOAD_FOLDER)}")
        
        # Test module availability
        logging.info("🧪 Testing module availability...")
        modules = controller.check_module_availability()
        available_count = sum(modules.values())
        total_count = len(modules)
        
        logging.info(f"📋 Module availability: {available_count}/{total_count} modules available")
        print(f"📋 Available modules: {modules}")
        
        if available_count == 0:
            logging.critical("🚨 No modules are available - application may not function correctly")
        elif available_count < total_count:
            logging.warning(f"⚠️ Only {available_count}/{total_count} modules available - some features may be limited")
        else:
            logging.info("✅ All modules available")

        # Get local IP for access information
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            logging.info(f"🌐 Local IP detected: {local_ip}")
        except Exception as ip_error:
            local_ip = 'localhost'
            logging.warning(f"Could not detect local IP, using localhost: {str(ip_error)}")

        # Start Flask app
        logging.info("🚀 Starting Flask development server...")
        print(f"🚀 Flask app running at: http://{local_ip}:5000")
        print(f"🔍 Debug info available at: http://{local_ip}:5000/debug")
        
        logging.info(f"Flask server starting on {local_ip}:5000")
        logging.info("Debug mode: True")
        
        app.run(host='0.0.0.0', port=5000, debug=True)
        
    except KeyboardInterrupt:
        logging.info("🛑 Flask application stopped by user (Ctrl+C)")
        print("\n🛑 Flask application stopped by user")
        
    except Exception as e:
        error_msg = f"Failed to start Flask app: {str(e)}"
        logging.critical(f" {error_msg}")
        logging.exception("Full traceback for Flask startup error:")
        print(f" {error_msg}")
        raise
        
    finally:
        logging.info("=== Flask Application Shutdown ===")
