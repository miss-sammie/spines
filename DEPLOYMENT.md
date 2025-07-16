# Spines 2.0 Deployment Guide

A beautiful archive system for your digital library with proper development and production environments.

## Quick Start

### Development Environment

For local development with hot reload and debugging:

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up --build

# Stop development environment
docker-compose -f docker-compose.dev.yml down

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

**Features:**
- Hot reload on code changes
- Debug logging enabled
- Full development tools (vim, nano, htop)
- Source code mounted for live editing
- All admin features enabled

### Production Environment

For production deployment on your desktop server:

```bash
# Start production environment
docker-compose -f docker-compose.prod.yml up --build -d

# Stop production environment
docker-compose -f docker-compose.prod.yml down

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# View specific service logs
docker-compose -f docker-compose.prod.yml logs -f spines-prod
docker-compose -f docker-compose.prod.yml logs -f cloudflared-prod
```

**Features:**
- Optimized for performance
- Cloudflare tunnel for external access
- Production logging levels
- Security hardened
- Automatic restarts

## Environment Configuration

### Development Environment Variables

The development environment uses these settings:
- `FLASK_ENV=development`
- `FLASK_DEBUG=true`
- `SPINES_LOG_LEVEL=DEBUG`
- `SPINES_ACCESS_MODE=local`
- `SPINES_PUBLIC_READ_ONLY=false`

### Production Environment Variables

The production environment uses these settings:
- `FLASK_ENV=production`
- `FLASK_DEBUG=false`
- `SPINES_LOG_LEVEL=WARN`
- `SPINES_ACCESS_MODE=local`
- `SPINES_PUBLIC_READ_ONLY=false`

## Cloudflare Tunnel Setup

For external access in production:

1. **Create a Cloudflare Tunnel:**
   - Go to Cloudflare Zero Trust dashboard
   - Navigate to Access > Tunnels
   - Create a new tunnel
   - Copy the tunnel token

2. **Configure Environment:**
   ```bash
   # Add to your .env file
   CLOUDFLARE_TOKEN=your-tunnel-token-here
   ```

3. **Start Production:**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

The tunnel will automatically start and provide external access to your spines instance.

## File Structure

```
spines-2.0/
├── books/                 # Your book library
├── data/                  # Application data
├── logs/                  # Application logs
├── temp/                  # Temporary files
├── src/                   # Application source code
├── static/                # Static assets
├── docker-compose.dev.yml # Development environment
├── docker-compose.prod.yml # Production environment
├── Dockerfile.dev         # Development Dockerfile
├── Dockerfile             # Production Dockerfile
└── .dockerignore          # Docker build exclusions
```

## Development Workflow

1. **Start Development:**
   ```bash
   docker-compose -f docker-compose.dev.yml up --build
   ```

2. **Make Changes:**
   - Edit files in `src/` or `static/`
   - Changes are automatically reloaded
   - View logs in real-time

3. **Test Changes:**
   ```bash
   # Run tests in development container
   docker exec -it spines-development python3 -m pytest
   ```

4. **Deploy to Production:**
   ```bash
   # Stop development
   docker-compose -f docker-compose.dev.yml down
   
   # Start production
   docker-compose -f docker-compose.prod.yml up --build -d
   ```

## Troubleshooting

### Common Issues

1. **Port Already in Use:**
   ```bash
   # Check what's using the port
   netstat -tulpn | grep 8888
   
   # Kill the process or change port in docker-compose
   ```

2. **Permission Issues:**
   ```bash
   # Fix file permissions
   sudo chown -R $USER:$USER books/ data/ logs/ temp/
   ```

3. **Cloudflare Tunnel Not Working:**
   - Check your tunnel token
   - Verify tunnel is active in Cloudflare dashboard
   - Check tunnel logs: `docker-compose -f docker-compose.prod.yml logs cloudflared-prod`

### Logs and Debugging

```bash
# Development logs
docker-compose -f docker-compose.dev.yml logs -f

# Production logs
docker-compose -f docker-compose.prod.yml logs -f

# Specific service logs
docker-compose -f docker-compose.prod.yml logs -f spines-prod

# Access container shell
docker exec -it spines-development bash
docker exec -it spines-production bash
```

## Migration from Old Setup

If you're migrating from the old spines setup:

1. **Backup Your Data:**
   ```bash
   cp -r ../spines/books ./books
   cp -r ../spines/data ./data
   ```

2. **Run Migration:**
   ```bash
   # Use the migration compose file
   docker-compose -f docker-compose.migration.yml up --build
   ```

3. **Start New Environment:**
   ```bash
   # Development
   docker-compose -f docker-compose.dev.yml up --build
   
   # Or production
   docker-compose -f docker-compose.prod.yml up --build -d
   ```

## Performance Tips

### Development
- Use volume mounts for hot reload
- Enable debug logging for troubleshooting
- Keep development tools for debugging

### Production
- Use multi-stage builds for smaller images
- Optimize logging levels
- Use Cloudflare tunnel for external access
- Enable health checks

## Security Considerations

- Production environment runs with minimal permissions
- Cloudflare tunnel provides secure external access
- Admin users are configurable via environment variables
- Logs are properly managed and rotated
- Temporary files are isolated

## Next Steps

- Add staging environment between dev and prod
- Implement automated backups
- Add monitoring and alerting
- Set up CI/CD pipeline
- Add SSL certificates for direct domain access 