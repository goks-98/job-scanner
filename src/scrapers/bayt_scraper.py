"""
Bayt.com scraper for Data Engineer positions in UAE.
"""

import re
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, Job


class BaytScraper(BaseScraper):
    """Scraper for Bayt.com (Middle East job board)."""
    
    @property
    def company_name(self) -> str:
        return "Bayt"
    
    @property
    def base_url(self) -> str:
        return "https://www.bayt.com/en/uae/jobs/data-engineer-jobs"
    
    def fetch_jobs(self) -> List[Dict[str, Any]]:
        """Fetch jobs from Bayt using requests."""
        jobs = []
        
        headers = {
            'User-Agent': self.config.get('selenium', {}).get('user_agent', 'Mozilla/5.0'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        try:
            self.logger.info("Fetching Bayt jobs for UAE")
            
            response = requests.get(self.base_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find job listings
            job_cards = soup.select('[data-job-id], .t-job, [class*="job-item"]')
            
            for card in job_cards:
                try:
                    job_data = self._extract_job_from_card(card)
                    if job_data:
                        jobs.append(job_data)
                except Exception as e:
                    self.logger.debug(f"Error extracting Bayt card: {e}")
                    continue
            
            self.logger.info(f"Found {len(job_cards)} Bayt jobs")
            
        except Exception as e:
            self.logger.error(f"Error fetching Bayt jobs: {e}")
        
        return jobs
    
    def _extract_job_from_card(self, card) -> Optional[Dict[str, Any]]:
        """Extract job data from card HTML."""
        try:
            # Get title
            title_elem = card.select_one('h2 a, .jb-title a, [class*="title"] a')
            title = title_elem.get_text(strip=True) if title_elem else ""
            url = title_elem.get('href', '') if title_elem else ""
            
            if url and not url.startswith('http'):
                url = f"https://www.bayt.com{url}"
            
            # Get company
            company_elem = card.select_one('[class*="company"], .jb-company')
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"
            
            # Get location
            loc_elem = card.select_one('[class*="location"], .jb-loc')
            location = loc_elem.get_text(strip=True) if loc_elem else "UAE"
            
            # Get posted date
            date_elem = card.select_one('[class*="date"], time')
            posted_date = date_elem.get_text(strip=True) if date_elem else None
            
            job_id = hashlib.md5(f"{title}{company}{url}".encode()).hexdigest()[:12]
            
            return {
                'id': job_id,
                'title': title,
                'company': company,
                'location': location,
                'url': url,
                'posted_date': posted_date
            }
            
        except Exception as e:
            self.logger.debug(f"Error extracting Bayt card: {e}")
            return None
    
    def _fetch_job_details(self, url: str) -> Dict[str, Any]:
        """Fetch detailed job information."""
        try:
            headers = {
                'User-Agent': self.config.get('selenium', {}).get('user_agent', 'Mozilla/5.0')
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            details = {}
            
            # Get description
            desc_elem = soup.select_one('[class*="description"], #job_description')
            if desc_elem:
                details['description'] = desc_elem.get_text(strip=True)
            
            # Get requirements
            req_elems = soup.select('[class*="requirements"] li, [class*="skills"] li')
            details['requirements'] = [r.get_text(strip=True) for r in req_elems]
            
            return details
            
        except Exception as e:
            self.logger.debug(f"Error fetching Bayt job details: {e}")
            return {}
    
    def parse_job(self, raw_job: Dict[str, Any]) -> Optional[Job]:
        """Parse raw job data into Job object."""
        try:
            details = {}
            if raw_job.get('url'):
                details = self._fetch_job_details(raw_job['url'])
            
            return Job(
                id=raw_job.get('id', ''),
                title=raw_job.get('title', ''),
                company=raw_job.get('company', self.company_name),
                location=raw_job.get('location', 'UAE'),
                description=details.get('description', ''),
                url=raw_job.get('url', ''),
                posted_date=datetime.now() - timedelta(days=7),  # Estimate
                requirements=details.get('requirements', [])
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing Bayt job: {e}")
            return None
