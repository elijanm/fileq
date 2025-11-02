"""
Intelligent Message Handler - Production-Ready with Audit Logging
Complete implementation with analytics, token tracking, and audit trails
"""

import logging
import requests
import json
import re
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import os
from pymongo import MongoClient

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://95.110.228.29:8201/v1')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'deepseek-r1:1.5b')
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:password@95.110.228.29:8711/admin?authSource=admin')
DB_NAME = os.getenv('DB_NAME', 'afhsync')



class AuditLogger:
    """Centralized audit logging for all SMS and responses"""
    
    def __init__(self):
        try:
            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            self.db = client[DB_NAME]
            self.audit_collection = self.db['audit_logs']
            self.token_collection = self.db['token_usage']
            
            # Create indexes for efficient querying
            self.audit_collection.create_index('phone')
            self.audit_collection.create_index('timestamp')
            self.audit_collection.create_index('session_id')
            self.token_collection.create_index('timestamp')
            
            self.journey_collection = self.db['user_journeys']
            self.journey_collection.create_index('session_id')
            self.journey_collection.create_index('phone')
            self.journey_collection.create_index([('timestamp', -1)])
            
            logger.info("Audit logger initialized")
        except Exception as e:
            logger.error(f"Audit logger initialization failed: {e}")
            self.db = None
    def track_event(self, session_id: str, phone: str, event_type: str, 
                   event_data: Dict, metadata: Dict = None):
        """Track any user journey event"""
        if  self.db is None:
            return
        
        try:
            event_record = {
                'session_id': session_id,
                'phone': phone,
                'event_type': event_type,  # 'state_change', 'preference_set', 'job_viewed', etc.
                'event_data': event_data,
                'metadata': metadata or {},
                'timestamp': datetime.utcnow()
            }
            
            self.journey_collection.insert_one(event_record)
            logger.info(f"Journey tracked: {event_type} for {phone}")
        except Exception as e:
            logger.error(f"Journey tracking failed: {e}")
    
    def track_state_transition(self, session_id: str, phone: str, 
                               from_state: str, to_state: str, trigger: str):
        """Track state machine transitions"""
        self.track_event(
            session_id=session_id,
            phone=phone,
            event_type='state_transition',
            event_data={
                'from_state': from_state,
                'to_state': to_state,
                'trigger': trigger
            }
        )
    
    def track_preference_completion(self, session_id: str, phone: str, 
                                   preferences: Dict):
        """Track when user completes preferences"""
        self.track_event(
            session_id=session_id,
            phone=phone,
            event_type='preferences_completed',
            event_data=preferences
        )
    
    def track_drop_off(self, session_id: str, phone: str, state: str, 
                      last_input: str):
        """Track where users abandon the flow"""
        self.track_event(
            session_id=session_id,
            phone=phone,
            event_type='drop_off',
            event_data={
                'abandoned_at_state': state,
                'last_input': last_input
            }
        )
    
    def get_journey_funnel(self, start_date: datetime = None) -> Dict:
        """Get conversion funnel analytics"""
        if  self.db is None:
            return {}
        
        try:
            pipeline = [
                {'$match': {'timestamp': {'$gte': start_date or datetime.utcnow()}}},
                {'$group': {
                    '_id': '$event_type',
                    'count': {'$sum': 1}
                }}
            ]
            
            results = list(self.journey_collection.aggregate(pipeline))
            return {r['_id']: r['count'] for r in results}
        except Exception as e:
            logger.error(f"Funnel analytics failed: {e}")
            return {}
       
    def log_sms(self, phone: str, direction: str, message: str, session_id: str, metadata: Dict = None):
        """Log all SMS messages (inbound and outbound)"""
        if self.db is None:
            return
        
        try:
            self.audit_collection.insert_one({
                'type': 'sms',
                'phone': phone,
                'direction': direction,  # 'inbound' or 'outbound'
                'message': message,
                'session_id': session_id,
                'timestamp': datetime.utcnow(),
                'metadata': metadata or {}
            })
        except Exception as e:
            logger.error(f"SMS audit logging failed: {e}")
    
    def log_ollama_request(self, prompt: str, response: str, model: str, tokens_used: int, 
                          duration_ms: float, session_id: str, success: bool = True):
        """Log Ollama API usage with token tracking"""
        if self.db is None:
            return
        
        try:
            self.token_collection.insert_one({
                'type': 'ollama_request',
                'model': model,
                'prompt': prompt,
                'response': response,
                'tokens_used': tokens_used,
                'duration_ms': duration_ms,
                'session_id': session_id,
                'success': success,
                'timestamp': datetime.utcnow()
            })
        except Exception as e:
            logger.error(f"Ollama audit logging failed: {e}")
    
    def log_user_action(self, phone: str, action: str, state_before: str, state_after: str, 
                       session_id: str, metadata: Dict = None):
        """Log user actions for journey analytics"""
        if self.db is None:
            return
        
        try:
            self.audit_collection.insert_one({
                'type': 'user_action',
                'phone': phone,
                'action': action,
                'state_before': state_before,
                'state_after': state_after,
                'session_id': session_id,
                'timestamp': datetime.utcnow(),
                'metadata': metadata or {}
            })
        except Exception as e:
            logger.error(f"Action audit logging failed: {e}")
    
    def get_session_audit_trail(self, session_id: str) -> List[Dict]:
        """Get complete audit trail for a session"""
        if self.db is None:
            return []
        
        try:
            return list(self.audit_collection.find(
                {'session_id': session_id}
            ).sort('timestamp', 1))
        except Exception as e:
            logger.error(f"Audit trail retrieval failed: {e}")
            return []
    
    def get_token_usage_stats(self, start_date: datetime = None, end_date: datetime = None) -> Dict:
        """Get token usage statistics"""
        if self.db is None:
            return {}
        
        try:
            query = {}
            if start_date and end_date:
                query['timestamp'] = {'$gte': start_date, '$lte': end_date}
            
            pipeline = [
                {'$match': query},
                {'$group': {
                    '_id': None,
                    'total_requests': {'$sum': 1},
                    'total_tokens': {'$sum': '$tokens_used'},
                    'avg_tokens': {'$avg': '$tokens_used'},
                    'avg_duration_ms': {'$avg': '$duration_ms'},
                    'failed_requests': {'$sum': {'$cond': [{'$eq': ['$success', False]}, 1, 0]}}
                }}
            ]
            
            result = list(self.token_collection.aggregate(pipeline))
            return result[0] if result else {}
        except Exception as e:
            logger.error(f"Token stats retrieval failed: {e}")
            return {}


