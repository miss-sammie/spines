# Spines 2.0 Development Environment Script (PowerShell)
# Usage: .\scripts\dev.ps1 [start|stop|restart|logs|shell|test]

param(
    [string]$Action = "start"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Set-Location $ProjectDir

switch ($Action.ToLower()) {
    "start" {
        Write-Host "🚀 Starting Spines 2.0 Development Environment..." -ForegroundColor Green
        docker-compose -f docker-compose.dev.yml up --build
    }
    "stop" {
        Write-Host "🛑 Stopping Spines 2.0 Development Environment..." -ForegroundColor Yellow
        docker-compose -f docker-compose.dev.yml down
    }
    "restart" {
        Write-Host "🔄 Restarting Spines 2.0 Development Environment..." -ForegroundColor Cyan
        docker-compose -f docker-compose.dev.yml down
        docker-compose -f docker-compose.dev.yml up --build
    }
    "logs" {
        Write-Host "📋 Showing Spines 2.0 Development Logs..." -ForegroundColor Blue
        docker-compose -f docker-compose.dev.yml logs -f
    }
    "shell" {
        Write-Host "🐚 Opening shell in Spines 2.0 Development Container..." -ForegroundColor Magenta
        docker exec -it spines-development bash
    }
    "test" {
        Write-Host "🧪 Running tests in Spines 2.0 Development Container..." -ForegroundColor Cyan
        docker exec -it spines-development python3 -m pytest
    }
    "clean" {
        Write-Host "🧹 Cleaning up Spines 2.0 Development Environment..." -ForegroundColor Red
        docker-compose -f docker-compose.dev.yml down -v
        docker system prune -f
    }
    default {
        Write-Host "Usage: .\scripts\dev.ps1 [start|stop|restart|logs|shell|test|clean]" -ForegroundColor White
        Write-Host ""
        Write-Host "Commands:" -ForegroundColor White
        Write-Host "  start   - Start development environment" -ForegroundColor Gray
        Write-Host "  stop    - Stop development environment" -ForegroundColor Gray
        Write-Host "  restart - Restart development environment" -ForegroundColor Gray
        Write-Host "  logs    - Show development logs" -ForegroundColor Gray
        Write-Host "  shell   - Open shell in development container" -ForegroundColor Gray
        Write-Host "  test    - Run tests in development container" -ForegroundColor Gray
        Write-Host "  clean   - Clean up containers and images" -ForegroundColor Gray
    }
} 