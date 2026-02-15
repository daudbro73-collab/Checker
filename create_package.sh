#!/bin/bash

echo "📦 Creating deployment package..."

# Remove old package if exists
rm -f aml_deploy.zip

# Create zip archive excluding unnecessary files
# Using tar because it preserves permissions and is standard on Mac/Linux
tar -czf aml_deploy.tar.gz \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='.DS_Store' \
    --exclude='*.pyc' \
    backend \
    Dockerfile \
    docker-compose.yml \
    DEPLOY_GUIDE.md

echo "✅ Package created: aml_deploy.tar.gz"
echo "---------------------------------------------------"
echo "👉 To upload to your server, run this command:"
echo "scp aml_deploy.tar.gz ubuntu@YOUR_SERVER_IP:~/"
echo ""
echo "👉 Then SSH into your server and run:"
echo "tar -xzf aml_deploy.tar.gz"
echo "cd ."
echo "docker-compose up -d --build"
