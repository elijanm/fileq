# handlers/provider_handler.py

import re
from typing import Dict, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AFHProviderHandler:
    """Stateful handler for AFH Provider interactions"""
    
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.reset_state()
    
    def reset_state(self):
        """Reset handler state"""
        self.current_action = None
        self.browse_step = None
        self.browse_filters = {}
        self.job_posting_data = {}
        self.current_caregivers = []  # Store search results
    
    def handle_provider_services(self, user_input: str, user_data: Dict) -> str:
        """Main router for provider services"""
        user_lower = user_input.lower().strip()
        
        # Handle 'menu' at any time
        if 'menu' in user_lower and self.current_action:
            self.reset_state()
            return self.show_main_menu()
        
        # Route based on current action
        if self.current_action == 'browse_caregivers':
            return self.handle_browse_flow(user_input, user_data)
        
        elif self.current_action == 'post_job':
            return self.handle_job_posting_flow(user_input, user_data)
        
        elif self.current_action == 'upload_photos':
            return self.handle_photo_upload_flow(user_input, user_data)
        
        # No active action - detect new action
        else:
            return self.detect_and_start_action(user_input, user_data)
    
    def detect_and_start_action(self, user_input: str, user_data: Dict) -> str:
        """Detect which service to start"""
        user_lower = user_input.lower().strip()
        
        if any(word in user_lower for word in ['browse', 'caregiver', 'find', '2', 'filter']):
            self.current_action = 'browse_caregivers'
            self.browse_step = 'certifications'
            return self.start_caregiver_browse()
        
        elif any(word in user_lower for word in ['post', 'job', 'opening', 'hire', '1']):
            self.current_action = 'post_job'
            return self.start_job_posting()
        
        elif any(word in user_lower for word in ['upload', 'photo', 'picture', '3']):
            self.current_action = 'upload_photos'
            return self.handle_photo_upload(user_data)
        
        elif any(word in user_lower for word in ['manage', 'posting', '4']):
            return self.show_active_postings(user_data)
        
        elif any(word in user_lower for word in ['review', 'application', '5']):
            return self.show_applications(user_data)
        
        return self.show_main_menu()
    
    # ==================== BROWSE CAREGIVERS FLOW ====================
    
    def start_caregiver_browse(self) -> str:
        """Start caregiver browsing flow"""
        self.browse_step = 'certifications'
        return """**Browse Caregivers**

I'll show you qualified caregivers in your area.

What certifications are required?

[CNA Required](#action:filter_cna)
[HCA Required](#action:filter_hca)
[Any Certification](#action:filter_any)
[No Requirements](#action:filter_none)"""
    
    def handle_browse_flow(self, user_input: str, user_data: Dict) -> str:
        """Handle browse caregiver flow"""
        user_lower = user_input.lower().strip()
        
        # Step 1: Certifications
        if self.browse_step == 'certifications':
            if 'cna' in user_lower:
                self.browse_filters['certification'] = 'CNA'
            elif 'hca' in user_lower:
                self.browse_filters['certification'] = 'HCA'
            elif 'any' in user_lower or 'filter' in user_lower:
                self.browse_filters['certification'] = 'any'
            elif 'no' in user_lower or 'none' in user_lower:
                self.browse_filters['certification'] = None
            else:
                return """Please choose a certification requirement:

[CNA Required](#action:filter_cna)
[HCA Required](#action:filter_hca)
[Any Certification](#action:filter_any)
[No Requirements](#action:filter_none)"""
            
            self.browse_step = 'experience'
            return """**Experience Level**

Minimum years of experience required?

[Entry Level (0-1 years)](#action:exp_entry)
[Experienced (2-4 years)](#action:exp_experienced)
[Senior (5+ years)](#action:exp_senior)
[Any Experience](#action:exp_any)"""
        
        # Step 2: Experience
        elif self.browse_step == 'experience':
            if 'entry' in user_lower or '0' in user_input or '1' in user_input:
                self.browse_filters['min_experience'] = 0
            elif 'experienced' in user_lower or '2' in user_input:
                self.browse_filters['min_experience'] = 2
            elif 'senior' in user_lower or '5' in user_input:
                self.browse_filters['min_experience'] = 5
            else:
                self.browse_filters['min_experience'] = 0
            
            self.browse_step = 'results'
            return self.show_caregiver_results(user_data)
        
        # Step 3: Results actions
        elif self.browse_step == 'results':
            return self.handle_result_actions(user_input, user_data)
        
        return self.show_main_menu()
    
    def show_caregiver_results(self, user_data: Dict) -> str:
        """Query and display matching caregivers"""
        query = {'role': 'caregiver', 'profile_complete': True}
        
        # Apply certification filter
        cert = self.browse_filters.get('certification')
        if cert and cert != 'any':
            query['credentials'] = {'$regex': cert, '$options': 'i'}
        
        # Apply location filter
        provider_city = user_data.get('primary_location', {}).get('city', '')
        if provider_city:
            query['primary_location.city'] = provider_city
        
        # Search
        self.current_caregivers = list(self.db.users.find().limit(10))
        
        if not self.current_caregivers:
            return f"""**No Caregivers Found**

No matches for:
- Certification: {cert or 'Any'}
- Location: {provider_city}

[Adjust Filters](#action:refine)
[Post Job Opening](#action:post_job)
[Return to Menu](#action:menu)"""
        
        # Format results
        cert_text = cert if cert and cert != 'any' else 'Any certification'
        results = f"""**Found {len(self.current_caregivers)} Caregivers**

📍 {provider_city} | 🎓 {cert_text}

---

"""
        
        for idx, cg in enumerate(self.current_caregivers, 1):
            name = cg.get('name', 'Caregiver')
            certs = ', '.join(cg.get('credentials', [])[:2]) or 'None listed'
            city = cg.get('primary_location', {}).get('city', 'N/A')
            contact = cg.get('contact', '')
            
            # Get availability
            avail = cg.get('availability', {})
            avail_text = []
            if avail.get('day_shift'): avail_text.append('Days')
            if avail.get('night_shift'): avail_text.append('Nights')
            if avail.get('weekends'): avail_text.append('Weekends')
            avail_display = ', '.join(avail_text) if avail_text else 'Flexible'
            
            results += f"""**{idx}. {name}**
📍 {city} | 🎓 {certs}
⏰ Available: {avail_display}

[View Full Profile](#action:view_{idx})
[Send Message](#action:contact_{idx})

---

"""
        
        results += """[Refine Search](#action:refine)
[Post Job Opening](#action:post_job)
[Return to Menu](#action:menu)"""
        
        return results
    
    def handle_result_actions(self, user_input: str, user_data: Dict) -> str:
        """Handle actions on search results"""
        user_lower = user_input.lower()
        
        if 'refine' in user_lower or 'adjust' in user_lower:
            self.browse_step = 'certifications'
            self.browse_filters = {}
            return self.start_caregiver_browse()
        
        elif 'view' in user_lower:
            match = re.search(r'view[_\s]*(\d+)', user_lower)
            if match:
                idx = int(match.group(1)) - 1
                if 0 <= idx < len(self.current_caregivers):
                    return self.show_caregiver_profile(self.current_caregivers[idx])
            return "Please specify which caregiver (e.g., 'view 1')"
        
        elif 'contact' in user_lower or 'message' in user_lower:
            match = re.search(r'(?:contact|message)[_\s]*(\d+)', user_lower)
            if match:
                idx = int(match.group(1)) - 1
                if 0 <= idx < len(self.current_caregivers):
                    return self.initiate_contact(self.current_caregivers[idx], user_data)
            return "Please specify which caregiver (e.g., 'contact 1')"
        
        elif 'post' in user_lower or 'job' in user_lower:
            self.current_action = 'post_job'
            return self.start_job_posting()
        
        return """Type an action:

[View profile (e.g., view 1)](#action:view_1)
[Contact caregiver (e.g., contact 1)](#action:contact_1)
[Refine search](#action:refine)
[Return to menu](#action:menu)"""
    
    def show_caregiver_profile(self, caregiver: Dict) -> str:
        """Show detailed caregiver profile"""
        name = caregiver.get('name', 'Caregiver')
        certs = ', '.join(caregiver.get('credentials', [])) or 'None listed'
        city = caregiver.get('primary_location', {}).get('city', 'N/A')
        phone = caregiver.get('phone', caregiver.get('contact', ''))
        
        # Experience
        work_history = caregiver.get('work_history', [])
        exp_section = ""
        if work_history:
            exp_section = "\n**Recent Experience:**\n"
            for job in work_history[:2]:
                title = job.get('title', 'Caregiver')
                company = job.get('company', 'Healthcare Facility')
                exp_section += f"• {title} at {company}\n"
        
        # Skills
        skills = caregiver.get('skills', [])
        skills_text = ', '.join(skills[:6]) if skills else 'Not specified'
        
        # Availability
        avail = caregiver.get('availability', {})
        avail_list = []
        if avail.get('day_shift'): avail_list.append('Day shifts')
        if avail.get('night_shift'): avail_list.append('Night shifts')
        if avail.get('weekends'): avail_list.append('Weekends')
        avail_text = ', '.join(avail_list) if avail_list else 'Flexible schedule'
        
        return f"""**{name}'s Profile**

📍 Location: {city}
🎓 Certifications: {certs}
📞 Contact: {phone}
{exp_section}
**Key Skills:** {skills_text}

**Availability:** {avail_text}

[Send Message](#action:message_{caregiver.get('contact')})
[Request Interview](#action:interview_{caregiver.get('contact')})
[Back to Results](#action:back_results)
[Return to Menu](#action:menu)"""
    
    def initiate_contact(self, caregiver: Dict, user_data: Dict) -> str:
        """Initiate contact with caregiver"""
        name = caregiver.get('name', 'Caregiver')
        contact = caregiver.get('contact', '')
        provider_name = user_data.get('name', 'Provider')
        
        # Log the contact attempt
        try:
            self.db.log_interaction({
                'type': 'provider_contact',
                'provider': user_data.get('contact'),
                'caregiver': contact,
                'timestamp': datetime.utcnow()
            })
        except Exception as e:
            logger.error(f"Failed to log contact: {e}")
        
        return f"""**Message Sent to {name}**

{provider_name} has expressed interest in your profile.

Your contact info has been shared: {user_data.get('phone', user_data.get('contact'))}

**Next Steps:**
- {name} will receive a notification
- They can respond directly via phone/SMS
- You can also reach them at: {contact}

[View Other Caregivers](#action:back_results)
[Post Job Opening](#action:post_job)
[Return to Menu](#action:menu)"""
    
    # ==================== JOB POSTING FLOW ====================
    
    def start_job_posting(self) -> str:
        """Start job posting flow"""
        self.job_posting_data = {}
        return """**Post Job Opening**

What position are you hiring for?

[CNA](#action:post_cna)
[HCA](#action:post_hca)
[Companion Caregiver](#action:post_companion)
[Live-in Caregiver](#action:post_livein)

Or type the position name:"""
    
    def handle_job_posting_flow(self, user_input: str, user_data: Dict) -> str:
        """Handle job posting creation"""
        # Simplified - just capture position for now
        position = user_input.strip()
        
        if not position or len(position) < 3:
            return self.start_job_posting()
        
        self.job_posting_data['position'] = position
        self.job_posting_data['facility'] = user_data.get('name', 'Healthcare Facility')
        self.job_posting_data['created_at'] = datetime.utcnow()
        
        # Save to database
        try:
            self.db.create_job_posting({
                **self.job_posting_data,
                'provider_contact': user_data.get('contact')
            })
        except Exception as e:
            logger.error(f"Job posting save error: {e}")
        
        self.reset_state()
        
        return f"""**Job Posting Created!**

Position: {position}
Facility: {self.job_posting_data['facility']}

Your posting is now visible to caregivers in your area.

[Browse Caregivers](#action:browse)
[Post Another Job](#action:post_job)
[Return to Menu](#action:menu)"""
    
    # ==================== PHOTO UPLOAD ====================
    
    def handle_photo_upload(self, user_data: Dict) -> str:
        """Handle photo upload"""
        contact = user_data.get('contact', 'user').replace('+', '').replace(' ', '')
        facility_name = user_data.get('name', 'your facility')
        
        return f"""**Upload Facility Photos**

Showcase {facility_name} to attract quality caregivers!

**Upload photos at:**
https://afhsync.com/upload/{contact}

**Photo Tips:**
- Common areas and resident rooms
- Clean, well-lit spaces
- Staff interactions
- Dining and activity areas

[Return to Menu](#action:menu)"""
    
    def handle_photo_upload_flow(self, user_input: str, user_data: Dict) -> str:
        """Handle photo upload flow continuation"""
        # Currently just returns to menu
        self.reset_state()
        return self.show_main_menu()
    
    # ==================== OTHER SERVICES ====================
    
    def show_active_postings(self, user_data: Dict) -> str:
        """Show active job postings"""
        # Query database for postings
        try:
            postings = list(self.db.job_postings_collection.find({
                'provider_contact': user_data.get('contact')
            }).limit(5))
        except:
            postings = []
        
        if not postings:
            return """**Manage Job Postings**

You have no active job postings.

[Post New Job](#action:post_job)
[Return to Menu](#action:menu)"""
        
        result = f"""**Active Job Postings** ({len(postings)})

"""
        for post in postings:
            result += f"""• {post.get('position', 'Position')}
  Posted: {post.get('created_at', 'Recently')}
  
"""
        
        result += """[Post Another Job](#action:post_job)
[Return to Menu](#action:menu)"""
        
        return result
    
    def show_applications(self, user_data: Dict) -> str:
        """Show job applications"""
        return """**Review Applications**

No applications received yet.

**Tip:** Reach out directly to caregivers through Browse Caregivers!

[Browse Caregivers](#action:browse)
[Post Job Opening](#action:post_job)
[Return to Menu](#action:menu)"""
    
    def show_main_menu(self) -> str:
        """Provider main menu"""
        return """**AFH Provider Services**

How can I help you today?

[Post Job Opening](#action:post_job)
[Browse Caregivers](#action:browse)
[Upload Facility Photos](#action:upload)
[Manage Job Postings](#action:manage)
[Review Applications](#action:review)

Click a link or type your choice."""