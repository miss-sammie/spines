# Spines 2.0 Production Environment Script (PowerShell)
# Usage: .\scripts\prod.ps1 [start|stop|restart|logs|status|backup|update|deploy]

param(
    [string]$Action = "start"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Set-Location $ProjectDir

switch ($Action.ToLower()) {
    "start" {
        Write-Host " Starting Spines 2.0 Production Environment..." -ForegroundColor Green
        docker-compose -f docker-compose.prod.yml --env-file $ProjectDir\.env up --build -d
        Write-Host " Production environment started!" -ForegroundColor Green
        Write-Host " Check status with: .\scripts\prod.ps1 status" -ForegroundColor Cyan
        Write-Host " View logs with: .\scripts\prod.ps1 logs" -ForegroundColor Cyan
    }
    "stop" {
        Write-Host " Stopping Spines 2.0 Production Environment..." -ForegroundColor Yellow
        docker-compose -f docker-compose.prod.yml --env-file $ProjectDir\.env down
        Write-Host " Production environment stopped!" -ForegroundColor Green
    }
    "restart" {
        Write-Host " Restarting Spines 2.0 Production Environment..." -ForegroundColor Cyan
        docker-compose -f docker-compose.prod.yml --env-file $ProjectDir\.env down
        docker-compose -f docker-compose.prod.yml --env-file $ProjectDir\.env up --build -d
        Write-Host " Production environment restarted!" -ForegroundColor Green
    }
    "deploy" {
        Write-Host " Deploying Spines 2.0 to Production..." -ForegroundColor Magenta
        
        # Pull latest changes
        if (Test-Path ".git") {
            Write-Host " Pulling latest changes..." -ForegroundColor Cyan
            git pull origin main
        }
        
        # Ensure directories exist
        Write-Host " Ensuring directories exist..." -ForegroundColor Cyan
        @("books", "data", "logs", "temp") | ForEach-Object {
            if (!(Test-Path $_)) {
                New-Item -ItemType Directory -Path $_ -Force | Out-Null
            }
        }
        
        # Stop existing containers
        Write-Host " Stopping existing containers..." -ForegroundColor Cyan
        docker-compose -f docker-compose.prod.yml --env-file $ProjectDir\.env down
        
        Write-Host "  Building and starting production environment..." -ForegroundColor Cyan
        docker-compose -f docker-compose.prod.yml --env-file $ProjectDir\.env build
        docker-compose -f docker-compose.prod.yml --env-file $ProjectDir\.env up -d
        
        # Wait and verify
        Write-Host " Waiting for services to be ready..." -ForegroundColor Cyan
        Start-Sleep 15
        
        # Health check
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8888/api/health" -UseBasicParsing -TimeoutSec 10
            Write-Host " Health check passed - deployment successful!" -ForegroundColor Green
        }
        catch {
            Write-Host "  Health check failed or endpoint not available" -ForegroundColor Yellow
        }
        
        Write-Host " Production deployment completed!" -ForegroundColor Green
        Write-Host " Spines should be available at http://localhost:8888" -ForegroundColor Cyan
    }
    "logs" {
        Write-Host " Showing Spines 2.0 Production Logs..." -ForegroundColor Blue
        docker-compose -f docker-compose.prod.yml --env-file $ProjectDir\.env logs -f
    }
    "status" {
        Write-Host " Spines 2.0 Production Environment Status:" -ForegroundColor White
        Write-Host ""
        docker-compose -f docker-compose.prod.yml --env-file $ProjectDir\.env ps
        Write-Host ""
        Write-Host " Health Check:" -ForegroundColor White
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8888/api/health" -UseBasicParsing
            Write-Host " Health check passed" -ForegroundColor Green
        }
        catch {
            Write-Host " Health check failed" -ForegroundColor Red
        }
    }
    "backup" {
        Write-Host " Creating backup of Spines 2.0 data..." -ForegroundColor Yellow
        $BackupDir = "backups\$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
        
        # Backup books
        if (Test-Path "books") {
            Write-Host " Backing up books..." -ForegroundColor Cyan
            Copy-Item -Path "books" -Destination $BackupDir -Recurse
        }
        
        # Backup data
        if (Test-Path "data") {
            Write-Host " Backing up data..." -ForegroundColor Cyan
            Copy-Item -Path "data" -Destination $BackupDir -Recurse
        }
        
        Write-Host " Backup created in: $BackupDir" -ForegroundColor Green
    }
    "update" {
        Write-Host " Updating Spines 2.0 Production Environment..." -ForegroundColor Cyan
        
        # Pull latest changes
        git pull origin main
        
        # Rebuild and restart
        docker-compose -f docker-compose.prod.yml --env-file $ProjectDir\.env down
        docker-compose -f docker-compose.prod.yml --env-file $ProjectDir\.env up --build -d
        
        Write-Host " Production environment updated!" -ForegroundColor Green
    }
    "shell" {
        Write-Host " Opening shell in Spines 2.0 Production Container..." -ForegroundColor Magenta
        docker exec -it spines-production bash
    }
    "clean" {
        Write-Host " Cleaning up Spines 2.0 Production Environment..." -ForegroundColor Red
        docker-compose -f docker-compose.prod.yml --env-file $ProjectDir\.env down -v
        docker system prune -f
    }
    default {
        Write-Host "Usage: .\scripts\prod.ps1 [start|stop|restart|logs|status|backup|update|deploy|shell|clean]" -ForegroundColor White
        Write-Host ""
        Write-Host "Commands:" -ForegroundColor White
        Write-Host "  start   - Start production environment" -ForegroundColor Gray
        Write-Host "  stop    - Stop production environment" -ForegroundColor Gray
        Write-Host "  restart - Restart production environment" -ForegroundColor Gray
        Write-Host "  deploy  - Full deployment with git pull and rebuild" -ForegroundColor Gray
        Write-Host "  logs    - Show production logs" -ForegroundColor Gray
        Write-Host "  status  - Show production status and health" -ForegroundColor Gray
        Write-Host "  backup  - Create backup of data" -ForegroundColor Gray
        Write-Host "  update  - Update and restart production" -ForegroundColor Gray
        Write-Host "  shell   - Open shell in production container" -ForegroundColor Gray
        Write-Host "  clean   - Clean up containers and images" -ForegroundColor Gray
        exit 1
    }
} 