"""
Enhanced SMS Flow Handlers with Ollama Intent Validation
"""

import logging
from typing import Dict, Optional, Tuple,List
import requests
import re
import os

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://95.110.228.29:8201/v1')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'deepseek-r1:1.5b')


class ResponseValidator:
    """Validate and extract structured data from user responses using Ollama"""
    
    @staticmethod
    def validate_location(message: str) -> Tuple[bool, Optional[Dict]]:
        """Validate and extract location information"""
        try:
            prompt = f"""Extract location from this message: "{message}"

Return ONLY valid JSON:
{{
    "valid": true/false,
    "city": "city name",
    "state": "full state name",
    "confidence": 0.0-1.0,
    "needs_clarification": true/false
}}

State abbreviations to full names:
WA/Wa → Washington
OR/Or → Oregon  
CA/Ca → California
ID/Id → Idaho

Examples:
"Auburn,Wa" → {{"valid": true, "city": "Auburn", "state": "Washington", "confidence": 0.95}}
"Seattle" → {{"valid": true, "city": "Seattle", "state": "Washington", "confidence": 0.9}}
"Tacoma WA" → {{"valid": true, "city": "Tacoma", "state": "Washington", "confidence": 0.95}}
"I live in Auburn" → {{"valid": true, "city": "Auburn", "state": "Washington", "confidence": 0.8}}
"Bellevue, Washington" → {{"valid": true, "city": "Bellevue", "state": "Washington", "confidence": 0.95}}
"yes" → {{"valid": false, "needs_clarification": true}}

IMPORTANT: Always convert state abbreviations to full names."""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 150
                },
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
                
                if json_match:
                    import json
                    data = json.loads(json_match.group())
                    
                    # Post-process to ensure state is full name
                    if data.get('state'):
                        data['state'] = ResponseValidator._normalize_state(data['state'])
                    
                    return data.get('valid', False), data
            
            # Fallback: manual parsing
            return ResponseValidator._fallback_location_parse(message)
                
        except Exception as e:
            logger.error(f"Location validation error: {e}")
            return ResponseValidator._fallback_location_parse(message)
    
    @staticmethod
    def _normalize_state(state: str) -> str:
        """Normalize state abbreviations to full names"""
        state_map = {
            'wa': 'Washington',
            'washington': 'Washington',
            'or': 'Oregon',
            'oregon': 'Oregon',
            'ca': 'California',
            'california': 'California',
            'id': 'Idaho',
            'idaho': 'Idaho'
        }
        return state_map.get(state.lower().strip(), state)
    
    @staticmethod
    def _fallback_location_parse(message: str) -> Tuple[bool, Dict]:
        """Fallback location parser when Ollama fails"""
        message = message.strip()
        
        # Handle "City, State" format
        if ',' in message:
            parts = message.split(',')
            city = parts[0].strip().title()
            state = parts[1].strip() if len(parts) > 1 else 'Washington'
            state = ResponseValidator._normalize_state(state)
            
            return True, {
                'valid': True,
                'city': city,
                'state': state,
                'confidence': 0.85
            }
        
        # Handle space-separated "City State"
        parts = message.split()
        if len(parts) >= 2:
            # Last part might be state
            potential_state = parts[-1]
            state_map = {'wa': True, 'or': True, 'ca': True, 'id': True}
            
            if potential_state.lower() in state_map:
                city = ' '.join(parts[:-1]).title()
                state = ResponseValidator._normalize_state(potential_state)
                
                return True, {
                    'valid': True,
                    'city': city,
                    'state': state,
                    'confidence': 0.85
                }
        
        # Default: treat as city in Washington
        if len(message) > 2:
            return True, {
                'valid': True,
                'city': message.title(),
                'state': 'Washington',
                'confidence': 0.7
            }
        
        return False, {'valid': False, 'needs_clarification': True}
    @staticmethod
    def validate_certifications(message: str) -> Tuple[bool, Optional[Dict]]:
        """Extract and validate certifications"""
        try:
            prompt = f"""Extract certifications from: "{message}"

Return ONLY valid JSON:
{{
    "valid": true/false,
    "certifications": ["cert1", "cert2"],
    "has_certifications": true/false,
    "needs_clarification": true/false
}}

Recognize: CNA, HCA, RN, LPN, CPR, First Aid, BLS, Dementia Care
Also accept: "none", "no certifications", "working on it"

Examples:
"CNA and CPR" → {{"valid": true, "certifications": ["CNA", "CPR"], "has_certifications": true}}
"none" → {{"valid": true, "certifications": [], "has_certifications": false}}
"I'm a registered nurse" → {{"valid": true, "certifications": ["RN"], "has_certifications": true}}"""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 150
                },
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
                
                if json_match:
                    import json
                    data = json.loads(json_match.group())
                    return data.get('valid', False), data
            
            return True, {'certifications': [message], 'has_certifications': True}
                
        except Exception as e:
            logger.error(f"Certification validation error: {e}")
            return True, {'certifications': [message], 'has_certifications': True}
    
    @staticmethod
    def validate_availability(message: str) -> Tuple[bool, Optional[Dict]]:
        """Extract and validate complex availability patterns"""
        try:
            prompt = f"""Extract detailed availability from: "{message}"

    Return ONLY valid JSON with this structure:
    {{
        "valid": true/false,
        "availability_pattern": "complex|simple|flexible",
        "schedule": [
            {{"days": ["Monday", "Tuesday"], "type": "shift", "hours": "8am-10pm"}},
            {{"days": ["Wednesday", "Thursday", "Friday"], "type": "live-in", "hours": "24/7"}},
            {{"days": ["Saturday", "Sunday"], "type": "shift", "hours": "8am-midnight"}}
        ],
        "summary": "brief description",
        "needs_clarification": true/false
    }}

    Parse complex patterns like:
    - "Monday, Tuesday from 8am-10pm" → shift work those days
    - "Wed-Friday live in" → live-in care those days
    - "Sat-Sunday from 8am-midnight" → weekend shifts

    Examples:
    "weekdays" → {{"valid": true, "availability_pattern": "simple", "schedule": [{{"days": ["weekdays"], "type": "flexible"}}], "summary": "Weekdays"}}

    "Monday, Tuesday from 8am-10pm, Wed-Friday live in, Sat-Sunday from 8am-midnight" → 
    {{
        "valid": true,
        "availability_pattern": "complex",
        "schedule": [
            {{"days": ["Monday", "Tuesday"], "type": "shift", "hours": "8am-10pm"}},
            {{"days": ["Wednesday", "Thursday", "Friday"], "type": "live-in", "hours": "24/7"}},
            {{"days": ["Saturday", "Sunday"], "type": "shift", "hours": "8am-midnight"}}
        ],
        "summary": "Mon-Tue shifts, Wed-Fri live-in, Sat-Sun shifts"
    }}

    "flexible" → {{"valid": true, "availability_pattern": "flexible", "schedule": [{{"days": ["any"], "type": "flexible"}}], "summary": "Flexible schedule"}}"""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 400
                },
                timeout=8
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                
                if json_match:
                    import json
                    data = json.loads(json_match.group())
                    return data.get('valid', False), data
            
            # Fallback: manual parsing
            return ResponseValidator._fallback_availability_parse(message)
                
        except Exception as e:
            logger.error(f"Availability validation error: {e}")
            return ResponseValidator._fallback_availability_parse(message)

    @staticmethod
    def _fallback_availability_parse(message: str) -> Tuple[bool, Dict]:
        """Fallback parser for complex availability patterns"""
        
        # Simple patterns
        simple_patterns = {
            'weekdays': 'Monday-Friday',
            'weekends': 'Saturday-Sunday',
            'nights': 'Night shifts',
            'days': 'Day shifts',
            'flexible': 'Flexible schedule',
            'anytime': 'Available anytime'
        }
        
        msg_lower = message.lower()
        for key, value in simple_patterns.items():
            if key in msg_lower:
                return True, {
                    'valid': True,
                    'availability_pattern': 'simple',
                    'schedule': [{'days': [key], 'type': 'flexible'}],
                    'summary': value,
                    'raw_input': message
                }
        
        # Complex pattern detection
        has_time_range = bool(re.search(r'\d{1,2}(?:am|pm)', msg_lower))
        has_live_in = 'live' in msg_lower and 'in' in msg_lower
        has_days = any(day in msg_lower for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'])
        
        if has_time_range or has_live_in or has_days:
            # Parse as complex pattern
            schedule = []
            
            # Split by common delimiters
            segments = re.split(r'[,;]', message)
            
            for segment in segments:
                segment = segment.strip()
                if not segment:
                    continue
                
                parsed_segment = {
                    'days': ResponseValidator._extract_days(segment),
                    'type': 'live-in' if 'live' in segment.lower() else 'shift',
                    'hours': ResponseValidator._extract_hours(segment),
                    'raw': segment
                }
                schedule.append(parsed_segment)
            
            return True, {
                'valid': True,
                'availability_pattern': 'complex',
                'schedule': schedule,
                'summary': ResponseValidator._generate_summary(schedule),
                'raw_input': message
            }
        
        # Default: accept as custom
        return True, {
            'valid': True,
            'availability_pattern': 'custom',
            'schedule': [{'days': ['custom'], 'type': 'custom', 'details': message}],
            'summary': message[:50],
            'raw_input': message
        }

    @staticmethod
    def _extract_days(text: str) -> List[str]:
        """Extract day names from text"""
        days_map = {
            'mon': 'Monday',
            'tue': 'Tuesday', 
            'wed': 'Wednesday',
            'thu': 'Thursday',
            'fri': 'Friday',
            'sat': 'Saturday',
            'sun': 'Sunday'
        }
        
        found_days = []
        text_lower = text.lower()
        
        for abbr, full_name in days_map.items():
            if abbr in text_lower or full_name.lower() in text_lower:
                found_days.append(full_name)
        
        # Handle ranges like "Wed-Friday"
        if '-' in text:
            range_match = re.search(r'(mon|tue|wed|thu|fri|sat|sun)\w*\s*-\s*(mon|tue|wed|thu|fri|sat|sun)\w*', text_lower)
            if range_match:
                # Simple range expansion
                return ['Range: ' + text]
        
        return found_days if found_days else ['unspecified']

    @staticmethod
    def _extract_hours(text: str) -> str:
        """Extract time ranges from text"""
        # Match patterns like "8am-10pm", "8am - 10pm", "8:00am-10:00pm"
        time_pattern = r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s*-\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))'
        match = re.search(time_pattern, text.lower())
        
        if match:
            return f"{match.group(1)}-{match.group(2)}"
        
        return "flexible"

    @staticmethod
    def _generate_summary(schedule: List[Dict]) -> str:
        """Generate human-readable summary from schedule"""
        summaries = []
        
        for seg in schedule:
            days = seg.get('days', [])
            type_info = seg.get('type', 'shift')
            hours = seg.get('hours', '')
            
            if days and days != ['unspecified']:
                day_str = ', '.join(days[:2])
                if len(days) > 2:
                    day_str = f"{days[0]}-{days[-1]}"
                
                if type_info == 'live-in':
                    summaries.append(f"{day_str} live-in")
                elif hours and hours != 'flexible':
                    summaries.append(f"{day_str} {hours}")
                else:
                    summaries.append(day_str)
        
        return '; '.join(summaries) if summaries else "Custom schedule"
    @staticmethod
    def validate_number(message: str, context: str = "facilities") -> Tuple[bool, Optional[int]]:
        """Extract and validate numeric responses"""
        try:
            prompt = f"""Extract number from: "{message}" (context: {context})

Return ONLY valid JSON:
{{
    "valid": true/false,
    "number": integer or null,
    "needs_clarification": true/false
}}

Examples:
"3" → {{"valid": true, "number": 3}}
"I have 5" → {{"valid": true, "number": 5}}
"one" → {{"valid": true, "number": 1}}
"not sure" → {{"valid": false, "needs_clarification": true}}"""

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
                content = result['choices'][0]['message']['content'].strip()
                json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
                
                if json_match:
                    import json
                    data = json.loads(json_match.group())
                    return data.get('valid', False), data.get('number')
            
            # Fallback: extract digits
            digits = re.findall(r'\d+', message)
            if digits:
                return True, int(digits[0])
            
            return False, None
                
        except Exception as e:
            logger.error(f"Number validation error: {e}")
            # Fallback
            digits = re.findall(r'\d+', message)
            return bool(digits), int(digits[0]) if digits else None