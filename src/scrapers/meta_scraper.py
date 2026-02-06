"""
Meta (Facebook) Careers scraper for Data Engineer positions.
"""

import re
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from .base_scraper import BaseScraper, Job


class MetaScraper(BaseScraper):
    """Scraper for Meta Careers page."""
    
    @property
    def company_name(self) -> str:
        return "Meta"
    
    @property
    def base_url(self) -> str:
        return "https://www.metacareers.com/jobs"
    
    def _build_search_url(self, location: str = "") -> str:
        """Build search URL with parameters."""
        # Meta uses query parameters for filtering
        params = {
            'q': 'Data Engineer',
            'sort_by_new': 'true'
        }
        if location:
            params['locations[0]'] = location
        
        return f"{self.base_url}?{urlencode(params)}"
    
    def fetch_jobs(self) -> List[Dict[str, Any]]:
        """Fetch jobs from Meta Careers."""
        jobs = []
        
        # Search EU locations first
        locations = self.priority_locations + self.secondary_locations
        
        for location in locations[:5]:
            try:
                url = self._build_search_url(location)
                self.logger.info(f"Fetching Meta jobs for: {location}")
                self.driver.get(url)
                self.random_delay(3, 5)  # Meta has aggressive rate limiting
                
                # Wait for job listings to load (React-based)
                self.wait_for_element(By.CSS_SELECTOR, '[data-testid="job-results"]', timeout=20)
                self.random_delay(2, 3)
                
                # Scroll to load more jobs
                self._scroll_to_load_jobs()
                
                # Find job cards
                job_cards = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    '[data-testid="job-card"], [class*="jobCard"]'
                )
                
                for card in job_cards:
                    try:
                        job_data = self._extract_job_from_card(card, location)
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        self.logger.debug(f"Error extracting Meta job card: {e}")
                        continue
                
                self.logger.info(f"Found {len(job_cards)} Meta jobs for {location}")
                
            except Exception as e:
                self.logger.error(f"Error fetching Meta jobs for {location}: {e}")
                continue
        
        return jobs
    
    def _scroll_to_load_jobs(self, scroll_count: int = 3):
        """Scroll page to load more jobs."""
        for _ in range(scroll_count):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.random_delay(1, 2)
    
    def _extract_job_from_card(self, card, search_location: str) -> Optional[Dict[str, Any]]:
        """Extract job data from a job card element."""
        try:
            # Get job title
            title_elem = card.find_element(By.CSS_SELECTOR, 'a[href*="/jobs/"]')
            title = title_elem.text.strip() if title_elem else ""
            url = title_elem.get_attribute('href') if title_elem else ""
            
            # Get location
            try:
                location_elem = card.find_element(By.CSS_SELECTOR, '[class*="location"]')
                location = location_elem.text.strip()
            except:
                location = search_location
            
            # Generate unique ID
            job_id = hashlib.md5(f"{title}{location}{url}".encode()).hexdigest()[:12]
            
            return {
                'id': job_id,
                'title': title,
                'location': location,
                'url': url if url.startswith('http') else f"https://www.metacareers.com{url}"
            }
            
        except Exception as e:
            self.logger.debug(f"Error extracting Meta card: {e}")
            return None
    
    def _fetch_job_details(self, url: str) -> Dict[str, Any]:
        """Fetch detailed job information."""
        try:
            self.driver.get(url)
            self.random_delay(2, 3)
            
            details = {}
            
            # Wait for content to load
            self.wait_for_element(By.CSS_SELECTOR, '[class*="jobDetail"]', timeout=15)
            
            # Get description
            desc_elems = self.driver.find_elements(By.CSS_SELECTOR, '[class*="description"]')
            if desc_elems:
                details['description'] = desc_elems[0].text.strip()
            
            # Get responsibilities/requirements
            list_items = self.driver.find_elements(By.CSS_SELECTOR, '[class*="responsibilities"] li')
            details['requirements'] = [li.text.strip() for li in list_items]
            
            return details
            
        except Exception as e:
            self.logger.debug(f"Error fetching Meta job details: {e}")
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
                posted_date=datetime.now() - timedelta(days=15),  # Estimate if not available
                requirements=details.get('requirements', [])
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing Meta job: {e}")
            return None
