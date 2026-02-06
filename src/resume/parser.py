"""
Resume parser to extract information from PDF resumes.
"""

import re
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field
import logging

import fitz  # PyMuPDF


@dataclass
class ParsedResume:
    """Data class representing parsed resume information."""
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    summary: str = ""
    skills: Dict[str, List[str]] = field(default_factory=dict)
    experience: List[Dict[str, Any]] = field(default_factory=list)
    education: List[Dict[str, Any]] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    raw_text: str = ""


class ResumeParser:
    """Parse PDF resumes and extract structured information."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def parse(self, pdf_path: str) -> ParsedResume:
        """
        Parse a PDF resume and extract structured information.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            ParsedResume object with extracted information
        """
        self.logger.info(f"Parsing resume: {pdf_path}")
        
        # Extract raw text
        raw_text = self._extract_text(pdf_path)
        
        # Parse sections
        resume = ParsedResume(raw_text=raw_text)
        
        # Extract contact information
        self._extract_contact_info(raw_text, resume)
        
        # Extract summary
        resume.summary = self._extract_summary(raw_text)
        
        # Extract skills
        resume.skills = self._extract_skills(raw_text)
        
        # Extract experience
        resume.experience = self._extract_experience(raw_text)
        
        # Extract education
        resume.education = self._extract_education(raw_text)
        
        # Extract certifications
        resume.certifications = self._extract_certifications(raw_text)
        
        return resume
    
    def _extract_text(self, pdf_path: str) -> str:
        """Extract text from PDF file."""
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            self.logger.error(f"Failed to extract text from PDF: {e}")
            return ""
    
    def _extract_contact_info(self, text: str, resume: ParsedResume):
        """Extract contact information from text."""
        lines = text.split('\n')
        
        # First line is usually the name
        if lines:
            # Look for name pattern
            for line in lines[:5]:
                line = line.strip()
                if line and not any(c in line for c in ['@', '+', 'http', '|']):
                    # Likely the name
                    name_match = re.match(r'^([A-Z][a-z]+\s+[A-Z][a-z]+)', line)
                    if name_match:
                        resume.name = line.split('|')[0].strip()
                        break
        
        # Extract email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        if email_match:
            resume.email = email_match.group()
        
        # Extract phone
        phone_match = re.search(r'[\+]?[\d\s\-\(\)]{10,}', text)
        if phone_match:
            resume.phone = phone_match.group().strip()
        
        # Extract LinkedIn
        linkedin_match = re.search(r'linkedin\.com/in/[\w\-]+', text, re.IGNORECASE)
        if linkedin_match:
            resume.linkedin = f"https://www.{linkedin_match.group()}"
        
        # Extract location
        location_patterns = [
            r'(Dubai|Abu Dhabi|UAE|United Arab Emirates)',
            r'([A-Z][a-z]+,\s*[A-Z]{2,})',
            r'Open to relocation to ([A-Za-z\s,]+)'
        ]
        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                resume.location = match.group(1) if len(match.groups()) > 0 else match.group()
                break
    
    def _extract_summary(self, text: str) -> str:
        """Extract professional summary."""
        # Look for summary section
        patterns = [
            r'(?:SUMMARY|PROFILE|OBJECTIVE)[:\s]*\n(.+?)(?=\n[A-Z]{2,}|\nSKILLS|\nEXPERIENCE)',
            r'^Data Engineer.+?(?=\n[A-Z]{2,}:)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip() if match.lastindex else match.group().strip()
        
        # Default: take first paragraph-like text
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if 'Data Engineer' in line and len(line) > 50:
                # Collect multi-line summary
                summary = line
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip() and not lines[j].strip().isupper():
                        summary += ' ' + lines[j].strip()
                    else:
                        break
                return summary
        
        return ""
    
    def _extract_skills(self, text: str) -> Dict[str, List[str]]:
        """Extract skills section."""
        skills = {
            'tools': [],
            'languages': [],
            'other': []
        }
        
        # Find skills section
        skills_match = re.search(r'SKILLS[:\s]*\n(.+?)(?=\n[A-Z]{2,}:|\nEXPERIENCE)', text, re.IGNORECASE | re.DOTALL)
        
        if skills_match:
            skills_text = skills_match.group(1)
            
            # Parse tools
            tools_match = re.search(r'Tools?[:\s]*(.+?)(?=\n|Programming|Languages)', skills_text, re.IGNORECASE)
            if tools_match:
                skills['tools'] = [s.strip() for s in re.split(r'[,;]', tools_match.group(1)) if s.strip()]
            
            # Parse programming languages
            lang_match = re.search(r'(?:Programming\s+)?Languages?[:\s]*(.+?)(?=\n|$)', skills_text, re.IGNORECASE)
            if lang_match:
                skills['languages'] = [s.strip() for s in re.split(r'[,;]', lang_match.group(1)) if s.strip()]
        
        return skills
    
    def _extract_experience(self, text: str) -> List[Dict[str, Any]]:
        """Extract work experience."""
        experience = []
        
        # Find experience section
        exp_match = re.search(r'EXPERIENCE[:\s]*\n(.+?)(?=\nCERTIFICATIONS|\nEDUCATION|\n[A-Z]{2,}:|\Z)', 
                              text, re.IGNORECASE | re.DOTALL)
        
        if not exp_match:
            return experience
        
        exp_text = exp_match.group(1)
        
        # Split by company/date patterns
        entries = re.split(r'\n(?=[A-Z][a-zA-Z\s]+\s*\|\s*[A-Z])', exp_text)
        
        for entry in entries:
            if not entry.strip():
                continue
            
            exp_entry = {
                'company': '',
                'title': '',
                'location': '',
                'dates': '',
                'bullets': []
            }
            
            lines = entry.strip().split('\n')
            if lines:
                # First line often has company and title
                first_line = lines[0]
                parts = first_line.split('|')
                if len(parts) >= 2:
                    exp_entry['company'] = parts[0].strip()
                    exp_entry['title'] = parts[1].strip()
                
                # Look for dates
                date_match = re.search(r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\s*[–-]\s*(Present|\d{4})', 
                                       entry, re.IGNORECASE)
                if date_match:
                    exp_entry['dates'] = f"{date_match.group(1)} - {date_match.group(2)}"
                
                # Extract bullet points
                bullets = re.findall(r'[●•]\s*(.+?)(?=\n[●•]|\n\n|\Z)', entry, re.DOTALL)
                exp_entry['bullets'] = [b.strip().replace('\n', ' ') for b in bullets]
            
            if exp_entry['company'] or exp_entry['bullets']:
                experience.append(exp_entry)
        
        return experience
    
    def _extract_education(self, text: str) -> List[Dict[str, Any]]:
        """Extract education information."""
        education = []
        
        edu_match = re.search(r'EDUCATION[:\s]*\n(.+?)(?=\n[A-Z]{2,}:|\Z)', text, re.IGNORECASE | re.DOTALL)
        
        if edu_match:
            edu_text = edu_match.group(1)
            
            # Extract degree info
            degree_match = re.search(r'(Bachelor|Master|B\.?E\.?|M\.?S\.?|B\.?S\.?).*?(?:–|-|in)\s*(.+?)(?=\n|$)', 
                                    edu_text, re.IGNORECASE)
            if degree_match:
                education.append({
                    'degree': degree_match.group(0).split('\n')[0].strip(),
                    'institution': '',
                    'dates': ''
                })
            
            # Look for institution
            institution_match = re.search(r'(University|Institute|College).+?(?=\n|$)', edu_text, re.IGNORECASE)
            if institution_match and education:
                education[0]['institution'] = institution_match.group(0).strip()
        
        return education
    
    def _extract_certifications(self, text: str) -> List[str]:
        """Extract certifications."""
        certs = []
        
        cert_match = re.search(r'CERTIFICATIONS?[:\s]*\n(.+?)(?=\nEDUCATION|\n[A-Z]{2,}:|\Z)', 
                               text, re.IGNORECASE | re.DOTALL)
        
        if cert_match:
            cert_text = cert_match.group(1)
            # Split by common separators
            certs = [c.strip() for c in re.split(r'[,;]|\n', cert_text) if c.strip() and len(c.strip()) > 5]
        
        return certs
