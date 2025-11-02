# handlers/service_provider_handler.py

import re
from typing import Dict, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ServiceProviderHandler:
    """Stateful handler for Service Provider interactions"""
    
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.reset_state()
    
    def reset_state(self):
        """Reset handler state"""
        self.current_action = None
        self.browse_step = None
        self.browse_filters = {}
        self.service_listing_data = {}
        self.current_requests = []
    
    def handle_service_provider_services(self, user_input: str, user_data: Dict) -> str:
        """Main router for service provider services"""
        user_lower = user_input.lower().strip()
        
        # Handle 'menu' at any time
        if 'menu' in user_lower and self.current_action:
            self.reset_state()
            return self.show_main_menu(user_data)
        
        # Route based on current action
        if self.current_action == 'browse_requests':
            return self.handle_browse_requests_flow(user_input, user_data)
        
        elif self.current_action == 'list_services':
            return self.handle_list_services_flow(user_input, user_data)
        
        elif self.current_action == 'upload_brochures':
            return self.handle_upload_flow(user_input, user_data)
        
        # No active action - detect new action
        else:
            return self.detect_and_start_action(user_input, user_data)
    
    def detect_and_start_action(self, user_input: str, user_data: Dict) -> str:
        """Detect which service to start"""
        user_lower = user_input.lower().strip()
        
        if any(word in user_lower for word in ['browse', 'request', 'find', '1', 'active', 'recent', 'all']):
            self.current_action = 'browse_requests'
            return self.start_browse_requests(user_data)
        
        elif any(word in user_lower for word in ['list', 'service', 'add', '2']):
            self.current_action = 'list_services'
            return self.start_list_services(user_data)
        
        elif any(word in user_lower for word in ['upload', 'brochure', 'document', '3']):
            self.current_action = 'upload_brochures'
            return self.handle_upload_brochures(user_data)
        
        elif any(word in user_lower for word in ['manage', 'offering', '4']):
            return self.show_manage_offerings(user_data)
        
        elif any(word in user_lower for word in ['pricing', 'price', '5']):
            return self.show_update_pricing(user_data)
        
        # Default: show menu
        return self.show_main_menu(user_data)
    
    # ==================== BROWSE AFH REQUESTS ====================
    
    def start_browse_requests(self, user_data: Dict) -> str:
        """Start browsing AFH requests"""
        self.browse_step = 'filter'
        return """**Browse AFH Requests**

Searching for service requests in your area...

[Active Requests](#action:active_requests) - Currently open
[Recent Requests](#action:recent_requests) - Last 30 days
[All Requests](#action:all_requests) - View all

Choose a filter:"""
    
    def handle_browse_requests_flow(self, user_input: str, user_data: Dict) -> str:
        """Handle browse requests flow"""
        user_lower = user_input.lower().strip()
        
        # Step 1: Filter selection
        if self.browse_step == 'filter':
            if 'active' in user_lower:
                self.browse_filters['status'] = 'active'
            elif 'recent' in user_lower:
                self.browse_filters['status'] = 'recent'
            else:
                self.browse_filters['status'] = 'all'
            
            self.browse_step = 'results'
            return self.show_request_results(user_data)
        
        # Step 2: Handle result actions
        elif self.browse_step == 'results':
            return self.handle_request_actions(user_input, user_data)
        
        return self.show_main_menu(user_data)
    
    def show_request_results(self, user_data: Dict) -> str:
        """Show AFH service requests"""
        
        # Query for requests
        query = {'type': 'service_request'}
        
        if self.browse_filters.get('status') == 'active':
            query['status'] = 'open'
        elif self.browse_filters.get('status') == 'recent':
            from datetime import timedelta
            query['created_at'] = {'$gte': datetime.utcnow() - timedelta(days=30)}
        
        # Get requests
        try:
            self.current_requests = list(self.db.service_requests_collection.find(query).limit(10))
        except:
            self.current_requests = []
        
        if not self.current_requests:
            return f"""**No Requests Found**

No service requests match your filter: {self.browse_filters.get('status', 'all')}

**Get Started:**
This feature is coming soon! AFH providers will be able to post service requests.

[List Your Services](#action:list_services)
[Upload Brochures](#action:upload_brochures)
[Return to Menu](#action:menu)"""
        
        # Format results
        status_text = self.browse_filters.get('status', 'all').title()
        results = f"""**{status_text} Service Requests** ({len(self.current_requests)})

"""
        
        for idx, req in enumerate(self.current_requests, 1):
            facility = req.get('facility_name', 'AFH Facility')
            service_type = req.get('service_type', 'Service')
            location = req.get('location', 'N/A')
            posted = req.get('created_at', 'Recently')
            
            results += f"""**{idx}. {service_type} Needed**
🏢 {facility}
📍 {location}
📅 Posted: {posted}

[View Details](#action:view_{idx})
[Submit Proposal](#action:propose_{idx})

---

"""
        
        results += """[Refine Search](#action:refine)
[Return to Menu](#action:menu)"""
        
        return results
    
    def handle_request_actions(self, user_input: str, user_data: Dict) -> str:
        """Handle actions on request results"""
        user_lower = user_input.lower()
        
        if 'refine' in user_lower:
            self.browse_step = 'filter'
            self.browse_filters = {}
            return self.start_browse_requests(user_data)
        
        elif 'view' in user_lower:
            match = re.search(r'view[_\s]*(\d+)', user_lower)
            if match:
                idx = int(match.group(1)) - 1
                if 0 <= idx < len(self.current_requests):
                    return self.show_request_details(self.current_requests[idx])
            return "Please specify which request (e.g., 'view 1')"
        
        elif 'propose' in user_lower or 'submit' in user_lower:
            match = re.search(r'(?:propose|submit)[_\s]*(\d+)', user_lower)
            if match:
                idx = int(match.group(1)) - 1
                if 0 <= idx < len(self.current_requests):
                    return self.submit_proposal(self.current_requests[idx], user_data)
            return "Please specify which request (e.g., 'propose 1')"
        
        return """Type an action:

[View details (e.g., view 1)](#action:view_1)
[Submit proposal (e.g., propose 1)](#action:propose_1)
[Refine search](#action:refine)
[Return to menu](#action:menu)"""
    
    def show_request_details(self, request: Dict) -> str:
        """Show detailed request information"""
        facility = request.get('facility_name', 'AFH Facility')
        service_type = request.get('service_type', 'Service')
        description = request.get('description', 'No description provided')
        location = request.get('location', 'Not specified')
        budget = request.get('budget', 'Not specified')
        
        return f"""**Service Request Details**

**Service:** {service_type}
**Facility:** {facility}
**Location:** {location}
**Budget:** {budget}

**Description:**
{description}

[Submit Proposal](#action:submit_proposal)
[Back to Results](#action:back_results)
[Return to Menu](#action:menu)"""
    
    def submit_proposal(self, request: Dict, user_data: Dict) -> str:
        """Submit proposal for service request"""
        facility = request.get('facility_name', 'AFH Facility')
        service_type = request.get('service_type', 'Service')
        provider_name = user_data.get('name', 'Service Provider')
        
        # Log proposal
        try:
            self.db.log_interaction({
                'type': 'service_proposal',
                'provider': user_data.get('contact'),
                'request_id': request.get('_id'),
                'timestamp': datetime.utcnow()
            })
        except Exception as e:
            logger.error(f"Failed to log proposal: {e}")
        
        return f"""**Proposal Submitted!**

Your proposal for {service_type} at {facility} has been sent.

**Next Steps:**
- {facility} will review your proposal
- They can contact you at: {user_data.get('phone', user_data.get('contact'))}
- Check back for updates

[View Other Requests](#action:back_results)
[List Your Services](#action:list_services)
[Return to Menu](#action:menu)"""
    
    # ==================== LIST SERVICES ====================
    
    def start_list_services(self, user_data: Dict) -> str:
        """Start service listing process"""
        
        # Check if services already listed
        existing_services = user_data.get('services_offered', [])
        
        if existing_services:
            services_list = '\n'.join(f"• {s}" for s in existing_services)
            return f"""**Your Listed Services**

{services_list}

[Add New Service](#action:add_service)
[Edit Services](#action:edit_services)
[Enable Service Requests](#action:enable_requests)
[Return to Menu](#action:menu)"""
        
        return """**List Your Services**

What services do you offer to AFH facilities?

**Common Services:**
- Medical Equipment & Supplies
- Facility Maintenance
- Transportation Services
- Food Service & Catering
- Professional Training
- Healthcare Consulting
- Therapy Services (PT, OT, Speech)
- Housekeeping Services

Type your service categories (comma-separated):"""
    
    def handle_list_services_flow(self, user_input: str, user_data: Dict) -> str:
        """Handle service listing flow"""
        user_lower = user_input.lower().strip()
        
        if 'enable' in user_lower or 'request' in user_lower:
            return self.enable_service_requests(user_data)
        
        # Parse services
        services = [s.strip().title() for s in user_input.split(',') if s.strip() and len(s.strip()) > 2]
        
        if not services:
            return self.start_list_services(user_data)
        
        # Save services
        try:
            self.db.update_user(user_data.get('contact'), {
                'services_offered': services,
                'service_provider_active': True,
                'services_updated_at': datetime.utcnow()
            })
        except Exception as e:
            logger.error(f"Failed to save services: {e}")
        
        self.reset_state()
        
        services_list = '\n'.join(f"• {s}" for s in services)
        
        return f"""**Services Listed Successfully!**

Your services are now visible to AFH facilities:

{services_list}

**What's Next?**

[Enable Service Requests](#action:enable_requests) - Coming Soon!
[Upload Brochures](#action:upload_brochures)
[Browse Requests](#action:browse_requests)
[Return to Menu](#action:menu)"""
    
    def enable_service_requests(self, user_data: Dict) -> str:
        """Enable service request notifications (coming soon)"""
        return """**Enable Service Requests** 🚧

**Coming Soon!**

This feature will allow AFH facilities to:
- Submit service requests directly to you
- View your services and pricing
- Contact you for quotes
- Schedule consultations

**Get Ready:**
1. List all your services ✓
2. Upload brochures and materials
3. Set pricing (optional)

We'll notify you when this feature launches!

[Upload Brochures](#action:upload_brochures)
[Update Pricing](#action:update_pricing)
[Return to Menu](#action:menu)"""
    
    # ==================== UPLOAD BROCHURES ====================
    
    def handle_upload_brochures(self, user_data: Dict) -> str:
        """Handle brochure upload"""
        contact = user_data.get('contact', 'user').replace('+', '').replace(' ', '')
        company_name = user_data.get('name', 'your company')
        
        return f"""**Upload Service Materials**

Showcase {company_name}'s services to AFH facilities!

**Upload at:**
https://afhsync.com/upload/{contact}

**Recommended Materials:**
- Service brochures and catalogs
- Pricing sheets
- Case studies
- Certifications and licenses
- Company presentations

[Return to Menu](#action:menu)"""
    
    def handle_upload_flow(self, user_input: str, user_data: Dict) -> str:
        """Handle upload flow continuation"""
        self.reset_state()
        return self.show_main_menu(user_data)
    
    # ==================== MANAGE OFFERINGS ====================
    
    def show_manage_offerings(self, user_data: Dict) -> str:
        """Show manage offerings"""
        services = user_data.get('services_offered', [])
        
        if not services:
            return """**Manage Offerings**

You haven't listed any services yet.

[List Your Services](#action:list_services)
[Return to Menu](#action:menu)"""
        
        services_list = '\n'.join(f"• {s}" for s in services)
        
        return f"""**Manage Your Offerings**

**Current Services:**
{services_list}

[Add More Services](#action:add_service)
[Remove Services](#action:remove_service)
[Update Descriptions](#action:update_descriptions)
[Return to Menu](#action:menu)"""
    
    def show_update_pricing(self, user_data: Dict) -> str:
        """Show pricing update (coming soon)"""
        return """**Update Pricing** 🚧

**Coming Soon!**

This feature will allow you to:
- Set pricing for each service
- Offer volume discounts
- Create custom packages
- Display pricing to facilities

For now, include pricing in your brochures!

[Upload Brochures](#action:upload_brochures)
[Return to Menu](#action:menu)"""
    
    # ==================== MAIN MENU ====================
    
    def show_main_menu(self, user_data: Dict) -> str:
        """Service provider main menu"""
        services = user_data.get('services_offered', [])
        service_status = f"✓ {len(services)} services listed" if services else "⚠️ No services listed"
        
        return f"""**Service Provider Services**

{service_status}

[List Your Services](#action:list_services)
[Browse AFH Requests](#action:browse_requests) 🚧 Coming Soon
[Upload Brochures](#action:upload_brochures)
[Manage Offerings](#action:manage_offerings)
[Update Pricing](#action:update_pricing) 🚧 Coming Soon

**🚧 = Coming Soon**

Click a link or type your choice."""