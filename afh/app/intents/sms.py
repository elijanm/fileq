"""
Enhanced SMS Webhook with Ollama Intent Detection
"""
import os,re
import requests
import json
from typing import Dict, Tuple, Optional
from utils.util import logger
# Ollama Configuration
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://95.110.228.29:8201/v1')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'deepseek-r1:1.5b')


class SMSIntentAnalyzer:
    """Analyze SMS intent using Ollama to determine optimal flow"""
    
    @staticmethod
    def analyze_intent(message: str, user_context: Optional[Dict] = None) -> Dict:
        """
        Analyze user intent to determine:
        1. What they want to do
        2. How urgent/complete their need is
        3. Whether SMS or browser is better suited
        """
        try:
            context_info = ""
            if user_context:
                context_info = f"\nUser context: {json.dumps(user_context)}"
            
            prompt = f"""You are analyzing an SMS message to AFHSync - a platform connecting caregivers, AFH facility owners, and service providers.

Message: "{message}"{context_info}

Analyze and return ONLY valid JSON with this structure:
{{
    "intent_type": "role_inquiry|job_search|hire_caregiver|offer_service|general_question|greeting|unclear",
    "confidence": 0.0-1.0,
    "role_detected": "caregiver|afh_provider|service_provider|none",
    "urgency": "low|medium|high",
    "complexity": "simple|moderate|complex",
    "best_channel": "sms|browser",
    "reasoning": "brief explanation",
    "needs_immediate_info": true/false,
    "suggested_questions": ["question1", "question2"]
}}

Guidelines:
- "best_channel": "sms" if user seems ready to answer 2-3 quick questions
- "best_channel": "browser" if they need to upload files, see visual options, or have complex needs
- "urgency": "high" if actively job hunting, hiring urgently, or time-sensitive
- "complexity": "complex" if needs file uploads, detailed forms, or visual browsing
- "needs_immediate_info": true if we should ask 1-2 questions before browser redirect

Examples:
"looking for caregiver jobs" → sms (can ask location quickly)
"need to post job with photos" → browser (needs uploads)
"I'm a CNA in Seattle" → sms (collect certifications/availability)
"want to advertise my AFH" → browser (needs photos/details)"""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 400
                },
                timeout=8
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                
                # Extract JSON from response
                json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
                if json_match:
                    intent_data = json.loads(json_match.group())
                    logger.info(f"Intent analyzed: {intent_data['intent_type']} via {intent_data['best_channel']}")
                    return intent_data
            
            # Fallback
            return SMSIntentAnalyzer._fallback_intent()
                
        except Exception as e:
            logger.error(f"Intent analysis error: {e}")
            return SMSIntentAnalyzer._fallback_intent()
    
    @staticmethod
    def _fallback_intent() -> Dict:
        """Fallback when Ollama is unavailable"""
        return {
            "intent_type": "unclear",
            "confidence": 0.3,
            "role_detected": "none",
            "urgency": "medium",
            "complexity": "simple",
            "best_channel": "sms",
            "reasoning": "Ollama unavailable, defaulting to SMS flow",
            "needs_immediate_info": True,
            "suggested_questions": ["What brings you to AFHSync today?"]
        }



