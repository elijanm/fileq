"""
AFHSync Resume Writing Service
- Resume builder from scratch
- Resume improvement service with Ollama AI
- Professional content enhancement
- PDF generation via WeasyPrint
- Smart input interpretation
"""

from typing import Dict, Optional, List
import logging
import requests
import re
import os
from weasyprint import HTML, CSS
from datetime import datetime

logger = logging.getLogger(__name__)

# Configuration
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://95.110.228.29:8201/v1')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'deepseek-r1:1.5b')


class ResumeService:
    """Handle resume writing and improvement services with AI enhancement"""
    
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
    
    def enhance_with_ai(self, text: str, context: str) -> str:
        """Use Ollama to enhance text quality"""
        try:
            prompt = f"""You are a professional resume writer specializing in healthcare and caregiving positions.

Task: {context}

User's input: "{text}"

Improve this text to be:
- Professional and concise (2-3 sentences max)
- Action-oriented with strong verbs
- Specific and quantifiable where possible
- ATS-friendly (no fancy formatting)
- Relevant to caregiving/healthcare

Return ONLY the improved text, no explanations or comments."""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 200
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                enhanced = result['choices'][0]['message']['content'].strip()
                # Remove quotes if present
                enhanced = enhanced.strip('"\'')
                logger.info(f"AI enhanced text: {text[:30]}... -> {enhanced[:30]}...")
                return enhanced
            else:
                logger.warning(f"AI enhancement failed, using original text")
                return text
                
        except Exception as e:
            logger.error(f"AI enhancement error: {e}")
            return text
    
    def parse_experience_with_ai(self, text: str) -> Dict:
        """Parse unstructured experience text into structured format"""
        try:
            prompt = f"""Extract structured information from this job experience description.

Text: "{text}"

Return ONLY valid JSON with this structure:
{{
    "title": "job title",
    "company": "company name",
    "location": "city, state",
    "duration": "start - end dates",
    "responsibilities": ["bullet 1", "bullet 2", "bullet 3"]
}}

If information is missing, use "Not specified". Keep responsibilities concise and action-oriented."""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 300
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Extract JSON from response
                json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
                if json_match:
                    import json
                    parsed = json.loads(json_match.group())
                    logger.info(f"AI parsed experience successfully")
                    return parsed
            
            # Fallback to basic parsing
            return self._basic_parse_experience(text)
                
        except Exception as e:
            logger.error(f"AI parsing error: {e}")
            return self._basic_parse_experience(text)
    
    def _basic_parse_experience(self, text: str) -> Dict:
        """Basic fallback parsing without AI"""
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        return {
            'title': lines[0] if lines else 'Caregiver',
            'company': 'Not specified',
            'location': 'Not specified',
            'duration': 'Not specified',
            'responsibilities': lines[1:] if len(lines) > 1 else ['Provided quality patient care']
        }
    
    def handle_resume_flow(self, user_input: str, user_data: Dict) -> str:
        """Handle the resume building/improvement flow"""
        user_lower = user_input.lower().strip()
        
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
        
        elif self.resume_step == 'upload_existing':
            return self.handle_existing_resume(user_input, user_data)
        
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
        
        elif self.resume_step == 'custom_skills':
            return self.handle_custom_skills(user_input)
        
        elif self.resume_step == 'generate':
            return self.handle_generate_choice(user_input, user_data)
        
        return "Something went wrong. Type 'menu' to return to services."
    
    def _extract_user_data(self, user_data: Dict) -> Dict:
        """Extract relevant user data for resume"""
        return {
            'name': user_data.get('name', ''),
            'contact': user_data.get('contact', ''),
            'email': user_data.get('email', user_data.get('contact') if '@' in user_data.get('contact', '') else ''),
            'phone': user_data.get('phone', user_data.get('contact') if user_data.get('contact_type') == 'phone' else ''),
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

In your own words, what type of caregiver position are you seeking?

Examples:
• "I want to work with elderly patients in assisted living"
• "Looking for home care position with dementia patients"
• "Seeking full-time CNA role at nursing home"

Don't worry about making it perfect - I'll help polish it!

Type your objective:"""
    
    def handle_objective(self, user_input: str, user_data: Dict) -> str:
        """Handle career objective input with AI enhancement"""
        if 'skip' in user_input.lower():
            creds = ', '.join(self.resume_data.get('credentials', ['Caregiver']))
            self.resume_data['objective'] = f"Dedicated {creds} seeking to provide compassionate, high-quality care in a professional healthcare setting."
        else:
            # Enhance with AI
            enhanced = self.enhance_with_ai(
                user_input,
                "Improve this career objective for a caregiver resume. Make it professional and compelling."
            )
            self.resume_data['objective'] = enhanced
            
            if enhanced != user_input:
                self.resume_step = 'experience'
                return f"""✅ **Enhanced Objective:**

"{enhanced}"

💼 **Work Experience**

Now let's add your work experience. Describe your most recent position in your own words:

Example: "I worked as a home health aide at ABC Care from 2020 to now, helping 5 elderly clients with daily activities"

Your experience:"""
        
        self.resume_step = 'experience'
        return """💼 **Work Experience**

Describe your most recent position in your own words. Include:
• Job title and company
• When you worked there
• What you did

Type your description:"""
    
    def handle_experience(self, user_input: str) -> str:
        """Handle experience input with AI parsing"""
        if 'skip' in user_input.lower() or 'none' in user_input.lower():
            self.resume_step = 'education'
            return self.ask_education()
        
        # Parse with AI
        parsed = self.parse_experience_with_ai(user_input)
        self.resume_data['current_job'] = parsed
        
        # Show parsed version for confirmation
        self.resume_step = 'experience_details'
        
        formatted = self._format_experience(parsed)
        
        return f"""✅ **I've structured your experience:**

{formatted}

Is this correct?
Type 'yes' to confirm
Type 'no' to re-enter
Type 'edit' to make changes"""
    
    def _format_experience(self, exp: Dict) -> str:
        """Format experience for display"""
        output = f"**{exp.get('title', 'Position')}**\n"
        output += f"{exp.get('company', '')}"
        
        if exp.get('location') and exp['location'] != 'Not specified':
            output += f", {exp['location']}"
        
        if exp.get('duration') and exp['duration'] != 'Not specified':
            output += f" ({exp['duration']})"
        
        output += "\n"
        
        if exp.get('responsibilities'):
            for resp in exp['responsibilities']:
                output += f"• {resp}\n"
        
        return output
    
    def handle_experience_details(self, user_input: str) -> str:
        """Confirm or edit experience"""
        user_lower = user_input.lower().strip()
        
        if 'yes' in user_lower:
            if 'experience_list' not in self.resume_data:
                self.resume_data['experience_list'] = []
            
            self.resume_data['experience_list'].append(self.resume_data['current_job'])
            del self.resume_data['current_job']
            
            self.resume_step = 'more_experience'
            return """✅ **Experience added!**

Do you have another position to add?

Type 'yes' to add more
Type 'no' to continue"""
        
        elif 'no' in user_lower:
            self.resume_step = 'experience'
            return "Let's try again. Describe your work experience:"
        
        elif 'edit' in user_lower:
            return """What would you like to change? Type:
• 'title' - Change job title
• 'company' - Change company name
• 'dates' - Change dates
• 'duties' - Change responsibilities"""
        
        else:
            return "Please type 'yes' to confirm, 'no' to re-enter, or 'edit' to make changes."
    
    def handle_more_experience(self, user_input: str) -> str:
        """Handle adding more experience"""
        if 'yes' in user_input.lower():
            self.resume_step = 'experience'
            return "Describe your next position:"
        else:
            self.resume_step = 'education'
            return self.ask_education()
    
    def ask_education(self) -> str:
        """Ask for education"""
        return """🎓 **Education**

What is your highest level of education?

Examples:
• "High school diploma from Lincoln High"
• "CNA certification from Seattle Training Center 2020"
• "Some college at community college"

Type your education or 'skip':"""
    
    def handle_education(self, user_input: str) -> str:
        """Handle education input"""
        if 'skip' not in user_input.lower():
            # Enhance with AI
            enhanced = self.enhance_with_ai(
                user_input,
                "Format this education entry professionally for a resume."
            )
            self.resume_data['education'] = [enhanced]
        else:
            self.resume_data['education'] = []
        
        self.resume_step = 'skills'
        
        # Auto-populate skills
        auto_skills = list(set([
            'Patient Care',
            'Vital Signs Monitoring',
            'Personal Hygiene Assistance',
            'Medication Administration',
            'Communication',
            'Documentation',
            'Compassionate Care',
            'Mobility Assistance'
        ] + self.resume_data.get('credentials', [])))
        
        suggested = ', '.join(auto_skills[:8])
        
        return f"""🔧 **Skills & Competencies**

Based on your profile, here are suggested skills:
{suggested}

Would you like to:
1️⃣ Use these suggested skills
2️⃣ Add your own skills
3️⃣ Combine both

Type 1, 2, or 3:"""
    
    def handle_skills(self, user_input: str) -> str:
        """Handle skills selection"""
        if '1' in user_input:
            self.resume_data['skills'] = [
                'Patient Care & Assessment',
                'Vital Signs Monitoring',
                'Medication Administration',
                'Personal Hygiene Assistance',
                'Mobility & Transfer Assistance',
                'Documentation & Record Keeping',
                'Communication & Interpersonal Skills',
                'Compassionate & Empathetic Care'
            ]
            self.resume_step = 'generate'
            return self.generate_resume_preview()
            
        elif '2' in user_input or '3' in user_input:
            self.resume_step = 'custom_skills'
            return """Type your skills separated by commas:

Example: "Wound care, Hoyer lift, Catheter care, Dementia care"

Your skills:"""
        else:
            return "Please type 1, 2, or 3"
    
    def handle_custom_skills(self, user_input: str) -> str:
        """Handle custom skills input"""
        skills = [s.strip() for s in user_input.split(',') if s.strip()]
        
        if self.resume_step == 'custom_skills':
            self.resume_data['skills'] = skills
            self.resume_step = 'generate'
            return self.generate_resume_preview()
        
        return "Please enter skills separated by commas."
    
    def generate_resume_preview(self) -> str:
        """Generate and preview the resume"""
        resume_text = self._format_resume_text()
        
        return f"""✅ **Your Professional Resume Preview**

{resume_text}

---

**Next Steps:**

1️⃣ Download as PDF
2️⃣ Make changes
3️⃣ Email to me
4️⃣ Save and return to menu

What would you like to do?"""
    
    def handle_generate_choice(self, user_input: str, user_data: Dict) -> str:
        """Handle post-generation choices"""
        if '1' in user_input:
            return self.generate_pdf(user_data)
        elif '2' in user_input:
            return "What would you like to change? Type: objective, experience, education, or skills"
        elif '3' in user_input:
            email = user_data.get('email', user_data.get('contact'))
            return f"Resume will be emailed to: {email}\nType 'confirm' to send"
        elif '4' in user_input:
            self.save_resume(user_data)
            self.reset()
            return "Resume saved! Type 'menu' to return to services."
        else:
            return "Please type 1, 2, 3, or 4"
    
    def _format_resume_text(self) -> str:
        """Format resume as plain text"""
        data = self.resume_data
        
        resume = f"{data['name'].upper()}\n"
        resume += f"{data.get('phone', data.get('contact', ''))}"
        
        if data.get('email') and data['email'] != data.get('phone'):
            resume += f" | {data['email']}"
        
        location = data.get('location', {})
        if location:
            resume += f"\n{location.get('city', '')}, {location.get('state', '')}"
        
        resume += f"\n\n{'='*60}\n"
        resume += f"\nPROFESSIONAL SUMMARY\n{data.get('objective', '')}\n"
        
        if data.get('credentials'):
            resume += f"\nCERTIFICATIONS\n"
            for cert in data['credentials']:
                resume += f"• {cert}\n"
        
        if data.get('experience_list'):
            resume += "\nPROFESSIONAL EXPERIENCE\n"
            for exp in data['experience_list']:
                resume += f"\n{self._format_experience(exp)}"
        
        if data.get('education'):
            resume += "\nEDUCATION\n"
            for edu in data['education']:
                resume += f"• {edu}\n"
        
        if data.get('skills'):
            resume += "\nSKILLS & COMPETENCIES\n"
            for skill in data['skills']:
                resume += f"• {skill}\n"
        
        if data.get('languages') and len(data['languages']) > 1:
            resume += f"\nLANGUAGES\n• {', '.join(data['languages'])}"
        
        return resume
    
    def generate_pdf(self, user_data: Dict) -> str:
        """Generate PDF using WeasyPrint"""
        try:
            html_content = self._generate_html_resume()
            
            # Generate PDF
            pdf_filename = f"resume_{user_data['contact']}_{datetime.now().strftime('%Y%m%d')}.pdf"
            pdf_path = f"/tmp/{pdf_filename}"
            
            HTML(string=html_content).write_pdf(pdf_path)
            
            # Save to database
            self.save_resume(user_data)
            
            logger.info(f"PDF generated: {pdf_path}")
            
            return f"""✅ **PDF Generated Successfully!**

Your professional resume has been created.

**Download:** https://afhsync.com/resume/download/{pdf_filename}

The PDF has been saved to your profile and is now visible to employers.

Type 'menu' to return to services."""
            
        except Exception as e:
            logger.error(f"PDF generation error: {e}")
            return f"""⚠️ PDF generation encountered an issue, but your resume has been saved.

**Text version:** https://afhsync.com/resume/view/{user_data['contact']}

Type 'menu' to return to services."""
    
    def _generate_html_resume(self) -> str:
        """Generate HTML for PDF conversion"""
        data = self.resume_data
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: letter;
            margin: 0.75in;
        }}
        body {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            font-size: 11pt;
            line-height: 1.4;
            color: #333;
        }}
        h1 {{
            font-size: 24pt;
            margin-bottom: 5px;
            color: #2c3e50;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        h2 {{
            font-size: 14pt;
            margin-top: 20px;
            margin-bottom: 10px;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 3px;
            text-transform: uppercase;
        }}
        .contact {{
            font-size: 10pt;
            margin-bottom: 20px;
            color: #555;
        }}
        .section {{
            margin-bottom: 15px;
        }}
        .job-title {{
            font-weight: bold;
            font-size: 12pt;
            margin-top: 10px;
        }}
        .job-details {{
            font-size: 10pt;
            color: #666;
            margin-bottom: 5px;
        }}
        ul {{
            margin: 5px 0;
            padding-left: 20px;
        }}
        li {{
            margin-bottom: 3px;
        }}
        .skills {{
            display: flex;
            flex-wrap: wrap;
        }}
        .skill-item {{
            width: 48%;
            margin-bottom: 5px;
        }}
    </style>
</head>
<body>
    <h1>{data['name']}</h1>
    <div class="contact">
        {data.get('phone', data.get('contact', ''))}"""
        
        if data.get('email') and data['email'] != data.get('phone'):
            html += f" | {data['email']}"
        
        location = data.get('location', {})
        if location:
            html += f" | {location.get('city', '')}, {location.get('state', '')}"
        
        html += """
    </div>
    
    <div class="section">
        <h2>Professional Summary</h2>
        <p>""" + data.get('objective', '') + """</p>
    </div>"""
        
        if data.get('credentials'):
            html += """
    <div class="section">
        <h2>Certifications</h2>
        <ul>"""
            for cert in data['credentials']:
                html += f"<li>{cert}</li>"
            html += "</ul></div>"
        
        if data.get('experience_list'):
            html += """
    <div class="section">
        <h2>Professional Experience</h2>"""
            for exp in data['experience_list']:
                html += f"""
        <div class="job-title">{exp.get('title', '')}</div>
        <div class="job-details">{exp.get('company', '')}"""
                
                if exp.get('location') and exp['location'] != 'Not specified':
                    html += f", {exp['location']}"
                if exp.get('duration') and exp['duration'] != 'Not specified':
                    html += f" | {exp['duration']}"
                
                html += "</div><ul>"
                
                if exp.get('responsibilities'):
                    for resp in exp['responsibilities']:
                        html += f"<li>{resp}</li>"
                
                html += "</ul>"
            html += "</div>"
        
        if data.get('education'):
            html += """
    <div class="section">
        <h2>Education</h2>
        <ul>"""
            for edu in data['education']:
                html += f"<li>{edu}</li>"
            html += "</ul></div>"
        
        if data.get('skills'):
            html += """
    <div class="section">
        <h2>Skills & Competencies</h2>
        <div class="skills">"""
            for skill in data['skills']:
                html += f'<div class="skill-item">• {skill}</div>'
            html += "</div></div>"
        
        if data.get('languages') and len(data['languages']) > 1:
            html += """
    <div class="section">
        <h2>Languages</h2>
        <p>""" + ', '.join(data['languages']) + """</p>
    </div>"""
        
        html += """
</body>
</html>"""
        
        return html
    
    def save_resume(self, user_data: Dict):
        """Save resume to database"""
        self.db.update_user(user_data['contact'], {
            'resume': self.resume_data,
            'has_resume': True,
            'resume_updated_at': datetime.utcnow()
        })
        logger.info(f"Resume saved for {user_data['contact']}")
    
    def reset(self):
        """Reset resume service state"""
        self.resume_step = None
        self.resume_data = {}