class OllamaCircuitBreaker:
    """Circuit breaker pattern for Ollama API reliability"""
    
    def __init__(self, failure_threshold: int = 3, timeout_seconds: int = 60):
        self.failures = 0
        self.last_failure = None
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
    
    def should_skip(self) -> bool:
        """Check if we should skip Ollama due to repeated failures"""
        if self.failures >= self.failure_threshold:
            if self.last_failure:
                elapsed = (datetime.now() - self.last_failure).total_seconds()
                if elapsed < self.timeout_seconds:
                    logger.warning(f"Circuit breaker open - skipping Ollama (failures: {self.failures})")
                    return True
                else:
                    # Timeout passed, reset
                    self.failures = 0
                    self.last_failure = None
        return False
    
    def record_failure(self):
        """Record a failure"""
        self.failures += 1
        self.last_failure = datetime.now()
    
    def record_success(self):
        """Record a success - resets counter"""
        self.failures = 0
        self.last_failure = None


class RoleBasedKnowledge:
    """Knowledge base for different user roles"""
    
    ROLE_SERVICES = {
        'caregiver': {
            'name': 'Caregiver',
            'keywords': ['job', 'work', 'resume', 'cv', 'hiring', 'position', 'apply', 'certification']
        },
        'afh_provider': {
            'name': 'AFH Provider',
            'keywords': ['hire', 'post job', 'find caregiver', 'staffing', 'employee', 'licensing', 'facility']
        },
        'service_provider': {
            'name': 'Service Provider',
            'keywords': ['service', 'provider', 'vendor', 'contractor', 'supplies', 'equipment', 'maintenance']
        }
    }
    
    GENERAL_TOPICS = {
        'greeting': ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'greetings', 'howdy'],
        'help': ['help', 'what can you do', 'commands', 'options', 'menu', 'services', 'features'],
        'farewell': ['bye', 'goodbye', 'see you', 'later', 'thanks', 'thank you']
    }
    
    @classmethod
    def detect_role_intent(cls, text: str) -> Optional[str]:
        """Detect which role the user might be interested in"""
        text_lower = text.lower().strip()
        
        # Direct role matches
        if text_lower in ['caregiver', 'carer', 'care giver', '1']:
            return 'caregiver'
        if text_lower in ['afh', 'afh provider', 'provider', 'facility owner', '2']:
            return 'afh_provider'
        if text_lower in ['service provider', 'service', 'vendor', '3']:
            return 'service_provider'
        
        # Keyword matching
        for role, info in cls.ROLE_SERVICES.items():
            for keyword in info['keywords']:
                if keyword in text_lower:
                    return role
        
        return None


