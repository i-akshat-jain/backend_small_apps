#!/bin/bash
set -e

echo "=== Deployment Script ==="

# Step 1: Navigate to backend_app directory and pull latest changes
cd /opt
if [ ! -d backend_app ]; then
    echo "Cloning repository from GitHub..."
    git clone -b main git@github.com-personal:i-akshat-jain/backend_small_apps.git backend_app
else
    echo "Pulling latest changes from git..."
    cd backend_app
    # Stash local changes if any
    git stash || true
    # Pull latest changes
    git pull origin main || {
        echo "Git pull failed, continuing with existing code..."
    }
    cd /opt
fi

# Step 2: Copy files from /opt/ to /opt/backend_app/ (overwrite after pull)
if [ -f /opt/sync-files.sh ]; then
    echo "Syncing local files (wsgi, asgi, manage.py, .env)..."
    /opt/sync-files.sh
fi

# Step 3: Clean up any leftover containers
echo "Cleaning up Docker system..."
docker compose -f docker-compose.yml down || true
docker system prune -f || true

# Step 4: Build and restart containers
cd /opt
echo "Building backend image..."
docker compose -f docker-compose.yml build --no-cache backend

echo "Starting containers..."
docker compose -f docker-compose.yml up -d

# Wait for backend to be healthy
echo "Waiting for backend to be ready..."
sleep 15

# Run migrations
echo "Running database migrations..."
docker exec sanatan_backend python manage.py migrate --noinput || true

# Collect static files
echo "Collecting static files..."
docker exec sanatan_backend python manage.py collectstatic --noinput || true

# Restart nginx to pick up any config changes
echo "Restarting nginx..."
docker restart nginx_proxy || true

echo "=== Deployment Complete ==="
echo "Backend: http://api.dharmsaar.gibberishtech.com"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

