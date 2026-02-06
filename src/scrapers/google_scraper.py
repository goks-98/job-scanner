"""
Google Careers scraper for Data Engineer positions.
"""

import re
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .base_scraper import BaseScraper, Job


class GoogleScraper(BaseScraper):
    """Scraper for Google Careers page."""
    
    @property
    def company_name(self) -> str:
        return "Google"
    
    @property
    def base_url(self) -> str:
        return "https://www.google.com/about/careers/applications/jobs/results"
    
    def _build_search_url(self, location: str = "") -> str:
        """Build search URL with parameters."""
        params = {
            'q': 'Data Engineer',
            'location': location,
            'sort_by': 'date'
        }
        return f"{self.base_url}?{urlencode(params)}"
    
    def fetch_jobs(self) -> List[Dict[str, Any]]:
        """Fetch jobs from Google Careers."""
        jobs = []
        
        # Search for EU locations first, then UAE
        locations = self.priority_locations + self.secondary_locations
        
        for location in locations[:5]:  # Limit to top 5 locations to avoid rate limiting
            try:
                url = self._build_search_url(location)
                self.logger.info(f"Fetching Google jobs for: {location}")
                self.driver.get(url)
                self.random_delay(2, 4)
                
                # Wait for job cards to load
                self.wait_for_element(By.CSS_SELECTOR, '[class*="job-results"]', timeout=15)
                self.random_delay(1, 2)
                
                # Find all job cards
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, 'li[class*="lLd3Je"]')
                
                for card in job_cards:
                    try:
                        job_data = self._extract_job_from_card(card, location)
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        self.logger.debug(f"Error extracting job card: {e}")
                        continue
                
                self.logger.info(f"Found {len(job_cards)} jobs for {location}")
                
            except Exception as e:
                self.logger.error(f"Error fetching Google jobs for {location}: {e}")
                continue
        
        return jobs
    
    def _extract_job_from_card(self, card, search_location: str) -> Optional[Dict[str, Any]]:
        """Extract job data from a job card element."""
        try:
            # Get job title
            title_elem = card.find_element(By.CSS_SELECTOR, 'h3')
            title = title_elem.text.strip() if title_elem else ""
            
            # Get location
            location_elem = card.find_element(By.CSS_SELECTOR, '[class*="location"]')
            location = location_elem.text.strip() if location_elem else search_location
            
            # Get job URL
            link_elem = card.find_element(By.CSS_SELECTOR, 'a')
            url = link_elem.get_attribute('href') if link_elem else ""
            
            # Generate unique ID
            job_id = hashlib.md5(f"{title}{location}{url}".encode()).hexdigest()[:12]
            
            return {
                'id': job_id,
                'title': title,
                'location': location,
                'url': url,
                'search_location': search_location
            }
            
        except Exception as e:
            self.logger.debug(f"Error extracting card data: {e}")
            return None
    
    def _fetch_job_details(self, url: str) -> Dict[str, Any]:
        """Fetch detailed job information from job page."""
        try:
            self.driver.get(url)
            self.random_delay(1, 2)
            
            details = {}
            
            # Get job description
            desc_elem = self.wait_for_element(By.CSS_SELECTOR, '[class*="description"]')
            if desc_elem:
                details['description'] = desc_elem.text.strip()
            
            # Get qualifications/requirements
            qual_elem = self.driver.find_elements(By.CSS_SELECTOR, '[class*="qualifications"] li')
            details['requirements'] = [q.text.strip() for q in qual_elem]
            
            # Try to find posting date
            date_elem = self.driver.find_elements(By.CSS_SELECTOR, '[class*="posted"]')
            if date_elem:
                details['posted_date'] = date_elem[0].text.strip()
            
            return details
            
        except Exception as e:
            self.logger.debug(f"Error fetching job details: {e}")
            return {}
    
    def parse_job(self, raw_job: Dict[str, Any]) -> Optional[Job]:
        """Parse raw job data into Job object."""
        try:
            # Fetch additional details if URL available
            details = {}
            if raw_job.get('url'):
                details = self._fetch_job_details(raw_job['url'])
            
            # Parse posting date if available
            posted_date = None
            if details.get('posted_date'):
                posted_date = self._parse_date(details['posted_date'])
            
            return Job(
                id=raw_job.get('id', ''),
                title=raw_job.get('title', ''),
                company=self.company_name,
                location=raw_job.get('location', ''),
                description=details.get('description', ''),
                url=raw_job.get('url', ''),
                posted_date=posted_date,
                requirements=details.get('requirements', [])
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing job: {e}")
            return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime."""
        try:
            # Handle relative dates like "2 days ago", "1 week ago"
            date_lower = date_str.lower()
            
            if 'today' in date_lower or 'just' in date_lower:
                return datetime.now()
            
            if 'yesterday' in date_lower:
                return datetime.now() - timedelta(days=1)
            
            # Match patterns like "X days ago", "X weeks ago"
            match = re.search(r'(\d+)\s*(day|week|month)s?\s*ago', date_lower)
            if match:
                num = int(match.group(1))
                unit = match.group(2)
                
                if unit == 'day':
                    return datetime.now() - timedelta(days=num)
                elif unit == 'week':
                    return datetime.now() - timedelta(weeks=num)
                elif unit == 'month':
                    return datetime.now() - timedelta(days=num * 30)
            
            return None
            
        except Exception:
            return None
