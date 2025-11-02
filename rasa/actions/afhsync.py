"""
Smart AFHSync Bot with:
- Fuzzy matching for typos
- Natural date parsing  
- Ollama (deepseek-r1:1.5b) fallback
- Resume writing service
"""

from enum import Enum
from typing import Dict, Optional, Any
import re
# from fuzzywuzzy import fuzz
from thefuzz import fuzz
import dateparser
from datetime import datetime
import requests
import json

# Configuration
OLLAMA_BASE_URL = "http://95.110.228.29:8201/v1"
OLLAMA_MODEL = "deepseek-r1:1.5b"  # Fastest local model

class State(Enum):
    START = "start"
    ROLE_SELECTION = "role_selection"
    ASK_CONTACT = "ask_contact"
    CHECK_REGISTRATION = "check_registration"
    ASK_NAME = "ask_name"
    ASK_LOCATION = "ask_location"
    ASK_AVAILABILITY = "ask_availability"
    ASK_CREDENTIALS = "ask_credentials"
    ASK_UPLOAD = "ask_upload"
    ASK_NOTIFICATION = "ask_notification"
    ASK_MISSING_CONTACT = "ask_missing_contact"
    SERVICE_MENU = "service_menu"
    COMPLETE = "complete"
    RESUME_SERVICE = "resume_service"

class SmartParser:
    """Intelligent parsing with fuzzy matching and Ollama fallback"""
    
    @staticmethod
    def fuzzy_match(user_input: str, options: dict, threshold: int = 70) -> Optional[str]:
        """Match user input to closest option even with typos"""
        user_input = user_input.lower().strip()
        
        best_match = None
        best_score = 0
        
        for key, value in options.items():
            score = fuzz.ratio(user_input, key)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = value
        
        return best_match
    
    @staticmethod
    def parse_availability(user_input: str) -> dict:
        """Parse natural language availability"""
        # Try to parse as a date
        parsed_date = dateparser.parse(user_input, settings={
            'PREFER_DATES_FROM': 'future',
            'RELATIVE_BASE': datetime.now()
        })
        
        if parsed_date:
            return {
                'type': 'specific_date',
                'date': parsed_date.strftime('%Y-%m-%d'),
                'day': parsed_date.strftime('%A'),
                'original': user_input
            }
        
        # Check for common patterns
        patterns = {
            'weekdays': ['weekday', 'weekdays', 'monday through friday', 'm-f', 'mon-fri'],
            'weekends': ['weekend', 'weekends', 'saturday and sunday', 'sat-sun'],
            'nights': ['night', 'nights', 'evening', 'evenings', 'overnight'],
            'days': ['day', 'days', 'morning', 'mornings', 'daytime'],
            'anytime': ['anytime', 'any time', 'flexible', 'whenever', 'always available']
        }
        
        for category, keywords in patterns.items():
            for keyword in keywords:
                if keyword in user_input.lower():
                    return {
                        'type': 'pattern',
                        'pattern': category,
                        'original': user_input
                    }
        
        return {
            'type': 'custom',
            'original': user_input
        }
    
    @staticmethod
    def ollama_fallback(user_input: str, context: str) -> Optional[dict]:
        """Use local Ollama model as intelligent fallback"""
        try:
            prompt = f"""Context: {context}
User said: "{user_input}"

Extract structured data as JSON only. Examples:
- "nww" or "now" → {{"choice": "now"}}
- "ltey" or "later" → {{"choice": "later"}}  
- "next tuesday" → {{"date": "2025-01-07", "day": "Tuesday"}}
- "weekdays" → {{"pattern": "weekdays"}}

Return ONLY valid JSON, no explanation."""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 100
                },
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                # Extract JSON from response
                json_match = re.search(r'\{[^}]+\}', content)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            print(f"Ollama fallback failed: {e}")
        
        return None

