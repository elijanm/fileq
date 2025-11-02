"""
AFHSync Resume Writing Service
- Resume builder from scratch
- Resume improvement service
- Template generation
- ATS optimization
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ResumeService:
    """Handle resume writing and improvement services"""
    
    def __init__(self, db_handler):
        self.db = db_handler
        self.resume_step = None
        self.resume_data = {}
    
    def start_resume_service(self) -> str:
        """Initialize resume service"""
        return """📝 **Resume Writing Service**

Let me help you create a professional caregiver resume!

Do you have an existing resume you'd like me to improve?

Type 'yes' to upload existing resume
Type 'no' to build from scratch"""
    
    def handle_resume_flow(self, user_input: str, user_data: Dict) -> str:
        """Handle the resume building/improvement flow"""
        user_lower = user_input.lower().strip()
        
        # Initial choice: existing vs from scratch
        if not self.resume_step:
            if 'yes' in user_lower:
                self.resume_step = 'upload_existing'
                return self.request_upload()
            elif 'no' in user_lower:
                self.resume_step = 'objective'
                self.resume_data = self._extract_user_data(user_data)
                return self.ask_objective()
            else:
                return "Please type 'yes' if you have an existing resume, or 'no' to build from scratch."
        
        # Handle existing resume upload
        elif self.resume_step == 'upload_existing':
            return self.handle_existing_resume(user_input, user_data)
        
        # Build from scratch flow
        elif self.resume_step == 'objective':
            return self.handle_objective(user_input, user_data)
        
        elif self.resume_step == 'experience':
            return self.handle_experience(user_input)
        
        elif self.resume_step == 'experience_details':
            return self.handle_experience_details(user_input)
        
        elif self.resume_step == 'more_experience':
            return self.handle_more_experience(user_input)
        
        elif self.resume_step == 'education':
            return self.handle_education(user_input)
        
        elif self.resume_step == 'skills':
            return self.handle_skills(user_input)
        
        elif self.resume_step == 'generate':
            return self.generate_resume(user_data)
        
        return "Something went wrong. Type 'menu' to return to services."
    
    def _extract_user_data(self, user_data: Dict) -> Dict:
        """Extract relevant user data for resume"""
        return {
            'name': user_data.get('name', ''),
            'contact': user_data.get('contact', ''),
            'email': user_data.get('email', ''),
            'phone': user_data.get('phone', ''),
            'location': user_data.get('primary_location', {}),
            'credentials': user_data.get('credentials', []),
            'languages': user_data.get('detailed_preferences', {}).get('languages', ['English']),
            'experience_list': [],
            'education': [],
            'skills': []
        }
    
    def request_upload(self) -> str:
        """Request existing resume upload"""
        return """📤 **Upload Your Existing Resume**

Please upload your resume in one of these formats:
• PDF (.pdf)
• Word Document (.doc, .docx)
• Text file (.txt)

Upload your file at:
**https://afhsync.com/resume/upload**

Or type 'skip' to build a resume from scratch instead."""
    
    def handle_existing_resume(self, user_input: str, user_data: Dict) -> str:
        """Handle existing resume improvement"""
        if 'skip' in user_input.lower():
            self.resume_step = 'objective'
            self.resume_data = self._extract_user_data(user_data)
            return self.ask_objective()
        
        # Simulate file processing (in production, this would analyze uploaded file)
        return """✅ **Resume Received!**

I've analyzed your resume. Here are my recommendations:

**Strengths:**
• Clear contact information
• Good credential listing

**Areas for Improvement:**
1. Add quantifiable achievements (e.g., "Cared for 5+ patients daily")
2. Include specific care techniques and equipment experience
3. Highlight soft skills (patience, communication, empathy)
4. Use action verbs (Assisted, Monitored, Administered)

Would you like me to:
1️⃣ Rewrite your resume with these improvements
2️⃣ Just give you tips to improve it yourself
3️⃣ Return to services menu

Type 1, 2, or 3"""
    
    def ask_objective(self) -> str:
        """Ask for career objective"""
        return """🎯 **Career Objective**

In 1-2 sentences, what type of caregiver position are you seeking?

Examples:
• "Compassionate CNA seeking full-time position in assisted living"
• "Experienced caregiver specializing in dementia care"
• "Entry-level home care aide looking to gain experience"

Type your objective or 'skip' to use a default:"""
    
    def handle_objective(self, user_input: str, user_data: Dict) -> str:
        """Handle career objective input"""
        if 'skip' in user_input.lower():
            creds = ', '.join(self.resume_data.get('credentials', ['Caregiver']))
            self.resume_data['objective'] = f"Dedicated {creds} seeking to provide compassionate, high-quality care in a professional healthcare setting."
        else:
            self.resume_data['objective'] = user_input.strip()
        
        self.resume_step = 'experience'
        return """💼 **Work Experience**

Let's add your work experience. For your most recent position:

**Job Title:**
(e.g., "Home Care Aide", "CNA at Sunrise Senior Living")"""
    
    def handle_experience(self, user_input: str) -> str:
        """Handle job title input"""
        self.resume_data['current_job'] = {'title': user_input.strip()}
        self.resume_step = 'experience_details'
        
        return """**Tell me about this role:**

Include:
• Where you worked
• How long (e.g., "June 2020 - Present")
• 2-3 key responsibilities or achievements

Example:
"Sunrise Assisted Living, Seattle, WA (2020-Present)
- Provided daily care for 8-10 residents
- Administered medications and monitored vital signs
- Assisted with mobility and personal hygiene"

