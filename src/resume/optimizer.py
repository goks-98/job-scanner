"""
Resume optimizer for ATS (Applicant Tracking System) compatibility.
"""

import re
from typing import List, Dict, Set, Any, Tuple
from collections import Counter
import logging

from .parser import ParsedResume


# Common Data Engineer keywords for ATS matching
DATA_ENGINEER_KEYWORDS = {
    # Core Skills
    'data engineering', 'data pipeline', 'etl', 'elt', 'data warehouse',
    'data lake', 'data lakehouse', 'data modeling', 'data architecture',
    
    # Programming
    'python', 'sql', 'scala', 'java', 'pyspark', 'spark',
    
    # Cloud Platforms
    'aws', 'azure', 'gcp', 'google cloud', 'amazon web services',
    
    # Data Tools
    'databricks', 'snowflake', 'bigquery', 'redshift', 'synapse',
    'airflow', 'apache airflow', 'dagster', 'prefect', 'luigi',
    'kafka', 'kinesis', 'pub/sub', 'rabbitmq',
    'hadoop', 'hdfs', 'hive', 'presto', 'trino',
    'dbt', 'fivetran', 'airbyte', 'stitch',
    
    # Databases
    'postgresql', 'mysql', 'mongodb', 'cassandra', 'redis',
    'dynamodb', 'cosmos db', 'elasticsearch',
    
    # Infrastructure
    'docker', 'kubernetes', 'terraform', 'ansible', 'ci/cd',
    'git', 'github actions', 'jenkins', 'gitlab',
    
    # Concepts
    'batch processing', 'stream processing', 'real-time',
    'data quality', 'data governance', 'data catalog',
    'medallion architecture', 'star schema', 'dimensional modeling',
    'rest api', 'microservices', 'event-driven',
    
    # Soft Skills
    'cross-functional', 'collaboration', 'stakeholder',
    'agile', 'scrum', 'documentation'
}


