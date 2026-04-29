#!/bin/bash
# Script to initialize SSL certificates using Let's Encrypt

set -e

# Configuration
CERTIFICATE_SETS=(
    "api.tutorbase.su"
    "app.tutorbase.su"
    "tutorbase.su,www.tutorbase.su"
)
EMAIL="alexey_gladilin@mail.ru" 
STAGING=0  # Set to 1 for testing

# Create directories
mkdir -p certbot/www certbot/conf

# Get certificates for each domain set
for DOMAIN_SET in "${CERTIFICATE_SETS[@]}"; do
    echo "Getting certificate for $DOMAIN_SET..."
    
    if [ $STAGING -eq 1 ]; then
        STAGING_ARG="--staging"
    else
        STAGING_ARG=""
    fi
    
    DOMAIN_ARGS=()
    IFS=',' read -ra DOMAINS <<< "$DOMAIN_SET"
    for DOMAIN in "${DOMAINS[@]}"; do
        DOMAIN_ARGS+=("-d" "$DOMAIN")
    done

    docker compose run --rm certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email $EMAIL \
        --agree-tos \
        --no-eff-email \
        $STAGING_ARG \
        "${DOMAIN_ARGS[@]}"
done

echo "SSL certificates obtained successfully!"
echo "Now restart nginx: docker compose restart nginx"
