"""
LinkedIn Jobs scraper for Data Engineer positions in UAE.
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


class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn Jobs (no login required for public listings)."""
    
    @property
    def company_name(self) -> str:
        return "LinkedIn"
    
    @property
    def base_url(self) -> str:
        return "https://www.linkedin.com/jobs/search"
    
    def _build_search_url(self, location: str = "Dubai") -> str:
        """Build search URL with parameters."""
        params = {
            'keywords': 'Data Engineer',
            'location': location,
            'sortBy': 'DD',  # Sort by date
            'f_TPR': 'r2592000'  # Last 30 days
        }
        return f"{self.base_url}?{urlencode(params)}"
    
    def fetch_jobs(self) -> List[Dict[str, Any]]:
        """Fetch jobs from LinkedIn (public listings only)."""
        jobs = []
        
        # Focus on UAE for LinkedIn
        locations = ['Dubai, UAE', 'Abu Dhabi, UAE', 'United Arab Emirates']
        
        for location in locations:
            try:
                url = self._build_search_url(location)
                self.logger.info(f"Fetching LinkedIn jobs for: {location}")
                self.driver.get(url)
                self.random_delay(3, 5)
                
                # Wait for job listings
                self.wait_for_element(By.CSS_SELECTOR, '.jobs-search__results-list', timeout=15)
                self.random_delay(2, 3)
                
                # Scroll to load more
                self._scroll_to_load()
                
                # Find job cards
                job_cards = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    '.jobs-search__results-list li, .job-card-container'
                )
                
                for card in job_cards:
                    try:
                        job_data = self._extract_job_from_card(card, location)
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        self.logger.debug(f"Error extracting LinkedIn card: {e}")
                        continue
                
                self.logger.info(f"Found {len(job_cards)} LinkedIn jobs for {location}")
                
            except Exception as e:
                self.logger.error(f"Error fetching LinkedIn jobs for {location}: {e}")
                continue
        
        return jobs
    
    def _scroll_to_load(self, scroll_count: int = 3):
        """Scroll to load more jobs."""
        for _ in range(scroll_count):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.random_delay(1.5, 2.5)
    
    def _extract_job_from_card(self, card, search_location: str) -> Optional[Dict[str, Any]]:
        """Extract job data from card."""
        try:
            # Get title and link
            title_elem = card.find_element(By.CSS_SELECTOR, 'h3.base-search-card__title, .job-card-list__title')
            title = title_elem.text.strip() if title_elem else ""
            
            link_elem = card.find_element(By.CSS_SELECTOR, 'a.base-card__full-link, a[href*="/jobs/view/"]')
            url = link_elem.get_attribute('href') if link_elem else ""
            
            # Get company
            try:
                company_elem = card.find_element(By.CSS_SELECTOR, 'h4.base-search-card__subtitle, .job-card-container__company-name')
                company = company_elem.text.strip()
            except:
                company = "Unknown"
            
            # Get location
            try:
                loc_elem = card.find_element(By.CSS_SELECTOR, '.job-search-card__location, .job-card-container__metadata-item')
                location = loc_elem.text.strip()
            except:
                location = search_location
            
            # Get posted date
            try:
                date_elem = card.find_element(By.CSS_SELECTOR, 'time, .job-search-card__listdate')
                posted_date = date_elem.get_attribute('datetime') or date_elem.text.strip()
            except:
                posted_date = None
            
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
            self.logger.debug(f"Error extracting LinkedIn card: {e}")
            return None
    
    def parse_job(self, raw_job: Dict[str, Any]) -> Optional[Job]:
        """Parse raw job data into Job object."""
        try:
            # Parse posted date
            posted_date = None
            if raw_job.get('posted_date'):
                try:
                    posted_date = datetime.fromisoformat(raw_job['posted_date'].replace('Z', '+00:00'))
                except:
                    posted_date = self._parse_relative_date(raw_job['posted_date'])
            
            return Job(
                id=raw_job.get('id', ''),
                title=raw_job.get('title', ''),
                company=raw_job.get('company', 'LinkedIn'),  # Use actual company from listing
                location=raw_job.get('location', ''),
                description='',  # Skip details fetch to avoid rate limiting
                url=raw_job.get('url', ''),
                posted_date=posted_date,
                requirements=[]
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing LinkedIn job: {e}")
            return None
    
    def _parse_relative_date(self, date_str: str) -> Optional[datetime]:
        """Parse relative dates like '2 days ago'."""
        try:
            date_lower = date_str.lower()
            
            if 'just now' in date_lower or 'today' in date_lower:
                return datetime.now()
            
            match = re.search(r'(\d+)\s*(day|week|month|hour)s?\s*ago', date_lower)
            if match:
                num = int(match.group(1))
                unit = match.group(2)
                
                if unit == 'hour':
                    return datetime.now() - timedelta(hours=num)
                elif unit == 'day':
                    return datetime.now() - timedelta(days=num)
                elif unit == 'week':
                    return datetime.now() - timedelta(weeks=num)
                elif unit == 'month':
                    return datetime.now() - timedelta(days=num * 30)
            
            return None
        except:
            return None
