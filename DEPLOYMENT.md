# Deployment Guide

This guide explains how to deploy the backend application to the server with Docker, Nginx reverse proxy, and SSL certificates.

## Server Information

- **Server IP:** `77.42.43.141`
- **SSH Access:** `root@77.42.43.141`
- **SSH Key:** `~/.ssh/id_ed25519_personal`
- **Domain:** `api.dharmsaar.gibberishtech.com`
- **GitHub Repository:** `git@github.com-personal:i-akshat-jain/backend_small_apps.git`

## Prerequisites

- ✅ Docker and Docker Compose installed on server
- ✅ Nginx installed on server (disabled, using Docker nginx)
- ✅ Git installed on server
- ✅ SSH key configured for GitHub access
- ⚠️ Domain DNS pointing to server IP (needs verification)
- ⚠️ SSL certificates (not yet configured)

## Directory Structure on Server

```
/opt/
├── backend_app/              # Backend application code (Git repository)
│   ├── .env                  # Environment variables (synced from /opt/.env)
│   ├── manage.py             # Django management script (synced from /opt/manage.py)
│   ├── Dockerfile            # Docker build configuration
│   ├── .dockerignore         # Docker ignore patterns
│   ├── requirements.txt      # Python dependencies
│   ├── core/
│   │   ├── settings/
│   │   │   ├── base.py       # Development settings
│   │   │   ├── prod.py       # Production settings
│   │   │   └── __init__.py   # Settings loader
│   │   ├── wsgi.py           # WSGI config (synced from /opt/wsgi.py)
│   │   └── asgi.py           # ASGI config (synced from /opt/asgi.py)
│   └── apps/                 # Django apps
├── nginx-proxy/              # Nginx configuration
│   ├── nginx.conf            # Main nginx configuration
│   ├── conf.d/
│   │   └── api.conf          # API domain configuration
│   ├── ssl/                  # SSL certificates (symlinks)
│   ├── certbot/              # Certbot certificates
│   │   ├── conf/             # Let's Encrypt certificates
│   │   └── www/              # Webroot for certbot
│   └── logs/                 # Nginx logs
├── docker-compose.yml        # Docker compose configuration
├── deploy.sh                 # Main deployment script
├── sync-files.sh             # Sync files from /opt/ to /opt/backend_app/
├── setup-ssl.sh              # SSL certificate setup script
├── enable-https.sh           # Enable HTTPS after SSL setup
├── setup-git.sh              # Git repository setup script
├── configure-github-ssh.sh   # GitHub SSH configuration script
├── README.md                 # Server documentation
│
# Working directory for editing files:
├── .env                      # Edit here, synced to backend_app/.env
├── manage.py                 # Edit here, synced to backend_app/manage.py
├── wsgi.py                   # Edit here, synced to backend_app/core/wsgi.py
└── asgi.py                   # Edit here, synced to backend_app/core/asgi.py
```

## Initial Setup (Completed)

### 1. Server Preparation ✅

- Docker and Docker Compose installed
- Nginx installed (system nginx disabled, using Docker nginx)
- Git installed
- Directories created

### 2. GitHub Access Setup ✅

SSH key copied from local machine to server:
```bash
# SSH key is at: ~/.ssh/id_ed25519
# SSH config configured for: github.com-personal
# Repository cloned to: /opt/backend_app
```

### 3. Git Repository Setup ✅

```bash
# Repository cloned
cd /opt/backend_app
git remote -v
# origin  git@github.com-personal:i-akshat-jain/backend_small_apps.git
```

### 4. Environment Configuration ✅

Environment file created at `/opt/.env` and synced to `/opt/backend_app/.env` during deployment.

## Deployment Workflow

### Standard Deployment Process

The deployment uses a **file sync workflow** where you edit files in `/opt/` and they're automatically synced to `/opt/backend_app/` before building:

1. **Edit files in `/opt/`** (your working directory):
   ```bash
   cd /opt
   nano .env          # Edit environment variables
   nano manage.py     # Edit Django management script
   nano wsgi.py       # Edit WSGI configuration
   nano asgi.py       # Edit ASGI configuration
   ```

2. **Run deployment**:
   ```bash
   cd /opt
   ./deploy.sh
   ```

3. **What happens automatically**:
   - ✅ Syncs files from `/opt/` → `/opt/backend_app/` (via `sync-files.sh`)
   - ✅ Pulls latest code from GitHub
   - ✅ Builds Docker image (includes your synced files)
   - ✅ Stops existing containers
   - ✅ Starts new containers
   - ✅ Waits for backend to be ready
   - ✅ Runs database migrations
   - ✅ Collects static files
   - ✅ Restarts nginx

