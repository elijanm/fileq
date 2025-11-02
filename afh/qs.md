# Quick Start Guide

## 🚀 Get Running in 5 Minutes

### Option 1: Docker (Recommended)

```bash
# 1. Clone and setup
git clone <repo-url>
cd afhsync-chatbot
cp .env.example .env

# 2. Start everything
chmod +x start.sh
./start.sh
# Choose option 1 (Development)

# 3. Access the app
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### Option 2: Local Python

```bash
# 1. Setup environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Start dependencies
docker run -d -p 27017:27017 mongo:7.0
docker run -d -p 6379:6379 redis:7-alpine

# 3. Configure and run
cp .env.example .env
python app.py
```

## 📱 Testing SMS Flow

### Using cURL

```bash
# Simulate SMS webhook
curl -X POST http://localhost:8000/webhook/sms \
  -d "From=+12065551234" \
  -d "Body=start"

# Response will contain chat URL:
# https://afhsync.com/chat/abc-123-def
```

### Using Test Script

```bash
python test_api.py
```

### Using Twilio (Production)

1. Sign up at https://www.twilio.com
2. Get a phone number
3. Set webhook to: `https://your-domain.com/webhook/sms`
4. Text "START" to your number

## 💬 Testing Chat Interface

```bash
# 1. Create session
curl -X POST http://localhost:8000/webhook/sms \
  -d "From=+12065551234" \
  -d "Body=start"

# 2. Extract session_id from response

# 3. Open in browser
# http://localhost:8000/chat/{session_id}
```

## 🐳 Docker Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop all services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build

# Check service status
docker-compose ps

# Access container shell
docker-compose exec app bash

# Check Redis
docker-compose exec redis redis-cli ping

# Check MongoDB
docker-compose exec mongo mongosh
```

## 🔧 Common Tasks

### View Active Sessions

```bash
# If using Redis
docker-compose exec redis redis-cli KEYS "session:*"

# Get session details
curl http://localhost:8000/api/session/{session_id}
```

### Clear All Sessions

```bash
docker-compose exec redis redis-cli FLUSHDB
```

### Check Database

```bash
# Connect to MongoDB
docker-compose exec mongo mongosh

# In MongoDB shell:
use afhsync
db.users.find().pretty()
db.jobs.find().pretty()
```

### Generate Test Resume

```bash
# Start chat and follow resume flow
# Or use CLI:
python main.py
# Then select "2. Resume writing service"
```

## 🔍 Debugging

### Check Logs

```bash
# Application logs
docker-compose logs -f app

# All services
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100 app
```

### Test Ollama Connection

```bash
# Test from container
docker-compose exec app curl http://95.110.228.29:8201/v1/models

# Or from host
curl http://95.110.228.29:8201/v1/models
```

### Verify WebSocket

```bash
# Install wscat
npm install -g wscat

# Test WebSocket
wscat -c ws://localhost:8000/ws/test-session-id
```

## 📊 Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

### API Documentation

- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Resource Usage

```bash
# Container stats
docker stats

# Service-specific
docker stats afhsync-chatbot afhsync-mongo afhsync-redis
```

## 🛠️ Development Workflow

### Making Changes

```bash
# 1. Edit code
nano app.py

# 2. Restart service (auto-reload in dev mode)
# Changes apply automatically

# 3. For utils/chatbot changes
docker-compose restart app
```

### Adding Dependencies

```bash
# 1. Add to requirements.txt
echo "new-package==1.0.0" >> requirements.txt

# 2. Rebuild
docker-compose up -d --build
```

### Database Migrations

```bash
# Access MongoDB
docker-compose exec mongo mongosh

# Create indexes, collections, etc.
use afhsync
db.users.createIndex({email: 1}, {unique: true})
```

## 🚨 Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in docker-compose.yml
```

### Redis Connection Failed

```bash
# Check if Redis is running
docker-compose ps redis

# Restart Redis
docker-compose restart redis

# View Redis logs
docker-compose logs redis
```

### MongoDB Connection Issues

```bash
# Check MongoDB status
docker-compose ps mongo

# View MongoDB logs
docker-compose logs mongo

# Restart MongoDB
docker-compose restart mongo
```

### WebSocket Not Connecting

```bash
# Check if app is running
docker-compose ps app

# Check logs for errors
docker-compose logs app | grep -i websocket

# Test WebSocket endpoint
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  http://localhost:8000/ws/test
```

### PDF Generation Fails

```bash
# Check WeasyPrint dependencies
docker-compose exec app python -c "import weasyprint; print('OK')"

# Check /tmp/resumes directory
docker-compose exec app ls -la /tmp/resumes

# Create if missing
docker-compose exec app mkdir -p /tmp/resumes
```

## 📱 Production Deployment

### Quick Deploy Checklist

- [ ] Update `.env` with production values
- [ ] Set strong MongoDB password
- [ ] Configure Redis password
- [ ] Get SSL certificates
- [ ] Update nginx.conf for HTTPS
- [ ] Set Twilio webhook to production URL
- [ ] Configure domain DNS
- [ ] Test SMS flow end-to-end
- [ ] Enable monitoring
- [ ] Set up backups

### Deploy Commands

```bash
# Pull latest code
git pull origin main

# Build and start
docker-compose -f docker-compose.yml up -d --build

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

## 🆘 Getting Help

- Check logs: `docker-compose logs -f`
- Run tests: `python test_api.py`
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## 📚 Next Steps

1. ✅ Get app running locally
2. ✅ Test SMS webhook
3. ✅ Test chat interface
4. ✅ Test resume generation
5. Configure Twilio for production
6. Deploy to production server
7. Set up monitoring
8. Configure backups
