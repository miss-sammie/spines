#!/bin/bash

# Spines 2.0 Production Environment Script
# Usage: ./scripts/prod.sh [start|stop|restart|logs|status|backup|update]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

case "${1:-start}" in
    start)
        echo "🚀 Starting Spines 2.0 Production Environment..."
        docker-compose -f docker-compose.prod.yml up --build -d
        echo "✅ Production environment started!"
        echo "📊 Check status with: $0 status"
        echo "📋 View logs with: $0 logs"
        ;;
    stop)
        echo "🛑 Stopping Spines 2.0 Production Environment..."
        docker-compose -f docker-compose.prod.yml down
        echo "✅ Production environment stopped!"
        ;;
    restart)
        echo "🔄 Restarting Spines 2.0 Production Environment..."
        docker-compose -f docker-compose.prod.yml down
        docker-compose -f docker-compose.prod.yml up --build -d
        echo "✅ Production environment restarted!"
        ;;
    logs)
        echo "📋 Showing Spines 2.0 Production Logs..."
        docker-compose -f docker-compose.prod.yml logs -f
        ;;
    status)
        echo "📊 Spines 2.0 Production Environment Status:"
        echo ""
        docker-compose -f docker-compose.prod.yml ps
        echo ""
        echo "🔍 Health Check:"
        curl -s http://localhost:8888/api/health || echo "❌ Health check failed"
        ;;
    backup)
        echo "💾 Creating backup of Spines 2.0 data..."
        BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        # Backup books
        if [ -d "books" ]; then
            echo "📚 Backing up books..."
            cp -r books "$BACKUP_DIR/"
        fi
        
        # Backup data
        if [ -d "data" ]; then
            echo "💿 Backing up data..."
            cp -r data "$BACKUP_DIR/"
        fi
        
        echo "✅ Backup created in: $BACKUP_DIR"
        ;;
    update)
        echo "🔄 Updating Spines 2.0 Production Environment..."
        
        # Pull latest changes
        git pull origin main
        
        # Rebuild and restart
        docker-compose -f docker-compose.prod.yml down
        docker-compose -f docker-compose.prod.yml up --build -d
        
        echo "✅ Production environment updated!"
        ;;
    shell)
        echo "🐚 Opening shell in Spines 2.0 Production Container..."
        docker exec -it spines-production bash
        ;;
    clean)
        echo "🧹 Cleaning up Spines 2.0 Production Environment..."
        docker-compose -f docker-compose.prod.yml down -v
        docker system prune -f
        ;;
    *)
        echo "Usage: $0 [start|stop|restart|logs|status|backup|update|shell|clean]"
        echo ""
        echo "Commands:"
        echo "  start   - Start production environment"
        echo "  stop    - Stop production environment"
        echo "  restart - Restart production environment"
        echo "  logs    - Show production logs"
        echo "  status  - Show production status and health"
        echo "  backup  - Create backup of data"
        echo "  update  - Update and restart production"
        echo "  shell   - Open shell in production container"
        echo "  clean   - Clean up containers and images"
        exit 1
        ;;
esac 