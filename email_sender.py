import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DiscordDigest')

load_dotenv()

def send_email(content):
    try:
        msg = MIMEText(content)
        msg['Subject'] = 'Your Daily Discord Digest'
        msg['From'] = os.getenv('EMAIL_USER')
        msg['To'] = os.getenv('EMAIL_TO')  # Send to yourself
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASSWORD'))
            smtp.send_message(msg)
            logger.info("Email sent successfully")
    except Exception as e:
        logger.error(f"Error sending email: {e}", exc_info=True)
        raise