### Deployment Script Details

The `deploy.sh` script performs these steps:

```bash
#!/bin/bash
# 1. Sync files from /opt/ to /opt/backend_app/
# 2. Pull latest from GitHub
# 3. Stop containers
# 4. Build Docker image
# 5. Start containers
# 6. Run migrations
# 7. Collect static files
# 8. Restart nginx
```

## File Sync Workflow

The `sync-files.sh` script automatically copies these files before each deployment:

- `/opt/.env` → `/opt/backend_app/.env`
- `/opt/manage.py` → `/opt/backend_app/manage.py`
- `/opt/wsgi.py` → `/opt/backend_app/core/wsgi.py`
- `/opt/asgi.py` → `/opt/backend_app/core/asgi.py`

**Why this workflow?**
- Edit files in a convenient location (`/opt/`)
- Files are automatically included in Docker build
- No need to manually copy files each time
- Git repository stays clean (synced files not committed)

## Docker Configuration

### Services

1. **backend** (`sanatan_backend`)
   - Image: Built from `/opt/backend_app/Dockerfile`
   - Port: 8000 (internal)
   - Settings: `core.settings.prod`
   - Environment: Production

2. **nginx** (`nginx_proxy`)
   - Image: `nginx:alpine`
   - Ports: 80 (HTTP), 443 (HTTPS)
   - Reverse proxy to backend
   - Serves static files

3. **certbot** (`certbot`)
   - Image: `certbot/certbot`
   - Auto-renews SSL certificates every 12 hours

### Docker Compose File

Located at `/opt/docker-compose.yml`:
- Uses Docker network: `app-network`
- Volumes for persistent data (media, staticfiles, logs)
- Health checks configured
- Auto-restart on failure

## Current Deployment Status

### ✅ Completed
- Docker and Docker Compose installed
- Git repository cloned and configured
- SSH access to GitHub working
- Docker images built
- Containers created
- Nginx proxy running
- Certbot container running

### ⚠️ Issues
- **Backend container restarting**: Worker failed to boot
  - Check logs: `docker logs sanatan_backend`
  - Likely causes: Database connection, missing environment variables, or settings error

### 🔄 Pending
- SSL certificate setup (not yet configured)
- HTTPS not enabled
- Backend container needs to be stable

## SSL Certificate Setup (Not Yet Done)

### Step 1: Obtain SSL Certificate

```bash
cd /opt
./setup-ssl.sh
```

**Note:** Update the email in `/opt/setup-ssl.sh` before running.

This will:
- Stop nginx temporarily
- Run certbot to obtain certificate
- Create symlinks for nginx

### Step 2: Enable HTTPS

After SSL certificate is obtained:

```bash
cd /opt
./enable-https.sh
```

This will:
- Update nginx configuration to enable HTTPS
- Redirect HTTP to HTTPS
- Restart nginx

### Step 3: Verify

```bash
curl -I https://api.dharmsaar.gibberishtech.com
```

## Updating the Application

### Option 1: Edit Files in /opt/ (Current Workflow)

```bash
# 1. Edit files in /opt/
cd /opt
nano .env
nano manage.py
# ... etc

# 2. Deploy (files auto-synced)
./deploy.sh
```

### Option 2: Using Git

```bash
# 1. Make changes locally and push to GitHub
git add .
git commit -m "Update configuration"
git push origin main

# 2. On server, pull and deploy
cd /opt/backend_app
git pull origin main
cd /opt
./deploy.sh
```

### Option 3: Direct Edit in backend_app

```bash
# Edit directly in backend_app (will be overwritten by git pull)
cd /opt/backend_app
nano .env
cd /opt
./deploy.sh
```

## Docker Commands

### View Running Containers
```bash
docker ps
```

### View All Containers (Including Stopped)
```bash
docker ps -a
```

### View Logs
```bash
# Backend logs (follow)
docker logs -f sanatan_backend

# Backend logs (last 50 lines)
docker logs --tail 50 sanatan_backend

# Nginx logs
docker logs -f nginx_proxy

# Certbot logs
docker logs -f certbot
```

### Restart Services
```bash
docker restart sanatan_backend
docker restart nginx_proxy
```

### Stop All Services
```bash
cd /opt
docker compose -f docker-compose.yml down
```

### Start All Services
```bash
cd /opt
docker compose -f docker-compose.yml up -d
```

