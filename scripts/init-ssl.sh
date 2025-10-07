#!/bin/bash
# Script to initialize SSL certificates using Let's Encrypt

set -e

# Configuration
DOMAINS=("api.xpyrkova23.ru" "app.xpyrkova23.ru")
EMAIL="alexey_gladilin@mail.ru" 
STAGING=0  # Set to 1 for testing

# Create directories
mkdir -p certbot/www certbot/conf

# Get certificates for each domain
for DOMAIN in "${DOMAINS[@]}"; do
    echo "Getting certificate for $DOMAIN..."
    
    if [ $STAGING -eq 1 ]; then
        STAGING_ARG="--staging"
    else
        STAGING_ARG=""
    fi
    
    docker compose run --rm certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email $EMAIL \
        --agree-tos \
        --no-eff-email \
        $STAGING_ARG \
        -d $DOMAIN
done

echo "SSL certificates obtained successfully!"
echo "Now restart nginx: docker compose restart nginx"
