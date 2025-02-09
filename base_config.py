
"""Base configuration settings for Discord Digest."""
from typing import Dict, Any

# Discord Bot Configuration
DISCORD_CONFIG: Dict[str, Any] = {
    'TARGET_CHANNEL_IDS': [],
    'DEFAULT_TIMEZONE': 'America/Los_Angeles',
    'DEFAULT_HOUR': 19,
    'DEFAULT_MINUTE': 0
}

# OpenAI Configuration
OPENAI_CONFIG: Dict[str, Any] = {
    'MODEL': 'gpt-3.5-turbo',
    'TEMPERATURE': 0.7,
    'MAX_TOKENS': 1000
}

# Email Configuration
EMAIL_CONFIG: Dict[str, Any] = {
    'SMTP_SERVER': 'smtp.gmail.com',
    'SMTP_PORT': 587,
    'SUBJECT_PREFIX': '[Discord Digest]'
}

# Database Configuration
DB_CONFIG: Dict[str, Any] = {
    'DB_NAME': 'messages.db',
    'MESSAGE_TABLE': 'messages'
}
