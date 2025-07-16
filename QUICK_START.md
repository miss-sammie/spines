# Spines 2.0 Quick Start Guide

Welcome to your beautiful archive system! Here's how to get started with proper dev/prod environments.

## 🚀 First Time Setup

1. **Copy environment file:**
   ```powershell
   Copy-Item env.example .env
   ```

2. **Edit `.env` file with your settings:**
   ```bash
   # Add your Cloudflare token for production
   CLOUDFLARE_TOKEN=your-tunnel-token-here
   
   # Set your admin users
   SPINES_ADMIN_USERS=hal,whisper
   ```

## 🛠️ Development Environment

**Start development with hot reload:**
```powershell
.\scripts\dev.ps1 start
```

**Stop development:**
```powershell
.\scripts\dev.ps1 stop
```

**View logs:**
```powershell
.\scripts\dev.ps1 logs
```

**Open shell in container:**
```powershell
.\scripts\dev.ps1 shell
```

**Run tests:**
```powershell
.\scripts\dev.ps1 test
```

## 🏭 Production Environment

**Start production:**
```powershell
.\scripts\prod.ps1 start
```

**Check production status:**
```powershell
.\scripts\prod.ps1 status
```

**View production logs:**
```powershell
.\scripts\prod.ps1 logs
```

**Create backup:**
```powershell
.\scripts\prod.ps1 backup
```

**Update production:**
```powershell
.\scripts\prod.ps1 update
```

## 📚 Your Library

- **Books**: `./books/` - Your digital library
- **Data**: `./data/` - Application data and metadata
- **Logs**: `./logs/` - Application logs
- **Temp**: `./temp/` - Temporary processing files

## 🌐 Access Your Library

- **Development**: http://localhost:8888
- **Production**: http://localhost:8888 (with Cloudflare tunnel for external access)

## 🔧 Common Commands

### Development Workflow
```powershell
# Start development
.\scripts\dev.ps1 start

# Make changes to src/ or static/
# Changes auto-reload!

# Run tests
.\scripts\dev.ps1 test

# Stop development
.\scripts\dev.ps1 stop
```

### Production Workflow
```powershell
# Start production
.\scripts\prod.ps1 start

# Check it's running
.\scripts\prod.ps1 status

# View logs
.\scripts\prod.ps1 logs

# Create backup before updates
.\scripts\prod.ps1 backup

# Update and restart
.\scripts\prod.ps1 update
```

## 🆘 Troubleshooting

**Port already in use:**
```powershell
# Check what's using port 8888
netstat -ano | findstr :8888

# Kill the process or change port in docker-compose files
```

**Permission issues:**
```powershell
# Fix file permissions (if needed)
icacls books /grant Everyone:F /T
icacls data /grant Everyone:F /T
```

**Container won't start:**
```powershell
# Check logs
.\scripts\dev.ps1 logs
# or
.\scripts\prod.ps1 logs

# Clean up and restart
.\scripts\dev.ps1 clean
.\scripts\dev.ps1 start
```

## 🎯 Next Steps

1. **Add your books** to the `books/` directory
2. **Configure Cloudflare tunnel** for external access
3. **Set up automated backups** with the backup script
4. **Customize the interface** in `static/` directory
5. **Add staging environment** when you're ready

## 💡 Pro Tips

- **Development**: Use hot reload for live editing
- **Production**: Always backup before updates
- **Logs**: Check logs first when troubleshooting
- **Health**: Use status command to verify everything is working
- **Backups**: Run backups regularly with the backup script

Happy archiving! 📚✨ 