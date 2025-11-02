"""
AFHSync Smart Resume Service - Streamlined Version
- Auto-populates from profile and public data
- Facility/position auto-enrichment
- "Generate for me" autopilot mode
- Skip known questions
"""

from typing import Dict, Optional, List
import logging
import requests
import re
import os
from weasyprint import HTML
from datetime import datetime

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://95.110.228.29:8201/v1')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'deepseek-r1:1.5b')


class ResumeService:
    """Smart resume builder with auto-population and facility enrichment"""
    
    def __init__(self, db_handler):
        self.db = db_handler
        self.resume_step = None
        self.resume_data = {}
        self.validation_results = {}
    
    def start_resume_service(self, user_data: Dict) -> str:
        """Check for existing resume and offer options"""
        existing_resume = user_data.get('resume', {})
        
        if existing_resume and existing_resume.get('experience'):
            last_updated = existing_resume.get('last_updated', 'recently')
            return f"""**Resume Found**

Last updated: {last_updated}

[View/Download PDF](#action:resume_download)
[Update resume](#action:resume_update)
[Build new from scratch](#action:resume_new)"""
        
        # New resume - offer quick generation
        return """**Resume Builder**

I can help you create a professional resume.

[Generate resume for me](#action:auto_generate) - AI builds it automatically
[Build step-by-step](#action:manual_build) - Answer questions yourself"""
    
    def handle_resume_flow(self, user_input: str, user_data: Dict) -> str:
        """Streamlined resume flow with auto-population"""
        user_lower = user_input.lower().strip()
        
        # Route based on choice
        if not self.resume_step:
            if 'auto' in user_lower or 'generate' in user_lower or 'for me' in user_lower:
                return self.auto_generate_resume(user_data)
            elif 'manual' in user_lower or 'step' in user_lower:
                return self.start_manual_build(user_data)
            elif 'download' in user_lower:
                return self.generate_pdf(user_data)
            elif 'update' in user_lower:
                return self.update_existing_resume(user_data)
            elif 'new' in user_lower:
                self.resume_data = {}
                return self.start_manual_build(user_data)
        
        # Handle manual build steps
        return self._handle_manual_step(user_input, user_data)
    
    # ==================== AUTO-GENERATION MODE ====================
    
    def auto_generate_resume(self, user_data: Dict) -> str:
        """AI auto-generates entire resume from profile data"""
        logger.info(f"Auto-generating resume for {user_data.get('name')}")
        
        # Initialize from profile
        self.resume_data = self._initialize_from_profile(user_data)
        
        # Check what's missing
        missing = self._check_missing_critical_data()
        
        if missing:
            # Ask only critical missing questions
            self.resume_step = 'quick_fill'
            return f"""**Quick Setup**

I need just a few details:

{self._format_missing_questions(missing)}

Type your answers (or 'skip' to auto-fill):"""
        
        # Generate everything with AI
        return self._full_auto_generation(user_data)
    
    def _initialize_from_profile(self, user_data: Dict) -> Dict:
        """Extract all available data from profile"""
        return {
            'name': user_data.get('name', ''),
            'phone': user_data.get('phone', user_data.get('contact', '')),
            'email': user_data.get('email', user_data.get('contact', '')),
            'city': user_data.get('primary_location', {}).get('city', ''),
            'state': user_data.get('primary_location', {}).get('state', 'WA'),
            'certifications': user_data.get('credentials', []),
            'languages': user_data.get('detailed_preferences', {}).get('languages', ['English']),
            'availability': user_data.get('availability', {}),
            'experience': [],
            'education': [],
            'skills': [],
            'objective': ''
        }
    
    def _check_missing_critical_data(self) -> List[str]:
        """Check what critical data is missing"""
        missing = []
        data = self.resume_data
        
        if not data.get('name'):
            missing.append('name')
        if not data.get('phone') and not data.get('email'):
            missing.append('contact')
        if not data.get('certifications'):
            missing.append('certifications')
        
        return missing
    
    def _format_missing_questions(self, missing: List[str]) -> str:
        """Format questions for missing data"""
        questions = {
            'name': "• Your full name",
            'contact': "• Phone number or email",
            'certifications': "• Your certifications (CNA, HCA, CPR, etc.)"
        }
        
        return '\n'.join([questions[m] for m in missing if m in questions])
    
    def _full_auto_generation(self, user_data: Dict) -> str:
        """Generate complete resume using AI"""
        try:
            # Generate objective
            self.resume_data['objective'] = self._ai_generate_objective()
            
            # Generate experience from past jobs (if any in profile)
            self.resume_data['experience'] = self._ai_generate_experience()
            
            # Generate skills
            self.resume_data['skills'] = self._ai_generate_skills()
            
            # Generate education
            self.resume_data['education'] = self._ai_generate_education()
            
            # Save
            self._auto_save_resume(user_data)
            
            return f"""**Resume Generated!**

I've created a professional resume using your profile data.

[View preview](#action:preview_resume)
[Download PDF](#action:download_pdf)
[Make edits](#action:edit_resume)"""
            
        except Exception as e:
            logger.error(f"Auto-generation error: {e}")
            return "Auto-generation encountered an issue. Let's build it step-by-step instead."
    
    # ==================== FACILITY AUTO-ENRICHMENT ====================
    
    def enrich_from_facility(self, job_title: str, facility_name: str, location: str) -> Dict:
        """Auto-enrich experience from facility and position data"""
        try:
            prompt = f"""Generate professional resume responsibilities for this position:

Job Title: {job_title}
Facility: {facility_name}
Location: {location}

Based on typical {job_title} duties at {facility_name}, generate 4-5 professional bullet points with:
- Strong action verbs
- Specific caregiving tasks
- Quantifiable metrics where appropriate
- Industry-standard terminology

Return only the bullet points, one per line."""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5,
                    "max_tokens": 400
                },
                timeout=20
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                
                responsibilities = []
                for line in content.split('\n'):
                    line = re.sub(r'^[-•*]\s*', '', line).strip()
                    if len(line) > 15:
                        if not line.endswith('.'):
                            line += '.'
                        responsibilities.append(line)
                
                return {
                    'title': job_title,
                    'company': facility_name,
                    'location': location,
                    'responsibilities': responsibilities[:5]
                }
            
            return self._basic_facility_template(job_title, facility_name, location)
            
        except Exception as e:
            logger.error(f"Facility enrichment error: {e}")
            return self._basic_facility_template(job_title, facility_name, location)
    
    def _basic_facility_template(self, job_title: str, facility: str, location: str) -> Dict:
        """Fallback template for facility enrichment"""
        templates = {
            'cna': [
                "Provided direct patient care to 8+ residents daily including bathing, dressing, and grooming.",
                "Monitored and recorded vital signs every 2-4 hours and reported changes to nursing staff.",
                "Assisted with mobility and transfers using proper body mechanics and safety protocols.",
                "Maintained accurate documentation of patient care activities and observations."
            ],
            'hca': [
                "Provided in-home care to elderly clients including meal preparation and light housekeeping.",
                "Assisted with activities of daily living and medication reminders.",
                "Monitored client wellbeing and communicated changes to family and healthcare team.",
                "Maintained safe and clean living environment for clients."
            ],
            'caregiver': [
                "Provided compassionate care to patients with various medical conditions.",
                "Assisted with personal care needs and daily activities.",
                "Monitored patient condition and reported concerns to medical staff.",
                "Maintained professional and empathetic relationship with patients and families."
            ]
        }
        
        job_key = 'cna' if 'cna' in job_title.lower() else 'hca' if 'hca' in job_title.lower() else 'caregiver'
        
        return {
            'title': job_title,
            'company': facility,
            'location': location,
            'responsibilities': templates[job_key]
        }
    
    # ==================== STREAMLINED MANUAL BUILD ====================
    
    def start_manual_build(self, user_data: Dict) -> str:
        """Start streamlined manual build - skip known data"""
        self.resume_data = self._initialize_from_profile(user_data)
        
        # Skip to first unknown field
        if not self.resume_data.get('objective'):
            self.resume_step = 'objective'
            return """**Career Goal**

What type of caregiver position are you seeking?

Example: "CNA position in assisted living"

Your goal:"""
        
        if not self.resume_data.get('experience'):
            self.resume_step = 'experience_quick'
            return self._ask_experience_quick()
        
        # All basic data exists
        return self._full_auto_generation(user_data)
    
    def _ask_experience_quick(self) -> str:
        """Quick experience collection with auto-enrichment"""
        return """**Work Experience**

Tell me about your most recent position:

Format: [Job Title] at [Facility Name], [City]

Example: "CNA at Sunrise Senior Living, Seattle"

Your position:"""
    
    def _handle_manual_step(self, user_input: str, user_data: Dict) -> str:
        """Handle manual build steps"""
        
        if self.resume_step == 'objective':
            self.resume_data['objective'] = self._enhance_text(user_input, "Make this career objective professional")
            self.resume_step = 'experience_quick'
            return self._ask_experience_quick()
        
        elif self.resume_step == 'experience_quick':
            # Parse: "CNA at Sunrise, Seattle"
            exp = self._parse_quick_experience(user_input)
            
            if exp:
                # Auto-enrich from facility
                enriched = self.enrich_from_facility(
                    exp['title'],
                    exp['company'],
                    exp.get('location', self.resume_data.get('city', ''))
                )
                
                enriched['duration'] = "Present"  # Can ask for dates if needed
                self.resume_data['experience'].append(enriched)
                
                return f"""**Experience Added**

{enriched['title']} at {enriched['company']}

Responsibilities auto-generated. Add another?

[Yes](#action:add_more_exp)
[No, finish resume](#action:finish_resume)"""
            else:
                return "Please use format: [Job Title] at [Facility], [City]"
        
        elif self.resume_step == 'finish':
            return self._full_auto_generation(user_data)
        
        return "Something went wrong. Type 'menu' to return."
    
    def _parse_quick_experience(self, text: str) -> Optional[Dict]:
        """Parse quick experience format"""
        # Pattern: "CNA at Sunrise Senior Living, Seattle"
        match = re.search(r'(.+?)\s+at\s+(.+?)(?:,\s*(.+))?$', text, re.IGNORECASE)
        
        if match:
            return {
                'title': match.group(1).strip().title(),
                'company': match.group(2).strip(),
                'location': match.group(3).strip() if match.group(3) else ''
            }
        return None
    
    # ==================== AI GENERATORS ====================
    
    def _ai_generate_objective(self) -> str:
        """Generate career objective from profile"""
        certs = ', '.join(self.resume_data.get('certifications', ['caregiver']))
        city = self.resume_data.get('city', 'the area')
        
        return f"Compassionate {certs} seeking a position providing quality patient care in {city}. Committed to delivering professional, empathetic care that improves patient quality of life."
    
    def _ai_generate_experience(self) -> List[Dict]:
        """Generate experience entries if none exist"""
        # If user has no experience, create entry-level template
        if not self.resume_data.get('certifications'):
            return []
        
        cert = self.resume_data['certifications'][0]
        city = self.resume_data.get('city', 'local area')
        
        return [{
            'title': cert,
            'company': f"{cert} Experience",
            'location': city,
            'duration': 'Recent',
            'responsibilities': [
                f"Completed {cert} training and certification program.",
                "Gained hands-on experience in patient care fundamentals.",
                "Demonstrated proficiency in vital signs monitoring and documentation.",
                "Provided compassionate care under clinical supervision."
            ]
        }]
    
    def _ai_generate_skills(self) -> List[str]:
        """Generate skills from certifications"""
        base_skills = [
            'Patient Care',
            'Vital Signs Monitoring',
            'ADL Assistance',
            'Documentation',
            'Communication',
            'Compassionate Care'
        ]
        
        certs = self.resume_data.get('certifications', [])
        if any('CNA' in c for c in certs):
            base_skills.extend(['Medication Administration', 'Wound Care'])
        if any('CPR' in c for c in certs):
            base_skills.append('CPR/First Aid')
        
        return base_skills[:10]
    
    def _ai_generate_education(self) -> List[str]:
        """Generate education from certifications"""
        education = []
        for cert in self.resume_data.get('certifications', []):
            education.append(f"{cert} Certification, Professional Training")
        
        if not education:
            education.append("High School Diploma or equivalent")
        
        return education
    
    def _enhance_text(self, text: str, instruction: str) -> str:
        """Quick AI text enhancement"""
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": f"{instruction}: {text}"}],
                    "temperature": 0.3,
                    "max_tokens": 150
                },
                timeout=8
            )
            
            if response.status_code == 200:
                enhanced = response.json()['choices'][0]['message']['content'].strip()
                enhanced = re.sub(r'<think>.*?</think>', '', enhanced, flags=re.DOTALL)
                enhanced = re.sub(r'^["\'`]+|["\'`]+$', '', enhanced).strip()
                if 10 < len(enhanced) < 500:
                    return enhanced
            
            return text
        except:
            return text
    
    # ==================== PDF GENERATION ====================
    
    def generate_pdf(self, user_data: Dict) -> str:
        """Generate PDF quickly"""
        try:
            if not self.resume_data.get('experience'):
                self.resume_data = user_data.get('resume', self.resume_data)
            
            html = self._generate_html_resume()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            pdf_filename = f"resume_{user_data.get('contact', 'user')}_{timestamp}.pdf"
            pdf_path = f"/tmp/{pdf_filename}"
            
            HTML(string=html).write_pdf(pdf_path)
            
            self._auto_save_resume(user_data)
            
            logger.info(f"PDF generated: {pdf_path}")
            
            return f"""**Resume Ready**

Download: /api/resume/download/{pdf_filename}

[Return to menu](#action:menu)"""
            
        except Exception as e:
            logger.error(f"PDF error: {e}")
            return "PDF generation failed. Contact support."
    
    def _generate_html_resume(self) -> str:
        """Generate clean HTML resume"""
        data = self.resume_data
        
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
@page {{ size: letter; margin: 0.75in; }}
body {{ font-family: Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #2c3e50; }}
h1 {{ font-size: 24pt; margin: 0 0 8px 0; color: #1a252f; border-bottom: 3px solid #3498db; padding-bottom: 8px; }}
h2 {{ font-size: 13pt; margin: 18px 0 8px 0; color: #2c3e50; border-bottom: 2px solid #95a5a6; padding-bottom: 4px; }}
.contact {{ font-size: 10pt; margin-bottom: 18px; text-align: center; color: #555; }}
.job-title {{ font-weight: bold; font-size: 12pt; margin-top: 10px; }}
.job-details {{ font-size: 10pt; color: #7f8c8d; margin-bottom: 6px; font-style: italic; }}
ul {{ margin: 5px 0 10px 0; padding-left: 20px; }}
li {{ margin-bottom: 4px; }}
.watermark {{ position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%) rotate(-45deg); font-size: 100pt; font-weight: bold; color: rgba(220, 220, 220, 0.2); z-index: -1; }}
</style>
</head>
<body>
<div class="watermark">UNPAID VERSION</div>
<h1>{data['name'].upper()}</h1>
<div class="contact">{data.get('phone', '')} | {data.get('email', '')} | {data.get('city', '')}, {data.get('state', '')}</div>
<p>{data.get('objective', '')}</p>"""
        
        if data.get('certifications'):
            html += '<h2>Certifications</h2><ul>'
            for cert in data['certifications']:
                html += f'<li>{cert}</li>'
            html += '</ul>'
        
        if data.get('experience'):
            html += '<h2>Experience</h2>'
            for exp in data['experience']:
                html += f'''<div class="job-title">{exp['title']}</div>
<div class="job-details">{exp['company']} | {exp.get('location', '')} | {exp.get('duration', '')}</div><ul>'''
                for resp in exp.get('responsibilities', []):
                    html += f'<li>{resp}</li>'
                html += '</ul>'
        
        if data.get('education'):
            html += '<h2>Education</h2><ul>'
            for edu in data['education']:
                html += f'<li>{edu}</li>'
            html += '</ul>'
        
        if data.get('skills'):
            html += '<h2>Skills</h2><ul>'
            for skill in data['skills']:
                html += f'<li>{skill}</li>'
            html += '</ul>'
        
        html += '</body></html>'
        return html
    
    def _auto_save_resume(self, user_data: Dict):
        """Save resume to database"""
        try:
            self.db.update_user(user_data.get('contact'), {
                'resume': self.resume_data,
                'has_resume': True,
                'resume_updated_at': datetime.utcnow()
            })
            logger.info(f"Resume saved for {user_data.get('name')}")
        except Exception as e:
            logger.error(f"Save error: {e}")
    
    def update_existing_resume(self, user_data: Dict) -> str:
        """Quick update to existing resume"""
        return """**Update Resume**

[Add experience](#action:add_exp)
[Update skills](#action:update_skills)
[Download current version](#action:download_pdf)"""
    
    def reset(self):
        """Reset state"""
        self.resume_step = None
        self.resume_data = {}
        self.validation_results = {}