class AFHSyncBot:
    def __init__(self):
        self.state = State.START
        self.data = {}
        self.parser = SmartParser()
        
    def process_message(self, user_input: str) -> str:
        """Main state machine logic"""
        
        if self.state == State.START:
            self.state = State.ROLE_SELECTION
            return self.show_role_selection()
            
        elif self.state == State.ROLE_SELECTION:
            return self.handle_role_selection(user_input)
            
        elif self.state == State.ASK_CONTACT:
            return self.handle_contact(user_input)
            
        elif self.state == State.CHECK_REGISTRATION:
            return self.check_registration()
            
        elif self.state == State.ASK_NAME:
            return self.handle_name(user_input)
            
        elif self.state == State.ASK_LOCATION:
            return self.handle_location(user_input)
            
        elif self.state == State.ASK_AVAILABILITY:
            return self.handle_availability(user_input)
            
        elif self.state == State.ASK_CREDENTIALS:
            return self.handle_credentials(user_input)
            
        elif self.state == State.ASK_UPLOAD:
            return self.handle_upload(user_input)
            
        elif self.state == State.ASK_NOTIFICATION:
            return self.handle_notification(user_input)
            
        elif self.state == State.ASK_MISSING_CONTACT:
            return self.handle_missing_contact(user_input)
            
        elif self.state == State.SERVICE_MENU:
            return self.handle_service_menu(user_input)
            
        elif self.state == State.RESUME_SERVICE:
            return "Resume service flow - switching to resume builder..."
            
        elif self.state == State.COMPLETE:
            if user_input.lower().strip() == 'restart':
                self.reset()
                return self.show_role_selection()
            return "Registration complete! Type 'restart' to start over."
    
    def show_role_selection(self) -> str:
        return """Welcome to AFHSync! Choose your role:
1) Caregiver
2) AFH Provider
3) Service Provider"""
    
    def handle_role_selection(self, user_input: str) -> str:
        options = {
            '1': 'caregiver',
            'caregiver': 'caregiver',
            'care giver': 'caregiver',
            '2': 'afh_provider',
            'afh provider': 'afh_provider',
            'afh': 'afh_provider',
            '3': 'service_provider',
            'service provider': 'service_provider',
            'service': 'service_provider'
        }
        
        role = self.parser.fuzzy_match(user_input, options)
        
        if role:
            self.data['role'] = role
            self.state = State.ASK_CONTACT
            return "Please provide your phone number or email to check your registration status."
        else:
            return "Invalid selection. Please choose 1, 2, or 3."
    
    def handle_contact(self, user_input: str) -> str:
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        phone_pattern = r'\d{10,}'
        
        email = re.search(email_pattern, user_input)
        phone = re.search(phone_pattern, user_input)
        
        if email:
            self.data['contact'] = email.group()
            self.data['contact_type'] = 'email'
        elif phone:
            self.data['contact'] = phone.group()
            self.data['contact_type'] = 'phone'
        else:
            return "I couldn't detect a valid phone or email. Please provide a valid phone number or email address."
        
        self.state = State.CHECK_REGISTRATION
        return self.check_registration()
    
    def check_registration(self) -> str:
        # Simulate registration check
        known_contacts = ['2065550000', 'admin@afhsync.com']
        
        if self.data['contact'] in known_contacts:
            self.data['is_registered'] = True
            self.state = State.SERVICE_MENU
            return self.show_service_menu()
        else:
            self.data['is_registered'] = False
            self.state = State.ASK_NAME
            return "Welcome to AFHSync! Let's get you registered.\n\nWhat's your full name?"
    
    def handle_name(self, user_input: str) -> str:
        self.data['name'] = user_input.strip()
        self.state = State.ASK_LOCATION
        return "What city or area are you located in?"
    
    def handle_location(self, user_input: str) -> str:
        self.data['location'] = user_input.strip()
        self.state = State.ASK_AVAILABILITY
        return "When are you available to work? (e.g., weekdays, next Tuesday, nights)"
    
    def handle_availability(self, user_input: str) -> str:
        # Try dateparser first
        availability = self.parser.parse_availability(user_input)
        
        # If still custom, try Ollama fallback
        if availability['type'] == 'custom':
            ollama_result = self.parser.ollama_fallback(
                user_input,
                "User is answering when they are available to work"
            )
            if ollama_result and 'pattern' in ollama_result:
                availability = {
                    'type': 'pattern',
                    'pattern': ollama_result['pattern'],
                    'original': user_input
                }
        
        self.data['availability'] = availability
        
        # Acknowledge what was understood
        if availability['type'] == 'specific_date':
            confirm = f"Got it - available on {availability['day']}, {availability['date']}."
        elif availability['type'] == 'pattern':
            confirm = f"Got it - available {availability['pattern']}."
        else:
            confirm = f"Got it - {availability['original']}."
        
        self.state = State.ASK_CREDENTIALS
        return f"""{confirm}

What certifications do you have?
1) CNA (Certified Nursing Assistant)
2) HCA (Home Care Aide)
3) RN (Registered Nurse)
4) CPR Certified
5) First Aid Certified
6) Other/None"""
    
    def handle_credentials(self, user_input: str) -> str:
        cred_map = {
            '1': 'CNA',
            'cna': 'CNA',
            '2': 'HCA',
            'hca': 'HCA',
            '3': 'RN',
            'rn': 'RN',
            'registered nurse': 'RN',
            '4': 'CPR',
            'cpr': 'CPR',
            '5': 'First Aid',
            'first aid': 'First Aid',
            '6': 'Other/None',
            'none': 'Other/None',
            'other': 'Other/None'
        }
        
        cred = self.parser.fuzzy_match(user_input, cred_map, threshold=60)
        self.data['credentials'] = cred if cred else user_input.strip()
        
        self.state = State.ASK_UPLOAD
        return "Would you like to upload your certification documents now or later?"
    
    def handle_upload(self, user_input: str) -> str:
        options = {
            'now': 'now',
            'later': 'later',
            'nww': 'now',
            'nw': 'now',
            'ltey': 'later',
            'ltr': 'later',
            'yes': 'now',
            'no': 'later'
        }
        
        choice = self.parser.fuzzy_match(user_input, options, threshold=60)
        
        # Fallback: check keywords
        if not choice:
            if any(word in user_input.lower() for word in ['now', 'nw', 'yes', 'upload']):
                choice = 'now'
            elif any(word in user_input.lower() for word in ['later', 'ltr', 'no', 'skip']):
                choice = 'later'
        
        # Ollama fallback
        if not choice:
            ollama_result = self.parser.ollama_fallback(
                user_input,
                "User is choosing whether to upload documents now or later"
            )
            if ollama_result and 'choice' in ollama_result:
                choice = ollama_result['choice']
        
        if not choice:
            return "I didn't understand. Please type 'now' or 'later'"
        
        self.data['upload_timing'] = choice
        
        if choice == 'now':
            upload_msg = f"Upload your documents at: https://afhsync.com/upload/{self.data['contact']}\n\n"
        else:
            upload_msg = "No problem! You can upload documents later from your profile.\n\n"
        
        self.state = State.ASK_NOTIFICATION
        return upload_msg + "How would you like to receive job notifications? Type 'mobile' for SMS or 'email' for email."
    
    def handle_notification(self, user_input: str) -> str:
        options = {
            'mobile': 'mobile',
            'sms': 'mobile',
            'text': 'mobile',
            'phone': 'mobile',
            'email': 'email',
            'mail': 'email'
        }
        
        choice = self.parser.fuzzy_match(user_input, options, threshold=60)
        
        if not choice:
            return "Please type 'mobile' or 'email'"
        
        self.data['notification_method'] = choice
        
        if choice == 'mobile' and self.data['contact_type'] != 'phone':
            self.state = State.ASK_MISSING_CONTACT
            return "Please provide your phone number for SMS notifications:"
        elif choice == 'email' and self.data['contact_type'] != 'email':
            self.state = State.ASK_MISSING_CONTACT
            return "Please provide your email address for email notifications:"
        
        return self.complete_registration()
    
    def handle_missing_contact(self, user_input: str) -> str:
        if self.data['notification_method'] == 'mobile':
            phone = re.search(r'\d{10,}', user_input)
            if phone:
                self.data['phone'] = phone.group()
            else:
                return "Invalid phone number. Please provide a valid 10-digit phone number:"
        else:
            email = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', user_input)
            if email:
                self.data['email'] = email.group()
            else:
                return "Invalid email. Please provide a valid email address:"
        
        return self.complete_registration()
    
    def complete_registration(self) -> str:
        link = f"https://afhsync.com/jobs?role={self.data['role']}&location={self.data['location']}&contact={self.data['contact']}"
        
        self.state = State.SERVICE_MENU
        
        return f"""Registration complete!

Name: {self.data['name']}
Location: {self.data['location']}
Credentials: {self.data['credentials']}

Your link: {link}

{self.show_service_menu()}"""
    
    def show_service_menu(self) -> str:
        if self.data['role'] == 'caregiver':
            return """Caregiver Services:
1) Browse job openings
2) Resume writing service
3) Update availability
4) View applications

What would you like to do?"""
        elif self.data['role'] == 'afh_provider':
            return """AFH Provider Services:
1) Post job opening
2) Browse caregivers
3) Manage postings

What would you like to do?"""
        else:
            return """Service Provider Options:
1) List your services
2) Browse AFH requests
3) Update offerings

What would you like to do?"""
    
    def handle_service_menu(self, user_input: str) -> str:
        if self.data['role'] == 'caregiver':
            if '2' in user_input or 'resume' in user_input.lower():
                # Switch to resume builder
                from resume_builder import ResumeBuilder
                resume_bot = ResumeBuilder(self.data)
                return "Starting resume builder...\n\n" + resume_bot.start()
            else:
                return "Service selected. Feature coming soon!"
        
        return "Service selected. Feature coming soon!"
    
    def reset(self):
        self.state = State.START
        self.data = {}

# Test
if __name__ == "__main__":
    bot = AFHSyncBot()
    
    print(bot.process_message("start"))
    
    while True:
        user_input = input("\nYou: ")
        
        if user_input.lower() in ['exit', 'quit']:
            break
        
        response = bot.process_message(user_input)
        print(f"\nBot: {response}")