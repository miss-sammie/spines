#!/bin/bash

# Deployment script for Spines 2.0
# This script can be used by GitHub Actions or run manually

set -e

# Configuration
ENVIRONMENT=${1:-production}
COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
CONTAINER_NAME="spines-${ENVIRONMENT}"

echo "🚀 Deploying Spines 2.0 to ${ENVIRONMENT} environment..."

# Check if we're in the right directory
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ Error: $COMPOSE_FILE not found. Are you in the correct directory?"
    exit 1
fi

# Pull latest changes (if running from GitHub Actions or if .git exists)
if [ -d ".git" ]; then
    echo "📥 Pulling latest changes..."
    git pull origin main
fi

# Create required directories if they don't exist
echo "📁 Ensuring directories exist..."
mkdir -p books data logs temp

# Build and deploy
echo "🏗️  Building and starting containers..."
docker-compose -f "$COMPOSE_FILE" down

# Clean up old images to save space
echo "🧹 Cleaning up old Docker images..."
docker system prune -f

# Build with no cache to ensure fresh deployment
docker-compose -f "$COMPOSE_FILE" build --no-cache

# Start the services
docker-compose -f "$COMPOSE_FILE" up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 15

# Check if services are running
if docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
    echo "✅ Deployment successful! Services are running."
    
    # Show running containers
    echo "📊 Running containers:"
    docker-compose -f "$COMPOSE_FILE" ps
    
    # Test health endpoint if available
    echo "🔍 Testing health endpoint..."
    sleep 5
    if curl -f http://localhost:8888/api/health > /dev/null 2>&1; then
        echo "✅ Health check passed"
    else
        echo "⚠️  Health check failed or endpoint not available"
    fi
    
    # Show recent logs
    echo "📋 Recent logs:"
    docker-compose -f "$COMPOSE_FILE" logs --tail=10
else
    echo "❌ Deployment failed! Services are not running."
    echo "📋 Error logs:"
    docker-compose -f "$COMPOSE_FILE" logs
    exit 1
fi

echo "🎉 Deployment to ${ENVIRONMENT} completed successfully!"
echo "🌐 Spines should be available at http://localhost:8888" 