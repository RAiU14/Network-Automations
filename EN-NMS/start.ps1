Write-Host "Starting EN-NMS with React frontend..." -ForegroundColor Cyan

# Start FastAPI backend in background
Start-Process -NoNewWindow python -ArgumentList "backend.py"

# Wait a moment for backend to start
Start-Sleep -Seconds 2

# Start React dev server
Set-Location frontend
npm run dev