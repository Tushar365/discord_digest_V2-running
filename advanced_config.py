
"""Advanced configuration settings for Discord Digest."""
from typing import Dict, Any, List
from langchain.prompts import PromptTemplate

# LangGraph Node Configurations
PREPROCESSING_CONFIG: Dict[str, Any] = {
    'min_message_length': 5,
    'max_messages_per_channel': 1000,
    'excluded_authors': ['bot', 'system']
}

# Summary Generation Templates
SUMMARY_TEMPLATES: Dict[str, str] = {
    'channel': """Analyze conversations in Channel {channel_id}:
{messages}
Format:
1. Key discussion topics
2. Important decisions
3. Action items
4. Notable quotes
5. Overall sentiment""",
    
    'cross_channel': """Analyze conversations across all channels:
{conversations}
Provide a comprehensive overview:
1. Cross-channel themes
2. Interconnected discussions
3. Significant patterns
4. Overall community insights"""
}

# LangGraph Pipeline Configuration
PIPELINE_CONFIG: Dict[str, Any] = {
    'nodes': ['preprocessor', 'analyzer', 'summarizer', 'formatter'],
    'max_retries': 3,
    'timeout': 300,
    'cache_results': True
}

# Monitoring and Logging
MONITORING_CONFIG: Dict[str, Any] = {
    'log_level': 'INFO',
    'enable_tracing': True,
    'metrics_enabled': True
}
