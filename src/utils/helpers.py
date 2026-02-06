"""
Utility helper functions for the job scanner application.
"""

import os
import yaml
import logging
from pathlib import Path
from datetime import datetime


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def load_config(config_path: str = None) -> dict:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Optional path to config file. Defaults to config/settings.yaml
        
    Returns:
        Configuration dictionary
    """
    if config_path is None:
        config_path = get_project_root() / "config" / "settings.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config


def setup_logging(log_file: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        log_file: Optional path to log file. Defaults to logs/app.log
        level: Logging level
        
    Returns:
        Configured logger instance
    """
    if log_file is None:
        log_file = get_project_root() / "logs" / "app.log"
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('job_scanner')


def ensure_directories():
    """Ensure all required directories exist."""
    root = get_project_root()
    directories = [
        root / "data" / "resumes",
        root / "logs",
        root / "config"
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def format_date(date_str: str) -> datetime:
    """
    Parse various date formats into datetime object.
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        datetime object
    """
    from dateutil import parser
    try:
        return parser.parse(date_str)
    except Exception:
        return None


def days_since_posted(posted_date: datetime) -> int:
    """
    Calculate days since job was posted.
    
    Args:
        posted_date: Date when job was posted
        
    Returns:
        Number of days since posting
    """
    if posted_date is None:
        return float('inf')
    
    now = datetime.now()
    delta = now - posted_date
    return delta.days


def normalize_location(location: str) -> str:
    """
    Normalize location string for consistent matching.
    
    Args:
        location: Raw location string
        
    Returns:
        Normalized location string
    """
    if not location:
        return ""
    
    # Remove extra whitespace
    location = " ".join(location.split())
    
    # Common location mappings
    mappings = {
        "United Arab Emirates": "UAE",
        "U.A.E.": "UAE",
        "Deutschland": "Germany",
        "España": "Spain",
        "Polska": "Poland",
        "Nederland": "Netherlands",
        "Éire": "Ireland",
    }
    
    for old, new in mappings.items():
        location = location.replace(old, new)
    
    return location


def is_eu_location(location: str) -> bool:
    """
    Check if location is in the European Union.
    
    Args:
        location: Location string
        
    Returns:
        True if location is in EU
    """
    eu_countries = [
        "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus",
        "Czech Republic", "Czechia", "Denmark", "Estonia", "Finland",
        "France", "Germany", "Greece", "Hungary", "Ireland",
        "Italy", "Latvia", "Lithuania", "Luxembourg", "Malta",
        "Netherlands", "Poland", "Portugal", "Romania", "Slovakia",
        "Slovenia", "Spain", "Sweden"
    ]
    
    location_lower = location.lower()
    return any(country.lower() in location_lower for country in eu_countries)


def is_uae_location(location: str) -> bool:
    """
    Check if location is in UAE.
    
    Args:
        location: Location string
        
    Returns:
        True if location is in UAE
    """
    uae_indicators = ["uae", "dubai", "abu dhabi", "sharjah", "united arab emirates"]
    location_lower = location.lower()
    return any(indicator in location_lower for indicator in uae_indicators)
