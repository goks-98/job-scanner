"""
Email notification service using Gmail SMTP.
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import List, Optional
from pathlib import Path
import logging

from src.utils.helpers import load_config


class EmailNotifier:
    """Send job notifications via Gmail SMTP."""
    
    def __init__(self, config: dict = None):
        """
        Initialize the email notifier.
        
        Args:
            config: Configuration dictionary. If None, loads from settings.yaml
        """
        self.config = config or load_config()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        email_config = self.config.get('email', {})
        self.sender = email_config.get('sender', '')
        self.password = email_config.get('password', '')
        self.recipient = email_config.get('recipient', '')
        self.smtp_server = email_config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = email_config.get('smtp_port', 587)
    
    def _create_job_card_html(self, job) -> str:
        """Create HTML card for a single job."""
        location_badge = ""
        if job.get('is_eu'):
            location_badge = '<span style="background: #4CAF50; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-left: 8px;">EU</span>'
        elif job.get('is_uae'):
            location_badge = '<span style="background: #2196F3; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-left: 8px;">UAE</span>'
        
        posted_date = job.get('posted_date', 'Unknown')
        if hasattr(posted_date, 'strftime'):
            posted_date = posted_date.strftime('%b %d, %Y')
        
        return f'''
        <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin-bottom: 16px; background: #fafafa;">
            <h3 style="margin: 0 0 8px 0; color: #1a1a1a;">
                {job.get('title', 'Unknown Position')} {location_badge}
            </h3>
            <p style="margin: 4px 0; color: #666;">
                <strong>{job.get('company', 'Unknown')}</strong> • {job.get('location', 'Unknown')}
            </p>
            <p style="margin: 4px 0; color: #888; font-size: 13px;">
                Posted: {posted_date}
            </p>
            <a href="{job.get('url', '#')}" 
               style="display: inline-block; margin-top: 12px; padding: 8px 16px; 
                      background: #1976D2; color: white; text-decoration: none; 
                      border-radius: 4px; font-weight: 500;">
                Apply Now →
            </a>
        </div>
        '''
    
    def _create_email_html(self, jobs: List[dict], resume_paths: List[str] = None) -> str:
        """Create full HTML email content."""
        eu_jobs = [j for j in jobs if j.get('is_eu')]
        uae_jobs = [j for j in jobs if j.get('is_uae')]
        other_jobs = [j for j in jobs if not j.get('is_eu') and not j.get('is_uae')]
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                     max-width: 600px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
            <div style="background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <h1 style="color: #1a1a1a; margin-bottom: 8px;">
                    🔔 New Data Engineer Jobs Found
                </h1>
                <p style="color: #666; margin-bottom: 24px;">
                    {len(jobs)} new positions matching your criteria • {datetime.now().strftime('%b %d, %Y')}
                </p>
        '''
        
        # EU Jobs Section
        if eu_jobs:
            html += f'''
                <h2 style="color: #4CAF50; border-bottom: 2px solid #4CAF50; padding-bottom: 8px;">
                    🇪🇺 EU Positions ({len(eu_jobs)})
                </h2>
            '''
            for job in eu_jobs:
                html += self._create_job_card_html(job)
        
        # UAE Jobs Section
        if uae_jobs:
            html += f'''
                <h2 style="color: #2196F3; border-bottom: 2px solid #2196F3; padding-bottom: 8px; margin-top: 24px;">
                    🇦🇪 UAE Positions ({len(uae_jobs)})
                </h2>
            '''
            for job in uae_jobs:
                html += self._create_job_card_html(job)
        
        # Other Jobs Section
        if other_jobs:
            html += f'''
                <h2 style="color: #757575; border-bottom: 2px solid #757575; padding-bottom: 8px; margin-top: 24px;">
                    🌍 Other Positions ({len(other_jobs)})
                </h2>
            '''
            for job in other_jobs:
                html += self._create_job_card_html(job)
        
        # Resume attachments note
        if resume_paths:
            html += f'''
                <div style="background: #E3F2FD; border-radius: 8px; padding: 16px; margin-top: 24px;">
                    <p style="margin: 0; color: #1565C0;">
                        <strong>📎 {len(resume_paths)} tailored resume(s) attached</strong><br>
                        <span style="font-size: 13px;">Each resume is optimized for the specific job posting.</span>
                    </p>
                </div>
            '''
        
        html += '''
                <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 24px 0;">
                <p style="color: #888; font-size: 12px; text-align: center;">
                    Generated by FAANG Job Scanner • <a href="#" style="color: #888;">Unsubscribe</a>
                </p>
            </div>
        </body>
        </html>
        '''
        
        return html
    
    def send_notification(self, jobs: List[dict], resume_paths: List[str] = None) -> bool:
        """
        Send job notification email.
        
        Args:
            jobs: List of job dictionaries
            resume_paths: Optional list of resume file paths to attach
            
        Returns:
            True if email sent successfully
        """
        if not jobs:
            self.logger.info("No jobs to notify about")
            return False
        
        if not self.sender or not self.password:
            self.logger.error("Email credentials not configured. Please update config/settings.yaml")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🔔 {len(jobs)} New Data Engineer Jobs Found - {datetime.now().strftime('%b %d')}"
            msg['From'] = self.sender
            msg['To'] = self.recipient
            
            # Create plain text version
            plain_text = f"Found {len(jobs)} new Data Engineer positions.\n\n"
            for job in jobs:
                plain_text += f"- {job.get('title')} at {job.get('company')}\n"
                plain_text += f"  Location: {job.get('location')}\n"
                plain_text += f"  URL: {job.get('url')}\n\n"
            
            # Create HTML version
            html_content = self._create_email_html(jobs, resume_paths)
            
            msg.attach(MIMEText(plain_text, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            # Attach resumes
            if resume_paths:
                for resume_path in resume_paths:
                    if os.path.exists(resume_path):
                        self._attach_file(msg, resume_path)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)
            
            self.logger.info(f"Successfully sent notification for {len(jobs)} jobs")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            return False
    
    def _attach_file(self, msg: MIMEMultipart, file_path: str):
        """Attach a file to the email."""
        try:
            with open(file_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            
            encoders.encode_base64(part)
            filename = os.path.basename(file_path)
            part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
            msg.attach(part)
            
        except Exception as e:
            self.logger.error(f"Failed to attach file {file_path}: {e}")
    
    def send_test(self) -> bool:
        """Send a test email to verify configuration."""
        test_jobs = [{
            'id': 'test123',
            'title': 'Senior Data Engineer (Test)',
            'company': 'Test Company',
            'location': 'Berlin, Germany',
            'url': 'https://example.com/job',
            'posted_date': datetime.now(),
            'is_eu': True,
            'is_uae': False
        }]
        
        self.logger.info("Sending test email...")
        return self.send_notification(test_jobs)
