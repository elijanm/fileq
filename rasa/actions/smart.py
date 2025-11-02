"""
AFHSync Smart Chatbot - Production Version
- Fuzzy matching for typos
- Natural date parsing  
- Ollama AI fallback
- MongoDB integration
- Multi-location support
- Gender identification
- Multiple certifications
- On-demand detailed preferences
- Resume writing service integration
- Job matching and notifications
"""

from enum import Enum
from typing import Dict, Optional, Any, List
import re
from thefuzz import fuzz
import dateparser
from datetime import datetime, timedelta
import requests
import json
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError
import os
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://95.110.228.29:8201/v1')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'deepseek-r1:1.5b')
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
DB_NAME = os.getenv('DB_NAME', 'afhsync')

class State(Enum):
    """All possible bot states"""
    START = "start"
    ROLE_SELECTION = "role_selection"
    ASK_CONTACT = "ask_contact"
    CHECK_REGISTRATION = "check_registration"
    ASK_NAME = "ask_name"
    ASK_GENDER = "ask_gender"
    ASK_LOCATION = "ask_location"
    ASK_MORE_CITIES = "ask_more_cities"
    ASK_AVAILABILITY = "ask_availability"
    ASK_CREDENTIALS = "ask_credentials"
    ASK_MORE_CREDENTIALS = "ask_more_credentials"
    ASK_BASIC_PREFERENCES = "ask_basic_preferences"
    ASK_UPLOAD = "ask_upload"
    ASK_NOTIFICATION = "ask_notification"
    ASK_MISSING_CONTACT = "ask_missing_contact"
    SERVICE_MENU = "service_menu"
    COMPLETE = "complete"
    RESUME_SERVICE = "resume_service"
    DETAILED_PREFERENCES = "detailed_preferences"
    BROWSE_JOBS = "browse_jobs"


