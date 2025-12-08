#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="outline-op-middleware"
IMAGE_TAG=$(git rev-parse --short HEAD)
TARGET="$1"

echo "=== Building Docker image ==="
docker build -t "$PROJECT_NAME:$IMAGE_TAG" -t "$PROJECT_NAME:latest" .
echo ""

echo "=== Saving image to tarball ==="
mkdir -p dist
docker save "$PROJECT_NAME:$IMAGE_TAG" | gzip > "dist/$PROJECT_NAME-$IMAGE_TAG.tar.gz"
echo ""

echo "=== Transferring files to $TARGET ==="
scp "dist/$PROJECT_NAME-$IMAGE_TAG.tar.gz" "$TARGET:/tmp/$PROJECT_NAME-$IMAGE_TAG.tar.gz"
scp docker-compose.prod.yml.template "$TARGET:/tmp/docker-compose.prod.yml.template"
scp .env "$TARGET:/tmp/.env"
echo ""

echo "=== Deploying on $TARGET ==="
ssh $TARGET bash << ENDSSH
set -e
PROJECT_NAME="outline-op-middleware"
IMAGE_TAG="$IMAGE_TAG"
PORT="\${PORT:-8001}"

echo "Loading Docker image..."
cd /tmp
gunzip -c \$PROJECT_NAME-\$IMAGE_TAG.tar.gz | docker load

echo "Preparing docker-compose.yml..."
export PROJECT_NAME IMAGE_TAG PORT
envsubst < docker-compose.prod.yml.template > docker-compose.yml

echo "Starting services..."
docker compose up -d

echo ""
echo "✅ Deployment successful!"
docker compose ps
ENDSSH

echo ""
echo "🎉 Deployment completed!"
echo "📦 Project: $PROJECT_NAME"
echo "🏷️ Version: $IMAGE_TAG"
echo "🖥️ Server: $TARGET"
