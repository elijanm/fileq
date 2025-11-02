"""
AFHSync Smart Resume Builder - Complete Redesign
Three modes: Create New | Tailor to JD | Upload & Enhance
"""

from typing import Dict, Optional, List
import logging
import requests
import re
import os
from weasyprint import HTML
from datetime import datetime
import json

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://95.110.228.29:8201/v1')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'deepseek-r1:1.5b')


class ResumeService:
    """Intelligent resume builder with 3 modes"""
    
    def __init__(self, db_handler):
        self.db = db_handler
        self.mode = None
        self.resume_data = {}
        self.jd_data = {}
        self.gaps = []
    
    # ==================== ENTRY POINT ====================
    
    def start_resume_service(self, user_data: Dict) -> str:
        """Show 3 options"""
        existing = user_data.get('resume', {})
        
        status = ""
        if existing and existing.get('experience'):
            last_updated = existing.get('last_updated', 'Unknown')
            status = f"\n**Current Resume:** Last updated {last_updated}"
        
        return f"""**Professional Resume Builder**{status}

Choose your approach:

**1. Create New Resume**
Just describe your career in plain language. Example:
"CNA with 4 years experience. Worked at Sunrise Seattle 2020-2023 and Brookdale Bellevue 2021-present. Have CNA, CPR, dementia care certs."

**2. Tailor to Job Description**
Paste a job posting and I'll create a targeted resume that matches it perfectly.

**3. Upload Existing Resume**
Upload your current resume - I'll identify gaps and suggest improvements.

Type 1, 2, 3 or describe your career:"""
    def handle_completed_resume_actions(self, user_input: str, user_data: Dict) -> str:
        """Handle actions after resume is complete"""
        user_lower = user_input.lower().strip()
        
        # Preview
        if 'preview' in user_lower or 'view' in user_lower:
            return self.generate_text_preview()
        
        # Download PDF
        elif 'download' in user_lower or 'pdf' in user_lower:
            return self.generate_pdf(user_data)
        
        # Tailor to job
        elif 'tailor' in user_lower or 'job' in user_lower or 'jd' in user_lower:
            self.mode = 'tailor'
            return """**Tailor to Job Description**

    Paste the job description you want to optimize for:"""
        
        # Edit
        elif 'edit' in user_lower or 'modify' in user_lower or 'change' in user_lower:
            return self.show_edit_options()
        
        # Start over
        elif 'new' in user_lower or 'start over' in user_lower:
            self.reset()
            return self.start_resume_service(user_data)
        
        # Default: show options again
        else:
            return self._show_completion()

    def generate_text_preview(self) -> str:
        """Generate formatted text preview of resume"""
        data = self.resume_data
        
        preview = f"""**RESUME PREVIEW**

    {'='*60}

    {data.get('name', 'YOUR NAME').upper()}
    {data.get('phone', '')} | {data.get('email', '')}
    {data.get('city', '')}, {data.get('state', 'WA')}

    {'='*60}

    PROFESSIONAL SUMMARY

    {data.get('objective', '')}

    """
        
        # Certifications
        if data.get('certifications'):
            preview += "CERTIFICATIONS & LICENSES\n\n"
            for cert in data['certifications']:
                preview += f"• {cert}\n"
            preview += "\n"
        
        # Experience
        if data.get('experience'):
            preview += "PROFESSIONAL EXPERIENCE\n\n"
            for exp in data['experience']:
                preview += f"{exp['title']}\n"
                preview += f"{exp['company']} | {exp.get('location', '')} | {exp.get('duration', '')}\n\n"
                
                for resp in exp.get('responsibilities', []):
                    preview += f"• {resp}\n"
                preview += "\n"
        
        # Skills
        if data.get('skills'):
            preview += "CORE COMPETENCIES\n\n"
            for skill in data['skills']:
                preview += f"• {skill}\n"
            preview += "\n"
        
        # Education
        if data.get('education'):
            preview += "EDUCATION & TRAINING\n\n"
            for edu in data['education']:
                preview += f"• {edu}\n"
            preview += "\n"
        
        preview += f"""{'='*60}

    **Actions:**

    [Download PDF](#action:download_pdf)
    [Tailor to job](#action:tailor_jd)
    [Edit resume](#action:edit_resume)
    [Start new resume](#action:resume_new)"""
        
        return preview

    def show_edit_options(self) -> str:
        """Show what can be edited"""
        return """**Edit Resume**

    What would you like to modify?

    **1. Professional Summary** - Update career objective
    **2. Work Experience** - Add/edit positions
    **3. Skills** - Add/remove skills
    **4. Certifications** - Update certifications
    **5. Education** - Modify education

    Type the number or section name:"""

    def handle_edit_request(self, section: str, user_data: Dict) -> str:
        """Handle editing a specific section"""
        section_lower = section.lower().strip()
        
        if '1' in section or 'summary' in section_lower or 'objective' in section_lower:
            return """**Edit Professional Summary**

    Current: {self.resume_data.get('objective', '')}

    Enter new professional summary:"""
        
        elif '2' in section or 'experience' in section_lower:
            return """**Edit Work Experience**

    [Add new position](#action:add_position)
    [Remove position](#action:remove_position)
    [Edit existing position](#action:edit_position)"""
        
        elif '3' in section or 'skill' in section_lower:
            current_skills = ', '.join(self.resume_data.get('skills', []))
            return f"""**Edit Skills**

    Current skills: {current_skills}

    Enter skills (comma-separated):"""
        
        elif '4' in section or 'cert' in section_lower:
            current_certs = ', '.join(self.resume_data.get('certifications', []))
            return f"""**Edit Certifications**

    Current: {current_certs}

    Enter certifications (comma-separated):"""
        
        elif '5' in section or 'education' in section_lower:
            current_edu = '\n'.join(self.resume_data.get('education', []))
            return f"""**Edit Education**

    Current:
    {current_edu}

    Enter education (one per line):"""
        
        return "Please choose a section (1-5) or type the section name."
    def handle_resume_flow(self, user_input: str, user_data: Dict) -> str:
        """Route to appropriate mode"""
        user_lower = user_input.lower().strip()
        
        # Handle actions on completed resume
        if self.resume_data.get('completed'):
            return self.handle_completed_resume_actions(user_input, user_data)
        
        # If filling gaps
        if hasattr(self, 'gaps') and self.gaps:
            return self.handle_gap_response(user_input, user_data)
        
        # Detect mode selection
        if not self.mode:
            if user_input.strip() == '1' or 'create new' in user_lower:
                self.mode = 'create'
                return """**Create New Resume**

    Describe your career in your own words. Include:
    - Your role/title and years of experience
    - Where you worked (facility names, cities, dates)
    - Your certifications
    - Any special skills or areas of focus

    Example: "I'm a CNA with 5 years experience. Worked at Sunrise Senior Living in Seattle from 2018-2022, now at Emerald Heights in Redmond. Certified in CNA, CPR, First Aid, and dementia care. Love working with elderly patients."

    Tell me about your career:"""
            
            elif user_input.strip() == '2' or 'tailor' in user_lower or 'job description' in user_lower:
                self.mode = 'tailor'
                return """**Tailor to Job Description**

    Paste the complete job description/posting below:"""
            
            elif user_input.strip() == '3' or 'upload' in user_lower:
                self.mode = 'upload'
                return """**Upload Existing Resume**

    Upload your resume (PDF, Word, or text) or paste the content:"""
            
            # Auto-detect if they just started describing
            elif len(user_input) > 50 and any(word in user_lower for word in 
                ['cna', 'hca', 'caregiver', 'worked', 'experience', 'years']):
                self.mode = 'create'
                return self.create_from_description(user_input, user_data)
            
            else:
                return "Please choose option 1, 2, or 3, or describe your career."
        
        # Route to mode handler
        if self.mode == 'create':
            if self.gaps:
                return self.handle_gap_response(user_input, user_data)
            else:
                return self.create_from_description(user_input, user_data)
        elif self.mode == 'tailor':
            return self.tailor_from_jd(user_input, user_data)
        elif self.mode == 'upload':
            return self.enhance_existing(user_input, user_data)
        
        return "Something went wrong. Type 'resume' to restart."
    
    def handle_resume_flow_old(self, user_input: str, user_data: Dict) -> str:
        """Route to appropriate mode"""
        user_lower = user_input.lower().strip()
        
        # Detect mode selection
        if not self.mode:
            if user_input.strip() == '1' or 'create new' in user_lower:
                self.mode = 'create'
                return """**Create New Resume**

Describe your career in your own words. Include:
- Your role/title and years of experience
- Where you worked (facility names, cities, dates)
- Your certifications
- Any special skills or areas of focus

Example: "I'm a CNA with 5 years experience. Worked at Sunrise Senior Living in Seattle from 2018-2022, now at Emerald Heights in Redmond. Certified in CNA, CPR, First Aid, and dementia care. Love working with elderly patients."

Tell me about your career:"""
            
            elif user_input.strip() == '2' or 'tailor' in user_lower or 'job description' in user_lower:
                self.mode = 'tailor'
                return """**Tailor to Job Description**

Paste the complete job description/posting below.

I'll analyze the requirements and create a resume that:
- Matches required skills and keywords
- Highlights relevant experience
- Optimized for ATS (Applicant Tracking Systems)
- Uses their language and priorities

Paste job description:"""
            
            elif user_input.strip() == '3' or 'upload' in user_lower:
                self.mode = 'upload'
                return """**Upload Existing Resume**

Upload your resume (PDF, Word, or text) or paste the content.

I'll analyze it and provide:
- Gap analysis
- Missing keywords
- Improvement recommendations
- Enhanced version

Upload or paste your resume:"""
            
            # Auto-detect if they just started describing
            elif len(user_input) > 50 and any(word in user_lower for word in 
                ['cna', 'hca', 'caregiver', 'worked', 'experience', 'years']):
                self.mode = 'create'
                return self.create_from_description(user_input, user_data)
            
            else:
                return "Please choose option 1, 2, or 3, or describe your career."
        
        # Route to mode handler
        if self.mode == 'create':
            return self.create_from_description(user_input, user_data)
        elif self.mode == 'tailor':
            return self.tailor_from_jd(user_input, user_data)
        elif self.mode == 'upload':
            return self.enhance_existing(user_input, user_data)
        
        return "Something went wrong. Type 'resume' to restart."
    
    # ==================== MODE 1: CREATE FROM DESCRIPTION ====================
    
    def create_from_description(self, description: str, user_data: Dict) -> str:
        """Create comprehensive resume from natural language description"""
        logger.info("Creating resume from description")
        
        # Step 1: Parse the description
        parsed = self._parse_career_description(description, user_data)
        
        if not parsed:
            return """I couldn't parse that. Please include:
- Your job title and years of experience
- Where you worked and when
- Your certifications

Try again:"""
        
        # Step 2: Initialize resume
        self.resume_data = self._initialize_from_profile(user_data)
        
        # Step 3: Build comprehensive resume using AI
        self._build_comprehensive_resume(parsed, user_data)
        
        # Step 4: Check for gaps
        self.gaps = self._identify_gaps()
        
        if self.gaps:
            return self._ask_to_fill_gaps()
        
        # No gaps - resume complete
        self._save_resume(user_data)
        return self._show_completion()
    
    def _parse_career_description(self, description: str, user_data: Dict) -> Optional[Dict]:
        """Parse natural language career description - IMPROVED"""
        try:
            user_name = user_data.get('name', '')
            user_city = user_data.get('primary_location', {}).get('city', '')
            
            prompt = f"""Parse this career description into structured resume data.

    User: {user_name}
    Known location: {user_city}
    Description: {description}

    Extract ALL work positions mentioned. Look for patterns like:
    - "Worked at X from DATE to DATE"
    - "Now at Y"
    - "Currently at Z"
    - "From YEAR-YEAR"

    For EACH position, extract:
    - Job title (default to the role mentioned, like CNA)
    - Employer/facility name
    - City and State
    - Start date (format as YYYY-MM if month known, or just YYYY)
    - End date (or "Present" if currently working)

    Return comprehensive JSON:
    {{
        "role": "Certified Nursing Assistant",
        "years_experience": 5,
        "positions": [
            {{
                "title": "Certified Nursing Assistant",
                "employer": "Sunrise Senior Living",
                "city": "Seattle",
                "state": "WA",
                "start_date": "2018-01",
                "end_date": "2022-12"
            }},
            {{
                "title": "Certified Nursing Assistant",
                "employer": "Emerald Heights",
                "city": "Redmond",
                "state": "WA",
                "start_date": "2022-01",
                "end_date": "Present"
            }}
        ],
        "certifications": ["CNA", "CPR", "First Aid", "Dementia Care"],
        "skills": ["elderly care", "dementia care", "patient care"],
        "specialties": ["elderly patients", "senior care"],
        "education": ["CNA Training Program"]
    }}

    CRITICAL: Extract ALL positions mentioned, including current position."""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 800
                },
                timeout=25
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    logger.info(f"Successfully parsed {len(parsed.get('positions', []))} positions")
                    return parsed
            
            return None
            
        except Exception as e:
            logger.error(f"Parse error: {e}", exc_info=True)
            return None
    def _build_comprehensive_resume(self, parsed: Dict, user_data: Dict):
        """Build complete resume from parsed data - ENHANCED LOGGING"""
    
        logger.info(f"Building resume from parsed data: {json.dumps(parsed, indent=2)}")
        
        # 1. Merge certifications
        user_certs = user_data.get('credentials', [])
        parsed_certs = parsed.get('certifications', [])
        all_certs = list(set(user_certs + parsed_certs))
        self.resume_data['certifications'] = all_certs
        logger.info(f"Certifications: {all_certs}")
        
        # 2. Generate professional summary
        self.resume_data['objective'] = self._generate_professional_summary(parsed)
        logger.info(f"Generated summary: {self.resume_data['objective'][:100]}...")
        
        # 3. Build each work experience with enrichment
        positions = parsed.get('positions', [])
        logger.info(f"Processing {len(positions)} positions")
        
        for idx, position in enumerate(positions):
            logger.info(f"Enriching position {idx+1}: {position.get('title')} at {position.get('employer')}")
            enriched_exp = self._enrich_position(position, parsed)
            self.resume_data['experience'].append(enriched_exp)
        
        logger.info(f"Total experiences added: {len(self.resume_data['experience'])}")
        
        # 4. Generate skills from everything
        self.resume_data['skills'] = self._generate_comprehensive_skills(parsed)
        logger.info(f"Generated {len(self.resume_data['skills'])} skills")
        
        # 5. Education (infer or use provided)
        if parsed.get('education'):
            self.resume_data['education'] = parsed['education']
        else:
            # Infer based on certifications
            if any('cna' in cert.lower() for cert in all_certs):
                self.resume_data['education'] = ['CNA Training Program - Certified']
            else:
                self.resume_data['education'] = ['High School Diploma or Equivalent']
        
        logger.info(f"Education: {self.resume_data['education']}")
        logger.info("Comprehensive resume build complete")
    
    def _generate_professional_summary(self, parsed: Dict) -> str:
        """Generate compelling professional summary"""
        try:
            role = parsed.get('role', 'Caregiver')
            years = parsed.get('years_experience', 0)
            certs = ', '.join(parsed.get('certifications', [])[:3])
            specialties = ', '.join(parsed.get('specialties', [])[:2])
            
            prompt = f"""Write a powerful 3-4 sentence professional summary for a resume.

Role: {role}
Experience: {years} years
Certifications: {certs}
Specialties: {specialties}

Create a summary that:
- Opens with strong positioning statement
- Highlights years and certifications
- Mentions key competencies
- Shows value proposition
- Is ATS-friendly with keywords

Return only the summary text, no labels."""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5,
                    "max_tokens": 250
                },
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result['choices'][0]['message']['content'].strip()
                summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL)
                summary = re.sub(r'^["\'`]+|["\'`]+$', '', summary)
                
                if len(summary) > 50:
                    return summary
            
            # Fallback
            return f"Dedicated {role} with {years}+ years of experience in compassionate patient care. Certified in {certs}. Proven expertise in {specialties}, maintaining high standards of care and patient satisfaction."
            
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            return f"{parsed.get('role', 'Caregiver')} with {parsed.get('years_experience', 0)} years of experience."
    
    def _enrich_position(self, position: Dict, parsed: Dict) -> Dict:
        """Enrich work position with comprehensive details"""
        try:
            title = position.get('title', 'Caregiver')
            employer = position.get('employer', 'Healthcare Facility')
            city = position.get('city', '')
            
            # Look up facility details if we have address
            facility_info = self._lookup_facility(employer, city)
            
            prompt = f"""Generate comprehensive job responsibilities for this position.

Position: {title} at {employer}, {city}
Facility type: {facility_info.get('type', 'healthcare facility')}
Duration: {position.get('start_date')} to {position.get('end_date', 'Present')}
Certifications: {', '.join(parsed.get('certifications', []))}
Specialties: {', '.join(parsed.get('specialties', []))}

Generate 5-6 detailed bullet points that:
- Start with strong action verbs
- Include specific duties typical for {title} at this facility
- Quantify where possible (number of patients, frequency)
- Incorporate relevant skills and certifications
- Show progression and achievements
- Use industry keywords

Return bullets only, one per line, no numbering."""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.6,
                    "max_tokens": 500
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
                    if len(line) > 20:
                        if not line.endswith('.'):
                            line += '.'
                        responsibilities.append(line)
                
                if responsibilities:
                    return {
                        'title': title,
                        'company': employer,
                        'location': f"{city}, {position.get('state', 'WA')}",
                        'address': position.get('address', ''),
                        'duration': f"{position.get('start_date', '')} - {position.get('end_date', 'Present')}",
                        'responsibilities': responsibilities[:6]
                    }
            
            # Fallback
            return {
                'title': title,
                'company': employer,
                'location': f"{city}, {position.get('state', 'WA')}",
                'duration': f"{position.get('start_date', '')} - {position.get('end_date', 'Present')}",
                'responsibilities': self._default_responsibilities(title)
            }
            
        except Exception as e:
            logger.error(f"Position enrichment error: {e}")
            return position
    
    def _lookup_facility(self, facility_name: str, city: str) -> Dict:
        """Look up facility details (placeholder for external API)"""
        # TODO: Integrate with Google Places API or facility database
        # For now, infer from name
        facility_types = {
            'senior living': 'assisted living facility',
            'nursing': 'skilled nursing facility',
            'memory care': 'memory care facility',
            'home': 'home health agency',
            'hospital': 'hospital',
            'rehab': 'rehabilitation center'
        }
        
        name_lower = facility_name.lower()
        for keyword, ftype in facility_types.items():
            if keyword in name_lower:
                return {'type': ftype, 'name': facility_name}
        
        return {'type': 'healthcare facility', 'name': facility_name}
    
    def _generate_comprehensive_skills(self, parsed: Dict) -> List[str]:
        """Generate comprehensive skill list"""
        # Combine parsed skills with standard skills for role
        base_skills = [
            'Patient Care & Assessment',
            'Vital Signs Monitoring',
            'Activities of Daily Living (ADL) Assistance',
            'Medication Administration',
            'Documentation & Charting',
            'Infection Control & Safety',
            'Patient Mobility & Transfers',
            'Compassionate Communication',
            'Team Collaboration',
            'Emergency Response'
        ]
        
        parsed_skills = [s.title() for s in parsed.get('skills', [])]
        
        # Merge and deduplicate
        all_skills = parsed_skills + base_skills
        seen = set()
        unique = []
        for skill in all_skills:
            if skill.lower() not in seen:
                seen.add(skill.lower())
                unique.append(skill)
        
        return unique[:15]
    
    def _default_responsibilities(self, title: str) -> List[str]:
        """Default responsibilities by job title"""
        templates = {
            'cna': [
                "Provided direct patient care including bathing, dressing, grooming, and feeding assistance.",
                "Monitored and recorded vital signs and reported changes to nursing staff.",
                "Assisted with patient mobility, transfers, and ambulation using proper techniques.",
                "Maintained accurate documentation of patient care activities and observations.",
                "Ensured patient safety and comfort while maintaining dignity and respect."
            ],
            'hca': [
                "Provided in-home personal care services including meal preparation and light housekeeping.",
                "Assisted clients with activities of daily living and medication reminders.",
                "Monitored client health status and communicated concerns to healthcare team.",
                "Maintained safe and clean living environment for clients.",
                "Provided companionship and emotional support to enhance quality of life."
            ]
        }
        
        title_lower = title.lower()
        if 'cna' in title_lower or 'nursing assistant' in title_lower:
            return templates['cna']
        elif 'hca' in title_lower or 'home care' in title_lower or 'home health' in title_lower:
            return templates['hca']
        
        return templates['cna']  # Default
    
    # ==================== MODE 2: TAILOR TO JOB DESCRIPTION ====================
    
    def tailor_from_jd(self, jd_text: str, user_data: Dict) -> str:
        """Create resume tailored to job description"""
        logger.info("Tailoring resume to JD")
        
        if len(jd_text) < 100:
            return "Please paste the complete job description (at least a few paragraphs)."
        
        # Step 1: Analyze JD
        jd_analysis = self._analyze_job_description(jd_text)
        
        if not jd_analysis:
            return "Could not analyze job description. Please ensure it's complete and try again."
        
        self.jd_data = jd_analysis
        
        # Step 2: Build resume matching JD
        self.resume_data = self._initialize_from_profile(user_data)
        self._build_jd_tailored_resume(jd_analysis, user_data)
        
        # Step 3: Check gaps
        self.gaps = self._identify_gaps()
        
        if self.gaps:
            return self._ask_to_fill_gaps()
        
        # Complete
        self._save_resume(user_data)
        return self._show_completion_with_jd_match()
    
    def _analyze_job_description(self, jd_text: str) -> Optional[Dict]:
        """Analyze job description comprehensively"""
        try:
            prompt = f"""Analyze this job description thoroughly:

{jd_text}

Extract:
1. Job title
2. Required skills (all mentioned)
3. Required certifications/licenses
4. Years of experience required
5. Key responsibilities (main duties)
6. Required competencies
7. ATS keywords (important terms that should appear)
8. Preferred qualifications
9. Company culture keywords

Return comprehensive JSON:
{{
    "job_title": "exact title",
    "experience_required": "X years",
    "required_certifications": ["cert1"],
    "required_skills": ["skill1", "skill2"],
    "key_responsibilities": ["resp1"],
    "competencies": ["comp1"],
    "ats_keywords": ["keyword1"],
    "preferred_qualifications": ["pref1"],
    "culture_keywords": ["compassionate", "team-oriented"]
}}"""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 700
                },
                timeout=20
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            
            return None
            
        except Exception as e:
            logger.error(f"JD analysis error: {e}")
            return None
    
    def _build_jd_tailored_resume(self, jd_analysis: Dict, user_data: Dict):
        """Build resume specifically matching JD"""
        
        # 1. Tailored professional summary
        self.resume_data['objective'] = self._generate_jd_matched_summary(jd_analysis, user_data)
        
        # 2. Skills matching JD (prioritize required skills)
        self.resume_data['skills'] = self._match_skills_to_jd(jd_analysis, user_data)
        
        # 3. Experience with JD keywords injected
        self.resume_data['experience'] = self._generate_jd_matched_experience(jd_analysis, user_data)
        
        # 4. Certifications (ensure required ones are highlighted)
        user_certs = user_data.get('credentials', [])
        required_certs = jd_analysis.get('required_certifications', [])
        self.resume_data['certifications'] = list(set(user_certs + required_certs))
        
        # 5. Education
        self.resume_data['education'] = user_data.get('education', ['High School Diploma or Equivalent'])
    
    def _generate_jd_matched_summary(self, jd_analysis: Dict, user_data: Dict) -> str:
        """Generate summary matching JD requirements"""
        job_title = jd_analysis.get('job_title', 'Caregiver')
        required_skills = ', '.join(jd_analysis.get('required_skills', [])[:3])
        culture_keywords = ', '.join(jd_analysis.get('culture_keywords', [])[:2])
        
        return f"Experienced {job_title} with proven expertise in {required_skills}. {culture_keywords} professional committed to delivering exceptional patient care and maintaining high safety standards. Seeking to contribute skills and dedication to a dynamic healthcare team."
    
    def _match_skills_to_jd(self, jd_analysis: Dict, user_data: Dict) -> List[str]:
        """Match and prioritize skills based on JD"""
        required = jd_analysis.get('required_skills', [])
        preferred = jd_analysis.get('preferred_qualifications', [])
        user_skills = user_data.get('skills', [])
        
        # Prioritize: required > user's existing > preferred
        all_skills = required + user_skills + preferred
        
        # Deduplicate
        seen = set()
        unique = []
        for skill in all_skills:
            if skill.lower() not in seen:
                seen.add(skill.lower())
                unique.append(skill.title())
        
        return unique[:15]
    
    def _generate_jd_matched_experience(self, jd_analysis: Dict, user_data: Dict) -> List[Dict]:
        """Generate experience entries with JD keywords"""
        # Use existing work history if available
        work_history = user_data.get('work_history', [])
        
        if work_history:
            # Enhance existing with JD keywords
            return [self._inject_jd_keywords(exp, jd_analysis) for exp in work_history[:3]]
        
        # Create generic experience with JD focus
        job_title = jd_analysis.get('job_title', 'Caregiver')
        responsibilities = jd_analysis.get('key_responsibilities', [])
        
        return [{
            'title': job_title,
            'company': 'Healthcare Facility',
            'location': user_data.get('primary_location', {}).get('city', 'Seattle') + ', WA',
            'duration': 'Recent Experience',
            'responsibilities': responsibilities[:6]
        }]
    
    def _inject_jd_keywords(self, experience: Dict, jd_analysis: Dict) -> Dict:
        """Inject JD keywords into experience responsibilities"""
        keywords = jd_analysis.get('ats_keywords', [])
        responsibilities = experience.get('responsibilities', [])
        
        # Enhance each responsibility
        enhanced = []
        for resp in responsibilities:
            # Try to naturally add missing keywords
            resp_lower = resp.lower()
            for keyword in keywords[:3]:
                if keyword.lower() not in resp_lower:
                    # Add naturally if relevant
                    if 'patient' in resp_lower and 'care' in keyword.lower():
                        resp = resp.replace('patient care', f'{keyword} patient care', 1)
                        break
            enhanced.append(resp)
        
        experience['responsibilities'] = enhanced
        return experience
    
    # ==================== MODE 3: ENHANCE EXISTING ====================
    
    def enhance_existing(self, resume_text: str, user_data: Dict) -> str:
        """Analyze and enhance existing resume"""
        logger.info("Enhancing existing resume")
        
        if len(resume_text) < 100:
            return "Please paste your complete resume content or upload a file."
        
        # Step 1: Parse existing resume
        parsed = self._parse_existing_resume(resume_text)
        
        if not parsed:
            return "Could not parse resume. Please ensure it includes work history and contact info."
        
        # Step 2: Identify gaps and weaknesses
        analysis = self._analyze_resume_quality(parsed)
        
        # Step 3: Generate enhanced version
        self.resume_data = parsed
        self._apply_enhancements(analysis)
        
        # Step 4: Show improvements
        return self._show_enhancement_report(analysis)
    
    def _parse_existing_resume(self, resume_text: str) -> Optional[Dict]:
        """Parse uploaded resume"""
        try:
            prompt = f"""Parse this existing resume into structured data:

{resume_text}

Extract all sections:
{{
    "name": "full name",
    "contact": {{"phone": "", "email": "", "city": ""}},
    "summary": "professional summary if exists",
    "experience": [
        {{"title": "", "company": "", "duration": "", "responsibilities": []}}
    ],
    "education": [],
    "skills": [],
    "certifications": []
}}"""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 1000
                },
                timeout=25
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            
            return None
            
        except Exception as e:
            logger.error(f"Resume parse error: {e}")
            return None
    
    def _analyze_resume_quality(self, parsed: Dict) -> Dict:
        """Analyze resume for gaps and improvements"""
        gaps = []
        strengths = []
        improvements = []
        
        # Check summary
        if not parsed.get('summary') or len(parsed.get('summary', '')) < 50:
            gaps.append('professional_summary')
            improvements.append('Add compelling professional summary')
        else:
            strengths.append('Has professional summary')
        
        # Check experience
        exp_count = len(parsed.get('experience', []))
        if exp_count == 0:
            gaps.append('work_experience')
            improvements.append('Add work experience')
        elif exp_count < 2:
            improvements.append('Add more work positions (2-3 recommended)')
        else:
            strengths.append(f'{exp_count} work positions listed')
        
        # Check quantification
        has_numbers = False
        for exp in parsed.get('experience', []):
            for resp in exp.get('responsibilities', []):
                if any(char.isdigit() for char in resp):
                    has_numbers = True
                    break
        
        if not has_numbers:
            improvements.append('Add quantifiable achievements (numbers, percentages)')
        
        # Check skills
        if len(parsed.get('skills', [])) < 5:
            gaps.append('skills')
            improvements.append('Expand skills section (8-12 recommended)')
        else:
            strengths.append(f"{len(parsed.get('skills', []))} skills listed")
        
        # Check action verbs
        weak_verbs = ['responsible for', 'duties include', 'helped']
        has_weak = False
        for exp in parsed.get('experience', []):
            for resp in exp.get('responsibilities', []):
                if any(verb in resp.lower() for verb in weak_verbs):
                    has_weak = True
                    break
        
        if has_weak:
            improvements.append('Replace weak phrases with strong action verbs')
        
        return {
            'gaps': gaps,
            'strengths': strengths,
            'improvements': improvements,
            'score': max(50, 100 - (len(gaps) * 15) - (len(improvements) * 5))
        }
    
    def _apply_enhancements(self, analysis: Dict):
        """Apply enhancements to resume"""
        # Enhance summary if weak
        if 'professional_summary' in analysis['gaps']:
            self.resume_data['objective'] = self._generate_professional_summary({
                'role': self.resume_data.get('experience', [{}])[0].get('title', 'Caregiver'),
                'years_experience': len(self.resume_data.get('experience', [])),
                'certifications': self.resume_data.get('certifications', [])
            })
        
        # Enhance responsibilities with action verbs
        for exp in self.resume_data.get('experience', []):
            exp['responsibilities'] = [
                self._strengthen_bullet(bullet) for bullet in exp.get('responsibilities', [])
            ]
        
        # Expand skills if needed
        if 'skills' in analysis['gaps']:
            self.resume_data['skills'] = self._generate_comprehensive_skills({
                'skills': self.resume_data.get('skills', []),
                'certifications': self.resume_data.get('certifications', [])
            })
    
    def _strengthen_bullet(self, bullet: str) -> str:
        """Strengthen responsibility bullet with action verbs"""
        weak_patterns = [
            (r'^responsible for', 'Managed'),
            (r'^duties included?', 'Performed'),
            (r'^helped (with)?', 'Assisted with'),
            (r'^worked (with|on)', 'Coordinated'),
            (r'^was in charge of', 'Supervised'),
            (r'^took care of', 'Provided')
        ]
        
        enhanced = bullet
        for pattern, replacement in weak_patterns:
            enhanced = re.sub(pattern, replacement, enhanced, flags=re.IGNORECASE)
        
        # Ensure starts with capital
        if enhanced and enhanced[0].islower():
            enhanced = enhanced[0].upper() + enhanced[1:]
        
        # Ensure ends with period
        if enhanced and not enhanced.endswith('.'):
            enhanced += '.'
        
        return enhanced
    
    def _show_enhancement_report(self, analysis: Dict) -> str:
        """Show what was improved"""
        score = analysis['score']
        
        report = f"""**Resume Analysis Complete**

**Quality Score:** {score}/100

**Strengths:**
{chr(10).join(f'✓ {s}' for s in analysis['strengths'])}

**Improvements Made:**
{chr(10).join(f'• {i}' for i in analysis['improvements'])}

**Enhanced Resume Ready**

Your resume has been professionally enhanced with:
- Stronger action verbs and achievement focus
- Better keyword optimization
- Improved formatting and structure
- Quantifiable metrics where applicable

[View enhanced resume](#action:preview_resume)
[Download PDF](#action:download_pdf)
[Make manual edits](#action:edit_resume)"""
        
        return report
    
    # ==================== GAP FILLING ====================
    
    def _identify_gaps(self) -> List[str]:
        """Identify what information is missing - FIXED"""
        gaps = []
        
        # Check professional summary
        if not self.resume_data.get('objective') or len(self.resume_data.get('objective', '')) < 30:
            gaps.append('professional_summary')
        
        # Check work experience - ONLY if truly empty
        if not self.resume_data.get('experience') or len(self.resume_data.get('experience', [])) == 0:
            gaps.append('work_experience')
        
        # Check education - but mark as optional
        if not self.resume_data.get('education') or len(self.resume_data.get('education', [])) == 0:
            gaps.append('education')
        
        # Skills are auto-generated, don't ask
        # Certifications came from parsing, don't ask again
        
        return gaps
    
    def _ask_to_fill_gaps(self) -> str:
        """Ask user to fill identified gaps"""
        gap_descriptions = {
            'professional_summary': 'Professional summary/objective',
            'work_experience': 'Work experience details',
            'education': 'Education/training background',
            'certifications': 'Certifications or licenses',
            'skills': 'Professional skills'
        }
        
        # Ask for most critical gap first
        current_gap = self.gaps[0]
        
        if current_gap == 'education':
            return """**Education Background**

Please provide your education:

Examples:
- "High School Diploma, Lincoln High, 2015"
- "CNA Training Program, Seattle Community College, 2018"
- "Associate Degree in Nursing, 2020"

Type your education (or 'skip' if none):"""
        
        elif current_gap == 'certifications':
            return """**Certifications & Licenses**

List your certifications (one per line or comma-separated):

Examples:
- Certified Nursing Assistant (CNA)
- CPR/First Aid Certified
- Dementia Care Specialist

Your certifications (or 'skip'):"""
        
        elif current_gap == 'skills':
            return """**Professional Skills**

List key skills (comma-separated):

Examples: Patient Care, Vital Signs, Medication Administration, ADL Assistance, Documentation

Your skills (or 'skip'):"""
        
        return f"Please provide: {gap_descriptions.get(current_gap, current_gap)}"
    
    def handle_gap_response(self, user_input: str, user_data: Dict) -> str:
        """Handle gap filling responses - IMPROVED"""
        if not self.gaps:
            return self._show_completion()
        
        current_gap = self.gaps[0]
        user_lower = user_input.lower().strip()
        
        if 'skip' not in user_lower and len(user_input) > 2:
            # Fill the gap
            if current_gap == 'work_experience':
                # Re-parse if they provided more experience details
                parsed = self._parse_career_description(user_input, user_data)
                if parsed and parsed.get('positions'):
                    for position in parsed['positions']:
                        enriched = self._enrich_position(position, parsed)
                        self.resume_data['experience'].append(enriched)
                    logger.info(f"Added {len(parsed['positions'])} more positions")
            
            elif current_gap == 'education':
                edu_lines = [line.strip() for line in user_input.split('\n') if line.strip()]
                if not edu_lines:
                    edu_lines = [user_input.strip()]
                self.resume_data['education'] = edu_lines
                self._sync_to_profile('education', edu_lines, user_data)
            
            elif current_gap == 'certifications':
                certs = [c.strip() for c in user_input.replace('\n', ',').split(',') if c.strip()]
                self.resume_data['certifications'].extend(certs)
                self._sync_to_profile('certifications', self.resume_data['certifications'], user_data)
            
            elif current_gap == 'skills':
                skills = [s.strip().title() for s in user_input.split(',') if s.strip()]
                self.resume_data['skills'].extend(skills)
                self._sync_to_profile('skills', self.resume_data['skills'], user_data)
        
        # Remove filled gap
        self.gaps.pop(0)
        
        # Check if more gaps
        if self.gaps:
            return self._ask_to_fill_gaps()
        
        # All gaps filled - show completion
        self._save_resume(user_data)
        return self._show_completion()
    # ==================== COMPLETION & OUTPUT ====================
    
    def _show_completion(self) -> str:
        """Show completion message"""
        exp_count = len(self.resume_data.get('experience', []))
        cert_count = len(self.resume_data.get('certifications', []))
        skill_count = len(self.resume_data.get('skills', []))
        
        return f"""**Professional Resume Complete!**

Your resume includes:
✓ Compelling professional summary
✓ {exp_count} work experience entries with detailed achievements
✓ {cert_count} certifications
✓ {skill_count} professional skills
✓ Education background

**What's Next?**

[Download PDF](#action:download_pdf) - Professional formatted resume
[View preview](#action:preview_resume) - See full text version
[Tailor to job](#action:tailor_new_jd) - Optimize for specific position
[Make edits](#action:edit_resume) - Modify any section

Your resume has been saved and synced to your profile."""
    
    def _show_completion_with_jd_match(self) -> str:
        """Show completion with JD match score"""
        job_title = self.jd_data.get('job_title', 'position')
        
        # Calculate match score
        required_skills = set(s.lower() for s in self.jd_data.get('required_skills', []))
        resume_skills = set(s.lower() for s in self.resume_data.get('skills', []))
        match_count = len(required_skills.intersection(resume_skills))
        match_score = int((match_count / len(required_skills)) * 100) if required_skills else 90
        
        return f"""**Resume Tailored to {job_title}!**

**JD Match Score:** {match_score}%

Your resume has been optimized with:
✓ Job-specific professional summary
✓ Required skills prioritized ({match_count}/{len(required_skills)} matched)
✓ ATS-friendly keywords integrated
✓ Responsibilities aligned with job requirements

**What's Next?**

[Download PDF](#action:download_pdf) - ATS-optimized resume
[View preview](#action:preview_resume) - Review full content
[Tailor to different job](#action:tailor_new_jd)
[Make edits](#action:edit_resume)

This resume is optimized for Applicant Tracking Systems and matches the job requirements."""
    
    def _save_resume(self, user_data: Dict):
        """Save complete resume to database"""
        try:
            contact = user_data.get('contact')
            if not contact:
                logger.warning("No contact for save")
                return
            
            # Mark as completed - IMPORTANT
            self.resume_data['completed'] = True
            self.resume_data['completed_at'] = datetime.utcnow().isoformat()
            self.resume_data['last_updated'] = datetime.utcnow().isoformat()
            
            # Sync key fields to profile
            self.db.update_user(contact, {
                'resume': self.resume_data,
                'has_resume': True,
                'resume_updated_at': datetime.utcnow(),
                'work_history': self.resume_data.get('experience', []),
                'skills': self.resume_data.get('skills', []),
                'education': self.resume_data.get('education', []),
                'career_objective': self.resume_data.get('objective', '')
            })
            
            logger.info(f"Resume completed and saved for {user_data.get('name')}")
            
        except Exception as e:
            logger.error(f"Save error: {e}")
    
    def _sync_to_profile(self, field: str, value: any, user_data: Dict):
        """Sync field to user profile"""
        try:
            contact = user_data.get('contact')
            if contact:
                self.db.update_user(contact, {field: value})
                logger.info(f"Synced {field} to profile")
        except Exception as e:
            logger.error(f"Sync error: {e}")
    
    # ==================== PDF GENERATION ====================
    
    def generate_pdf(self, user_data: Dict) -> str:
        """Generate professional PDF"""
        try:
            html = self._generate_html_resume()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            pdf_filename = f"resume_{user_data.get('name', 'user').replace(' ', '_')}_{timestamp}.pdf"
            pdf_path = f"/tmp/{pdf_filename}"
            
            HTML(string=html).write_pdf(pdf_path)
            
            logger.info(f"PDF generated: {pdf_path}")
            
            return f"""**Resume PDF Ready**

Download: `/api/resume/download/{pdf_filename}`

**File:** {pdf_filename}

[Create new version](#action:resume_new)
[Tailor to different JD](#action:tailor_jd)
[Return to menu](#action:menu)"""
            
        except Exception as e:
            logger.error(f"PDF error: {e}")
            return f"PDF generation failed. [View text version](#action:preview_resume)"
    
    def _generate_html_resume(self) -> str:
        """Generate clean professional HTML"""
        data = self.resume_data
        
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
@page {{ size: letter; margin: 0.75in; }}
body {{ font-family: Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #2c3e50; }}
h1 {{ font-size: 24pt; margin: 0 0 8px 0; color: #1a252f; border-bottom: 3px solid #3498db; padding-bottom: 8px; }}
h2 {{ font-size: 13pt; margin: 18px 0 8px 0; color: #2c3e50; border-bottom: 2px solid #95a5a6; padding-bottom: 4px; text-transform: uppercase; }}
.contact {{ font-size: 10pt; margin-bottom: 18px; text-align: center; color: #555; }}
.summary {{ margin-bottom: 18px; text-align: justify; line-height: 1.6; }}
.job-title {{ font-weight: bold; font-size: 12pt; margin-top: 10px; }}
.job-details {{ font-size: 10pt; color: #7f8c8d; margin-bottom: 6px; font-style: italic; }}
ul {{ margin: 5px 0 10px 0; padding-left: 20px; }}
li {{ margin-bottom: 4px; }}
.skills-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 5px; }}
</style>
</head>
<body>
<h1>{data.get('name', 'Professional Resume').upper()}</h1>
<div class="contact">{data.get('phone', '')} | {data.get('email', '')} | {data.get('city', '')}, {data.get('state', 'WA')}</div>
<div class="summary">{data.get('objective', '')}</div>"""
        
        # Certifications
        if data.get('certifications'):
            html += '<h2>Certifications & Licenses</h2><ul>'
            for cert in data['certifications']:
                html += f'<li>{cert}</li>'
            html += '</ul>'
        
        # Experience
        if data.get('experience'):
            html += '<h2>Professional Experience</h2>'
            for exp in data['experience']:
                html += f'''<div class="job-title">{exp['title']}</div>
<div class="job-details">{exp['company']} | {exp.get('location', '')} | {exp.get('duration', '')}</div><ul>'''
                for resp in exp.get('responsibilities', []):
                    html += f'<li>{resp}</li>'
                html += '</ul>'
        
        # Skills
        if data.get('skills'):
            html += '<h2>Core Competencies</h2><div class="skills-grid">'
            for skill in data['skills']:
                html += f'<div>• {skill}</div>'
            html += '</div><br>'
        
        # Education
        if data.get('education'):
            html += '<h2>Education & Training</h2><ul>'
            for edu in data['education']:
                html += f'<li>{edu}</li>'
            html += '</ul>'
        
        html += '</body></html>'
        return html
    
    def _initialize_from_profile(self, user_data: Dict) -> Dict:
        """Initialize resume structure from profile"""
        contact = user_data.get('contact', '')
        contact_type = user_data.get('contact_type', '')
        
        phone = contact if contact_type == 'phone' else user_data.get('phone', '')
        email = contact if '@' in contact else user_data.get('email', '')
        
        return {
            'name': user_data.get('name', ''),
            'phone': phone,
            'email': email,
            'city': user_data.get('primary_location', {}).get('city', ''),
            'state': user_data.get('primary_location', {}).get('state', 'WA'),
            'certifications': user_data.get('credentials', []),
            'experience': [],
            'education': user_data.get('education', []),
            'skills': user_data.get('skills', []),
            'objective': '',
            'contact': contact
        }
    
    def reset(self):
        """Reset service state"""
        self.mode = None
        self.resume_data = {}
        self.jd_data = {}
        self.gaps = []