class MongoDBHandler:
    """Handle all MongoDB operations"""
    
    def __init__(self):
        try:
            self.client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[DB_NAME]
            self.users = self.db['users']
            self.jobs = self.db['jobs']
            self.applications = self.db['applications']
            
            # Create indexes
            self._create_indexes()
            
            logger.info("✅ Connected to MongoDB")
        except ConnectionFailure as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise
    
    def _create_indexes(self):
        """Create database indexes for performance"""
        try:
            # User indexes
            self.users.create_index('contact', unique=True)
            self.users.create_index('role')
            self.users.create_index([('locations.city', 1), ('locations.state', 1)])
            self.users.create_index('status')
            self.users.create_index([('created_at', -1)])
            
            # Job indexes
            self.jobs.create_index('status')
            self.jobs.create_index([('location.city', 1), ('location.state', 1)])
            self.jobs.create_index('role_type')
            self.jobs.create_index([('posted_at', -1)])
            
            # Application indexes
            self.applications.create_index('job_id')
            self.applications.create_index('caregiver_id')
            self.applications.create_index('status')
            self.applications.create_index([('applied_at', -1)])
            
            logger.info("✅ Database indexes created")
        except Exception as e:
            logger.warning(f"⚠️  Index creation warning: {e}")
    
    def find_user_by_contact(self, contact: str) -> Optional[Dict]:
        """Find user by phone or email"""
        try:
            return self.users.find_one({'contact': contact})
        except Exception as e:
            logger.error(f"Error finding user: {e}")
            return None
    
    def create_user(self, user_data: Dict) -> Optional[str]:
        """Create new user and return user_id"""
        try:
            user_data['created_at'] = datetime.utcnow()
            user_data['updated_at'] = datetime.utcnow()
            user_data['status'] = 'active'
            user_data['profile_views'] = 0
            
            result = self.users.insert_one(user_data)
            logger.info(f"✅ Created user: {user_data.get('name')} ({user_data.get('contact')})")
            return str(result.inserted_id)
        except DuplicateKeyError:
            logger.warning(f"⚠️  User already exists: {user_data.get('contact')}")
            return None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    def update_user(self, contact: str, update_data: Dict) -> bool:
        """Update user data"""
        try:
            update_data['updated_at'] = datetime.utcnow()
            result = self.users.update_one(
                {'contact': contact},
                {'$set': update_data}
            )
            if result.modified_count > 0:
                logger.info(f"✅ Updated user: {contact}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False
    
    def add_to_array(self, contact: str, field: str, value: Any) -> bool:
        """Add item to array field (credentials, locations, etc.)"""
        try:
            result = self.users.update_one(
                {'contact': contact},
                {'$addToSet': {field: value}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error adding to array: {e}")
            return False
    
    def get_jobs(self, filters: Dict, limit: int = 20) -> List[Dict]:
        """Get jobs matching filters"""
        try:
            return list(self.jobs.find(filters).limit(limit).sort('posted_at', -1))
        except Exception as e:
            logger.error(f"Error getting jobs: {e}")
            return []
    
    def get_user_stats(self, contact: str) -> Dict:
        """Get user statistics"""
        try:
            user = self.find_user_by_contact(contact)
            if not user:
                return {}
            
            applications = list(self.applications.find({'caregiver_contact': contact}))
            
            return {
                'total_applications': len(applications),
                'pending': len([a for a in applications if a['status'] == 'pending']),
                'interviews': len([a for a in applications if a.get('interview_scheduled')]),
                'profile_views': user.get('profile_views', 0),
                'member_since': user.get('created_at')
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}


class SmartParser:
    """Intelligent parsing with fuzzy matching and AI fallback"""
    
    @staticmethod
    def fuzzy_match(user_input: str, options: dict, threshold: int = 70) -> Optional[str]:
        """Match user input to closest option even with typos"""
        user_input = user_input.lower().strip()
        
        # First try exact match
        if user_input in options:
            return options[user_input]
        
        # Then fuzzy match
        best_match = None
        best_score = 0
        
        for key, value in options.items():
            score = fuzz.ratio(user_input, key.lower())
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
            'weekdays': ['weekday', 'weekdays', 'monday through friday', 'm-f', 'mon-fri', 'monday-friday'],
            'weekends': ['weekend', 'weekends', 'saturday and sunday', 'sat-sun', 'saturday-sunday'],
            'nights': ['night', 'nights', 'evening', 'evenings', 'overnight', 'night shift'],
            'days': ['day', 'days', 'morning', 'mornings', 'daytime', 'day shift'],
            'anytime': ['anytime', 'any time', 'flexible', 'whenever', 'always available', 'all times']
        }
        
        user_lower = user_input.lower()
        for category, keywords in patterns.items():
            for keyword in keywords:
                if keyword in user_lower:
                    return {
                        'type': 'pattern',
                        'pattern': category,
                        'original': user_input
                    }
        
        # Custom availability (e.g., "Monday-Friday 8am-10pm")
        return {
            'type': 'custom',
            'original': user_input
        }
    
    @staticmethod
    def parse_location(location_text: str) -> Dict:
        """Parse location into city and state"""
        state_map = {
            'wa': 'Washington',
            'washington': 'Washington',
            'seattle': 'Washington',  # Major city → state inference
            'tacoma': 'Washington',
            'spokane': 'Washington',
            'or': 'Oregon',
            'oregon': 'Oregon',
            'portland': 'Oregon',
            'ca': 'California',
            'california': 'California',
            'id': 'Idaho',
            'idaho': 'Idaho'
        }
        
        location_text = location_text.lower().strip()
        city = None
        state = None
        
        # Pattern: "city in state" (e.g., "Auburn in Seattle" or "Auburn in WA")
        if ' in ' in location_text:
            parts = location_text.split(' in ')
            city = parts[0].strip().title()
            state_indicator = parts[1].strip()
            
            for key, value in state_map.items():
                if key in state_indicator:
                    state = value
                    break
        
        # Pattern: "city, state" (e.g., "Auburn, WA")
        elif ',' in location_text:
            parts = location_text.split(',')
            city = parts[0].strip().title()
            if len(parts) > 1:
                state_part = parts[1].strip()
                for key, value in state_map.items():
                    if key in state_part:
                        state = value
                        break
        
        # Just city name
        else:
            city = location_text.title()
            # Try to infer state from known cities
            for key, value in state_map.items():
                if key in location_text:
                    state = value
                    break
        
        # Default to Washington if not specified
        if not state:
            state = 'Washington'
        
        return {
            'city': city,
            'state': state,
            'original': location_text
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
            logger.debug(f"Ollama fallback failed: {e}")
        
        return None


class AFHSyncBot:
    """Main chatbot class with state machine"""
    
    def __init__(self):
        self.state = State.START
        self.data = {}
        self.parser = SmartParser()
        self.db = MongoDBHandler()
        self.last_activity = datetime.now()
        
        logger.info("🤖 AFHSync Bot initialized")
    
    def process_message(self, user_input: str) -> str:
        """Main state machine logic"""
        self.last_activity = datetime.now()
        
        # Sanitize input
        user_input = self._sanitize_input(user_input)
        
        logger.debug(f"State: {self.state.value}, Input: {user_input[:50]}")
        
        try:
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
            
            elif self.state == State.ASK_GENDER:
                return self.handle_gender(user_input)
                
            elif self.state == State.ASK_LOCATION:
                return self.handle_location(user_input)
            
            elif self.state == State.ASK_MORE_CITIES:
                return self.handle_more_cities(user_input)
                
            elif self.state == State.ASK_AVAILABILITY:
                return self.handle_availability(user_input)
                
            elif self.state == State.ASK_CREDENTIALS:
                return self.handle_credentials(user_input)
            
            elif self.state == State.ASK_MORE_CREDENTIALS:
                return self.handle_more_credentials(user_input)
            
            elif self.state == State.ASK_BASIC_PREFERENCES:
                return self.handle_basic_preferences(user_input)
                
            elif self.state == State.ASK_UPLOAD:
                return self.handle_upload(user_input)
                
            elif self.state == State.ASK_NOTIFICATION:
                return self.handle_notification(user_input)
                
            elif self.state == State.ASK_MISSING_CONTACT:
                return self.handle_missing_contact(user_input)
                
            elif self.state == State.SERVICE_MENU:
                return self.handle_service_menu(user_input)
            
            elif self.state == State.BROWSE_JOBS:
                return self.handle_browse_jobs(user_input)
                
            elif self.state == State.RESUME_SERVICE:
                return "Resume service flow - switching to resume builder..."
            
            elif self.state == State.DETAILED_PREFERENCES:
                return self.handle_detailed_preferences(user_input)
                
            elif self.state == State.COMPLETE:
                if user_input.lower().strip() == 'restart':
                    self.reset()
                    self.state = State.ROLE_SELECTION
                    return self.show_role_selection()
                return "Registration complete! Type 'restart' to start over or 'menu' to see services."
        
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return "Sorry, an error occurred. Please try again or type 'restart'."
    
    def _sanitize_input(self, user_input: str) -> str:
        """Sanitize user input"""
        # Remove excessive whitespace
        sanitized = ' '.join(user_input.split())
        # Limit length
        max_length = 500
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        return sanitized.strip()
    
    # ==================== STATE HANDLERS ====================
    
    def show_role_selection(self) -> str:
        """Show role selection menu"""
        return """Welcome to AFHSync! 👋

Choose your role:
1️⃣ Caregiver
2️⃣ AFH Provider
3️⃣ Service Provider

Type the number or role name."""
    
    def handle_role_selection(self, user_input: str) -> str:
        """Handle role selection"""
        options = {
            '1': 'caregiver',
            'caregiver': 'caregiver',
            'care giver': 'caregiver',
            'carer': 'caregiver',
            '2': 'afh_provider',
            'afh provider': 'afh_provider',
            'afh': 'afh_provider',
            'provider': 'afh_provider',
            '3': 'service_provider',
            'service provider': 'service_provider',
            'service': 'service_provider'
        }
        
        role = self.parser.fuzzy_match(user_input, options, threshold=65)
        
        if role:
            self.data['role'] = role
            self.state = State.ASK_CONTACT
            return "Great! Please provide your phone number or email to check your registration status."
        else:
            return "❌ Invalid selection. Please choose:\n1 for Caregiver\n2 for AFH Provider\n3 for Service Provider"
    
    def handle_contact(self, user_input: str) -> str:
        """Handle contact information"""
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
            return "❌ I couldn't detect a valid phone or email.\n\nPlease provide:\n• 10-digit phone number (e.g., 2065551234)\n• Email address (e.g., name@email.com)"
        
        self.state = State.CHECK_REGISTRATION
        return self.check_registration()
    
    def check_registration(self) -> str:
        """Check if user is already registered"""
        existing_user = self.db.find_user_by_contact(self.data['contact'])
        
        if existing_user:
            self.data.update(existing_user)
            self.data['is_registered'] = True
            self.data.pop('_id', None)  # Remove MongoDB ID
            
            self.state = State.SERVICE_MENU
            
            return f"""✅ Welcome back, {existing_user.get('name', 'User')}! 👋

{self.show_service_menu()}"""
        else:
            self.data['is_registered'] = False
            self.state = State.ASK_NAME
            return "📝 Welcome to AFHSync! Let's get you registered.\n\n**What's your full name?**"
    
    def handle_name(self, user_input: str) -> str:
        """Handle name input"""
        self.data['name'] = user_input.strip().title()
        self.state = State.ASK_GENDER
        
        return f"""Nice to meet you, {self.data['name']}! 

**What is your gender?**
1️⃣ Male
2️⃣ Female  
3️⃣ Non-binary
4️⃣ Prefer not to say"""
    
    def handle_gender(self, user_input: str) -> str:
        """Handle gender selection"""
        gender_map = {
            '1': 'Male',
            'male': 'Male',
            'm': 'Male',
            'man': 'Male',
            '2': 'Female',
            'female': 'Female',
            'f': 'Female',
            'woman': 'Female',
            '3': 'Non-binary',
            'non-binary': 'Non-binary',
            'nonbinary': 'Non-binary',
            'nb': 'Non-binary',
            'enby': 'Non-binary',
            '4': 'Prefer not to say',
            'prefer not to say': 'Prefer not to say',
            'no answer': 'Prefer not to say',
            'skip': 'Prefer not to say'
        }
        
        gender = self.parser.fuzzy_match(user_input, gender_map, threshold=60)
        self.data['gender'] = gender if gender else 'Prefer not to say'
        
        self.state = State.ASK_LOCATION
        return "**What city or area are you located in?**\n\n_Examples: Auburn, WA  |  Seattle  |  Tacoma, Washington_"
    
    def handle_location(self, user_input: str) -> str:
        """Handle location input"""
        if 'locations' not in self.data:
            self.data['locations'] = []
        
        location_obj = self.parser.parse_location(user_input)
        self.data['locations'].append(location_obj)
        
        if not self.data.get('primary_location'):
            self.data['primary_location'] = location_obj
        
        self.state = State.ASK_MORE_CITIES
        return f"""✅ Got it - **{location_obj['city']}, {location_obj['state']}**

**Are there any other cities you're comfortable working in?**

_Type city names (comma-separated) or 'done' if finished._"""
    
    def handle_more_cities(self, user_input: str) -> str:
        """Handle additional cities"""
        if user_input.lower().strip() in ['done', 'no', 'none', 'finish', 'finished', 'skip']:
            cities_list = [f"{loc['city']}, {loc['state']}" for loc in self.data['locations']]
            
            self.state = State.ASK_AVAILABILITY
            return f"""📍 **Your coverage areas:** {', '.join(cities_list)}

**When are you available to work?**

_Examples:_
- Weekdays
- Monday, Tuesday, Friday 8am-10pm
- Nights
- Flexible/Anytime"""
        
        # Parse multiple cities
        cities = [c.strip() for c in user_input.split(',')]
        added_cities = []
        
        for city_text in cities:
            if city_text:
                location_obj = self.parser.parse_location(city_text)
                self.data['locations'].append(location_obj)
                added_cities.append(location_obj['city'])
        
        if added_cities:
            return f"""✅ **Added:** {', '.join(added_cities)}

Any more cities? _Type city names or 'done'._"""
        else:
            return "Please enter city names or type 'done'."
    
    def handle_availability(self, user_input: str) -> str:
        """Handle availability input"""
        availability = self.parser.parse_availability(user_input)
        
        # Try Ollama fallback if custom
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
        
        # Confirm understanding
        if availability['type'] == 'specific_date':
            confirm = f"✅ Available on **{availability['day']}, {availability['date']}**"
        elif availability['type'] == 'pattern':
            confirm = f"✅ Available **{availability['pattern']}**"
        else:
            confirm = f"✅ Noted: **{availability['original']}**"
        
        self.state = State.ASK_CREDENTIALS
        return f"""{confirm}

**What certifications do you have?**
1️⃣ CNA (Certified Nursing Assistant)
2️⃣ HCA (Home Care Aide)
3️⃣ RN (Registered Nurse)
4️⃣ CPR Certified
5️⃣ First Aid Certified
6️⃣ Other/None

_You can select multiple (e.g., "1, 4" or "CNA, CPR")_"""
    
    def handle_credentials(self, user_input: str) -> str:
        """Handle credentials input"""
        cred_map = {
            '1': 'CNA',
            'cna': 'CNA',
            'certified nursing assistant': 'CNA',
            '2': 'HCA',
            'hca': 'HCA',
            'home care aide': 'HCA',
            '3': 'RN',
            'rn': 'RN',
            'registered nurse': 'RN',
            'nurse': 'RN',
            '4': 'CPR',
            'cpr': 'CPR',
            'cpr certified': 'CPR',
            '5': 'First Aid',
            'first aid': 'First Aid',
            'firstaid': 'First Aid',
            '6': 'Other/None',
            'none': 'Other/None',
            'other': 'Other/None',
            'no certification': 'Other/None'
        }
        
        if 'credentials' not in self.data:
            self.data['credentials'] = []
        
        # Handle comma or space separated
        if ',' in user_input or len(user_input.split()) > 1:
            items = re.split('[,\s]+', user_input.strip())
            
            for item in items:
                item = item.strip()
                if item:
                    cred = self.parser.fuzzy_match(item, cred_map, threshold=60)
                    if cred and cred not in self.data['credentials']:
                        self.data['credentials'].append(cred)
            
            if self.data['credentials']:
                self.state = State.ASK_MORE_CREDENTIALS
                return f"""✅ **Added:** {', '.join(self.data['credentials'])}

**Do you have any other certifications?**

_Type number(s), name(s), or 'done' if finished._"""
        
        # Single credential
        else:
            cred = self.parser.fuzzy_match(user_input.lower(), cred_map, threshold=60)
            
            if cred:
                if cred not in self.data['credentials']:
                    self.data['credentials'].append(cred)
                
                self.state = State.ASK_MORE_CREDENTIALS
                return f"""✅ **Added:** {cred}

**Do you have any other certifications?**

_Type number, name, or 'done' if finished._"""
            else:
                return "❌ Invalid selection. Please choose 1-6 or type the certification name."
    
    def handle_more_credentials(self, user_input: str) -> str:
        """Handle additional credentials"""
        if user_input.lower().strip() in ['none', 'done', 'no', 'finish', 'finished', 'skip']:
            self.state = State.ASK_BASIC_PREFERENCES
            creds_summary = ', '.join(self.data['credentials'])
            
            return f"""✅ **Your certifications:** {creds_summary}

**Quick question - Are there any dealbreakers for you?**

_Common dealbreakers:_
1️⃣ No pets (allergies)
2️⃣ Non-smoking only
3️⃣ No dealbreakers - I'm flexible

_Type numbers or 'skip' to set later._"""
        
        # Add more credentials
        return self.handle_credentials(user_input)
    
    def handle_basic_preferences(self, user_input: str) -> str:
        """Handle basic dealbreaker preferences"""
        if user_input.lower().strip() in ['skip', 'later', 'none', '3', 'flexible', 'no', 'no dealbreakers']:
            self.data['dealbreakers'] = []
            self.data['preferences_complete'] = False
            self.state = State.ASK_UPLOAD
            return "✅ Great! We'll match you with all available jobs.\n\n**Would you like to upload your certification documents now or later?**"
        
        dealbreaker_map = {
            '1': 'No pets (allergies)',
            'no pets': 'No pets (allergies)',
            'allergic': 'No pets (allergies)',
            'pet allergies': 'No pets (allergies)',
            'allergies': 'No pets (allergies)',
            
            '2': 'Non-smoking only',
            'non-smoking': 'Non-smoking only',
            'no smoking': 'Non-smoking only',
            'smoke free': 'Non-smoking only',
            
            '3': 'No dealbreakers',
            'flexible': 'No dealbreakers',
            'open': 'No dealbreakers',
            'none': 'No dealbreakers'
        }
        
        if 'dealbreakers' not in self.data:
            self.data['dealbreakers'] = []
        
        items = re.split('[,\s]+', user_input.strip())
        
        for item in items:
            item = item.strip()
            if item:
                db = self.parser.fuzzy_match(item, dealbreaker_map, threshold=60)
                if db and db not in self.data['dealbreakers']:
                    self.data['dealbreakers'].append(db)
                    if self.data['dealbreakers']:
                        self.data['preferences_complete'] = False
                    self.state = State.ASK_UPLOAD
                    db_summary = ', '.join(self.data['dealbreakers'])
                    return f"""✅ **Noted:** {db_summary} We'll only match you with compatible positions. You can add more preferences anytime from your profile.
Would you like to upload your certification documents now or later?"""
            else:
             return "Please select 1, 2, 3, or type 'skip'"
def handle_upload(self, user_input: str) -> str:
    """Handle document upload timing"""
    options = {
        'now': 'now',
        'later': 'later',
        'nww': 'now',
        'nw': 'now',
        'ltey': 'later',
        'ltr': 'later',
        'yes': 'now',
        'no': 'later',
        'upload': 'now',
        'skip': 'later'
    }
    
    choice = self.parser.fuzzy_match(user_input, options, threshold=60)
    
    # Keyword fallback
    if not choice:
        if any(word in user_input.lower() for word in ['now', 'nw', 'yes', 'upload', 'sure']):
            choice = 'now'
        elif any(word in user_input.lower() for word in ['later', 'ltr', 'no', 'skip', 'not']):
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
        return "Please type 'now' or 'later'"
    
    self.data['upload_timing'] = choice
    
    if choice == 'now':
        upload_msg = f"📤 Upload your documents at:\n**https://afhsync.com/upload/{self.data['contact']}**\n\n"
    else:
        upload_msg = "✅ No problem! You can upload documents later from your profile.\n\n"
    
    self.state = State.ASK_NOTIFICATION
    return upload_msg + "**How would you like to receive job notifications?**\n\n_Type 'mobile' for SMS or 'email' for email._"

def handle_notification(self, user_input: str) -> str:
    """Handle notification preference"""
    options = {
        'mobile': 'mobile',
        'sms': 'mobile',
        'text': 'mobile',
        'phone': 'mobile',
        'txt': 'mobile',
        'email': 'email',
        'mail': 'email',
        'e-mail': 'email'
    }
    
    choice = self.parser.fuzzy_match(user_input, options, threshold=60)
    
    if not choice:
        return "Please type 'mobile' for SMS or 'email' for email notifications."
    
    self.data['notification_method'] = choice
    
    # Check if we need secondary contact
    if choice == 'mobile' and self.data['contact_type'] != 'phone':
        self.state = State.ASK_MISSING_CONTACT
        return "📱 Please provide your phone number for SMS notifications:"
    elif choice == 'email' and self.data['contact_type'] != 'email':
        self.state = State.ASK_MISSING_CONTACT
        return "📧 Please provide your email address for email notifications:"
    
    return self.complete_registration()

def handle_missing_contact(self, user_input: str) -> str:
    """Handle secondary contact information"""
    if self.data['notification_method'] == 'mobile':
        phone = re.search(r'\d{10,}', user_input)
        if phone:
            self.data['phone'] = phone.group()
        else:
            return "❌ Invalid phone number. Please provide a valid 10-digit phone number:"
    else:
        email = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', user_input)
        if email:
            self.data['email'] = email.group()
        else:
            return "❌ Invalid email. Please provide a valid email address:"
    
    return self.complete_registration()

def complete_registration(self) -> str:
    """Complete user registration and save to database"""
    # Save to MongoDB
    user_id = self.db.create_user(self.data)
    
    if not user_id:
        return "⚠️ This contact is already registered. Type 'restart' to try again or 'menu' for services."
    
    self.data['user_id'] = user_id
    
    # Format data for display
    cities = [loc['city'] for loc in self.data['locations']]
    location_param = ','.join(cities)
    
    creds = ', '.join(self.data['credentials'])
    locations = ', '.join([f"{loc['city']}, {loc['state']}" for loc in self.data['locations']])
    dealbreakers = ', '.join(self.data['dealbreakers']) if self.data['dealbreakers'] else 'None - Open to all'
    
    # Generate profile link
    link = f"https://afhsync.com/profile/{self.data['contact']}"
    
    self.state = State.SERVICE_MENU
    
    return f"""✅ **Registration Complete!** 📋 Your Profile:

Name: {self.data['name']}
Gender: {self.data['gender']}
Locations: {locations}
Certifications: {creds}
Dealbreakers: {dealbreakers}

🔗 Your Profile: {link}
{self.show_service_menu()}"""

def show_service_menu(self) -> str:
    """Show service menu based on role"""
    if self.data['role'] == 'caregiver':
        pref_reminder = ""
        if not self.data.get('preferences_complete', False):
            pref_reminder = "\n💡 _Tip: Complete your detailed preferences for better job matches!_\n"
        
        return f"""**Caregiver Services:** 1️⃣ Browse job openings
2️⃣ Resume writing service
3️⃣ Complete job preferences (pets, environment, etc.)
4️⃣ Update availability
5️⃣ View applications
{pref_reminder}
What would you like to do? (Type number or service name)"""
    elif self.data['role'] == 'afh_provider':
            return """**AFH Provider Services:** 1️⃣ Post job opening
2️⃣ Browse caregivers
3️⃣ Manage postings
4️⃣ View applications
What would you like to do?"""
    else:
            return """**Service Provider Options:** 1️⃣ List your services
2️⃣ Browse AFH requests
3️⃣ Update offerings
What would you like to do?"""
def handle_service_menu(self, user_input: str) -> str:
    """Handle service menu selection"""
    user_lower = user_input.lower().strip()
    
    if self.data['role'] == 'caregiver':
        if '1' in user_input or 'browse' in user_lower or 'job' in user_lower:
            self.state = State.BROWSE_JOBS
            return self.browse_jobs()
        
        elif '2' in user_input or 'resume' in user_lower:
            self.state = State.RESUME_SERVICE
            return self.start_resume_service()
        
        elif '3' in user_input or 'preference' in user_lower or 'detail' in user_lower:
            self.state = State.DETAILED_PREFERENCES
            return self.start_detailed_preferences()
        
        elif '4' in user_input or 'availability' in user_lower or 'update' in user_lower:
            return self.update_availability()
        
        elif '5' in user_input or 'application' in user_lower:
            return self.view_applications()
        
        else:
            return "Please select a service (1-5) or type 'menu' to see options again."
    
    return "Service selected. Feature coming soon! Type 'menu' to return."

def browse_jobs(self) -> str:
    """Browse available jobs with smart filtering"""
    # Build filter based on user data
    job_filters = {
        'role_type': 'caregiver',
        'status': 'active'
    }
    
    # Add location filter
    if self.data.get('locations'):
        cities = [loc['city'] for loc in self.data['locations']]
        job_filters['$or'] = [
            {'location.city': {'$in': cities}},
            {'remote': True}
        ]
    
    # Get jobs from MongoDB
    available_jobs = self.db.get_jobs(job_filters, limit=20)
    
    # Filter by dealbreakers
    if self.data.get('dealbreakers'):
        filtered_jobs = []
        for job in available_jobs:
            skip_job = False
            
            if 'No pets (allergies)' in self.data['dealbreakers'] and job.get('has_pets'):
                skip_job = True
            
            if 'Non-smoking only' in self.data['dealbreakers'] and job.get('smoking_household'):
                skip_job = True
            
            if not skip_job:
                filtered_jobs.append(job)
        
        available_jobs = filtered_jobs
    
    if not available_jobs:
        return """📭 **No jobs match your criteria yet.** We'll notify you when new positions open!
Options:

Type 'preferences' to adjust your preferences
Type 'menu' to return to services"""
    # Check if user needs to refine preferences
    if not self.data.get('preferences_complete', False) and len(available_jobs) > 10:
        return f"""🎯 **Found {len(available_jobs)} jobs in your area!** Would you like to refine your preferences to see better matches?
Type 'yes' to answer a few quick questions
Type 'no' to see all jobs"""
# Show first 5 jobs
    job_list = []
    for i, job in enumerate(available_jobs[:5]):
        location = job.get('location', {})
        job_list.append(
            f"{i+1}. **{job.get('title', 'Caregiver Position')}**\n"
            f"   📍 {location.get('city', 'TBD')}, {location.get('state', 'WA')}\n"
            f"   💵 ${job.get('pay_rate', 'TBD')}/hr | {job.get('shift_type', 'Flexible')}"
        )
    
    self.data['current_jobs'] = available_jobs  # Store for detail viewing
    
    return f"""🔍 **Available Jobs** ({len(available_jobs)} total): {chr(10).join(job_list)}
Type a number to see details, 'more' for additional jobs, or 'menu' to return."""

def handle_browse_jobs(self, user_input: str) -> str:
    """Handle job browsing interactions"""
    user_lower = user_input.lower().strip()
    
    # Check for job number selection
    if user_input.isdigit():
        job_num = int(user_input)
        current_jobs = self.data.get('current_jobs', [])
        
        if 1 <= job_num <= len(current_jobs):
            job = current_jobs[job_num - 1]
            return self.show_job_details(job)
        else:
            return f"Invalid job number. Please select 1-{len(current_jobs)} or type 'menu'."
    
    # Handle "more" request
    elif 'more' in user_lower:
        current_jobs = self.data.get('current_jobs', [])
        if len(current_jobs) > 5:
            job_list = []
            for i, job in enumerate(current_jobs[5:10], start=6):
                location = job.get('location', {})
                job_list.append(
                    f"{i}. **{job.get('title', 'Caregiver Position')}**\n"
                    f"   📍 {location.get('city', 'TBD')}, {location.get('state', 'WA')}\n"
                    f"   💵 ${job.get('pay_rate', 'TBD')}/hr"
                )
            return f"""🔍 **More Jobs:** {chr(10).join(job_list)}
Type a number to see details or 'menu' to return."""
        else:
            return "No more jobs available. Type 'menu' to return."
        # Handle menu return
    elif 'menu' in user_lower:
        self.state = State.SERVICE_MENU
        return self.show_service_menu()
    
    # Handle yes/no for preferences
    elif 'yes' in user_lower:
        self.state = State.DETAILED_PREFERENCES
        return self.start_detailed_preferences()
    
    elif 'no' in user_lower:
        return self.browse_jobs()
    
    else:
        return "Please type a job number, 'more', 'yes', 'no', or 'menu'."

def show_job_details(self, job: Dict) -> str:
    """Show detailed job information"""
    location = job.get('location', {})
    
    details = f"""📋 **Job Details** {job.get('title', 'Caregiver Position')}
📍 Location: {location.get('city', 'TBD')}, {location.get('state', 'WA')}
💵 Pay Rate: ${job.get('pay_rate', 'TBD')}/hr
⏰ Shift Type: {job.get('shift_type', 'Flexible')}
📅 Schedule: {job.get('schedule', 'TBD')}
Requirements:

Certifications: {', '.join(job.get('required_credentials', ['None listed']))}
Experience: {job.get('experience_required', 'Not specified')}

Environment:

Pets: {'Yes' if job.get('has_pets') else 'No'}
Smoking: {'Yes' if job.get('smoking_household') else 'No'}

Description:
{job.get('description', 'Contact employer for details')}
Type 'apply' to apply, 'back' to see more jobs, or 'menu' to return.""" 

    return details

def start_resume_service(self) -> str:
    """Start resume building service"""
    return """📝 **Resume Writing Service** Let me help you create a professional caregiver resume!
Do you have an existing resume you'd like me to improve?
Type 'yes' to upload existing resume
Type 'no' to build from scratch"""

def start_detailed_preferences(self) -> str:
    """Start detailed preference questionnaire"""
    if 'pref_step' not in self.data:
        self.data['pref_step'] = 'pets'
    
    return """🏠 **Let's build your detailed job preferences!** This helps us match you with the best opportunities.
Environment Preferences
Are you comfortable working with pets?
1️⃣ Yes - I love pets
2️⃣ No - Allergies or discomfort
3️⃣ Depends on the type/size"""

def handle_detailed_preferences(self, user_input: str) -> str:
    """Handle detailed preferences flow"""
    if 'detailed_preferences' not in self.data:
        self.data['detailed_preferences'] = {}
    
    if 'pref_step' not in self.data:
        self.data['pref_step'] = 'pets'
    
    step = self.data['pref_step']
    
    if step == 'pets':
        pet_map = {
            '1': 'Love pets',
            'yes': 'Love pets',
            'love': 'Love pets',
            '2': 'No pets',
            'no': 'No pets',
            'allergies': 'No pets',
            '3': 'Depends on type',
            'depends': 'Depends on type'
        }
        
        choice = self.parser.fuzzy_match(user_input, pet_map, threshold=60)
        if choice:
            self.data['detailed_preferences']['pets'] = choice
            self.data['pref_step'] = 'household_activity'
            
            # Update dealbreakers if needed
            if choice == 'No pets' and 'No pets (allergies)' not in self.data.get('dealbreakers', []):
                if 'dealbreakers' not in self.data:
                    self.data['dealbreakers'] = []
                self.data['dealbreakers'].append('No pets (allergies)')
            
            return """**What type of household environment do you prefer?** 1️⃣ Quiet and calm
2️⃣ Active and busy
3️⃣ No preference"""
        else:
            return "Please choose 1, 2, or 3"
        
        elif step == 'household_activity':
            activity_map = {
            '1': 'Quiet and calm',
            'quiet': 'Quiet and calm',
            'calm': 'Quiet and calm',
            '2': 'Active and busy',
            'active': 'Active and busy',
            'busy': 'Active and busy',
            '3': 'No preference',
            'no preference': 'No preference',
            'either': 'No preference'
        }
        
        choice = self.parser.fuzzy_match(user_input, activity_map, threshold=60)
        if choice:
            self.data['detailed_preferences']['household_activity'] = choice
            self.data['pref_step'] = 'languages'
            
            return """🗣️ **Language Skills** What languages do you speak?
Type languages separated by commas (e.g., English, Spanish, Tagalog)
Or type 'English only'"""
else:
return "Please choose 1, 2, or 3" 

elif step == 'languages':
        if 'english only' in user_input.lower():
            self.data['detailed_preferences']['languages'] = ['English']
        else:
            languages = [lang.strip().title() for lang in user_input.split(',')]
            self.data['detailed_preferences']['languages'] = languages
        
        self.data['pref_step'] = 'mobility'
        
        langs = ', '.join(self.data['detailed_preferences']['languages'])
        return f"""✅ **Languages:** {langs} 💪 Physical Capabilities
Can you assist with patient mobility and lifting?
1️⃣ Yes - Can lift 50+ lbs
2️⃣ Yes - Can lift up to 25 lbs
3️⃣ Limited - Prefer non-physical care
4️⃣ No lifting - Companionship only"""

elif step == 'mobility':
        mobility_map = {
            '1': 'Can lift 50+ lbs',
            'yes': 'Can lift 50+ lbs',
            '50': 'Can lift 50+ lbs',
            'heavy': 'Can lift 50+ lbs',
            '2': 'Can lift up to 25 lbs',
            '25': 'Can lift up to 25 lbs',
            'light': 'Can lift up to 25 lbs',
            '3': 'Prefer non-physical care',
            'limited': 'Prefer non-physical care',
            '4': 'Companionship only',
            'companionship': 'Companionship only',
            'no lifting': 'Companionship only'
        }
        
        choice = self.parser.fuzzy_match(user_input, mobility_map, threshold=60)
        if choice:
            self.data['detailed_preferences']['mobility'] = choice
            self.data['pref_step'] = 'transportation'
            
            return """🚗 **Transportation** Do you have reliable transportation?
1️⃣ Yes - Own vehicle
2️⃣ Yes - Public transit
3️⃣ Need transportation assistance"""
else:
return "Please choose 1, 2, 3, or 4"

elif step == 'transportation':
        transport_map = {
            '1': 'Own vehicle',
            'yes': 'Own vehicle',
            'car': 'Own vehicle',
            'vehicle': 'Own vehicle',
            '2': 'Public transit',
            'public': 'Public transit',
            'transit': 'Public transit',
            'bus': 'Public transit',
            '3': 'Need assistance',
            'need': 'Need assistance',
            'no': 'Need assistance'
        }
        
        choice = self.parser.fuzzy_match(user_input, transport_map, threshold=60)
        if choice:
            self.data['detailed_preferences']['transportation'] = choice
            self.data['pref_step'] = 'shift_preference'
            
            return """⏰ **Shift Preferences** What shift types work best for you?
1️⃣ Day shifts (8am-4pm)
2️⃣ Evening shifts (4pm-12am)
3️⃣ Night shifts (12am-8am)
4️⃣ Live-in care
5️⃣ Flexible - Any shift
You can select multiple (e.g., "1, 2" or "day, evening")"""
else:
return "Please choose 1, 2, or 3"

elif step == 'shift_preference':
        shift_map = {
            '1': 'Day shifts',
            'day': 'Day shifts',
            'days': 'Day shifts',
            'morning': 'Day shifts',
            '2': 'Evening shifts',
            'evening': 'Evening shifts',
            'evenings': 'Evening shifts',
            '3': 'Night shifts',
            'night': 'Night shifts',
            'nights': 'Night shifts',
            'overnight': 'Night shifts',
            '4': 'Live-in care',
            'live-in': 'Live-in care',
            'live in': 'Live-in care',
            '5': 'Flexible',
            'flexible': 'Flexible',
            'any': 'Flexible',
            'all': 'Flexible'
        }
        
        shifts = []
        items = re.split('[,\s]+', user_input.strip())
        
        for item in items:
            if item:
                shift = self.parser.fuzzy_match(item, shift_map, threshold=60)
                if shift and shift not in shifts:
                    shifts.append(shift)
        
        if shifts:
            self.data['detailed_preferences']['shift_preferences'] = shifts
            self.data['pref_step'] = 'special_care'
            
            shifts_str = ', '.join(shifts)
            return f"""✅ **Shifts:** {shifts_str} 🏥 Special Care Experience
Do you have experience with any of these conditions?
1️⃣ Dementia/Alzheimer's
2️⃣ Diabetes management
3️⃣ Hospice/End-of-life care
4️⃣ Post-surgical care
5️⃣ Stroke recovery
6️⃣ None of the above
Select multiple or type 'none'"""
else:
return "Please choose from options 1-5"

elif step == 'special_care':
        if 'none' in user_input.lower() or '6' in user_input:
            self.data['detailed_preferences']['special_care'] = ['General care']
        else:
            care_map = {
                '1': 'Dementia/Alzheimer\'s',
                'dementia': 'Dementia/Alzheimer\'s',
                'alzheimer': 'Dementia/Alzheimer\'s',
                '2': 'Diabetes management',
                'diabetes': 'Diabetes management',
                '3': 'Hospice care',
                'hospice': 'Hospice care',
                'end-of-life': 'Hospice care',
                '4': 'Post-surgical care',
                'post-surgical': 'Post-surgical care',
                'surgery': 'Post-surgical care',
                '5': 'Stroke recovery',
                'stroke': 'Stroke recovery',
                '6': 'None',
                'none': 'General care'
            }
            
            care_types = []
            items = re.split('[,\s]+', user_input.strip())
            
            for item in items:
                if item:
                    care = self.parser.fuzzy_match(item, care_map, threshold=60)
                    if care and care not in care_types:
                        care_types.append(care)
            
            self.data['detailed_preferences']['special_care'] = care_types if care_types else ['General care']
        
        self.data['pref_step'] = 'dietary'
        
        care_str = ', '.join(self.data['detailed_preferences']['special_care'])
        return f"""✅ **Experience:** {care_str} 🍽️ Dietary Accommodations
Are you comfortable preparing meals following special diets?
1️⃣ Yes - All dietary restrictions (kosher, halal, vegan, etc.)
2️⃣ Yes - Basic restrictions only
3️⃣ Prefer no meal preparation"""

elif step == 'dietary':
        dietary_map = {
            '1': 'All dietary restrictions',
            'yes': 'All dietary restrictions',
            'all': 'All dietary restrictions',
            '2': 'Basic restrictions',
            'basic': 'Basic restrictions',
            '3': 'No meal prep',
            'no': 'No meal prep',
            'prefer not': 'No meal prep'
        }
        
        choice = self.parser.fuzzy_match(user_input, dietary_map, threshold=60)
        if choice:
            self.data['detailed_preferences']['dietary'] = choice
            
            # Save updated preferences to MongoDB
            self.data['preferences_complete'] = True
            self.db.update_user(self.data['contact'], {
                'detailed_preferences': self.data['detailed_preferences'],
                'preferences_complete': True,
                'dealbreakers': self.data.get('dealbreakers', [])
            })
            
            # Reset preference step
            del self.data['pref_step']
            
            self.state = State.SERVICE_MENU
            
            # Generate summary
            prefs = self.data['detailed_preferences']
            summary = f"""✅ **Preferences Saved!** 📋 Your Complete Profile:
Environment:

Pets: {prefs.get('pets', 'Not specified')}
Household: {prefs.get('household_activity', 'Not specified')}

Skills:

Languages: {', '.join(prefs.get('languages', ['English']))}
Mobility: {prefs.get('mobility', 'Not specified')}
Special Care: {', '.join(prefs.get('special_care', ['General care']))}
Dietary: {prefs.get('dietary', 'Not specified')}

Logistics:

Transportation: {prefs.get('transportation', 'Not specified')}
Shifts: {', '.join(prefs.get('shift_preferences', ['Not specified']))}

These preferences will help us match you with the best opportunities!
{self.show_service_menu()}"""

return summary
        else:
            return "Please choose 1, 2, or 3"
    
    return "Something went wrong. Type 'menu' to return to services."

def update_availability(self) -> str:
    """Update availability"""
    return """📅 **Update Availability** When are you available to work?
Examples:

Weekdays
Monday, Wednesday, Friday 9am-5pm
Nights
Flexible

Type your availability or 'cancel' to return."""
def view_applications(self) -> str:
    """View job applications"""
    stats = self.db.get_user_stats(self.data['contact'])
    
    return f"""📊 **Your Applications**Total Applications: {stats.get('total_applications', 0)}
Pending Review: {stats.get('pending', 0)}
Interviews Scheduled: {stats.get('interviews', 0)}
Profile Views: {stats.get('profile_views', 0)}

Type 'menu' to return to services."""
def reset(self):
    """Reset bot state"""
    contact = self.data.get('contact')  # Preserve contact if returning user
    self.state = State.START
    self.data = {}
    if contact:
        self.data['contact'] = contact
    logger.info("🔄 Bot reset")
    
    =========================== MAIN EXECUTION ===========================
if name == "main":
print("=" * 60)
print("AFHSync Smart Chatbot - Interactive Test Mode")
print("=" * 60)
print("\nCommands:")
print("  • Type your messages normally")
print("  • 'exit' or 'quit' - Exit the program")
print("  • 'restart' - Restart conversation")
print("  • 'debug' - Show current state and data")
print("=" * 60)
print()

try:
    bot = AFHSyncBot()
    
    print(bot.process_message("start"))
    print()
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['exit', 'quit']:
                print("\n👋 Goodbye! Thank you for using AFHSync.")
                break
            
            if user_input.lower() == 'debug':
                print(f"\n🔍 Debug Info:")
                print(f"State: {bot.state.value}")
                print(f"Data keys: {list(bot.data.keys())}")
                print(f"Last activity: {bot.last_activity}")
                print()
                continue
            
            response = bot.process_message(user_input)
            print(f"\nBot: {response}\n")
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted. Type 'exit' to quit or continue chatting.")
            continue

except KeyboardInterrupt:
    print("\n\n👋 Goodbye!")
except Exception as e:
    logger.error(f"Fatal error: {e}", exc_info=True)
    print(f"\n❌ Fatal error: {e}")