#!/bin/bash

#  Chatbot Startup Script
# Checks dependencies and starts the application

set -e

echo "=================================================="
echo "    Chatbot - Startup Script"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating from template...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✅ Created .env file. Please update with your settings.${NC}"
    echo ""
fi

# Check Docker
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker found${NC}"
else
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

# Check Docker Compose
if command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}✅ Docker Compose found${NC}"
else
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose first.${NC}"
    exit 1
fi

echo ""
echo "Select startup mode:"
echo "1. Development (with hot reload)"
echo "2. Production (optimized)"
echo "3. Test mode (run tests only)"
echo "4. Stop all services"
echo ""
read -p "Enter choice [1-4]: " choice

case $choice in
    1)
        echo ""
        echo "🚀 Starting in DEVELOPMENT mode..."
        docker-compose up --build
        ;;
    2)
        echo ""
        echo "🚀 Starting in PRODUCTION mode..."
        docker-compose -f docker-compose.yml up -d --build
        echo ""
        echo -e "${GREEN}✅ Services started${NC}"
        echo ""
        echo "Access points:"
        echo "  - API: http://localhost:8000"
        echo "  - Docs: http://localhost:8000/docs"
        echo "  - Health: http://localhost:8000/health"
        echo ""
        echo "View logs:"
        echo "  docker-compose logs -f app"
        ;;
    3)
        echo ""
        echo "🧪 Running tests..."
        
        # Start services if not running
        docker-compose up -d mongo redis
        sleep 3
        
        # Install test dependencies
        pip install websocket-client requests
        
        # Run tests
        python test_api.py