class IntentClassifier:
    """Lightweight intent classification with optional AI fallback"""
    
    circuit_breaker = OllamaCircuitBreaker()
    audit_logger = AuditLogger()
    
    @staticmethod
    def classify_with_context(user_input: str, current_role: Optional[str] = None, 
                             session_id: str = None) -> Tuple[str, float]:
        """Classify user intent - keyword first, AI only if needed"""
        user_lower = user_input.lower().strip()
        
        # Quick keyword checks (covers 90% of cases)
        for intent, keywords in RoleBasedKnowledge.GENERAL_TOPICS.items():
            for keyword in keywords:
                if keyword in user_lower:
                    return intent, 0.95
        
        # Service request keywords
        service_keywords = {
            'browse': 'service_request',
            'job': 'service_request',
            'resume': 'service_request',
            'preference': 'service_request',
            'preferences': 'service_request',
            'upload': 'service_request',
            'availability': 'service_request',
            'application': 'service_request',
            'menu': 'navigation',
            'back': 'navigation',
        }
        
        for keyword, intent in service_keywords.items():
            if keyword in user_lower:
                return intent, 0.9
        
        # Number selections
        if user_input.strip().isdigit():
            return 'menu_selection', 0.95
        
        # Role detection
        detected_role = RoleBasedKnowledge.detect_role_intent(user_input)
        if detected_role:
            return f'role_specific_{detected_role}', 0.85
        
        # Only use AI for truly ambiguous inputs
        if len(user_input) < 3:
            return 'unclear', 0.3
        
        # Check circuit breaker before calling AI
        if IntentClassifier.circuit_breaker.should_skip():
            return 'unclear', 0.4
        
        # AI classification as fallback
        return IntentClassifier._ai_classify(user_input, current_role, session_id)
    
    @staticmethod
    def _ai_classify(user_input: str, current_role: Optional[str], session_id: str) -> Tuple[str, float]:
        """Use Ollama for complex classification with full audit logging"""
        start_time = datetime.now()
        
        try:
            role_context = f"User is a {current_role}" if current_role else "User role unknown"
            
            prompt = f"""Classify intent for AFHSync platform.

{role_context}
User message: "{user_input}"

Return: intent|confidence
Options: greeting|help|farewell|service_request|job_search|unclear
Example: service_request|0.9"""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 50
                },
                timeout=5
            )
            
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                
                # Extract token usage
                tokens_used = result.get('usage', {}).get('total_tokens', 0)
                
                # Log successful request
                IntentClassifier.audit_logger.log_ollama_request(
                    prompt=prompt,
                    response=content,
                    model=OLLAMA_MODEL,
                    tokens_used=tokens_used,
                    duration_ms=duration_ms,
                    session_id=session_id or 'unknown',
                    success=True
                )
                
                # Reset circuit breaker on success
                IntentClassifier.circuit_breaker.record_success()
                
                if '|' in content:
                    intent, conf = content.split('|')
                    return intent.strip(), float(conf.strip())
            else:
                # Log failed request
                IntentClassifier.audit_logger.log_ollama_request(
                    prompt=prompt,
                    response=f"HTTP {response.status_code}",
                    model=OLLAMA_MODEL,
                    tokens_used=0,
                    duration_ms=duration_ms,
                    session_id=session_id or 'unknown',
                    success=False
                )
                IntentClassifier.circuit_breaker.record_failure()
            
        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"AI classification error: {e}")
            
            # Log exception
            IntentClassifier.audit_logger.log_ollama_request(
                prompt=prompt if 'prompt' in locals() else 'N/A',
                response=str(e),
                model=OLLAMA_MODEL,
                tokens_used=0,
                duration_ms=duration_ms,
                session_id=session_id or 'unknown',
                success=False
            )
            IntentClassifier.circuit_breaker.record_failure()
        
        return 'unclear', 0.3


