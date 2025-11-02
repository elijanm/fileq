#!/bin/bash

set -e

echo "🚀 Setting up Authentication Service..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Generate environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Generating .env file..."
    
    # Generate secure random keys
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    REDIS_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
    MONGO_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
    GRAFANA_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
    
    cat > .env << EOF
ENCRYPTION_KEY=${ENCRYPTION_KEY}
JWT_SECRET=${JWT_SECRET}
REDIS_PASSWORD=${REDIS_PASSWORD}
MONGO_ROOT_USERNAME=admin
MONGO_ROOT_PASSWORD=${MONGO_PASSWORD}
MONGODB_URI=mongodb://admin:${MONGO_PASSWORD}@mongodb:27017/auth_db?authSource=admin
GRAFANA_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
AUDIT_RETENTION_DAYS=90
LOG_LEVEL=INFO
ENVIRONMENT=development
EOF

    echo "✅ Generated .env file with secure random keys"
    echo "📋 Grafana admin password: ${GRAFANA_PASSWORD}"
fi

# Generate SSL certificates
echo "🔐 Generating SSL certificates..."
bash scripts/generate-ssl.sh

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p {kratos,grafana/dashboards,grafana/datasources}

# Build and start services
echo "🐳 Building and starting services..."
docker-compose up -d --build

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 30

# Check service health
echo "🔍 Checking service health..."
for service in auth-api kratos redis mongodb; do
    if docker-compose ps | grep $service | grep -q "Up"; then
        echo "✅ $service is running"
    else
        echo "❌ $service failed to start"
        docker-compose logs $service
    fi
done

# Display access information
echo ""
echo "🎉 Setup complete!"
echo ""
echo "📊 Access URLs:"
echo "   • Auth API: https://localhost/auth"
echo "   • Grafana: http://localhost:3000 (admin:${GRAFANA_ADMIN_PASSWORD})"
echo "   • Prometheus: http://localhost:9090"
echo ""
echo "🔧 Next steps:"
echo "   1. Update your domain in kratos/kratos.yml"
echo "   2. Configure your SMTP settings for email"
echo "   3. Set up proper SSL certificates for production"
echo "   4. Review security settings in nginx.conf"
echo ""