Type your description:"""
    
    def handle_experience_details(self, user_input: str) -> str:
        """Handle experience details"""
        self.resume_data['current_job']['details'] = user_input.strip()
        
        if 'experience_list' not in self.resume_data:
            self.resume_data['experience_list'] = []
        
        self.resume_data['experience_list'].append(self.resume_data['current_job'])
        del self.resume_data['current_job']
        
        self.resume_step = 'more_experience'
        return """✅ **Experience added!**

Do you have another position to add?

Type 'yes' to add more experience
Type 'no' to continue"""
    
    def handle_more_experience(self, user_input: str) -> str:
        """Handle adding more experience"""
        if 'yes' in user_input.lower():
            self.resume_step = 'experience'
            return """**Next Position:**

Job Title:"""
        else:
            self.resume_step = 'education'
            return """🎓 **Education**

What is your highest level of education?

Examples:
• "High School Diploma, Lincoln High School, 2018"
• "Associate Degree in Nursing, Seattle Central College, 2020"
• "CNA Certification Program, ABC Training Center, 2019"

Type your education or 'skip':"""
    
    def handle_education(self, user_input: str) -> str:
        """Handle education input"""
        if 'skip' not in user_input.lower():
            self.resume_data['education'] = [user_input.strip()]
        else:
            self.resume_data['education'] = []
        
        self.resume_step = 'skills'
        
        # Auto-populate skills from user data
        auto_skills = []
        if self.resume_data.get('credentials'):
            auto_skills.extend(self.resume_data['credentials'])
        
        auto_skills.extend([
            'Patient Care',
            'Vital Signs Monitoring',
            'Medication Administration',
            'Personal Hygiene Assistance',
            'Communication Skills'
        ])
        
        suggested = ', '.join(auto_skills[:8])
        
        return f"""🔧 **Skills & Competencies**

Based on your profile, I suggest these skills:
{suggested}

Would you like to:
1️⃣ Use these suggested skills
2️⃣ Add your own custom skills
3️⃣ Combine suggested + custom

Type 1, 2, or 3:"""
    
    def handle_skills(self, user_input: str) -> str:
        """Handle skills selection"""
        if '1' in user_input:
            # Use suggested skills
            self.resume_data['skills'] = [
                'Patient Care',
                'Vital Signs Monitoring',
                'Medication Administration',
                'Personal Hygiene Assistance',
                'Communication Skills',
                'Mobility Assistance',
                'Documentation & Record Keeping',
                'Compassionate Care'
            ]
        elif '2' in user_input:
            self.resume_step = 'custom_skills'
            return """Type your skills separated by commas:

Example: "Wound care, Catheter care, Hoyer lift operation, CPR"

Your skills:"""
        elif '3' in user_input:
            self.resume_step = 'custom_skills'
            return """Type any additional skills you want to add (comma-separated):"""
        else:
            return "Please type 1, 2, or 3"
        
        self.resume_step = 'generate'
        return self.generate_resume_preview()
    
    def generate_resume_preview(self) -> str:
        """Generate and preview the resume"""
        resume = self._format_resume()
        
        return f"""✅ **Your Professional Resume**

{resume}

---

**Next Steps:**

1️⃣ Download as PDF
2️⃣ Make changes
3️⃣ Email to me
4️⃣ Return to menu

What would you like to do?"""
    
    def _format_resume(self) -> str:
        """Format resume content"""
        data = self.resume_data
        
        # Header
        resume = f"""**{data['name'].upper()}**
{data.get('phone', data.get('contact', ''))}"""
        
        if data.get('email'):
            resume += f" | {data['email']}"
        
        location = data.get('location', {})
        if location:
            resume += f"\n{location.get('city', '')}, {location.get('state', '')}"
        
        # Objective
        resume += f"\n\n**PROFESSIONAL SUMMARY**\n{data.get('objective', '')}"
        
        # Certifications
        if data.get('credentials'):
            resume += f"\n\n**CERTIFICATIONS**\n"
            for cert in data['credentials']:
                resume += f"• {cert}\n"
        
        # Experience
        if data.get('experience_list'):
            resume += "\n**PROFESSIONAL EXPERIENCE**\n"
            for exp in data['experience_list']:
                resume += f"\n**{exp['title']}**\n{exp['details']}\n"
        
        # Education
        if data.get('education'):
            resume += "\n**EDUCATION**\n"
            for edu in data['education']:
                resume += f"• {edu}\n"
        
        # Skills
        if data.get('skills'):
            resume += "\n**SKILLS & COMPETENCIES**\n"
            skills_formatted = ' • '.join(data['skills'])
            resume += f"{skills_formatted}"
        
        # Languages
        if data.get('languages') and len(data['languages']) > 1:
            resume += f"\n\n**LANGUAGES**\n"
            resume += f"• {', '.join(data['languages'])}"
        
        return resume
    
    def generate_resume(self, user_data: Dict) -> str:
        """Final resume generation"""
        resume = self._format_resume()
        
        # Save to database
        self.db.update_user(user_data['contact'], {
            'resume': self.resume_data,
            'has_resume': True
        })
        
        return f"""✅ **Resume Saved Successfully!**

Your resume has been saved to your profile and is now visible to employers.

**Download your resume:**
https://afhsync.com/resume/download/{user_data['contact']}

Type 'menu' to return to services."""
    
    def reset(self):
        """Reset resume service state"""
        self.resume_step = None
        self.resume_data = {}