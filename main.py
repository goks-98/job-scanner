#!/usr/bin/env python
"""
FAANG Job Scanner & ATS Resume Generator

Scans Data Engineer positions from Big Tech company career pages,
filters for EU/UAE locations, generates ATS-optimized resumes,
and sends email notifications.

Usage:
    python main.py                  # Run full scan with defaults
    python main.py --test-email     # Send test email
    python main.py --test-resume    # Generate sample resume
    python main.py --stats          # Show database statistics
    python main.py --scrapers       # List available scrapers
"""

import argparse
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.helpers import load_config, setup_logging, ensure_directories
from src.database.job_store import JobStore
from src.notifications.email_notifier import EmailNotifier
from src.resume.parser import ResumeParser
from src.resume.optimizer import ResumeOptimizer
from src.resume.generator import ResumeGenerator


# Available scrapers
SCRAPER_CLASSES = {
    'google': ('src.scrapers.google_scraper', 'GoogleScraper'),
    'meta': ('src.scrapers.meta_scraper', 'MetaScraper'),
    'apple': ('src.scrapers.apple_scraper', 'AppleScraper'),
    'netflix': ('src.scrapers.netflix_scraper', 'NetflixScraper'),
    'linkedin': ('src.scrapers.linkedin_scraper', 'LinkedInScraper'),
    'bayt': ('src.scrapers.bayt_scraper', 'BaytScraper'),
    'gulftalent': ('src.scrapers.gulftalent_scraper', 'GulfTalentScraper'),
}


def get_scraper(name: str, config: dict):
    """Dynamically import and instantiate a scraper."""
    if name not in SCRAPER_CLASSES:
        raise ValueError(f"Unknown scraper: {name}")
    
    module_path, class_name = SCRAPER_CLASSES[name]
    
    import importlib
    module = importlib.import_module(module_path)
    scraper_class = getattr(module, class_name)
    
    return scraper_class(config)


def run_scrapers(config: dict, logger: logging.Logger, 
                scrapers: List[str] = None) -> List[Dict[str, Any]]:
    """
    Run all enabled scrapers and collect jobs.
    
    Args:
        config: Configuration dictionary
        logger: Logger instance
        scrapers: Optional list of specific scrapers to run
        
    Returns:
        List of job dictionaries
    """
    all_jobs = []
    
    # Determine which scrapers to run
    if scrapers:
        scraper_names = scrapers
    else:
        scraper_names = list(SCRAPER_CLASSES.keys())
    
    for name in scraper_names:
        try:
            logger.info(f"Running {name} scraper...")
            
            with get_scraper(name, config) as scraper:
                jobs = scraper.scrape()
                
                # Convert Job objects to dicts
                job_dicts = [job.to_dict() for job in jobs]
                all_jobs.extend(job_dicts)
                
                logger.info(f"{name}: Found {len(jobs)} matching jobs")
                
        except Exception as e:
            logger.error(f"Error running {name} scraper: {e}")
            continue
    
    return all_jobs


