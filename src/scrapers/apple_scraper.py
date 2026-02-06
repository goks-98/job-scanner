"""
Apple Jobs scraper for Data Engineer positions.
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


class AppleScraper(BaseScraper):
    """Scraper for Apple Jobs page."""
    
    @property
    def company_name(self) -> str:
        return "Apple"
    
    @property
    def base_url(self) -> str:
        return "https://jobs.apple.com/en-us/search"
    
    def _build_search_url(self, location: str = "") -> str:
        """Build search URL with parameters."""
        params = {
            'search': 'Data Engineer',
            'sort': 'newest',
        }
        if location:
            params['location'] = location
        
        return f"{self.base_url}?{urlencode(params)}"
    
    def fetch_jobs(self) -> List[Dict[str, Any]]:
        """Fetch jobs from Apple Jobs."""
        jobs = []
        
        locations = self.priority_locations + self.secondary_locations
        
        for location in locations[:5]:
            try:
                url = self._build_search_url(location)
                self.logger.info(f"Fetching Apple jobs for: {location}")
                self.driver.get(url)
                self.random_delay(2, 4)
                
                # Wait for search results
                self.wait_for_element(By.CSS_SELECTOR, 'table.table--results', timeout=15)
                self.random_delay(1, 2)
                
                # Find job rows
                job_rows = self.driver.find_elements(By.CSS_SELECTOR, 'tbody.table-body tr')
                
                for row in job_rows:
                    try:
                        job_data = self._extract_job_from_row(row, location)
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        self.logger.debug(f"Error extracting Apple job row: {e}")
                        continue
                
                self.logger.info(f"Found {len(job_rows)} Apple jobs for {location}")
                
            except Exception as e:
                self.logger.error(f"Error fetching Apple jobs for {location}: {e}")
                continue
        
        return jobs
    
    def _extract_job_from_row(self, row, search_location: str) -> Optional[Dict[str, Any]]:
        """Extract job data from a table row."""
        try:
            # Get job title and link
            title_elem = row.find_element(By.CSS_SELECTOR, 'td.table-col-1 a')
            title = title_elem.text.strip() if title_elem else ""
            url = title_elem.get_attribute('href') if title_elem else ""
            
            # Get location
            try:
                location_elem = row.find_element(By.CSS_SELECTOR, 'td.table-col-2')
                location = location_elem.text.strip()
            except:
                location = search_location
            
            # Get posted date
            try:
                date_elem = row.find_element(By.CSS_SELECTOR, 'td.table-col-3')
                posted_date = date_elem.text.strip()
            except:
                posted_date = None
            
            # Generate unique ID
            job_id = hashlib.md5(f"{title}{location}{url}".encode()).hexdigest()[:12]
            
            return {
                'id': job_id,
                'title': title,
                'location': location,
                'url': url,
                'posted_date': posted_date
            }
            
        except Exception as e:
            self.logger.debug(f"Error extracting Apple row: {e}")
            return None
    
    def _fetch_job_details(self, url: str) -> Dict[str, Any]:
        """Fetch detailed job information."""
        try:
            self.driver.get(url)
            self.random_delay(2, 3)
            
            details = {}
            
            # Get job description
            desc_elem = self.wait_for_element(By.CSS_SELECTOR, '#jd-job-description')
            if desc_elem:
                details['description'] = desc_elem.text.strip()
            
            # Get key qualifications
            qual_elem = self.driver.find_elements(By.CSS_SELECTOR, '#jd-key-qualifications li')
            details['requirements'] = [q.text.strip() for q in qual_elem]
            
            return details
            
        except Exception as e:
            self.logger.debug(f"Error fetching Apple job details: {e}")
            return {}
    
    def parse_job(self, raw_job: Dict[str, Any]) -> Optional[Job]:
        """Parse raw job data into Job object."""
        try:
            details = {}
            if raw_job.get('url'):
                details = self._fetch_job_details(raw_job['url'])
            
            # Parse posting date
            posted_date = None
            if raw_job.get('posted_date'):
                posted_date = self._parse_date(raw_job['posted_date'])
            
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
            self.logger.error(f"Error parsing Apple job: {e}")
            return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse Apple's date format."""
        try:
            # Apple typically uses "Jan 15, 2024" format
            return datetime.strptime(date_str, '%b %d, %Y')
        except:
            try:
                return datetime.strptime(date_str, '%B %d, %Y')
            except:
                return None
