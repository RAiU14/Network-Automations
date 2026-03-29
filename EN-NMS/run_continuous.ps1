while ($true) {
    Write-Host "Polling at $(Get-Date)" -ForegroundColor Cyan
    python poller.py config.yaml
    python dashboard_generator.py
    Start-Sleep -Seconds 60
}