def process_jobs(jobs: List[Dict], config: dict, logger: logging.Logger) -> List[str]:
    """
    Process jobs: parse resume, optimize for each job, generate resumes.
    
    Args:
        jobs: List of job dictionaries
        config: Configuration dictionary
        logger: Logger instance
        
    Returns:
        List of generated resume paths
    """
    if not jobs:
        logger.info("No jobs to process")
        return []
    
    # Parse original resume
    resume_path = Path(__file__).parent / "Gokul CV.pdf"
    if not resume_path.exists():
        logger.error(f"Resume not found at: {resume_path}")
        return []
    
    logger.info(f"Parsing resume: {resume_path}")
    parser = ResumeParser()
    parsed_resume = parser.parse(str(resume_path))
    
    # Initialize optimizer and generator
    optimizer = ResumeOptimizer()
    generator = ResumeGenerator()
    
    resume_paths = []
    
    for job in jobs:
        try:
            logger.info(f"Processing: {job.get('title')} at {job.get('company')}")
            
            # Extract keywords from job
            job_keywords = optimizer.extract_keywords_from_job(
                job.get('description', ''),
                job.get('requirements', [])
            )
            
            # Optimize resume for this job
            optimized = optimizer.optimize_resume(
                parsed_resume,
                job_keywords,
                job.get('title', 'Data Engineer'),
                job.get('company', 'Unknown')
            )
            
            # Generate tailored resume
            resume_file = generator.generate(
                optimized,
                job.get('id', ''),
                job.get('title', 'Data Engineer'),
                job.get('company', 'Unknown')
            )
            
            resume_paths.append(resume_file)
            logger.info(f"Generated: {resume_file}")
            
        except Exception as e:
            logger.error(f"Error processing job {job.get('id')}: {e}")
            continue
    
    return resume_paths


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='FAANG Job Scanner & ATS Resume Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--test-email', action='store_true',
                       help='Send a test email notification')
    parser.add_argument('--test-resume', action='store_true',
                       help='Generate a sample resume')
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics')
    parser.add_argument('--scrapers', action='store_true',
                       help='List available scrapers')
    parser.add_argument('--only', nargs='+', choices=list(SCRAPER_CLASSES.keys()),
                       help='Run only specific scrapers')
    parser.add_argument('--no-email', action='store_true',
                       help='Skip sending email notification')
    parser.add_argument('--no-resume', action='store_true',
                       help='Skip generating resumes')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup
    ensure_directories()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logging(level=log_level)
    
    logger.info("=" * 60)
    logger.info("FAANG Job Scanner & ATS Resume Generator")
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    # Load config
    try:
        config = load_config()
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        logger.info("Please ensure config/settings.yaml exists with valid configuration")
        return 1
    
    # Handle special commands
    if args.scrapers:
        print("\nAvailable Scrapers:")
        print("-" * 40)
        for name in SCRAPER_CLASSES:
            print(f"  - {name}")
        return 0
    
    if args.test_email:
        logger.info("Sending test email...")
        notifier = EmailNotifier(config)
        if notifier.send_test():
            logger.info("Test email sent successfully!")
        else:
            logger.error("Failed to send test email. Check your configuration.")
        return 0
    
    if args.test_resume:
        logger.info("Generating sample resume...")
        generator = ResumeGenerator()
        path = generator.generate_sample()
        logger.info(f"Sample resume generated: {path}")
        return 0
    
    if args.stats:
        with JobStore() as store:
            stats = store.get_stats()
            print("\nDatabase Statistics:")
            print("-" * 40)
            for key, value in stats.items():
                print(f"  {key.replace('_', ' ').title()}: {value}")
        return 0
    
    # Run the full job scanning pipeline
    try:
        # Run scrapers
        logger.info("Starting job scan...")
        jobs = run_scrapers(config, logger, args.only)
        
        if not jobs:
            logger.info("No matching jobs found")
            return 0
        
        logger.info(f"Found {len(jobs)} total matching jobs")
        
        # Store jobs in database
        with JobStore() as store:
            new_count = store.add_jobs(jobs)
            logger.info(f"Added {new_count} new jobs to database")
            
            # Get unnotified jobs
            unnotified = store.get_unnotified_jobs()
            
            if not unnotified:
                logger.info("No new jobs to notify about")
                return 0
            
            logger.info(f"Processing {len(unnotified)} new jobs")
            
            # Convert to dicts for processing
            jobs_to_process = []
            for job in unnotified:
                jobs_to_process.append({
                    'id': job.id,
                    'title': job.title,
                    'company': job.company,
                    'location': job.location,
                    'description': job.description,
                    'url': job.url,
                    'posted_date': job.posted_date,
                    'requirements': json.loads(job.requirements) if job.requirements else [],
                    'is_eu': job.is_eu,
                    'is_uae': job.is_uae
                })
            
            # Generate resumes
            resume_paths = []
            if not args.no_resume:
                resume_paths = process_jobs(jobs_to_process, config, logger)
                
                # Update database with resume paths
                for i, job in enumerate(jobs_to_process):
                    if i < len(resume_paths):
                        store.mark_resume_generated(job['id'], resume_paths[i])
            
            # Send email notification
            if not args.no_email:
                logger.info("Sending email notification...")
                notifier = EmailNotifier(config)
                if notifier.send_notification(jobs_to_process, resume_paths):
                    # Mark jobs as notified
                    job_ids = [j['id'] for j in jobs_to_process]
                    store.mark_as_notified(job_ids)
                    logger.info("Email notification sent successfully!")
                else:
                    logger.warning("Failed to send email notification")
        
        logger.info("=" * 60)
        logger.info("Job scan completed successfully!")
        logger.info(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Scan interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