### Rebuild and Restart
```bash
cd /opt
docker compose -f docker-compose.yml up -d --build
```

## Troubleshooting

### Backend Container Restarting

**Check logs:**
```bash
docker logs sanatan_backend --tail 100
```

**Common issues:**
1. **Database connection error**: Check `.env` file has correct DB credentials
2. **Missing SECRET_KEY**: Ensure `SECRET_KEY` is set in `.env`
3. **Settings import error**: Check `DJANGO_SETTINGS_MODULE` is correct
4. **Port already in use**: Check if port 8000 is available

**Debug steps:**
```bash
# Check container status
docker ps -a | grep backend

# Check environment variables
docker exec sanatan_backend env | grep DJANGO

# Try running Django commands manually
docker exec -it sanatan_backend python manage.py check
docker exec -it sanatan_backend python manage.py migrate
```

### Nginx Not Working

**Check nginx configuration:**
```bash
docker exec nginx_proxy nginx -t
```

**View nginx logs:**
```bash
# Access logs
tail -f /opt/nginx-proxy/logs/access.log

# Error logs
tail -f /opt/nginx-proxy/logs/error.log

# Or from container
docker logs nginx_proxy
```

**Test backend connection:**
```bash
# From nginx container
docker exec nginx_proxy wget -O- http://backend:8000/admin/

# From host
curl http://localhost:8000/admin/
```

### Git Pull Issues

**Check SSH connection:**
```bash
ssh -T git@github.com-personal
```

**Check git remote:**
```bash
cd /opt/backend_app
git remote -v
```

**Force pull:**
```bash
cd /opt/backend_app
git fetch origin
git reset --hard origin/main
```

### File Sync Issues

**Manually sync files:**
```bash
/opt/sync-files.sh
```

**Check if files exist:**
```bash
ls -la /opt/.env /opt/manage.py /opt/wsgi.py /opt/asgi.py
ls -la /opt/backend_app/.env /opt/backend_app/manage.py
```

## SSL Certificate Renewal

Certbot is configured to auto-renew certificates. The certbot container runs continuously and checks for renewal every 12 hours.

**Manual renewal:**
```bash
docker exec certbot certbot renew
docker restart nginx_proxy
```

**Check certificate expiry:**
```bash
docker exec certbot certbot certificates
```

## GitHub Actions Integration

The Dockerfile in this repository can be used in GitHub Actions for CI/CD. Example workflow:

```yaml
name: Deploy to Server

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Copy files to server
        uses: appleboy/scp-action@master
        with:
          host: 77.42.43.141
          username: root
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          source: "."
          target: "/opt/backend_app"
          
      - name: Deploy on server
        uses: appleboy/ssh-action@master
        with:
          host: 77.42.43.141
          username: root
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt
            ./deploy.sh
```

## Security Notes

1. ✅ Keep your `.env` file secure and never commit it to git
2. ✅ Use strong SECRET_KEY in production
3. ✅ Keep DEBUG=False in production
4. ⚠️ SSL certificates not yet configured (HTTP only)
5. ✅ Regularly update dependencies
6. ✅ Monitor logs for suspicious activity
7. ✅ SSH keys properly configured
8. ✅ Docker containers isolated in network

## Quick Reference

### Common Commands

```bash
# Deploy
cd /opt && ./deploy.sh

# View logs
docker logs -f sanatan_backend

# Restart backend
docker restart sanatan_backend

# Check status
docker ps

# Sync files manually
/opt/sync-files.sh

# Pull from git
cd /opt/backend_app && git pull origin main
```

### File Locations

- **Edit files:** `/opt/.env`, `/opt/manage.py`, `/opt/wsgi.py`, `/opt/asgi.py`
- **Deployed files:** `/opt/backend_app/`
- **Docker compose:** `/opt/docker-compose.yml`
- **Nginx config:** `/opt/nginx-proxy/conf.d/api.conf`
- **Logs:** `/opt/nginx-proxy/logs/`, `/opt/backend_app/logs/`

## Next Steps

1. ⚠️ Fix backend container restart issue
2. ⚠️ Set up SSL certificates
3. ⚠️ Enable HTTPS
4. ⚠️ Verify domain DNS is pointing to server
5. ⚠️ Test API endpoints
6. ⚠️ Set up monitoring/logging

## Notes

- System nginx is disabled (using Docker nginx)
- Files edited in `/opt/` are automatically synced during deployment
- Git repository is at `/opt/backend_app/`
- Docker images are built fresh on each deployment (no cache)
- Certbot runs in background for auto-renewal