class IntelligentMessageHandler:
    """Production-ready message handler with full audit trail"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.conversation_history = []
        self.audit_logger = AuditLogger()
        self.session_id = None
        self.provider_handler=None
    
    def process_with_intelligence(self, user_input: str, bot_state: str, 
                                 user_role: Optional[str] = None, 
                                 session_id: str = None) -> str:
        """Process user input with intelligent routing and audit logging"""
        
        self.session_id = session_id
        state_before = bot_state
        logger.info(f"=== HANDLER INPUT === State: '{bot_state}', Input: '{user_input}', Role: {user_role}")
        bot_state_upper = bot_state.upper()
        # Get role from bot data if not provided
        if not user_role and self.bot.data.get('role'):
            user_role = self.bot.data.get('role')
        
        # Check for established context
        has_context = any([
            self.bot.data.get('city'),
            self.bot.data.get('certifications'),
            self.bot.data.get('role')
        ])
        
        # Force SERVICE_MENU if profile is complete but state is START
        if (self.bot.data.get('profile_complete') or 
            self.bot.data.get('sms_step') == 'portal_ready'):
            if bot_state_upper in ['START', 'ROLE_SELECTION']:
                bot_state_upper = 'SERVICE_MENU'
                self.bot.state = self.bot.state.__class__['SERVICE_MENU']
        
        # States requiring direct bot handling
        DIRECT_PASS_STATES = [
            'ASK_CONTACT', 'ASK_NAME', 'ASK_GENDER', 'ASK_LOCATION', 
            'ASK_MORE_CITIES', 'ASK_AVAILABILITY', 'ASK_CREDENTIALS',
            'ASK_MORE_CREDENTIALS', 'ASK_BASIC_PREFERENCES', 'ASK_UPLOAD',
            'ASK_NOTIFICATION', 'ASK_MISSING_CONTACT', 'DETAILED_PREFERENCES'
        ]
        
        if bot_state_upper in DIRECT_PASS_STATES:
            logger.info(f"Direct pass to bot - State: {bot_state_upper}")
            response = self.bot.process_message(user_input)
            self._log_interaction(user_input, response, bot_state_upper, self.bot.state.value, user_role)
            return response
        
        # Special state handling
        if bot_state_upper == 'BROWSE_JOBS':
            response = self.bot.handle_browse_jobs(user_input)
            self._log_interaction(user_input, response, bot_state_upper, self.bot.state.value, user_role)
            return response
        
        if bot_state_upper == 'RESUME_SERVICE':
            response = self.bot.resume_service.handle_resume_flow(user_input, self.bot.data)
            self._log_interaction(user_input, response, bot_state_upper, self.bot.state.value, user_role)
            return response
        
        # Handle service requests for users with context
        if has_context and user_role:
            response = self._handle_service_request(user_input, user_role, bot_state_upper)
            self._log_interaction(user_input, response, state_before, self.bot.state.value, user_role)
            return response
        
        # Classify intent for new/unclear users
        intent, confidence = IntentClassifier.classify_with_context(
            user_input, user_role, session_id
        )
        
        logger.info(f"Intent: {intent}, Confidence: {confidence}, Role: {user_role}, State: {bot_state_upper}")
        
        # Add to conversation history
        self.conversation_history.append({
            'input': user_input,
            'intent': intent,
            'confidence': confidence,
            'role': user_role,
            'state': bot_state_upper,
            'timestamp': datetime.now().isoformat()
        })
        
        # Route based on intent
        if intent == 'greeting':
            response = self._handle_greeting(bot_state_upper, user_role)
        elif intent == 'help':
            response = self._handle_help_request(bot_state_upper, user_role)
        elif intent == 'navigation':
            if 'menu' in user_input.lower():
                self.bot.state = self.bot.state.__class__['SERVICE_MENU']
                response = self._show_service_menu(user_role)
            else:
                response = self._show_service_menu(user_role)
        elif intent == 'farewell':
            response = self._handle_farewell()
        elif intent == 'service_request':
            response = self._handle_service_request(user_input, user_role, bot_state_upper)
        elif confidence < 0.4:
            response = self._handle_unclear(user_input, bot_state_upper, user_role)
        else:
            response = self.bot.process_message(user_input)
        
        self._log_interaction(user_input, response, state_before, self.bot.state.value, user_role)
        return response
    
    def _log_interaction(self, user_input: str, bot_response: str, 
                        state_before: str, state_after: str, user_role: Optional[str]):
        """Log complete interaction for audit"""
        phone = self.bot.data.get('contact', 'unknown')
        
        self.audit_logger.log_user_action(
            phone=phone,
            action='message_exchange',
            state_before=state_before,
            state_after=state_after,
            session_id=self.session_id or 'unknown',
            metadata={
                'user_input': user_input,
                'bot_response': bot_response[:200],  # Truncate for storage
                'user_role': user_role,
                'input_length': len(user_input),
                'response_length': len(bot_response)
            }
        )
        
        
        # Journey tracking - state transitions
        if state_before != state_after:
            self.audit_logger.track_state_transition(
                session_id=self.session_id or 'unknown',
                phone=phone,
                from_state=state_before,
                to_state=state_after,
                trigger=user_input[:50]
            )
    
    def _handle_service_request(self, user_input: str, user_role: str, bot_state: str) -> str:
        """Handle service requests from users with established profiles"""
        user_lower = user_input.lower().strip()
        print(user_lower,"JKKKK")
        if user_role == 'caregiver':
            if any(word in user_lower for word in ['browse', 'job', 'opening', 'find', 'search', '1']):
                self.bot.state = self.bot.state.__class__['BROWSE_JOBS']
                return self.bot.browse_jobs()
            
            elif any(word in user_lower for word in ['resume', 'cv', 'build', '2']):
                self.bot.state = self.bot.state.__class__['RESUME_SERVICE']
                return self.bot.resume_service.start_resume_service(self.bot.data)
            
            elif any(word in user_lower for word in ['preference', 'preferences', 'complete', 'profile', 'detail', '3']):
                self.bot.state = self.bot.state.__class__['DETAILED_PREFERENCES']
                return self.bot.start_detailed_preferences()
            
            elif any(word in user_lower for word in ['upload', 'certification', 'document', '4']):
                contact = self.bot.data.get('contact', 'user')
                return f"""**Upload Certifications**

