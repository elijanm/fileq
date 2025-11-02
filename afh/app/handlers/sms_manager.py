import json
from typing import Dict, Tuple, Optional
from handlers.validator import ResponseValidator  
from utils.util import logger
class SMSConversationState:
    """Track SMS conversation state"""
    def __init__(self, db_handler):
        self.db = db_handler
    
    def get_state(self, phone: str) -> Dict:
        """Get current conversation state for phone number"""
        if not self.db:
            return {'step': 'new', 'role': None, 'questions_asked': 0}
        
        user = self.db.find_user_by_contact(phone)
        if not user:
            return {'step': 'new', 'role': None, 'questions_asked': 0}
        
        return {
            'step': user.get('sms_step', 'new'),
            'role': user.get('role'),
            'questions_asked': user.get('sms_questions_asked', 0)
        }
    
    def update_state(self, phone: str, step: str, increment_questions: bool = True):
        """Update conversation state"""
        if not self.db:
            logger.warning("Database not available for state update")
            return False
        
        try:
            update_data = {'sms_step': step}
            
            if increment_questions:
                user = self.db.find_user_by_contact(phone)
                current = user.get('sms_questions_asked', 0) if user else 0
                update_data['sms_questions_asked'] = current + 1
            
            return self.db.update_user(phone, update_data)
        except Exception as e:
            logger.error(f"Error updating state: {e}")
            return False

        
