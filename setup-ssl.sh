#!/bin/bash

# SSL Certificate Setup Script for WihWIN
# This script obtains Let's Encrypt SSL certificates

# Configuration
DOMAIN="your-domain.com"  # CHANGE THIS to your domain (e.g., api.wihwin.com)
EMAIL="your-email@example.com"  # CHANGE THIS to your email

echo "=========================================="
echo "  WihWIN SSL Certificate Setup"
echo "=========================================="
echo ""
echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo ""

# Check if domain and email are configured
if [ "$DOMAIN" = "your-domain.com" ] || [ "$EMAIL" = "your-email@example.com" ]; then
    echo "❌ ERROR: Please edit this script and set your DOMAIN and EMAIL"
    echo ""
    echo "Edit setup-ssl.sh and change:"
    echo "  DOMAIN=\"your-domain.com\"  →  DOMAIN=\"api.wihwin.com\""
    echo "  EMAIL=\"your-email@example.com\"  →  EMAIL=\"you@gmail.com\""
    exit 1
fi

# Create certbot directories
echo "Creating certbot directories..."
mkdir -p certbot/conf
mkdir -p certbot/www

# Start nginx and certbot for initial certificate request
echo ""
echo "Starting services..."
docker-compose up -d nginx

# Wait for nginx to be ready
echo "Waiting for nginx to start..."
sleep 5

# Request certificate
echo ""
echo "Requesting SSL certificate from Let's Encrypt..."
docker-compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN

# Check if certificate was obtained
if [ -d "certbot/conf/live/$DOMAIN" ]; then
    echo ""
    echo "✅ SSL certificate obtained successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Update nginx/nginx.conf:"
    echo "   - Change 'server_name _' to 'server_name $DOMAIN'"
    echo "   - Change 'your-domain.com' to '$DOMAIN' in SSL paths"
    echo ""
    echo "2. Restart services:"
    echo "   docker-compose restart nginx"
    echo ""
    echo "3. Update EC2 Security Group to allow HTTPS (port 443)"
    echo ""
    echo "4. Test HTTPS:"
    echo "   curl https://$DOMAIN/health"
else
    echo ""
    echo "❌ Failed to obtain SSL certificate"
    echo ""
    echo "Common issues:"
    echo "1. Domain not pointing to this server's IP"
    echo "2. Port 80 not open in EC2 Security Group"
    echo "3. DNS propagation not complete (wait 5-10 minutes)"
fi