Upload your certification documents here:
[Upload Documents](#action:upload_docs)

Or visit: https://afhsync.com/upload/{contact}

[Return to Menu](#action:menu)"""
            
            elif any(word in user_lower for word in ['availability', 'schedule', 'update', '5']):
                return self.bot.update_availability()
            
            elif any(word in user_lower for word in ['application', 'view', 'applied', '6']):
                return self.bot.view_applications()
            
            elif 'menu' in user_lower:
                self.bot.state = self.bot.state.__class__['SERVICE_MENU']
                return self._show_service_menu(user_role)
            
            else:
                return self._show_service_menu(user_role)
        
        elif user_role == 'afh_provider':
            from handlers.afh_ import AFHProviderHandler
            if self.provider_handler is None:
                self.provider_handler = AFHProviderHandler(self.bot, self.bot.db)
            return self.provider_handler.handle_provider_services(user_input, self.bot.data)
        
            if any(word in user_lower for word in ['post', 'job', 'opening', 'hire', '1']):
                return """**Post Job Opening**

Let's create your job posting.

What position are you hiring for?

**Common positions:**
[CNA](#action:post_cna)
[HCA](#action:post_hca)
[Companion Care](#action:post_companion)
[Live-in Caregiver](#action:post_livein)

Or type the position name."""
            
            elif any(word in user_lower for word in ['browse', 'caregiver', 'find', '2','filter']):
                return """**Browse Caregivers**

I'll show you qualified caregivers in your area.

What certifications are required?

[CNA Required](#action:filter_cna)
[HCA Required](#action:filter_hca)
[Any Certification](#action:filter_any)
[No Requirements](#action:filter_none)"""
            
            elif any(word in user_lower for word in ['upload', 'photo', 'picture', '3']):
                contact = self.bot.data.get('contact', 'user')
                return f"""**Upload Facility Photos**

Upload facility photos here:
[Upload Photos](#action:upload_photos)

Or visit: https://afhsync.com/upload/{contact}

[Return to Menu](#action:menu)"""
            
            elif 'menu' in user_lower:
                return self._show_service_menu(user_role)
            
            else:
                return self._show_service_menu(user_role)
        
        elif user_role == 'service_provider':
            if any(word in user_lower for word in ['browse', 'request', 'find', '1']):
                return """**Browse AFH Requests**

Searching for service requests in your area...

[Active Requests](#action:active_requests)
[Recent Requests](#action:recent_requests)
[All Requests](#action:all_requests)

[Return to Menu](#action:menu)"""
            
            elif any(word in user_lower for word in ['upload', 'brochure', 'document', '2']):
                contact = self.bot.data.get('contact', 'user')
                return f"""**Upload Service Materials**

Upload your brochures and materials:
[Upload Brochures](#action:upload_brochures)

Or visit: https://afhsync.com/upload/{contact}

[Return to Menu](#action:menu)"""
            
            elif 'menu' in user_lower:
                return self._show_service_menu(user_role)
            
            else:
                return self._show_service_menu(user_role)
        
        return self._show_service_menu(user_role)
    
    def _show_service_menu(self, user_role: Optional[str]) -> str:
        """Show role-specific service menu with links"""
        
        if user_role == 'caregiver':
            pref_complete = self.bot.data.get('preferences_complete', False)
            reminder = "" if pref_complete else "\nComplete your preferences for better job matches.\n"
            
            return f"""**Caregiver Services**

What would you like to do?

[Browse job openings](#action:browse_jobs)
[Build your resume](#action:resume_builder)
[Complete job preferences](#action:complete_profile)
[Upload certifications](#action:upload_certs)
[Update availability](#action:update_availability)
[View applications](#action:view_applications)
{reminder}
Click a link or type your choice."""
        
        elif user_role == 'afh_provider':
            return """**AFH Provider Services**

How can I help you today?

[Post job opening](#action:post_job)
[Browse caregivers](#action:browse_caregivers)
[Upload facility photos](#action:upload_photos)
[Manage job postings](#action:manage_postings)
[Review applications](#action:review_applications)

Click a link or type your choice."""
        
        elif user_role == 'service_provider':
            return """**Service Provider Services**

What would you like to do?

[List your services](#action:list_services)
[Browse AFH requests](#action:browse_requests)
[Upload brochures](#action:upload_brochures)
[Manage offerings](#action:manage_offerings)
[Update pricing](#action:update_pricing)

Click a link or type your choice."""
        
        else:
            return """**Welcome to AFHSync**

I see we're still setting up. Are you a:

[Caregiver](#action:select_role_caregiver) - Looking for jobs
[AFH Owner](#action:select_role_afh) - Hiring caregivers
[Service Provider](#action:select_role_service) - Offering services

Please select your role to continue."""
    
    def _handle_greeting(self, bot_state: str, user_role: Optional[str]) -> str:
        """Handle greetings"""
        if not user_role:
            return """Hello! Welcome to AFHSync.

Are you a:

[Caregiver](#action:select_role_caregiver)
[AFH Owner](#action:select_role_afh)
[Service Provider](#action:select_role_service)

Select your role to get started."""
        
        return f"Hello! {self._show_service_menu(user_role)}"
    
    def _handle_help_request(self, bot_state: str, user_role: Optional[str]) -> str:
        """Provide help"""
        return self._show_service_menu(user_role)
    
    def _handle_unclear(self, user_input: str, bot_state: str, user_role: Optional[str]) -> str:
        """Handle unclear input with context-aware guidance"""
        if user_role:
            return f"""I'm not sure I understood that.

{self._show_service_menu(user_role)}"""
        
        if bot_state in ['ROLE_SELECTION', 'START']:
            return """I'm not quite sure what you're asking for.

I help three types of users on AFHSync:

[Caregiver](#action:select_role_caregiver) - Find jobs and build careers
[AFH Owner](#action:select_role_afh) - Hire qualified caregivers
[Service Provider](#action:select_role_service) - Offer services to facilities

Which one are you?"""
        
        return """I didn't quite understand that.

[Show menu](#action:menu)
[Get help](#action:help)

Or try rephrasing your request."""
    
    def _handle_farewell(self) -> str:
        """Handle goodbye messages"""
        return """Thank you for using AFHSync!

Feel free to return anytime. Your session will remain active for easy access.

Take care!"""
    
    def _provide_context_help(self, bot_state: str, user_role: Optional[str]) -> str:
        """Provide contextual help based on current state"""
        help_map = {
            'ROLE_SELECTION': """**Choose your role:**

[Caregiver](#action:select_role_caregiver) - Looking for caregiving jobs
[AFH Owner](#action:select_role_afh) - Need to hire caregivers
[Service Provider](#action:select_role_service) - Offering services to facilities

Click a link or type 1, 2, or 3.""",
            
            'ASK_CONTACT': "Please provide your phone number or email address.",
            'ASK_NAME': "What's your full name?",
            'ASK_LOCATION': "Which city are you located in? (e.g., Seattle, Auburn, Tacoma)",
            'ASK_AVAILABILITY': "When are you available to work? (e.g., weekdays, nights, flexible)",
            'SERVICE_MENU': self._show_service_menu(user_role),
            
            'BROWSE_JOBS': """**Job Browsing:**

Type a job number (1-5) to see details
[Show more jobs](#action:more_jobs)
[Refine preferences](#action:complete_profile)
[Return to menu](#action:menu)"""
        }
        
        help_text = help_map.get(bot_state)
        if help_text:
            return help_text
        
        if user_role:
            return self._show_service_menu(user_role)
        
        return """[Show menu](#action:menu)
[Get help](#action:help)"""
    
    def _is_valid_for_state(self, user_input: str, bot_state: str) -> bool:
        """Check if input makes sense for current state"""
        active_states = [
            'ASK_NAME', 'ASK_GENDER', 'ASK_LOCATION', 'ASK_AVAILABILITY',
            'ASK_CREDENTIALS', 'ASK_BASIC_PREFERENCES', 'ASK_UPLOAD',
            'ASK_NOTIFICATION', 'SERVICE_MENU', 'BROWSE_JOBS'
        ]
        
        if bot_state in active_states:
            return True
        
        if bot_state == 'ROLE_SELECTION':
            valid_inputs = ['1', '2', '3', 'caregiver', 'afh', 'provider', 'service']
            return any(inp in user_input.lower() for inp in valid_inputs)
        
        if bot_state == 'ASK_CONTACT':
            has_email = '@' in user_input
            has_phone = any(char.isdigit() for char in user_input) and len(user_input) >= 10
            return has_email or has_phone
        
        return True
    
    def get_conversation_summary(self) -> Dict:
        """Get summary of conversation for analytics"""
        if not self.conversation_history:
            return {
                'total_messages': 0,
                'intents': [],
                'avg_confidence': 0,
                'session_duration': 0,
                'unique_intents': []
            }
        
        intents = [msg['intent'] for msg in self.conversation_history]
        confidences = [msg['confidence'] for msg in self.conversation_history]
        
        # Calculate session duration
        if len(self.conversation_history) > 1:
            first_timestamp = datetime.fromisoformat(self.conversation_history[0]['timestamp'])
            last_timestamp = datetime.fromisoformat(self.conversation_history[-1]['timestamp'])
            duration_seconds = (last_timestamp - first_timestamp).total_seconds()
        else:
            duration_seconds = 0
        
        return {
            'total_messages': len(self.conversation_history),
            'intents': intents,
            'avg_confidence': sum(confidences) / len(confidences) if confidences else 0,
            'session_duration': duration_seconds,
            'unique_intents': list(set(intents)),
            'role': self.conversation_history[-1].get('role') if self.conversation_history else None,
            'last_state': self.conversation_history[-1].get('state') if self.conversation_history else None,
            'first_message_time': self.conversation_history[0]['timestamp'] if self.conversation_history else None,
            'last_message_time': self.conversation_history[-1]['timestamp'] if self.conversation_history else None
        }
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        logger.info(f"Conversation history cleared for session {self.session_id}")
    
    def get_last_intent(self) -> Optional[Dict]:
        """Get the most recent intent classification"""
        if self.conversation_history:
            return {
                'intent': self.conversation_history[-1]['intent'],
                'confidence': self.conversation_history[-1]['confidence'],
                'timestamp': self.conversation_history[-1]['timestamp']
            }
        return None
    
    def get_audit_trail(self) -> List[Dict]:
        """Get complete audit trail for this session"""
        if self.session_id:
            return self.audit_logger.get_session_audit_trail(self.session_id)
        return []


class ResponseFormatter:
    """Format responses for different channels (SMS vs Browser)"""
    
    @staticmethod
    def format_for_sms(text: str) -> str:
        """Remove links and formatting for SMS - plain text only"""
        # Remove markdown links [text](#action:id) -> text
        text = re.sub(r'\[([^\]]+)\]\(#action:[^\)]+\)', r'\1', text)
        
        # Remove other markdown links
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
        # Remove bold **text** -> text
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        
        # Remove code blocks
        text = re.sub(r'`([^`]+)`', r'\1', text)
        
        # Clean up extra whitespace
        text = re.sub(r'\n\n+', '\n\n', text)
        
        return text.strip()
    
    @staticmethod
    def format_for_browser(text: str) -> str:
        """Ensure proper formatting for browser (links already present)"""
        return text
    
    @staticmethod
    def add_context_banner(text: str, user_data: Dict) -> str:
        """Add context information at top of message"""
        name = user_data.get('name')
        city = user_data.get('city')
        
        if name and city:
            return f"**{name} from {city}**\n\n{text}"
        elif name:
            return f"**{name}**\n\n{text}"
        
        return text