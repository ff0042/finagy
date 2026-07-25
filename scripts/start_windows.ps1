# FinAlly - Windows PowerShell Launch Script
$ErrorActionPreference = "Stop"

Write-Host "[INFO] Launching FinAlly (Finance Ally)..." -ForegroundColor Cyan

$ImageName = "finally-app"
$ContainerName = "finally-container"
$Port = 8000

# Determine project root directory whether script is run from project root or scripts folder
if ($PSScriptRoot) {
    $ProjectDir = Split-Path -Parent $PSScriptRoot
} else {
    $ProjectDir = Get-Location
}

# Check if Docker is running
docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker is not running. Please start Docker Desktop and try again." -ForegroundColor Red
    exit 1
}

# Build image
Write-Host "[BUILD] Building Docker image ($ImageName)..." -ForegroundColor Yellow
docker build -t $ImageName $ProjectDir
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker build failed." -ForegroundColor Red
    exit 1
}

# Stop existing container if running
$ExistingContainer = docker ps -a -q -f "name=$ContainerName"
if ($ExistingContainer) {
    Write-Host "[CLEANUP] Stopping previous container instance..." -ForegroundColor Yellow
    docker stop $ContainerName 2>&1 | Out-Null
    docker rm $ContainerName 2>&1 | Out-Null
}

# Ensure db directory exists
$EnvFile = Join-Path $ProjectDir ".env"
$DbVolumeDir = Join-Path $ProjectDir "db"

if (-not (Test-Path $DbVolumeDir)) {
    New-Item -ItemType Directory -Path $DbVolumeDir | Out-Null
}

# Run container
Write-Host "[RUN] Starting FinAlly container on port $Port..." -ForegroundColor Green
if (Test-Path $EnvFile) {
    docker run -d --name $ContainerName -p "${Port}:8000" --env-file $EnvFile -v "${DbVolumeDir}:/app/db" $ImageName
} else {
    docker run -d --name $ContainerName -p "${Port}:8000" -v "${DbVolumeDir}:/app/db" $ImageName
}

$Url = "http://localhost:$Port"
Write-Host "[SUCCESS] FinAlly service is up and running!" -ForegroundColor Green
Write-Host "[URL] Access the workstation at: $Url" -ForegroundColor Cyan
