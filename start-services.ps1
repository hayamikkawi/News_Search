# GlobalSearch Quick Start Script
# Usage: .\start-services.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GlobalSearch Service Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "[1/5] Checking Docker..." -ForegroundColor Yellow
try {
    docker ps | Out-Null
    Write-Host "✓ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker is not running. Please start Docker Desktop first" -ForegroundColor Red
    exit 1
}

# Create necessary directories
Write-Host ""
Write-Host "[2/5] Creating necessary directories..." -ForegroundColor Yellow
$directories = @(
    "shared/indexer/input",
    "shared/indexer/output", 
    "shared/logs",
    "mysql-data"
)

foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Gray
    }
}
Write-Host "✓ Directory structure ready" -ForegroundColor Green

# Stop old containers (if any)
Write-Host ""
Write-Host "[3/5] Cleaning up old containers..." -ForegroundColor Yellow
docker-compose -f docker-compose.crawler-full.yml down 2>$null
Write-Host "✓ Cleanup complete" -ForegroundColor Green

# Start all services
Write-Host ""
Write-Host "[4/5] Starting all services..." -ForegroundColor Yellow
Write-Host "  This may take a few minutes, please wait..." -ForegroundColor Gray
docker-compose -f docker-compose.crawler-full.yml up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Services started successfully" -ForegroundColor Green
} else {
    Write-Host "✗ Failed to start services" -ForegroundColor Red
    exit 1
}

# Wait for services to be ready
Write-Host ""
Write-Host "[5/5] Waiting for services to be ready..." -ForegroundColor Yellow
Write-Host "  Waiting for database initialization..." -ForegroundColor Gray
Start-Sleep -Seconds 15

Write-Host "  Waiting for IR service to start..." -ForegroundColor Gray
$maxAttempts = 30
$attempt = 0
$apiReady = $false

while ($attempt -lt $maxAttempts -and !$apiReady) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $apiReady = $true
        }
    } catch {
        # Continue waiting
    }
    
    if (!$apiReady) {
        Write-Host "." -NoNewline -ForegroundColor Gray
        Start-Sleep -Seconds 2
        $attempt++
    }
}

Write-Host ""
if ($apiReady) {
    Write-Host "✓ IR API service is ready" -ForegroundColor Green
} else {
    Write-Host "⚠ IR API service is taking longer to start, please check later" -ForegroundColor Yellow
}

# Display status
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Service Status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
docker-compose -f docker-compose.crawler-full.yml ps

# Display access information
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Access Information" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Frontend UI: " -NoNewline; Write-Host "http://localhost" -ForegroundColor Green
Write-Host "API Docs: " -NoNewline; Write-Host "http://localhost:8000/docs" -ForegroundColor Green
Write-Host "API Health: " -NoNewline; Write-Host "http://localhost:8000/health" -ForegroundColor Green
Write-Host ""

# Display useful commands
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Useful Commands" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "View all logs:" -ForegroundColor Yellow
Write-Host "  docker-compose -f docker-compose.crawler-full.yml logs -f" -ForegroundColor Gray
Write-Host ""
Write-Host "View IR service logs:" -ForegroundColor Yellow
Write-Host "  docker logs -f ttds_ir" -ForegroundColor Gray
Write-Host ""
Write-Host "View crawler logs:" -ForegroundColor Yellow
Write-Host "  docker logs -f ttds_crawler" -ForegroundColor Gray
Write-Host ""
Write-Host "Stop all services:" -ForegroundColor Yellow
Write-Host "  docker-compose -f docker-compose.crawler-full.yml down" -ForegroundColor Gray
Write-Host ""

# Ask whether to open browser
Write-Host ""
$openBrowser = Read-Host "Open frontend in browser? (Y/n)"
if ($openBrowser -ne 'n' -and $openBrowser -ne 'N') {
    Start-Process "http://localhost"
}

Write-Host ""
Write-Host "✓ Startup complete!" -ForegroundColor Green
Write-Host ""
