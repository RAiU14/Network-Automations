import os
import sys
import subprocess
from pathlib import Path

# Ensure we are in the root directory
os.chdir(Path(__file__).resolve().parent)

def check_dependencies():
    print("Checking dependencies...")
    try:
        import django
        import rest_framework
        import corsheaders
        print("[OK] Core Django dependencies found.")
    except ImportError as e:
        print(f"[ERROR] Missing dependency: {e.name}")
        print("Please run: pip install django djangorestframework django-cors-headers")
        sys.exit(1)

def init_database():
    print("Ensuring Django database is synchronized...")
    subprocess.run([sys.executable, "django_backend/manage.py", "migrate"], check=True)

def run_backend():
    print("\nStarting Network Automations Platform (Django Mode)...")
    print("Main API: http://127.0.0.1:8000/api/")
    print("Admin Portal: http://127.0.0.1:8000/admin/ (admin / admin123)")
    print("Press Ctrl+C to stop.\n")
    
    try:
        subprocess.run([
            sys.executable, "django_backend/manage.py", "runserver", "127.0.0.1:8000"
        ])
    except KeyboardInterrupt:
        print("\nShutdown requested.")

if __name__ == "__main__":
    check_dependencies()
    init_database()
    run_backend()
