"""
Resume Builder for Caregivers
Can either upload existing resume or build from scratch
"""

from enum import Enum
from typing import Dict, List, Optional
import re

class ResumeState(Enum):
    START = "start"
    UPLOAD_OR_BUILD = "upload_or_build"
    UPLOAD_RESUME = "upload_resume"
    ASK_EXPERIENCE_COUNT = "ask_experience_count"
    ASK_JOB_TITLE = "ask_job_title"
    ASK_EMPLOYER = "ask_employer"
    ASK_DATES = "ask_dates"
    ASK_RESPONSIBILITIES = "ask_responsibilities"
    ASK_EDUCATION = "ask_education"
    ASK_SKILLS = "ask_skills"
    ASK_CERTIFICATIONS = "ask_certifications"
    ASK_REFERENCES = "ask_references"
    GENERATE_RESUME = "generate_resume"
    COMPLETE = "complete"

class ResumeBuilder:
    def __init__(self, user_data: Dict):
        self.state = ResumeState.START
        self.user_data = user_data  # Data from main registration
        self.resume_data = {
            'name': user_data.get('name', ''),
            'contact': user_data.get('contact', ''),
            'location': user_data.get('location', ''),
            'credentials': user_data.get('credentials', ''),
            'experience': [],
            'education': [],
            'skills': [],
            'references': []
        }
        self.current_job = {}
        self.current_job_index = 0
        self.total_jobs = 0
        
    def start(self) -> str:
        self.state = ResumeState.UPLOAD_OR_BUILD
        return """Resume Writing Service

Do you have an existing resume you'd like me to improve, or would you like to build one from scratch?

Type 'upload' to upload your resume
Type 'build' to create a new resume"""
    
    def process_message(self, user_input: str) -> str:
        if self.state == ResumeState.UPLOAD_OR_BUILD:
            return self.handle_upload_or_build(user_input)
            
        elif self.state == ResumeState.UPLOAD_RESUME:
            return self.handle_upload(user_input)
            
        elif self.state == ResumeState.ASK_EXPERIENCE_COUNT:
            return self.handle_experience_count(user_input)
            
        elif self.state == ResumeState.ASK_JOB_TITLE:
            return self.handle_job_title(user_input)
            
        elif self.state == ResumeState.ASK_EMPLOYER:
            return self.handle_employer(user_input)
            
        elif self.state == ResumeState.ASK_DATES:
            return self.handle_dates(user_input)
            
        elif self.state == ResumeState.ASK_RESPONSIBILITIES:
            return self.handle_responsibilities(user_input)
            
        elif self.state == ResumeState.ASK_EDUCATION:
            return self.handle_education(user_input)
            
        elif self.state == ResumeState.ASK_SKILLS:
            return self.handle_skills(user_input)
            
        elif self.state == ResumeState.ASK_CERTIFICATIONS:
            return self.handle_certifications(user_input)
            
        elif self.state == ResumeState.ASK_REFERENCES:
            return self.handle_references(user_input)
            
        elif self.state == ResumeState.GENERATE_RESUME:
            return self.generate_resume()
            
        elif self.state == ResumeState.COMPLETE:
            return "Resume complete! Type 'menu' to return to services."
    
    def handle_upload_or_build(self, user_input: str) -> str:
        choice = user_input.lower().strip()
        
        if 'upload' in choice or 'improve' in choice:
            self.state = ResumeState.UPLOAD_RESUME
            return f"Please upload your resume at: https://afhsync.com/resume/upload/{self.user_data.get('contact')}\n\nOnce uploaded, type 'done' to continue."
        
        elif 'build' in choice or 'create' in choice or 'new' in choice:
            self.state = ResumeState.ASK_EXPERIENCE_COUNT
            return "Let's build your resume!\n\nHow many previous jobs would you like to include? (1-5)"
        
        else:
            return "Please type 'upload' or 'build'"
    
    def handle_upload(self, user_input: str) -> str:
        if 'done' in user_input.lower():
            self.state = ResumeState.COMPLETE
            return """Great! I'll review your resume and provide an improved version within 24 hours.

You'll receive it at: {self.user_data.get('contact')}

The improved resume will include:
- ATS-optimized formatting
- Healthcare-specific keywords
- Achievement-focused descriptions
- Professional summary
- Skills highlighting

Type 'menu' to return to services."""
        else:
            return "Please upload your resume and type 'done' when finished."
    
    def handle_experience_count(self, user_input: str) -> str:
        # Extract number
        numbers = re.findall(r'\d+', user_input)
        if numbers:
            count = int(numbers[0])
            if 1 <= count <= 5:
                self.total_jobs = count
                self.current_job_index = 0
                self.state = ResumeState.ASK_JOB_TITLE
                return f"Job 1 of {self.total_jobs}\n\nWhat was your job title?"
        
        return "Please enter a number between 1 and 5"
    
    def handle_job_title(self, user_input: str) -> str:
        self.current_job['title'] = user_input.strip()
        self.state = ResumeState.ASK_EMPLOYER
        return "What was the employer/facility name?"
    
    def handle_employer(self, user_input: str) -> str:
        self.current_job['employer'] = user_input.strip()
        self.state = ResumeState.ASK_DATES
        return "When did you work there? (e.g., Jan 2020 - Present, 2019-2021)"
    
    def handle_dates(self, user_input: str) -> str:
        self.current_job['dates'] = user_input.strip()
        self.state = ResumeState.ASK_RESPONSIBILITIES
        return """What were your main responsibilities?

Please describe 2-3 key duties or achievements. You can type them all at once or send multiple messages.

Type 'done' when finished."""
    
    def handle_responsibilities(self, user_input: str) -> str:
        if 'done' in user_input.lower():
            # Save current job
            self.resume_data['experience'].append(self.current_job.copy())
            self.current_job = {}
            self.current_job_index += 1
            
            # Check if more jobs needed
            if self.current_job_index < self.total_jobs:
                self.state = ResumeState.ASK_JOB_TITLE
                return f"\nJob {self.current_job_index + 1} of {self.total_jobs}\n\nWhat was your job title?"
            else:
                # Move to education
                self.state = ResumeState.ASK_EDUCATION
                return "\nEducation\n\nWhat's your highest level of education? (e.g., High School Diploma, Associate Degree, Bachelor's)"
        
        else:
            # Add responsibility
            if 'responsibilities' not in self.current_job:
                self.current_job['responsibilities'] = []
            self.current_job['responsibilities'].append(user_input.strip())
            return "Got it. Add another responsibility or type 'done' to continue."
    
    def handle_education(self, user_input: str) -> str:
        self.resume_data['education'].append({
            'level': user_input.strip()
        })
        
        self.state = ResumeState.ASK_SKILLS
        return """Skills

What key skills do you have? List them separated by commas.

Examples: Patient care, Medication administration, Vital signs monitoring, CPR, First aid, Documentation"""
    
    def handle_skills(self, user_input: str) -> str:
        # Parse comma-separated skills
        skills = [s.strip() for s in user_input.split(',')]
        self.resume_data['skills'] = skills
        
        self.state = ResumeState.ASK_CERTIFICATIONS
        return f"""Certifications

I see you have: {self.user_data.get('credentials')}

Would you like to add any other certifications? (or type 'none')"""
    
    def handle_certifications(self, user_input: str) -> str:
        if 'none' not in user_input.lower():
            certs = [s.strip() for s in user_input.split(',')]
            self.resume_data['certifications'] = certs
        
        self.state = ResumeState.ASK_REFERENCES
        return """References

Do you have professional references you'd like to include?

Type 'yes' to add references or 'no' to skip"""
    
    def handle_references(self, user_input: str) -> str:
        choice = user_input.lower().strip()
        
        if 'yes' in choice:
            return """Please provide reference information in this format:

Name, Title, Phone/Email

Type 'done' when finished adding references."""
        else:
            self.state = ResumeState.GENERATE_RESUME
            return self.generate_resume()
    
    def generate_resume(self) -> str:
        self.state = ResumeState.COMPLETE
        
        # Generate resume URL
        resume_url = f"https://afhsync.com/resume/view/{self.user_data.get('contact')}"
        
        summary = f"""Resume Complete!

I've created a professional caregiver resume for:
{self.resume_data['name']}

Included:
- {len(self.resume_data['experience'])} work experiences
- {len(self.resume_data['skills'])} key skills
- Education and certifications
- Professional summary optimized for healthcare

View your resume: {resume_url}
Download PDF: {resume_url}/download

Your resume is ATS-optimized and ready to send to employers!

Type 'menu' to return to services."""
        
        # In production: Generate actual PDF using reportlab/weasyprint
        # self._generate_pdf_resume()
        
        return summary
    
    def _generate_pdf_resume(self):
        """Generate actual PDF resume - implement with reportlab"""
        # TODO: Use reportlab or weasyprint to generate professional PDF
        # Include:
        # - Professional header with contact info
        # - Summary section
        # - Experience with bullet points
        # - Education
        # - Skills grid
        # - Certifications
        # - References
        pass

# Usage example
if __name__ == "__main__":
    # Simulated user data from main registration
    user_data = {
        'name': 'John Smith',
        'contact': '2065551234',
        'location': 'Seattle',
        'credentials': 'CNA'
    }
    
    resume_bot = ResumeBuilder(user_data)
    print(resume_bot.start())
    
    while True:
        user_input = input("\nYou: ")
        
        if user_input.lower() in ['exit', 'quit', 'menu']:
            break
        
        response = resume_bot.process_message(user_input)
        print(f"\nBot: {response}")