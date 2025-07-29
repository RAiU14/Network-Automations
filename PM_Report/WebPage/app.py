import os
from flask import Flask, render_template, request, redirect, url_for, flash

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'zip'}

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    technologies = ['Wireless', 'Switching', 'Security', 'Others']  # expand as needed
    return render_template('upload.html', technologies=technologies)

@app.route('/upload', methods=['POST'])
def upload():
    ticket = request.form.get('ticket')
    comment = request.form.get('comment')
    technology = request.form.get('technology')
    file = request.files.get('file')

    if not ticket:
        flash('Ticket Number is required.', 'warning')
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

    # Create upload folder if not exists
    ticket_folder = os.path.join(UPLOAD_FOLDER, ticket)
    os.makedirs(ticket_folder, exist_ok=True)

    # Save the uploaded file
    filename = "logs.zip"
    file_path = os.path.join(ticket_folder, filename)
    file.save(file_path)

    # Save a simple metadata file
    meta_path = os.path.join(ticket_folder, 'metadata.txt')
    with open(meta_path, 'w') as f:
        f.write(f'Ticket Number: {ticket}\n')
        f.write(f'Comment: {comment}\n')
        f.write(f'Technology: {technology}\n')

    flash(f'Logs uploaded successfully for ticket {ticket}.', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    # Run on all IPs (0.0.0.0) to allow LAN access
    app.run(host='0.0.0.0', port=5000, debug=True)
