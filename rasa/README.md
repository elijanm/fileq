#  Rasa Bot

This bot handles:
- user → registration (stepwise form)
- afs → job posts (free-text with location extraction)
- Service Providers → advertise services

## 🚀 Quickstart

1. Train the model:
   docker compose run rasa rasa train

2. Start services:
   docker compose up

3. Test with REST:
   curl -X POST http://localhost:5005/webhooks/rest/webhook \
        -H "Content-Type: application/json" \
        -d '{"sender":"test-user","message":"Caregiver needed in Federal Way 98003"}'
