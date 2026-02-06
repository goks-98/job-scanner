"""
Netflix Jobs scraper for Data Engineer positions.
"""

import re
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, Job


class NetflixScraper(BaseScraper):
    """Scraper for Netflix Jobs page using requests + BeautifulSoup."""
    
    @property
    def company_name(self) -> str:
        return "Netflix"
    
    @property
    def base_url(self) -> str:
        return "https://jobs.netflix.com/search"
    
    def _build_search_url(self, location: str = "") -> str:
        """Build search URL with parameters."""
        params = {
            'q': 'Data Engineer',
            'sort': 'posting_date_desc'
        }
        if location:
            params['location'] = location
        
        return f"{self.base_url}?{urlencode(params)}"
    
    def fetch_jobs(self) -> List[Dict[str, Any]]:
        """Fetch jobs from Netflix Jobs using requests."""
        jobs = []
        
        # Netflix has simpler page, can use requests
        headers = {
            'User-Agent': self.config.get('selenium', {}).get('user_agent', 'Mozilla/5.0')
        }
        
        locations = self.priority_locations + self.secondary_locations
        
        for location in locations[:5]:
            try:
                url = self._build_search_url(location)
                self.logger.info(f"Fetching Netflix jobs for: {location}")
                
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find job cards
                job_cards = soup.select('[class*="job-card"], [class*="posting-card"], .position')
                
                for card in job_cards:
                    try:
                        job_data = self._extract_job_from_card(card, location)
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        self.logger.debug(f"Error extracting Netflix card: {e}")
                        continue
                
                self.logger.info(f"Found {len(job_cards)} Netflix jobs for {location}")
                
            except Exception as e:
                self.logger.error(f"Error fetching Netflix jobs for {location}: {e}")
                continue
        
        return jobs
    
    def _extract_job_from_card(self, card, search_location: str) -> Optional[Dict[str, Any]]:
        """Extract job data from card HTML element."""
        try:
            # Get job title
            title_elem = card.select_one('h4, h3, .title, [class*="title"]')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # Get URL
            link_elem = card.select_one('a[href*="/jobs/"]')
            url = link_elem.get('href', '') if link_elem else ""
            if url and not url.startswith('http'):
                url = f"https://jobs.netflix.com{url}"
            
            # Get location
            location_elem = card.select_one('[class*="location"], .location')
            location = location_elem.get_text(strip=True) if location_elem else search_location
            
            # Generate unique ID
            job_id = hashlib.md5(f"{title}{location}{url}".encode()).hexdigest()[:12]
            
            return {
                'id': job_id,
                'title': title,
                'location': location,
                'url': url
            }
            
        except Exception as e:
            self.logger.debug(f"Error extracting Netflix card data: {e}")
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
            desc_elem = soup.select_one('[class*="description"], .job-description')
            if desc_elem:
                details['description'] = desc_elem.get_text(strip=True)
            
            # Get requirements
            req_elems = soup.select('[class*="qualifications"] li, [class*="requirements"] li')
            details['requirements'] = [r.get_text(strip=True) for r in req_elems]
            
            return details
            
        except Exception as e:
            self.logger.debug(f"Error fetching Netflix job details: {e}")
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
                company=self.company_name,
                location=raw_job.get('location', ''),
                description=details.get('description', ''),
                url=raw_job.get('url', ''),
                posted_date=datetime.now() - timedelta(days=15),  # Estimate
                requirements=details.get('requirements', [])
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing Netflix job: {e}")
            return None
