# EN-NMS Auto Start Script
Write-Host "Setting up EN-NMS prototype..." -ForegroundColor Cyan

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "Python not found. Please install Python 3.8+ and add to PATH." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
}

& .\venv\Scripts\Activate.ps1

Write-Host "Installing required packages..."
pip install pysnmp jinja2 pyyaml

Write-Host "Initializing database..."
python -c "from utils import init_db, load_config; cfg = load_config('config.yaml'); init_db(cfg['database']['path'])"

Write-Host "Adding devices from config.yaml to database..."
python -c "import sqlite3, yaml; cfg = yaml.safe_load(open('config.yaml')); conn = sqlite3.connect(cfg['database']['path']); cursor = conn.cursor(); [cursor.execute('INSERT OR IGNORE INTO devices (name, ip, snmp_community, snmp_version) VALUES (?,?,?,?)', (d['name'], d['ip'], d['snmp_community'], d['snmp_version'])) for d in cfg['devices']]; conn.commit(); conn.close()"

Write-Host "Running first polling cycle..."
python poller.py config.yaml

Write-Host "Generating static dashboard..."
python dashboard_generator.py

Write-Host "`nEN-NMS prototype is ready!" -ForegroundColor Green
Write-Host "Open the 'static/index.html' file in your browser to view the dashboard." -ForegroundColor Yellow
Write-Host "To run polling periodically, use: .\run_continuous.ps1" -ForegroundColor Yellow
