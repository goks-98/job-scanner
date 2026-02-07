"""
SQLite database for storing and tracking scraped jobs.
"""

import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from sqlalchemy import create_engine, Column, String, Text, Boolean, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from src.utils.helpers import get_project_root


Base = declarative_base()


class JobModel(Base):
    """SQLAlchemy model for jobs table."""
    __tablename__ = 'jobs'
    
    id = Column(String(50), primary_key=True)
    title = Column(String(500), nullable=False)
    company = Column(String(200), nullable=False)
    location = Column(String(200))
    description = Column(Text)
    url = Column(String(1000))
    posted_date = Column(DateTime)
    requirements = Column(Text)  # JSON string
    keywords = Column(Text)  # JSON string
    is_eu = Column(Boolean, default=False)
    is_uae = Column(Boolean, default=False)
    scraped_at = Column(DateTime, default=datetime.now)
    notified = Column(Boolean, default=False)
    notified_at = Column(DateTime, default=datetime.now)
    resume_generated = Column(Boolean, default=False)
    resume_path = Column(String(500))


class JobStore:
    """Database interface for job storage and tracking."""
    
    def __init__(self, db_path: str = None):
        """
        Initialize the job store.
        
        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            db_path = get_project_root() / "data" / "jobs.db"
        
        # Ensure directory exists
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(self.engine)
        
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def add_job(self, job_data: Dict[str, Any]) -> bool:
        """
        Add a new job to the database.
        
        Args:
            job_data: Job data dictionary
            
        Returns:
            True if job was added, False if it already exists
        """
        try:
            # Check if job already exists
            existing = self.session.query(JobModel).filter_by(id=job_data['id']).first()
            if existing:
                return False
            
            # Convert list fields to JSON strings
            import json
            requirements = json.dumps(job_data.get('requirements', []))
            keywords = json.dumps(job_data.get('keywords', []))
            
            # Handle date fields (convert string to datetime if needed)
            posted_date = job_data.get('posted_date')
            if isinstance(posted_date, str):
                try:
                    posted_date = datetime.fromisoformat(posted_date)
                except ValueError:
                    posted_date = None
                    
            scraped_at = job_data.get('scraped_at', datetime.now())
            if isinstance(scraped_at, str):
                try:
                    scraped_at = datetime.fromisoformat(scraped_at)
                except ValueError:
                    scraped_at = datetime.now()
            
            job = JobModel(
                id=job_data['id'],
                title=job_data['title'],
                company=job_data['company'],
                location=job_data.get('location', ''),
                description=job_data.get('description', ''),
                url=job_data.get('url', ''),
                posted_date=posted_date,
                requirements=requirements,
                keywords=keywords,
                is_eu=job_data.get('is_eu', False),
                is_uae=job_data.get('is_uae', False),
                scraped_at=scraped_at
            )
            
            self.session.add(job)
            self.session.commit()
            return True
            
        except Exception as e:
            self.session.rollback()
            raise e
    
    def add_jobs(self, jobs: List[Dict[str, Any]]) -> int:
        """
        Add multiple jobs to the database.
        
        Args:
            jobs: List of job data dictionaries
            
        Returns:
            Number of new jobs added
        """
        added = 0
        for job in jobs:
            if self.add_job(job):
                added += 1
        return added
    
    def get_unnotified_jobs(self) -> List[JobModel]:
        """Get all jobs that haven't been notified yet."""
        return self.session.query(JobModel).filter_by(notified=False).all()
    
    def mark_as_notified(self, job_ids: List[str]):
        """Mark jobs as notified."""
        self.session.query(JobModel).filter(
            JobModel.id.in_(job_ids)
        ).update({'notified': True, 'notified_at': datetime.now()}, synchronize_session='fetch')
        self.session.commit()
    
    def mark_resume_generated(self, job_id: str, resume_path: str):
        """Mark that a resume was generated for this job."""
        job = self.session.query(JobModel).filter_by(id=job_id).first()
        if job:
            job.resume_generated = True
            job.resume_path = resume_path
            self.session.commit()
    
    def get_job_by_id(self, job_id: str) -> Optional[JobModel]:
        """Get a job by its ID."""
        return self.session.query(JobModel).filter_by(id=job_id).first()
    
    def get_all_jobs(self, limit: int = 100) -> List[JobModel]:
        """Get all jobs, ordered by scraped date."""
        return self.session.query(JobModel).order_by(
            JobModel.scraped_at.desc()
        ).limit(limit).all()
    
    def get_eu_jobs(self, unnotified_only: bool = False) -> List[JobModel]:
        """Get all EU jobs."""
        query = self.session.query(JobModel).filter_by(is_eu=True)
        if unnotified_only:
            query = query.filter_by(notified=False)
        return query.all()
    
    def get_uae_jobs(self, unnotified_only: bool = False) -> List[JobModel]:
        """Get all UAE jobs."""
        query = self.session.query(JobModel).filter_by(is_uae=True)
        if unnotified_only:
            query = query.filter_by(notified=False)
        return query.all()
    
    def job_exists(self, job_id: str) -> bool:
        """Check if a job already exists in the database."""
        return self.session.query(JobModel).filter_by(id=job_id).first() is not None
    
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        return {
            'total_jobs': self.session.query(JobModel).count(),
            'eu_jobs': self.session.query(JobModel).filter_by(is_eu=True).count(),
            'uae_jobs': self.session.query(JobModel).filter_by(is_uae=True).count(),
            'notified': self.session.query(JobModel).filter_by(notified=True).count(),
            'pending': self.session.query(JobModel).filter_by(notified=False).count(),
            'resumes_generated': self.session.query(JobModel).filter_by(resume_generated=True).count()
        }
    
    def close(self):
        """Close the database session."""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
