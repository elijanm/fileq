"""
AFHSync Smart Chatbot - Main Bot Logic
- State machine
- Message processing
- Conversation flow
- NO EMOJIS - Professional clean interface
"""

from enum import Enum
from typing import Dict, Optional, List
import re
from datetime import datetime
import logging

from utils.util import SmartParser, MongoDBHandler
from services.resume import ResumeService

logger = logging.getLogger(__name__)


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


class AFHSyncBot:
    """Main chatbot class with state machine"""
    
    def __init__(self):
        self.state = State.START
        self.data = {}
        self.parser = SmartParser()
        self.db = MongoDBHandler()
        self.resume_service = ResumeService(self.db)
        self.last_activity = datetime.now()
        
        logger.info("AFHSync Bot initialized")
    
    def process_message(self, user_input: str) -> str:
        """Main state machine logic"""
        self.last_activity = datetime.now()
        
        # Sanitize input
        user_input = self._sanitize_input(user_input)
        
        logger.info(f"State: {self.state.value}, Input: {user_input[:50]}")
        
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
                return self.resume_service.handle_resume_flow(user_input, self.data)
            
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
        sanitized = ' '.join(user_input.split())
        max_length = 500
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        return sanitized.strip()
    
    # ==================== STATE HANDLERS ====================
    
    def show_role_selection(self) -> str:
        """Show role selection menu"""
        return """Welcome to AFHSync!

Choose your role:

[Caregiver](#action:select_role_caregiver)
[AFH Provider](#action:select_role_afh)
[Service Provider](#action:select_role_service)"""
    
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
            return "Invalid selection. Please select your role from the options above."
    
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
            return "I couldn't detect a valid phone or email.\n\nPlease provide:\n• 10-digit phone number (e.g., 2065551234)\n• Email address (e.g., name@email.com)"
        
        self.state = State.CHECK_REGISTRATION
        return self.check_registration()
    
    def check_registration(self) -> str:
        """Check if user is already registered"""
        existing_user = self.db.find_user_by_contact(self.data['contact'])
        
        if existing_user:
            self.data.update(existing_user)
            self.data['is_registered'] = True
            self.data.pop('_id', None)
            
            self.state = State.SERVICE_MENU
            
            return f"""Welcome back, {existing_user.get('name', 'User')}!

{self.show_service_menu()}"""
        else:
            self.data['is_registered'] = False
            self.state = State.ASK_NAME
            return "Welcome to AFHSync! Let's get you registered.\n\n**What's your full name?**"
    
    def handle_name(self, user_input: str) -> str:
        """Handle name input"""
        self.data['name'] = user_input.strip().title()
        self.state = State.ASK_GENDER
        
        return f"""Nice to meet you, {self.data['name']}!

**What is your gender?**

[Male](#action:gender_male)
[Female](#action:gender_female)
[Non-binary](#action:gender_nonbinary)
[Prefer not to say](#action:gender_skip)"""
    
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
        return "**What city or area are you located in?**\n\nExamples: Auburn, WA  |  Seattle  |  Tacoma, Washington"
    
    def handle_location(self, user_input: str) -> str:
        """Handle location input"""
        if 'locations' not in self.data:
            self.data['locations'] = []
        
        location_obj = self.parser.parse_location(user_input)
        self.data['locations'].append(location_obj)
        
        if not self.data.get('primary_location'):
            self.data['primary_location'] = location_obj
        
        self.state = State.ASK_MORE_CITIES
        return f"""Got it - **{location_obj['city']}, {location_obj['state']}**

**Are there any other cities you're comfortable working in?**

Type city names (comma-separated) or 'done' if finished."""
    
    def handle_more_cities(self, user_input: str) -> str:
        """Handle additional cities"""
        if user_input.lower().strip() in ['done', 'no', 'none', 'finish', 'finished', 'skip']:
            cities_list = [f"{loc['city']}, {loc['state']}" for loc in self.data['locations']]
            
            self.state = State.ASK_AVAILABILITY
            return f"""**Your coverage areas:** {', '.join(cities_list)}

**When are you available to work?**

Examples:
- Weekdays
- Monday, Tuesday, Friday 8am-10pm
- Nights
- Flexible/Anytime"""
        
        cities = [c.strip() for c in user_input.split(',')]
        added_cities = []
        
        for city_text in cities:
            if city_text:
                location_obj = self.parser.parse_location(city_text)
                self.data['locations'].append(location_obj)
                added_cities.append(location_obj['city'])
        
        if added_cities:
            return f"""**Added:** {', '.join(added_cities)}

Any more cities? Type city names or 'done'."""
        else:
            return "Please enter city names or type 'done'."
    
    def handle_availability(self, user_input: str) -> str:
        """Handle availability input"""
        availability = self.parser.parse_availability(user_input)
        
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
        
        if availability['type'] == 'specific_date':
            confirm = f"Available on **{availability['day']}, {availability['date']}**"
        elif availability['type'] == 'pattern':
            confirm = f"Available **{availability['pattern']}**"
        else:
            confirm = f"Noted: **{availability['original']}**"
        
        self.state = State.ASK_CREDENTIALS
        return f"""{confirm}

**What certifications do you have?**

[CNA](#action:cert_cna)
[HCA](#action:cert_hca)
[RN](#action:cert_rn)
[CPR](#action:cert_cpr)
[First Aid](#action:cert_firstaid)
[None](#action:cert_none)

You can select multiple or type certification names."""
    
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
        
        if ',' in user_input or len(user_input.split()) > 1:
            items = re.split(r'[,\s]+', user_input.strip())
            
            for item in items:
                item = item.strip()
                if item:
                    cred = self.parser.fuzzy_match(item, cred_map, threshold=60)
                    if cred and cred not in self.data['credentials']:
                        self.data['credentials'].append(cred)
            
            if self.data['credentials']:
                self.state = State.ASK_MORE_CREDENTIALS
                return f"""**Added:** {', '.join(self.data['credentials'])}

**Do you have any other certifications?**

Type certification names or 'done' if finished."""
        
        else:
            cred = self.parser.fuzzy_match(user_input.lower(), cred_map, threshold=60)
            
            if cred:
                if cred not in self.data['credentials']:
                    self.data['credentials'].append(cred)
                
                self.state = State.ASK_MORE_CREDENTIALS
                return f"""**Added:** {cred}

**Do you have any other certifications?**

Type certification name or 'done' if finished."""
            else:
                return "Invalid selection. Please select from the options above or type certification names."
    
    def handle_more_credentials(self, user_input: str) -> str:
        """Handle additional credentials"""
        if user_input.lower().strip() in ['none', 'done', 'no', 'finish', 'finished', 'skip']:
            self.state = State.ASK_BASIC_PREFERENCES
            creds_summary = ', '.join(self.data['credentials'])
            
            return f"""**Your certifications:** {creds_summary}

**Quick question - Are there any dealbreakers for you?**

Common dealbreakers:

[No pets (allergies)](#action:deal_nopets)
[Non-smoking only](#action:deal_nosmoking)
[No dealbreakers](#action:deal_none)

Type 'skip' to set later."""
        
        return self.handle_credentials(user_input)
    
    def handle_basic_preferences(self, user_input: str) -> str:
        """Handle basic dealbreaker preferences"""
        if user_input.lower().strip() in ['skip', 'later', 'none', '3', 'flexible', 'no', 'no dealbreakers']:
            self.data['dealbreakers'] = []
            self.data['preferences_complete'] = False
            self.state = State.ASK_UPLOAD
            return "Great! We'll match you with all available jobs.\n\n**Would you like to upload your certification documents now or later?**"
        
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
        
        items = re.split(r'[,\s]+', user_input.strip())
        
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
            return f"""**Noted:** {db_summary}

We'll only match you with compatible positions. You can add more preferences anytime from your profile.

**Would you like to upload your certification documents now or later?**"""
        else:
            return "Please select from the options above or type 'skip'"
    
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
        
        if not choice:
            if any(word in user_input.lower() for word in ['now', 'nw', 'yes', 'upload', 'sure']):
                choice = 'now'
            elif any(word in user_input.lower() for word in ['later', 'ltr', 'no', 'skip', 'not']):
                choice = 'later'
        
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
            upload_msg = f"Upload your documents at:\nhttps://afhsync.com/upload/{self.data['contact']}\n\n"
        else:
            upload_msg = "No problem! You can upload documents later from your profile.\n\n"
        
        self.state = State.ASK_NOTIFICATION
        return upload_msg + "**How would you like to receive job notifications?**\n\n[Mobile/SMS](#action:notify_mobile)\n[Email](#action:notify_email)"
    
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
            return "Please select Mobile/SMS or Email for notifications."
        
        self.data['notification_method'] = choice
        
        if choice == 'mobile' and self.data['contact_type'] != 'phone':
            self.state = State.ASK_MISSING_CONTACT
            return "Please provide your phone number for SMS notifications:"
        elif choice == 'email' and self.data['contact_type'] != 'email':
            self.state = State.ASK_MISSING_CONTACT
            return "Please provide your email address for email notifications:"
        
        return self.complete_registration()
    
    def handle_missing_contact(self, user_input: str) -> str:
        """Handle secondary contact information"""
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
        """Complete user registration and save to database"""
        user_id = self.db.create_user(self.data)
        
        if not user_id:
            return "This contact is already registered. Type 'restart' to try again or 'menu' for services."
        
        self.data['user_id'] = user_id
        
        creds = ', '.join(self.data['credentials'])
        locations = ', '.join([f"{loc['city']}, {loc['state']}" for loc in self.data['locations']])
        dealbreakers = ', '.join(self.data['dealbreakers']) if self.data['dealbreakers'] else 'None - Open to all'
        
        link = f"https://afhsync.com/profile/{self.data['contact']}"
        
        self.state = State.SERVICE_MENU
        
        return f"""**Registration Complete!**

**Your Profile:**
- Name: {self.data['name']}
- Gender: {self.data['gender']}
- Locations: {locations}
- Certifications: {creds}
- Dealbreakers: {dealbreakers}

Your Profile: {link}

{self.show_service_menu()}"""
    
    def show_service_menu(self) -> str:
        """Show service menu based on role"""
        if self.data['role'] == 'caregiver':
            pref_reminder = ""
            if not self.data.get('preferences_complete', False):
                pref_reminder = "\nTip: Complete your detailed preferences for better job matches.\n"
            
            return f"""**Caregiver Services:**

[Browse job openings](#action:browse_jobs)
[Resume writing service](#action:resume_builder)
[Complete job preferences](#action:complete_profile)
[Update availability](#action:update_availability)
[View applications](#action:view_applications)
{pref_reminder}
What would you like to do?"""
        elif self.data['role'] == 'afh_provider':
            return """**AFH Provider Services:**

[Post job opening](#action:post_job)
[Browse caregivers](#action:browse_caregivers)
[Manage postings](#action:manage_postings)
[View applications](#action:review_applications)

What would you like to do?"""
        else:
            return """**Service Provider Options:**

[List your services](#action:list_services)
[Browse AFH requests](#action:browse_requests)
[Update offerings](#action:manage_offerings)

What would you like to do?"""
    
    def handle_service_menu(self, user_input: str) -> str:
        """Handle service menu selection"""
        user_lower = user_input.lower().strip()
        
        if not self.data.get('contact'):
            self.state = State.ASK_CONTACT
            return "To access services, please provide your phone number or email:"
        
        if self.data['role'] == 'caregiver':
            if '1' in user_input or 'browse' in user_lower or 'job' in user_lower:
                self.state = State.BROWSE_JOBS
                return self.browse_jobs()
            
            elif '2' in user_input or 'resume' in user_lower:
                self.state = State.RESUME_SERVICE
                return self.resume_service.start_resume_service()
            
            elif '3' in user_input or 'preference' in user_lower or 'detail' in user_lower:
                self.state = State.DETAILED_PREFERENCES
                return self.start_detailed_preferences()
            
            elif '4' in user_input or 'availability' in user_lower or 'update' in user_lower:
                return self.update_availability()
            
            elif '5' in user_input or 'application' in user_lower:
                return self.view_applications()
            
            else:
                return "Please select a service or type 'menu' to see options again."
        
        return "Service selected. Feature coming soon! Type 'menu' to return."
    
    def browse_jobs(self) -> str:
        """Browse available jobs with clickable links"""
        job_filters = {
            'role_type': 'caregiver',
            'status': 'active'
        }
        
        if self.data.get('locations'):
            cities = [loc['city'] for loc in self.data['locations']]
            job_filters['$or'] = [
                {'location.city': {'$in': cities}},
                {'remote': True}
            ]
        elif self.data.get('city'):
            job_filters['$or'] = [
                {'location.city': self.data['city']},
                {'remote': True}
            ]
        
        available_jobs = self.db.get_jobs(job_filters, limit=20)
        
        # Apply dealbreaker filters
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
            return """**No jobs match your criteria yet**

We'll notify you when new positions open!

[Adjust your preferences](#action:complete_profile)
[Return to menu](#action:menu)"""
        
        if not self.data.get('preferences_complete', False) and len(available_jobs) > 10:
            return f"""**Found {len(available_jobs)} jobs in your area**

Would you like to refine your preferences for better matches?

[Yes, refine preferences](#action:complete_profile)
[No, show all jobs](#action:show_all_jobs)"""
        
        job_list = []
        for i, job in enumerate(available_jobs[:5]):
            location = job.get('location', {})
            job_list.append(
                f"**{i+1}. {job.get('title', 'Caregiver Position')}**\n"
                f"   Location: {location.get('city', 'TBD')}, {location.get('state', 'WA')}\n"
                f"   Pay: ${job.get('pay_rate', 'TBD')}/hr | {job.get('shift_type', 'Flexible')}"
            )
        
        self.data['current_jobs'] = available_jobs
        
        more_link = f"\n[Show more jobs](#action:more_jobs)" if len(available_jobs) > 5 else ""
        
        return f"""**Available Jobs** ({len(available_jobs)} total)

{chr(10).join(job_list)}

Type a number (1-5) to see details{more_link}
[Return to menu](#action:menu)"""
    
    def handle_browse_jobs(self, user_input: str) -> str:
        """Handle job browsing interactions"""
        user_lower = user_input.lower().strip()
        
        if user_input.isdigit():
            job_num = int(user_input)
            current_jobs = self.data.get('current_jobs', [])
            
            if 1 <= job_num <= len(current_jobs):
                job = current_jobs[job_num - 1]
                return self.show_job_details(job)
            else:
                return f"Invalid job number. Please select 1-{len(current_jobs)} or [return to menu](#action:menu)."
        
        elif 'more' in user_lower or 'show more' in user_lower:
            current_jobs = self.data.get('current_jobs', [])
            if len(current_jobs) > 5:
                job_list = []
                for i, job in enumerate(current_jobs[5:10], start=6):
                    location = job.get('location', {})
                    job_list.append(
                        f"**{i}. {job.get('title', 'Caregiver Position')}**\n"
                        f"   Location: {location.get('city', 'TBD')}, {location.get('state', 'WA')}\n"
                        f"   Pay: ${job.get('pay_rate', 'TBD')}/hr"
                    )
                return f"""**More Jobs:**

{chr(10).join(job_list)}

Type a number to see details
[Return to menu](#action:menu)"""
            else:
                return """No more jobs available.

[Browse again](#action:browse_jobs)
[Return to menu](#action:menu)"""
        
        elif 'menu' in user_lower:
            self.state = State.SERVICE_MENU
            return self.show_service_menu()
        
        elif 'yes' in user_lower or 'refine' in user_lower:
            self.state = State.DETAILED_PREFERENCES
            return self.start_detailed_preferences()
        
        elif 'no' in user_lower or 'show all' in user_lower:
            return self.browse_jobs()
        
        else:
            return "Please type a job number, 'more', or select an option above."
    
    def show_job_details(self, job: Dict) -> str:
        """Show detailed job information"""
        location = job.get('location', {})
        
        details = f"""**Job Details**

**{job.get('title', 'Caregiver Position')}**

Location: {location.get('city', 'TBD')}, {location.get('state', 'WA')}
Pay Rate: ${job.get('pay_rate', 'TBD')}/hr
Shift Type: {job.get('shift_type', 'Flexible')}
Schedule: {job.get('schedule', 'TBD')}

**Requirements:**
- Certifications: {', '.join(job.get('required_credentials', ['None listed']))}
- Experience: {job.get('experience_required', 'Not specified')}

**Environment:**
- Pets: {'Yes' if job.get('has_pets') else 'No'}
- Smoking: {'Yes' if job.get('smoking_household') else 'No'}

**Description:**
{job.get('description', 'Contact employer for details')}

[Apply to this job](#action:apply_job)
[See more jobs](#action:browse_jobs)
[Return to menu](#action:menu)"""
        
        return details
    
    def start_detailed_preferences(self) -> str:
        """Start detailed preference questionnaire"""
        # if 'pref_step' not in self.data:
        #     self.data['pref_step'] = 'pets'
        print(self.data)
        existing_step = self.data.get('pref_step')
    
        if existing_step and existing_step != 'pets':
            # Resume from where they left off
            logger.info(f"Resuming preferences from step: {existing_step}")
            return self._get_question_for_step(existing_step)
    
        self.data['pref_step'] = 'pets'
        
        return """**Let's build your detailed job preferences**

This helps us match you with the best opportunities.

**Environment Preferences**

Are you comfortable working with pets?

[Yes - I love pets](#action:pref_pets_yes)
[No - Allergies or discomfort](#action:pref_pets_no)
[Depends on the type/size](#action:pref_pets_depends)"""
    
    def handle_detailed_preferences(self, user_input: str) -> str:
        """Handle detailed preferences flow with clickable links"""
        if 'detailed_preferences' not in self.data:
            self.data['detailed_preferences'] = {}
        
        # if 'pref_step' not in self.data:
        #     self.data['pref_step'] = 'pets'
        
        step = self.data.get('pref_step', 'pets')
        logger.info(f"STEP:: {step}")
        if step == 'pets':
            pet_map = {
                '1': 'Love pets',
                'yes': 'Love pets',
                'love': 'Love pets',
                'i love pets': 'Love pets',
                '2': 'No pets',
                'no': 'No pets',
                'allergies': 'No pets',
                'discomfort': 'No pets',
                '3': 'Depends on type',
                'depends': 'Depends on type',
                'type': 'Depends on type'
            }
            
            choice = self.parser.fuzzy_match(user_input, pet_map, threshold=60)
            if choice:
                self.data['detailed_preferences']['pets'] = choice
                self.data['pref_step'] = 'household_activity'
                
                if choice == 'No pets' and 'No pets (allergies)' not in self.data.get('dealbreakers', []):
                    if 'dealbreakers' not in self.data:
                        self.data['dealbreakers'] = []
                    self.data['dealbreakers'].append('No pets (allergies)')
                
                return """**What type of household environment do you prefer?**

[Quiet and calm](#action:pref_house_quiet)
[Active and busy](#action:pref_house_active)
[No preference](#action:pref_house_none)"""
            else:
                return "Please select one of the options above."
        
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
                
                return """**Language Skills**

What languages do you speak?

[English only](#action:lang_english)
[Multiple languages](#action:lang_multiple)

Or type languages separated by commas (e.g., English, Spanish, Tagalog)"""
            else:
                return "Please select one of the options above."
        
        elif step == 'languages':
            if 'english only' in user_input.lower():
                self.data['detailed_preferences']['languages'] = ['English']
            else:
                languages = [lang.strip().title() for lang in user_input.split(',') if lang.strip()]
                self.data['detailed_preferences']['languages'] = languages if languages else ['English']
            
            self.data['pref_step'] = 'mobility'
            
            langs = ', '.join(self.data['detailed_preferences']['languages'])
            return f"""**Languages:** {langs}

**Physical Capabilities**

Can you assist with patient mobility and lifting?

[Yes - Can lift 50+ lbs](#action:mobility_heavy)
[Yes - Can lift up to 25 lbs](#action:mobility_light)
[Limited - Prefer non-physical care](#action:mobility_limited)
[No lifting - Companionship only](#action:mobility_none)"""
        
        elif step == 'mobility':
            mobility_map = {
                '1': 'Can lift 50+ lbs',
                'yes': 'Can lift 50+ lbs',
                '50': 'Can lift 50+ lbs',
                'heavy': 'Can lift 50+ lbs',
                'lift 50': 'Can lift 50+ lbs',
                '2': 'Can lift up to 25 lbs',
                '25': 'Can lift up to 25 lbs',
                'light': 'Can lift up to 25 lbs',
                'lift up to 25': 'Can lift up to 25 lbs',
                '3': 'Prefer non-physical care',
                'limited': 'Prefer non-physical care',
                'non-physical': 'Prefer non-physical care',
                '4': 'Companionship only',
                'companionship': 'Companionship only',
                'no lifting': 'Companionship only'
            }
            
            choice = self.parser.fuzzy_match(user_input, mobility_map, threshold=60)
            if choice:
                self.data['detailed_preferences']['mobility'] = choice
                self.data['pref_step'] = 'transportation'
                
                return """**Transportation**

Do you have reliable transportation?

[Yes - Own vehicle](#action:transport_vehicle)
[Yes - Public transit](#action:transport_transit)
[Need transportation assistance](#action:transport_need)"""
            else:
                return "Please select one of the options above."
        
        elif step == 'transportation':
            transport_map = {
                '1': 'Own vehicle',
                'yes': 'Own vehicle',
                'car': 'Own vehicle',
                'vehicle': 'Own vehicle',
                'own vehicle': 'Own vehicle',
                '2': 'Public transit',
                'public': 'Public transit',
                'transit': 'Public transit',
                'bus': 'Public transit',
                '3': 'Need assistance',
                'need': 'Need assistance',
                'no': 'Need assistance',
                'assistance': 'Need assistance'
            }
            
            choice = self.parser.fuzzy_match(user_input, transport_map, threshold=60)
            if choice:
                self.data['detailed_preferences']['transportation'] = choice
                self.data['pref_step'] = 'shift_preference'
                
                return """**Shift Preferences**

What shift types work best for you?

[Day shifts (8am-4pm)](#action:shift_day)
[Evening shifts (4pm-12am)](#action:shift_evening)
[Night shifts (12am-8am)](#action:shift_night)
[Live-in care](#action:shift_livein)
[Flexible - Any shift](#action:shift_flexible)

You can select multiple or type your preferences."""
            else:
                return "Please select one of the options above."
        
        elif step == 'shift_preference':
            shift_map = {
                '1': 'Day shifts',
                'day': 'Day shifts',
                'days': 'Day shifts',
                'morning': 'Day shifts',
                'day shifts': 'Day shifts',
                '2': 'Evening shifts',
                'evening': 'Evening shifts',
                'evenings': 'Evening shifts',
                'evening shifts': 'Evening shifts',
                '3': 'Night shifts',
                'night': 'Night shifts',
                'nights': 'Night shifts',
                'overnight': 'Night shifts',
                'night shifts': 'Night shifts',
                '4': 'Live-in care',
                'live-in': 'Live-in care',
                'live in': 'Live-in care',
                'livein': 'Live-in care',
                '5': 'Flexible',
                'flexible': 'Flexible',
                'any': 'Flexible',
                'all': 'Flexible',
                'any shift': 'Flexible'
            }
            
            shifts = []
            items = re.split(r'[,\s]+', user_input.strip())
            
            for item in items:
                if item:
                    shift = self.parser.fuzzy_match(item, shift_map, threshold=60)
                    if shift and shift not in shifts:
                        shifts.append(shift)
            
            if shifts:
                self.data['detailed_preferences']['shift_preferences'] = shifts
                self.data['pref_step'] = 'special_care'
                
                shifts_str = ', '.join(shifts)
                return f"""**Shifts:** {shifts_str}

**Special Care Experience**

Do you have experience with any of these conditions?

[Dementia/Alzheimer's](#action:care_dementia)
[Diabetes management](#action:care_diabetes)
[Hospice/End-of-life care](#action:care_hospice)
[Post-surgical care](#action:care_surgery)
[Stroke recovery](#action:care_stroke)
[None of the above](#action:care_none)

Select multiple or type your experience."""
            else:
                return "Please select at least one shift preference from the options above."
        
        elif step == 'special_care':
            if 'none' in user_input.lower() or 'none of the above' in user_input.lower():
                self.data['detailed_preferences']['special_care'] = ['General care']
            else:
                care_map = {
                    '1': "Dementia/Alzheimer's",
                    'dementia': "Dementia/Alzheimer's",
                    'alzheimer': "Dementia/Alzheimer's",
                    "alzheimer's": "Dementia/Alzheimer's",
                    '2': 'Diabetes management',
                    'diabetes': 'Diabetes management',
                    '3': 'Hospice care',
                    'hospice': 'Hospice care',
                    'end-of-life': 'Hospice care',
                    '4': 'Post-surgical care',
                    'post-surgical': 'Post-surgical care',
                    'surgery': 'Post-surgical care',
                    'surgical': 'Post-surgical care',
                    '5': 'Stroke recovery',
                    'stroke': 'Stroke recovery',
                    '6': 'None',
                    'none': 'General care'
                }
                
                care_types = []
                items = re.split(r'[,\s]+', user_input.strip())
                
                for item in items:
                    if item:
                        care = self.parser.fuzzy_match(item, care_map, threshold=60)
                        if care and care not in care_types:
                            care_types.append(care)
                
                self.data['detailed_preferences']['special_care'] = care_types if care_types else ['General care']
            
            self.data['pref_step'] = 'dietary'
            
            care_str = ', '.join(self.data['detailed_preferences']['special_care'])
            return f"""**Experience:** {care_str}

**Dietary Accommodations**

Are you comfortable preparing meals following special diets?

[Yes - All dietary restrictions](#action:diet_all)
[Yes - Basic restrictions only](#action:diet_basic)
[Prefer no meal preparation](#action:diet_none)"""
        
        elif step == 'dietary':
            dietary_map = {
                '1': 'All dietary restrictions',
                'yes': 'All dietary restrictions',
                'all': 'All dietary restrictions',
                'all dietary': 'All dietary restrictions',
                '2': 'Basic restrictions',
                'basic': 'Basic restrictions',
                '3': 'No meal prep',
                'no': 'No meal prep',
                'prefer not': 'No meal prep',
                'no meal': 'No meal prep'
            }
            
            choice = self.parser.fuzzy_match(user_input, dietary_map, threshold=60)
            if choice:
                self.data['detailed_preferences']['dietary'] = choice
                
                self.data['preferences_complete'] = True
                self.db.update_user(self.data['contact'], {
                    'detailed_preferences': self.data['detailed_preferences'],
                    'preferences_complete': True,
                    'dealbreakers': self.data.get('dealbreakers', [])
                })
                
                del self.data['pref_step']
                
                self.state = State.SERVICE_MENU
                # self.audit_logger.track_preference_completion(
                #     session_id='current_session',  # Pass from handler
                #     phone=self.data['contact'],
                #     preferences=self.data['detailed_preferences']
                # )
                
                prefs = self.data['detailed_preferences']
                summary = f"""**Preferences Saved**

**Your Complete Profile:**

**Environment:**
- Pets: {prefs.get('pets', 'Not specified')}
- Household: {prefs.get('household_activity', 'Not specified')}

**Skills:**
- Languages: {', '.join(prefs.get('languages', ['English']))}
- Mobility: {prefs.get('mobility', 'Not specified')}
- Special Care: {', '.join(prefs.get('special_care', ['General care']))}
- Dietary: {prefs.get('dietary', 'Not specified')}

**Logistics:**
- Transportation: {prefs.get('transportation', 'Not specified')}
- Shifts: {', '.join(prefs.get('shift_preferences', ['Not specified']))}

These preferences will help us match you with the best opportunities!

[Return to menu](#action:menu)"""
                
                return summary
            else:
                return "Please select one of the options above."
        
        return "[Return to menu](#action:menu)"
    
    def update_availability(self) -> str:
        """Update availability"""
        return """**Update Availability**

When are you available to work?

Examples:
- Weekdays
- Monday, Wednesday, Friday 9am-5pm
- Nights
- Flexible

Type your availability or [cancel](#action:menu)"""
    
    def view_applications(self) -> str:
        """View job applications"""
        stats = self.db.get_user_stats(self.data['contact'])
        
        return f"""**Your Applications**

- Total Applications: {stats.get('total_applications', 0)}
- Pending Review: {stats.get('pending', 0)}
- Interviews Scheduled: {stats.get('interviews', 0)}
- Profile Views: {stats.get('profile_views', 0)}

[Return to menu](#action:menu)"""
    
    def reset(self):
        """Reset bot state"""
        contact = self.data.get('contact')
        self.state = State.START
        self.data = {}
        if contact:
            self.data['contact'] = contact
        logger.info("Bot reset")