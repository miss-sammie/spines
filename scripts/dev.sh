#!/bin/bash

# Spines 2.0 Development Environment Script
# Usage: ./scripts/dev.sh [start|stop|restart|logs|shell|test]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Function to create necessary directories
create_directories() {
    echo "Setting up Spines development environment..."
    
    # Create necessary directories if they don't exist
    directories=("books" "data" "logs" "temp")
    
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            echo "Creating directory: $dir"
            mkdir -p "$dir"
        else
            echo "Directory exists: $dir"
        fi
    done
}

case "${1:-start}" in
    start)
        create_directories
        echo "🚀 Starting Spines 2.0 Development Environment..."
        docker-compose -f docker-compose.dev.yml up --build
        ;;
    stop)
        echo "🛑 Stopping Spines 2.0 Development Environment..."
        docker-compose -f docker-compose.dev.yml down
        ;;
    restart)
        create_directories
        echo "🔄 Restarting Spines 2.0 Development Environment..."
        docker-compose -f docker-compose.dev.yml down
        docker-compose -f docker-compose.dev.yml up --build
        ;;
    logs)
        echo "📋 Showing Spines 2.0 Development Logs..."
        docker-compose -f docker-compose.dev.yml logs -f
        ;;
    shell)
        echo "🐚 Opening shell in Spines 2.0 Development Container..."
        docker exec -it spines-development bash
        ;;
    test)
        echo "🧪 Running tests in Spines 2.0 Development Container..."
        docker exec -it spines-development python3 -m pytest
        ;;
    clean)
        echo "🧹 Cleaning up Spines 2.0 Development Environment..."
        docker-compose -f docker-compose.dev.yml down -v
        docker system prune -f
        ;;
    *)
        echo "Usage: $0 [start|stop|restart|logs|shell|test|clean]"
        echo ""
        echo "Commands:"
        echo "  start   - Start development environment"
        echo "  stop    - Stop development environment"
        echo "  restart - Restart development environment"
        echo "  logs    - Show development logs"
        echo "  shell   - Open shell in development container"
        echo "  test    - Run tests in development container"
        echo "  clean   - Clean up containers and images"
        exit 1
        ;;
esac 