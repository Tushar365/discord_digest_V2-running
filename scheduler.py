"""
Discord Message Digest Scheduler

This script manages the scheduling and delivery of daily message digests from Discord.
It supports customizable timezone settings and provides options for immediate testing
and schedule preview.
"""

import logging
import logging.handlers
import os
import pytz
from typing import Dict, Union
from datetime import datetime
from argparse import ArgumentParser, Namespace
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from summary_engine import generate_summary
from email_sender import send_email
from base_config import DISCORD_CONFIG

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging with rotation
log_file = os.path.join('logs', 'scheduler.log')
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set up rotating file handler
file_handler = logging.handlers.RotatingFileHandler(
    log_file,
    maxBytes=1024 * 1024,  # 1MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(formatter)

# Set up console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Configure root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Import configuration values
DEFAULT_TIMEZONE = DISCORD_CONFIG['DEFAULT_TIMEZONE']
DEFAULT_HOUR = DISCORD_CONFIG['DEFAULT_HOUR']
DEFAULT_MINUTE = DISCORD_CONFIG['DEFAULT_MINUTE']

def get_next_email_time(timezone: str = DEFAULT_TIMEZONE, hour=DEFAULT_HOUR, minute=DEFAULT_MINUTE):
    """
    Calculate the next scheduled email time.
    
    Args:
        timezone (str): Timezone string
        hour (int): Hour of day (0-23)
        minute (int): Minute of hour (0-59)
        
    Returns:
        dict: Schedule information including next run time and countdown
    """
    logger.info(f"Calculating next email time for {timezone} at {hour:02d}:{minute:02d}")
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
        logger.info(f"Initializing DigestScheduler with timezone: {timezone}")
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
            tz = pytz.timezone(timezone)
            logger.debug(f"Timezone '{timezone}' validated successfully")
            return tz
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Invalid timezone: {timezone}. Defaulting to {DEFAULT_TIMEZONE}")
            return pytz.timezone(DEFAULT_TIMEZONE)

    def daily_job(self) -> None:
        """Execute the daily digest job."""
        logger.info("Starting daily digest job")
        try:
            logger.info("Generating summary")
            summary = generate_summary()
            if summary:
                logger.info("Sending email digest")
                send_email(summary)
                logger.info("Daily digest sent successfully")
            else:
                logger.warning("No content available for digest")
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
        logger.debug(f"Calculating next email time for {hour:02d}:{minute:02d}")
        now = datetime.now(self.timezone)
        trigger = CronTrigger(hour=hour, minute=minute)
        next_run = trigger.get_next_fire_time(None, now)
        
        logger.info(f"Next email scheduled for: {next_run}")
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
        logger.info(f"Starting scheduler with time {hour:02d}:{minute:02d}")
        self.scheduler.add_job(
            self.daily_job,
            CronTrigger(hour=hour, minute=minute),
            id='daily_digest'
        )
        
        next_run = self.get_next_email_time(hour, minute)
        logger.info(f"Scheduler started. Next run at: {next_run['next_email_time']}")
        
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped by user")
        except Exception as e:
            logger.error(f"Scheduler error: {str(e)}", exc_info=True)
        finally:
            logger.info("Scheduler shutdown complete")

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
    args = parser.parse_args()
    logger.debug(f"Parsed arguments: {args}")
    return args

def main() -> None:
    """Main entry point for the script."""
    logger.info("Starting Discord Message Digest Scheduler")
    args = parse_arguments()
    scheduler = DigestScheduler(args.timezone)
    
    if args.preview:
        logger.info("Preview mode activated")
        next_email_info = scheduler.get_next_email_time()
        logger.info(f"Next email will be sent at: {next_email_info['next_email_time']}")
        logger.info(f"Time until next email: {next_email_info['time_until_next_email']}")
        logger.info(f"Timezone: {next_email_info['timezone']}")
        return
        
    if args.test:
        logger.info("Test mode activated - running job immediately")
        scheduler.daily_job()
    else:
        logger.info("Starting scheduler in normal mode")
        scheduler.start()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}", exc_info=True)
        raise