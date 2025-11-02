"""
Progressive Profile Builder - Saves data immediately as user provides it
"""

from typing import Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ProgressiveProfileBuilder:
    """Builds user profile progressively with immediate saves"""
    
    def __init__(self, db_handler, bot_instance):
        self.db = db_handler
        self.bot = bot_instance
        self.transition_threshold = 3  # Redirect after 3 meaningful answers
        self.answers_collected = 0
    
    def process_and_save(self, user_input: str, field: str, contact: str) -> bool:
        """Save data immediately as it's collected"""
        try:
            update_data = {
                field: user_input,
                'updated_at': datetime.utcnow(),
                f'{field}_collected_at': datetime.utcnow()
            }
            
            success = self.db.update_user(contact, update_data)
            
            if success:
                self.answers_collected += 1
                logger.info(f"✅ Saved {field} for {contact}")
            
            return success
        except Exception as e:
            logger.error(f"Error saving {field}: {e}")
            return False
    
    def should_transition_to_browser(self) -> bool:
        """Determine if it's time to send user to browser portal"""
        return self.answers_collected >= self.transition_threshold
    
    def generate_portal_link(self, session_id: str, role: str) -> str:
        """Generate contextual portal link"""
        return f"https://afhsync.com/chat/{session_id}?context={role}"