class ResumeOptimizer:
    """Optimize resumes for ATS systems by matching job keywords."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.base_keywords = DATA_ENGINEER_KEYWORDS
    
    def extract_keywords_from_job(self, job_description: str, requirements: List[str] = None) -> Set[str]:
        """
        Extract relevant keywords from a job description.
        
        Args:
            job_description: Full job description text
            requirements: List of job requirements
            
        Returns:
            Set of extracted keywords
        """
        text = job_description.lower()
        if requirements:
            text += ' ' + ' '.join(requirements).lower()
        
        # Find matching keywords from our base set
        found_keywords = set()
        for keyword in self.base_keywords:
            if keyword in text:
                found_keywords.add(keyword)
        
        # Extract additional technical terms
        # Look for tools/technologies patterns
        tech_patterns = [
            r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\b',  # CamelCase
            r'\b(\w+(?:SQL|DB|ML|AI|ETL|API))\b',  # Tech suffixes
        ]
        
        for pattern in tech_patterns:
            matches = re.findall(pattern, job_description)
            for match in matches:
                if len(match) > 2:
                    found_keywords.add(match.lower())
        
        # Extract years of experience requirement
        exp_match = re.search(r'(\d+)\+?\s*years?', text, re.IGNORECASE)
        if exp_match:
            found_keywords.add(f"{exp_match.group(1)}+ years experience")
        
        return found_keywords
    
    def calculate_match_score(self, resume: ParsedResume, job_keywords: Set[str]) -> Tuple[float, Dict[str, List[str]]]:
        """
        Calculate how well a resume matches job keywords.
        
        Args:
            resume: Parsed resume object
            job_keywords: Set of keywords from job description
            
        Returns:
            Tuple of (match score 0-100, dict of matched/missing keywords)
        """
        resume_text = resume.raw_text.lower()
        
        # Also include skill lists
        all_skills = []
        for skill_list in resume.skills.values():
            all_skills.extend([s.lower() for s in skill_list])
        resume_text += ' ' + ' '.join(all_skills)
        
        matched = []
        missing = []
        
        for keyword in job_keywords:
            if keyword.lower() in resume_text:
                matched.append(keyword)
            else:
                missing.append(keyword)
        
        score = (len(matched) / len(job_keywords) * 100) if job_keywords else 0
        
        return score, {'matched': matched, 'missing': missing}
    
    def optimize_resume(self, resume: ParsedResume, job_keywords: Set[str], 
                       job_title: str, company: str) -> Dict[str, Any]:
        """
        Optimize resume content for specific job keywords.
        
        Args:
            resume: Parsed resume object
            job_keywords: Keywords extracted from job description
            job_title: Target job title
            company: Target company name
            
        Returns:
            Dictionary with optimized resume sections
        """
        self.logger.info(f"Optimizing resume for {job_title} at {company}")
        
        score, analysis = self.calculate_match_score(resume, job_keywords)
        self.logger.info(f"Initial match score: {score:.1f}%")
        
        optimized = {
            'name': resume.name,
            'contact': {
                'email': resume.email,
                'phone': resume.phone,
                'location': resume.location,
                'linkedin': resume.linkedin
            },
            'target_title': self._optimize_title(resume, job_title),
            'summary': self._optimize_summary(resume.summary, job_keywords, job_title, company),
            'skills': self._optimize_skills(resume.skills, job_keywords),
            'experience': self._optimize_experience(resume.experience, job_keywords),
            'education': resume.education,
            'certifications': self._prioritize_certifications(resume.certifications, job_keywords),
            'match_score': score,
            'matched_keywords': analysis['matched'],
            'suggested_keywords': analysis['missing'][:10]  # Top 10 missing keywords to potentially add
        }
        
        return optimized
    
    def _optimize_title(self, resume: ParsedResume, job_title: str) -> str:
        """Optimize the resume title to match job title."""
        # If job title is similar, use it
        job_lower = job_title.lower()
        
        if 'senior' in job_lower and 'senior' not in resume.name.lower():
            if resume.experience and len(resume.experience) >= 2:
                return f"Senior {self._extract_core_title(job_title)}"
        
        return self._extract_core_title(job_title) or "Data Engineer"
    
    def _extract_core_title(self, title: str) -> str:
        """Extract core job title."""
        # Remove company-specific prefixes/suffixes
        core = re.sub(r'\([^)]*\)', '', title)  # Remove parentheses
        core = re.sub(r'[,-].*$', '', core)  # Remove after comma/dash
        return core.strip()
    
    def _optimize_summary(self, summary: str, keywords: Set[str], 
                         job_title: str, company: str) -> str:
        """Optimize professional summary."""
        if not summary:
            summary = "Data Engineer with experience designing, building and maintaining data platforms."
        
        # Add missing high-value keywords naturally
        high_value_missing = []
        summary_lower = summary.lower()
        
        priority_keywords = ['data pipeline', 'etl', 'data warehouse', 'cloud', 
                            'python', 'sql', 'spark', 'airflow']
        
        for kw in priority_keywords:
            if kw in keywords and kw not in summary_lower:
                high_value_missing.append(kw)
        
        # Keep summary under ATS-friendly length (3-4 sentences)
        sentences = summary.split('.')
        if len(sentences) > 4:
            summary = '. '.join(sentences[:4]) + '.'
        
        return summary
    
    def _optimize_skills(self, skills: Dict[str, List[str]], keywords: Set[str]) -> Dict[str, List[str]]:
        """Optimize and reorder skills based on job keywords."""
        optimized = {'technical': [], 'tools': [], 'soft_skills': []}
        
        all_skills = []
        for category, skill_list in skills.items():
            all_skills.extend(skill_list)
        
        # Score and sort skills by relevance to job
        scored_skills = []
        for skill in all_skills:
            score = 0
            skill_lower = skill.lower()
            for kw in keywords:
                if kw in skill_lower or skill_lower in kw:
                    score += 1
            scored_skills.append((skill, score))
        
        # Sort by score (matching keywords first)
        scored_skills.sort(key=lambda x: x[1], reverse=True)
        
        # Categorize
        for skill, _ in scored_skills:
            skill_lower = skill.lower()
            if any(term in skill_lower for term in ['python', 'sql', 'scala', 'java', 'spark']):
                optimized['technical'].append(skill)
            elif any(term in skill_lower for term in ['team', 'communication', 'agile', 'collaboration']):
                optimized['soft_skills'].append(skill)
            else:
                optimized['tools'].append(skill)
        
        return optimized
    
    def _optimize_experience(self, experience: List[Dict], keywords: Set[str]) -> List[Dict]:
        """Optimize experience bullets for keyword matching."""
        optimized = []
        
        for exp in experience:
            opt_exp = exp.copy()
            
            # Reorder bullets: put keyword-matching ones first
            if 'bullets' in exp:
                scored_bullets = []
                for bullet in exp['bullets']:
                    score = sum(1 for kw in keywords if kw in bullet.lower())
                    scored_bullets.append((bullet, score))
                
                scored_bullets.sort(key=lambda x: x[1], reverse=True)
                opt_exp['bullets'] = [b[0] for b in scored_bullets]
            
            optimized.append(opt_exp)
        
        return optimized
    
    def _prioritize_certifications(self, certifications: List[str], keywords: Set[str]) -> List[str]:
        """Prioritize certifications relevant to job."""
        if not certifications:
            return []
        
        scored = []
        for cert in certifications:
            score = sum(1 for kw in keywords if kw in cert.lower())
            # Boost cloud certs
            if any(cloud in cert.lower() for cloud in ['aws', 'azure', 'gcp', 'google']):
                score += 2
            # Boost databricks/snowflake
            if any(tool in cert.lower() for tool in ['databricks', 'snowflake']):
                score += 2
            scored.append((cert, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in scored]
