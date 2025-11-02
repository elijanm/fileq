#!/bin/bash
# ==============================
# AFHSync Rasa Project Generator
# ==============================

# mkdir -p {actions,data,models}

# ---------- domain.yml ----------
cat > domain.yml <<'EOF'
version: "3.1"

intents:
  - caregiver_welcome
  - afh_welcome
  - service_welcome
  - register_caregiver
  - post_job
  - advertise_service
  - see_jobs
  - faq
  - inform

entities:
  - name
  - location
  - location_details
  - availability
  - credentials
  - phone_number
  - days
  - schedule_type
  - urgency
  - gender_preference
  - service_type
  - service_description

slots:
  name: {type: text}
  location: {type: text}
  location_details: {type: text}
  availability: {type: text}
  credentials: {type: list}
  phone_number: {type: text}
  days: {type: list}
  schedule_type: {type: text}
  urgency: {type: text}
  gender_preference: {type: text}
  service_type: {type: text}
  service_description: {type: text}

forms:
  caregiver_registration_form:
    required_slots:
      - name
      - location
      - availability
      - credentials
      - phone_number
  service_registration_form:
    required_slots:
      - name
      - service_type
      - service_description
      - phone_number

responses:
  utter_caregiver_welcome:
    - text: |
        👋 Welcome to AFHSync Caregiver Portal!  
        1️⃣ Register as caregiver  
        2️⃣ See jobs  
        3️⃣ Learn more
  utter_afh_welcome:
    - text: "👋 Welcome AFH Provider! Just type your caregiver job request."
  utter_service_welcome:
    - text: "👋 Welcome Service Provider! Please advertise your service."
  utter_ask_name:
    - text: "What’s your full name?"
  utter_ask_location:
    - text: "Where are you located?"
  utter_ask_availability:
    - text: "When are you available to work?"
  utter_ask_credentials:
    - text: "What certifications do you have?"
  utter_ask_phone_number:
    - text: "Please provide a phone number."
  utter_registration_complete:
    - text: "Thank you {name}, your caregiver profile is now complete ✅"
  utter_ask_service_type:
    - text: "What kind of service do you offer?"
  utter_ask_service_description:
    - text: "Please describe your service."
  utter_service_registration_complete:
    - text: "Thank you {name}, your service offering has been listed ✅"
  utter_job_parsed:
    - text: |
        ✅ Job parsed:
        - Location: {location} {location_details}
        - Days: {days}
        - Schedule: {schedule_type}
        - Credentials: {credentials}
        - Urgency: {urgency}
        - Phone: {phone_number}
EOF

# ---------- config.yml ----------
cat > config.yml <<'EOF'
language: en
pipeline:
  - name: WhitespaceTokenizer
  - name: RegexFeaturizer
  - name: LexicalSyntacticFeaturizer
  - name: CountVectorsFeaturizer
  - name: DIETClassifier
    epochs: 100
  - name: RegexEntityExtractor
  - name: EntitySynonymMapper
  - name: FallbackClassifier
    threshold: 0.3

policies:
  - name: RulePolicy
  - name: MemoizationPolicy
  - name: TEDPolicy
    max_history: 5
    epochs: 50
EOF

# ---------- endpoints.yml ----------
cat > endpoints.yml <<'EOF'
action_endpoint:
  url: "http://action_server:5055/webhook"
EOF

# ---------- credentials.yml ----------
cat > credentials.yml <<'EOF'
rest:
socketio:
  user_message_evt: user_uttered
  bot_message_evt: bot_uttered
  session_persistence: true
EOF

# ---------- nlu.yml ----------
cat > data/nlu.yml <<'EOF'
version: "3.1"
nlu:
- intent: caregiver_welcome
  examples: |
    - hi
    - hello
- intent: afh_welcome
  examples: |
    - I am an AFH provider
    - I run an AFH
- intent: service_welcome
  examples: |
    - I am a service provider
    - I offer services
- intent: register_caregiver
  examples: |
    - 1
    - I want to register
- intent: see_jobs
  examples: |
    - 2
    - Show me jobs
- intent: faq
  examples: |
    - 3
    - How does this work?
- intent: post_job
  examples: |
    - Caregiver needed in [Tacoma](location) [near St. Joseph hospital](location_details) [tomorrow](days)
    - Looking for [live-in](schedule_type) caregiver in [Federal Way 98003](location)
- intent: advertise_service
  examples: |
    - My name is [Sarah](name) and I offer [CPR training](service_type).
    - We provide [meal prep](service_type) for AFHs.
EOF

# ---------- stories.yml ----------
cat > data/stories.yml <<'EOF'
version: "3.1"
stories:
- story: caregiver welcome
  steps:
    - intent: caregiver_welcome
    - action: utter_caregiver_welcome
- story: AFH welcome
  steps:
    - intent: afh_welcome
    - action: utter_afh_welcome
- story: Service welcome
  steps:
    - intent: service_welcome
    - action: utter_service_welcome
EOF

# ---------- rules.yml ----------
cat > data/rules.yml <<'EOF'
version: "3.1"
rules:
- rule: Caregiver registration
  steps:
    - intent: register_caregiver
    - action: caregiver_registration_form
    - active_loop: caregiver_registration_form
    - action: action_save_caregiver
    - action: utter_registration_complete

- rule: Service registration
  steps:
    - intent: advertise_service
    - action: service_registration_form
    - active_loop: service_registration_form
    - action: action_save_service
    - action: utter_service_registration_complete

- rule: AFH job post
  steps:
    - intent: post_job
    - action: utter_job_parsed
EOF

# ---------- actions.py ----------
cat > actions/actions.py <<'EOF'
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from typing import Any, Dict, List, Text
import requests

class ActionSaveCaregiver(Action):
    def name(self) -> Text:
        return "action_save_caregiver"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        caregiver_profile = {
            "name": tracker.get_slot("name"),
            "location": tracker.get_slot("location"),
            "availability": tracker.get_slot("availability"),
            "credentials": tracker.get_slot("credentials"),
            "phone_number": tracker.get_slot("phone_number"),
            "status": "pending_verification"
        }
        print("Caregiver Profile Saved:", caregiver_profile)
        return []

class ActionSaveService(Action):
    def name(self) -> Text:
        return "action_save_service"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        service_offer = {
            "name": tracker.get_slot("name"),
            "service_type": tracker.get_slot("service_type"),
            "service_description": tracker.get_slot("service_description"),
            "phone_number": tracker.get_slot("phone_number"),
            "status": "active"
        }
        print("Service Offering Saved:", service_offer)
        return []
EOF

# ---------- requirements.txt ----------
cat > actions/requirements.txt <<'EOF'
requests
geopy
EOF

# ---------- Dockerfile ----------
cat > Dockerfile <<'EOF'
FROM rasa/rasa:3.6.15-full
WORKDIR /app
COPY . /app
EXPOSE 5005
CMD ["run", "--enable-api", "--cors", "*", "--debug"]
EOF

# ---------- docker-compose.yml ----------
cat > docker-compose.yml <<'EOF'
version: '3.9'
services:
  rasa:
    build: .
    container_name: rasa-server
    ports:
      - "5005:5005"
    volumes:
      - ./:/app
    command: run --enable-api --cors "*" --debug
    depends_on:
      - action_server

  action_server:
    build: ./actions
    container_name: rasa-action-server
    ports:
      - "5055:5055"
    volumes:
      - ./actions:/app/actions
EOF

# ---------- README.md ----------
cat > README.md <<'EOF'
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
EOF

echo "✅  Rasa project generated in ./"
