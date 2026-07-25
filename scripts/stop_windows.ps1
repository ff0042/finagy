# FinAlly - Windows PowerShell Stop Script
$ErrorActionPreference = "Continue"

Write-Host "[STOP] Stopping FinAlly container..." -ForegroundColor Yellow

$ContainerName = "finally-container"
docker stop $ContainerName 2>&1 | Out-Null
docker rm $ContainerName 2>&1 | Out-Null

Write-Host "[SUCCESS] FinAlly container stopped. Data persists in volume." -ForegroundColor Green
