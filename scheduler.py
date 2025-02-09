#!/usr/bin/env python3

"""
Discord Message Digest Scheduler

This script manages the scheduling and delivery of daily message digests from Discord.
It supports customizable timezone settings and provides options for immediate testing
and schedule preview.
"""

import logging
import pytz
from typing import Dict, Union
from datetime import datetime
from argparse import ArgumentParser, Namespace
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from summary_engine import generate_summary
from email_sender import send_email

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_TIMEZONE = 'America/Los_Angeles'
DEFAULT_HOUR = 19
DEFAULT_MINUTE = 00

# Standalone function for backwards compatibility
def get_next_email_time(timezone: str = DEFAULT_TIMEZONE, hour=DEFAULT_HOUR, minute=DEFAULT_MINUTE):
    """
    Standalone function for backwards compatibility.
    Calculate the next scheduled email time.
    
    Args:
        timezone (str): Timezone string
        hour (int): Hour of day (0-23)
        minute (int): Minute of hour (0-59)
        
    Returns:
        dict: Schedule information including next run time and countdown
    """
    scheduler = DigestScheduler(timezone)
    return scheduler.get_next_email_time(hour, minute)

class DigestScheduler:
    """Manages the scheduling and execution of daily digest jobs."""
    
    def __init__(self, timezone: str = DEFAULT_TIMEZONE):
        """
        Initialize the DigestScheduler.
        
        Args:
            timezone (str): Timezone string (e.g., 'Asia/Kolkata', 'America/Los_Angeles')
        """
        self.timezone = self._validate_timezone(timezone)
        self.scheduler = BlockingScheduler(timezone=self.timezone)
        
    @staticmethod
    def _validate_timezone(timezone: str) -> pytz.timezone:
        """
        Validate and return a timezone object.
        
        Args:
            timezone (str): Timezone string to validate
            
        Returns:
            pytz.timezone: Validated timezone object
        """
        try:
            return pytz.timezone(timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Invalid timezone: {timezone}. Defaulting to {DEFAULT_TIMEZONE}")
            return pytz.timezone(DEFAULT_TIMEZONE)

    def daily_job(self) -> None:
        """Execute the daily digest job."""
        try:
            logger.info("Starting digest job")
            summary = generate_summary()
            send_email(summary)
            logger.info("Digest sent successfully")
        except Exception as e:
            logger.error(f"Error in daily job: {str(e)}", exc_info=True)

    def get_next_email_time(
        self,
        hour: int = DEFAULT_HOUR,
        minute: int = DEFAULT_MINUTE
    ) -> Dict[str, Union[datetime, str]]:
        """
        Calculate the next scheduled email time.
        
        Args:
            hour (int): Hour of day (0-23)
            minute (int): Minute of hour (0-59)
            
        Returns:
            dict: Schedule information including next run time and countdown
        """
        now = datetime.now(self.timezone)
        trigger = CronTrigger(hour=hour, minute=minute)
        next_run = trigger.get_next_fire_time(None, now)
        
        return {
            'next_email_time': next_run,
            'time_until_next_email': next_run - now,
            'timezone': str(self.timezone)
        }

    def start(self, hour: int = DEFAULT_HOUR, minute: int = DEFAULT_MINUTE) -> None:
        """
        Start the scheduler.
        
        Args:
            hour (int): Hour of day (0-23)
            minute (int): Minute of hour (0-59)
        """
        self.scheduler.add_job(
            self.daily_job,
            CronTrigger(hour=hour, minute=minute),
            id='daily_digest'
        )
        
        logger.info(f"Scheduler started at {datetime.now(self.timezone)}")
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped")

def parse_arguments() -> Namespace:
    """Parse and return command line arguments."""
    parser = ArgumentParser(description='Discord Message Digest Scheduler')
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run job immediately'
    )
    parser.add_argument(
        '--preview',
        action='store_true',
        help='Show next email time'
    )
    parser.add_argument(
        '--timezone',
        type=str,
        default=DEFAULT_TIMEZONE,
        help='Timezone for scheduling (e.g., America/Los_Angeles)'
    )
    return parser.parse_args()

def main() -> None:
    """Main entry point for the script."""
    args = parse_arguments()
    scheduler = DigestScheduler(args.timezone)
    
    if args.preview:
        next_email_info = scheduler.get_next_email_time()
        logger.info(f"Next email will be sent at: {next_email_info['next_email_time']}")
        logger.info(f"Time until next email: {next_email_info['time_until_next_email']}")
        logger.info(f"Timezone: {next_email_info['timezone']}")
        return
        
    if args.test:
        scheduler.daily_job()
    else:
        scheduler.start()

if __name__ == "__main__":
    main()