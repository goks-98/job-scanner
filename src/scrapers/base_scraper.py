"""
Base scraper class that all company-specific scrapers inherit from.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging
import time
import random

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from src.utils.helpers import (
    load_config, 
    days_since_posted, 
    is_eu_location, 
    is_uae_location,
    normalize_location
)


@dataclass
class Job:
    """Data class representing a job posting."""
    id: str
    title: str
    company: str
    location: str
    description: str
    url: str
    posted_date: Optional[datetime] = None
    requirements: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    is_eu: bool = False
    is_uae: bool = False
    scraped_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'description': self.description,
            'url': self.url,
            'posted_date': self.posted_date.isoformat() if self.posted_date else None,
            'requirements': self.requirements,
            'keywords': self.keywords,
            'is_eu': self.is_eu,
            'is_uae': self.is_uae,
            'scraped_at': self.scraped_at.isoformat()
        }


class BaseScraper(ABC):
    """
    Abstract base class for all job scrapers.
    
    Each company-specific scraper must implement:
    - fetch_jobs(): Get raw job listings from the career page
    - parse_job(): Extract structured job info from raw data
    """
    
    def __init__(self, config: dict = None):
        """
        Initialize the scraper.
        
        Args:
            config: Configuration dictionary. If None, loads from settings.yaml
        """
        self.config = config or load_config()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.driver = None
        
        # Job filtering criteria
        self.job_titles = self.config.get('job_preferences', {}).get('titles', ['Data Engineer'])
        self.max_age_days = self.config.get('job_preferences', {}).get('max_age_days', 30)
        self.priority_locations = self.config.get('job_preferences', {}).get('locations', {}).get('priority', [])
        self.secondary_locations = self.config.get('job_preferences', {}).get('locations', {}).get('secondary', [])
    
    def setup_driver(self) -> webdriver.Chrome:
        """
        Set up Selenium WebDriver with Chrome.
        
        Returns:
            Configured Chrome WebDriver instance
        """
        options = Options()
        
        selenium_config = self.config.get('selenium', {})
        
        if selenium_config.get('headless', True):
            options.add_argument('--headless=new')
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument(f"user-agent={selenium_config.get('user_agent', 'Mozilla/5.0')}")
        
        # Suppress logging
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(selenium_config.get('timeout', 30))
        
        return driver
    
    def __enter__(self):
        """Context manager entry."""
        self.driver = self.setup_driver()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup driver."""
        if self.driver:
            self.driver.quit()
    
    def random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Add random delay to avoid detection."""
        time.sleep(random.uniform(min_seconds, max_seconds))
    
    def wait_for_element(self, by: By, value: str, timeout: int = 10):
        """
        Wait for an element to be present.
        
        Args:
            by: Selenium By locator type
            value: Locator value
            timeout: Maximum wait time in seconds
            
        Returns:
            WebElement if found, None otherwise
        """
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            self.logger.warning(f"Timeout waiting for element: {value}")
            return None
    
    @abstractmethod
    def fetch_jobs(self) -> List[Dict[str, Any]]:
        """
        Fetch raw job listings from the career page.
        
        Returns:
            List of raw job data dictionaries
        """
        pass
    
    @abstractmethod
    def parse_job(self, raw_job: Dict[str, Any]) -> Optional[Job]:
        """
        Parse raw job data into a Job object.
        
        Args:
            raw_job: Raw job data from fetch_jobs
            
        Returns:
            Job object if parsing successful, None otherwise
        """
        pass
    
    def filter_jobs(self, jobs: List[Job]) -> List[Job]:
        """
        Filter jobs based on configured criteria.
        
        Args:
            jobs: List of Job objects
            
        Returns:
            Filtered list of jobs matching criteria
        """
        filtered = []
        
        for job in jobs:
            # Check job title matches
            title_match = any(
                title.lower() in job.title.lower() 
                for title in self.job_titles
            )
            if not title_match:
                continue
            
            # Check job age
            if job.posted_date:
                age = days_since_posted(job.posted_date)
                if age > self.max_age_days:
                    continue
            
            # Mark EU/UAE status
            normalized_location = normalize_location(job.location)
            job.is_eu = is_eu_location(normalized_location)
            job.is_uae = is_uae_location(normalized_location)
            
            filtered.append(job)
        
        # Sort: EU jobs first, then UAE, then others
        filtered.sort(key=lambda j: (not j.is_eu, not j.is_uae))
        
        return filtered
    
    def scrape(self) -> List[Job]:
        """
        Main scraping method - fetches, parses, and filters jobs.
        
        Returns:
            List of filtered Job objects
        """
        self.logger.info(f"Starting scrape for {self.__class__.__name__}")
        
        try:
            raw_jobs = self.fetch_jobs()
            self.logger.info(f"Fetched {len(raw_jobs)} raw jobs")
            
            jobs = []
            for raw_job in raw_jobs:
                job = self.parse_job(raw_job)
                if job:
                    jobs.append(job)
            
            self.logger.info(f"Parsed {len(jobs)} jobs")
            
            filtered_jobs = self.filter_jobs(jobs)
            self.logger.info(f"Filtered to {len(filtered_jobs)} matching jobs")
            
            return filtered_jobs
            
        except Exception as e:
            self.logger.error(f"Error during scraping: {str(e)}")
            return []
    
    @property
    @abstractmethod
    def company_name(self) -> str:
        """Return the company name for this scraper."""
        pass
    
    @property
    @abstractmethod
    def base_url(self) -> str:
        """Return the base URL for the career page."""
        pass
