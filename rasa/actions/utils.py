"""
AFHSync Utilities
- Smart parsing with fuzzy matching
- Natural date parsing
- MongoDB handler
- Ollama AI fallback
"""

from typing import Dict, Optional, Any, List
import re
from thefuzz import fuzz
import dateparser
from datetime import datetime
import requests
import json
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError
import os
import logging

logger = logging.getLogger(__name__)

# Configuration
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://95.110.228.29:8201/v1')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'deepseek-r1:1.5b')
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:password@95.110.228.29:8711/admin?authSource=admin')
DB_NAME = os.getenv('DB_NAME', 'afhsync')


class MongoDBHandler:
    """Handle all MongoDB operations"""
    
    def __init__(self):
        try:
            self.client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            self.db = self.client[DB_NAME]
            self.users = self.db['users']
            self.jobs = self.db['jobs']
            self.applications = self.db['applications']
            
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
            'seattle': 'Washington',
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
        
        # Pattern: "city in state"
        if ' in ' in location_text:
            parts = location_text.split(' in ')
            city = parts[0].strip().title()
            state_indicator = parts[1].strip()
            
            for key, value in state_map.items():
                if key in state_indicator:
                    state = value
                    break
        
        # Pattern: "city, state"
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