class SMSConversationManager:
    """Manages SMS conversation flow based on intent"""
    
    def __init__(self, db_handler):
        self.db = db_handler
        self.state_manager = SMSConversationState(db_handler)
        self.validator = ResponseValidator()
    
    
    async def handle_sms_conversation(
        self,
        phone: str, 
        message: str, 
        session_id: str, 
        state: Dict, 
        intent: Dict,
        user_data: Dict
    ) -> str:
        """Handle SMS conversation flow"""
        
        current_step = state['step']
        role = state['role']
        questions_asked = state['questions_asked']
        
        # New user - determine if SMS or browser
        if current_step == 'new':
            return self.handle_new_user(phone, message, session_id, intent)
        
        # Role selection step
        elif current_step == 'role_selection':
            return self.handle_role_selection(phone, message, session_id)
        
        # Role-specific flows
        elif role == 'caregiver':
            return self.handle_caregiver_flow(phone, message, session_id, questions_asked, intent)
        
        elif role == 'afh_provider':
            return self.handle_afh_flow(phone, message, session_id, questions_asked, intent)
        
        elif role == 'service_provider':
            return self.handle_service_flow(phone, message, session_id, questions_asked, intent)
        
        # Default
        else:
            url = f"https://afhsync.com/chat/{session_id}"
            return f"Continue here:\n{url}"


    def handle_new_user( self,phone: str, message: str, session_id: str, intent: Dict) -> str:
        """Handle brand new user"""
        role_detected = intent.get('role_detected', 'none')
        best_channel = intent.get('best_channel', 'sms')
        
        # If complex or needs browser immediately
        if best_channel == 'browser' or intent.get('complexity') == 'complex':
            url = f"https://afhsync.com/chat/{session_id}"
            self.state_manager.update_state(phone, 'browser_redirect', False)
            return f"👋 Welcome to AFHSync!\n\nContinue here for full features:\n{url}"
        
        # If clear role detected
        if role_detected != 'none':
            self.db.update_user(phone, {'role': role_detected})
            self.state_manager.update_state(phone, 'collecting_info')
            return self.get_first_question_for_role(role_detected)
        
        # Ask for role
        self.state_manager.update_state(phone, 'role_selection')
        return "👋 Welcome to AFHSync!\n\nAre you a:\n1️⃣ Caregiver\n2️⃣ AFH Owner\n3️⃣ Service Provider\n\nReply with number"


    def handle_role_selection( self,phone: str, message: str, session_id: str) -> str:
        """Handle role selection"""
        role_map = {
            '1': 'caregiver', 'caregiver': 'caregiver',
            '2': 'afh_provider', 'afh': 'afh_provider', 'owner': 'afh_provider',
            '3': 'service_provider', 'service': 'service_provider'
        }
        
        role = None
        for key, value in role_map.items():
            if key in message.lower():
                role = value
                break
        
        if role:
            self.db.update_user(phone, {'role': role})
            self.state_manager.update_state(phone, 'collecting_info',True)
            return self.get_first_question_for_role(role)
        
        return "Please reply with 1, 2, or 3"


    def get_first_question_for_role( self,role: str) -> str:
        """Get first question based on role"""
        questions = {
            'caregiver': "Great! What city are you in?",
            'afh_provider': "Perfect! How many facilities do you own?",
            'service_provider': "Excellent! What service do you provide?"
        }
        return questions.get(role, "Let's get started!")

    def handle_caregiver_flow(
        self, 
        phone: str, 
        message: str, 
        session_id: str, 
        questions_asked: int,
        intent: Dict
    ) -> str:
        """Caregiver SMS flow with intelligent validation"""
        
        # Check if intent suggests they want to skip to browser
        if intent.get('best_channel') == 'browser' or intent.get('complexity') == 'complex':
            self.state_manager.update_state(phone, 'portal_ready', False)
            return self.generate_portal_handoff(session_id, 'caregiver')
        
        if questions_asked == 0:
            return "What city are you in?"
        
        elif questions_asked == 1:
            # Validate location
            valid, location_data = self.validator.validate_location(message)
            
            if not valid or location_data.get('needs_clarification'):
                return "I didn't catch that. What city are you in?\n\n(e.g., Seattle, Tacoma, Auburn)"
            
            # Save validated location
            self.db.update_user(phone, {
                'city': location_data.get('city'),
                'state': location_data.get('state', 'Washington'),
                'location_raw': message
            })
            self.state_manager.update_state(phone, 'collecting_info')
            
            return "What certifications do you have?\n\n(CNA, HCA, RN, CPR, or 'none')"
        
        elif questions_asked == 2:
            # Validate certifications
            valid, cert_data = self.validator.validate_certifications(message)
            
            if not valid or cert_data.get('needs_clarification'):
                return "Please list your certifications or type 'none'\n\n(e.g., CNA, CPR, First Aid)"
            
            # Save certifications
            self.db.update_user(phone, {
                'certifications': cert_data.get('certifications', []),
                'has_certifications': cert_data.get('has_certifications', False),
                'certifications_raw': message
            })
            self.state_manager.update_state(phone, 'collecting_info')
            
            return "When are you available?\n\n(weekdays, nights, weekends, flexible)"
        
        elif questions_asked == 3:
            # Validate availability
            valid, avail_data = self.validator.validate_availability(message)
            
            if not valid or avail_data.get('needs_clarification'):
                return "When can you work?\n\n(weekdays, nights, flexible, etc.)"
            
            # Save availability
            self.db.update_user(phone, {
                'availability_type': avail_data.get('availability_type'),
                'availability_details': avail_data.get('details'),
                'availability_raw': message
            })
            self.state_manager.update_state(phone, 'portal_ready', False)
            
            return self.generate_portal_handoff(session_id, 'caregiver')
        
        return self.generate_portal_handoff(session_id, 'caregiver')
    
    def handle_afh_flow(
        self, 
        phone: str, 
        message: str, 
        session_id: str, 
        questions_asked: int,
        intent: Dict
    ) -> str:
        """AFH Owner SMS flow with validation"""
        
        # Check intent for early browser redirect
        if intent.get('best_channel') == 'browser' or intent.get('complexity') == 'complex':
            self.state_manager.update_state(phone, 'portal_ready', False)
            return self.generate_portal_handoff(session_id, 'afh_provider')
        
        if questions_asked == 0:
            return "How many AFH facilities do you own?"
        
        elif questions_asked == 1:
            # Validate number
            valid, number = self.validator.validate_number(message, "facilities")
            
            if not valid:
                return "How many facilities?\n\n(Please respond with a number)"
            
            self.db.update_user(phone, {
                'number_of_facilities': number,
                'facilities_raw': message
            })
            self.state_manager.update_state(phone, 'collecting_info')
            
            return "Where is your primary facility located?"
        
        elif questions_asked == 2:
            # Validate location
            valid, location_data = self.validator.validate_location(message)
            
            if not valid or location_data.get('needs_clarification'):
                return "What city is your facility in?\n\n(e.g., Seattle, Bellevue)"
            
            self.db.update_user(phone, {
                'facility_city': location_data.get('city'),
                'facility_state': location_data.get('state', 'Washington'),
                'facility_location_raw': message
            })
            self.state_manager.update_state(phone, 'collecting_info')
            
            return "How many residents can you accommodate?"
        
        elif questions_asked == 3:
            # Validate capacity number
            valid, capacity = self.validator.validate_number(message, "residents")
            
            if not valid:
                return "How many residents?\n\n(Please respond with a number)"
            
            self.db.update_user(phone, {
                'capacity': capacity,
                'capacity_raw': message
            })
            self.state_manager.update_state(phone, 'portal_ready', False)
            
            return self.generate_portal_handoff(session_id, 'afh_provider')
        
        return self.generate_portal_handoff(session_id, 'afh_provider')
    
    def handle_service_flow(
        self, 
        phone: str, 
        message: str, 
        session_id: str, 
        questions_asked: int,
        intent: Dict
    ) -> str:
        """Service Provider SMS flow with validation"""
        
        # Check intent for early browser redirect
        if intent.get('best_channel') == 'browser' or intent.get('complexity') == 'complex':
            self.state_manager.update_state(phone, 'portal_ready', False)
            return self.generate_portal_handoff(session_id, 'service_provider')
        
        if questions_asked == 0:
            return "What service do you provide?\n\n(cleaning, staffing, supplies, maintenance, etc.)"
        
        elif questions_asked == 1:
            # Basic validation - accept any reasonable response
            if len(message.strip()) < 3:
                return "Please describe your service\n\n(e.g., cleaning, staffing, meal prep)"
            
            self.db.update_user(phone, {
                'service_type': message.strip(),
                'service_type_raw': message
            })
            self.state_manager.update_state(phone, 'collecting_info')
            
            return "What area do you serve?\n\n(e.g., King County, Seattle area)"
        
        elif questions_asked == 2:
            # Validate service area
            valid, location_data = self.validator.validate_location(message)
            
            if not valid:
                return "What area do you serve?\n\n(city, county, or region)"
            
            self.db.update_user(phone, {
                'service_area': location_data.get('city') if location_data else message,
                'service_area_raw': message
            })
            self.state_manager.update_state(phone, 'portal_ready', False)
            
            return self.generate_portal_handoff(session_id, 'service_provider')
        
        return self.generate_portal_handoff(session_id, 'service_provider')
    def generate_portal_handoff(self, session_id: str, role: str) -> str:
        """Generate portal handoff message"""
        url = f"https://afhsync.com/chat/{session_id}?context={role}"
        
        messages = {
            'caregiver': f"Great start!\n\nContinue here:\n{url}\n\nBrowse jobs, build resume, upload docs",
            'afh_provider': f"Thanks!\n\nComplete setup:\n{url}\n\nUpload photos, post jobs, browse caregivers",
            'service_provider': f"Perfect!\n\nFinish profile:\n{url}\n\nUpload brochures, set pricing, find clients"
        }
        
        return messages.get(role, f"Continue here:\n{url}")
    def determine_response(
        self, 
        phone: str, 
        message: str, 
        session_id: str, 
        intent: Dict,
        user_data: Optional[Dict] = None
    ) -> str:
        """Determine appropriate SMS response based on intent"""
        
        best_channel = intent.get('best_channel', 'sms')
        role_detected = intent.get('role_detected', 'none')
        needs_info = intent.get('needs_immediate_info', True)
        
        # New user - no profile yet
        if not user_data or not user_data.get('role'):
            
            # If clear role detected and low complexity, collect via SMS
            if role_detected != 'none' and intent.get('complexity') == 'simple':
                # Save role immediately
                self.db.update_user(phone, {
                    'role': role_detected,
                    'intent_detected': intent.get('intent_type')
                })
                
                return self._get_first_question(role_detected, session_id)
            
            # If complex or unclear, ask role then redirect
            elif best_channel == 'browser' or intent.get('complexity') == 'complex':
                return self._quick_role_then_browser(session_id)
            
            # Default: simple SMS role selection
            else:
                return "👋 Welcome to AFHSync!\n\nAre you a:\n1️⃣ Caregiver\n2️⃣ AFH Owner\n3️⃣ Service Provider\n\nReply with number or name"
        
        # Returning user with role
        else:
            role = user_data.get('role')
            
            # If they need complex features, redirect immediately
            if best_channel == 'browser' or intent.get('complexity') == 'complex':
                return self._browser_redirect(session_id, role, intent)
            
            # If simple request, handle via SMS
            else:
                return self._handle_returning_user_sms(role, intent, session_id)
    
    def _get_first_question(self, role: str, session_id: str) -> str:
        """Get first contextual question based on role"""
        questions = {
            'caregiver': "Great! 👩‍⚕️ What city are you in?",
            'afh_provider': "Perfect! 🏠 How many facilities do you own?",
            'service_provider': "Excellent! 🛠️ What type of service? (cleaning, staffing, supplies, etc.)"
        }
        
        return questions.get(role, self._quick_role_then_browser(session_id))
    
    def _quick_role_then_browser(self, session_id: str) -> str:
        """Ask role, then immediately redirect to browser"""
        url = f"https://afhsync.com/chat/{session_id}"
        return f"👋 Welcome to AFHSync!\n\nAre you a Caregiver, AFH Owner, or Service Provider?\n\nReply, then continue here:\n{url}"
    
    def _browser_redirect(self, session_id: str, role: str, intent: Dict) -> str:
        """Smart browser redirect with context"""
        url = f"https://afhsync.com/chat/{session_id}?context={role}"
        
        messages = {
            'caregiver': f"🔗 Continue in your portal:\n{url}\n\nYou can browse jobs, build your resume, and upload certifications there.",
            'afh_provider': f"🔗 Complete setup here:\n{url}\n\nYou can upload photos, post jobs, and browse caregivers.",
            'service_provider': f"🔗 Finish your profile:\n{url}\n\nUpload brochures, set pricing, and find AFH clients."
        }
        
        return messages.get(role, f"Continue here:\n{url}")
    
    def _handle_returning_user_sms(self, role: str, intent: Dict, session_id: str) -> str:
        """Handle returning user with simple SMS request"""
        intent_type = intent.get('intent_type')
        
        if intent_type == 'job_search' and role == 'caregiver':
            return "I'll show you matching jobs! 🔍\n\nWhat's your availability? (weekdays, nights, flexible, etc.)"
        
        elif intent_type == 'hire_caregiver' and role == 'afh_provider':
            return "Let's post your job! 📋\n\nWhat position? (CNA, HCA, companion, etc.)"
        
        else:
            # Default to browser for anything complex
            return self._browser_redirect(session_id, role, intent)

