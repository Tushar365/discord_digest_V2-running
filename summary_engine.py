# summary_generator.py
from openai import OpenAI 
from dotenv import load_dotenv
from message_db import get_daily_messages
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DiscordDigest')

load_dotenv()

from langgraph_pipeline import create_pipeline
import base_config as bc
import advanced_config as ac

def generate_summary():
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_KEY'))
        pipeline = create_pipeline()
        
        # Get messages from database
        channel_ids = os.getenv('TARGET_CHANNEL_IDS', '').split(',')
        messages = get_daily_messages(channel_ids)
        print(f"Retrieved {len(messages)} messages from database")
        
        # Group messages by channel_id
        channel_conversations = {}
        total_messages = len(messages)
        unique_authors = set()
        
        for content, author, timestamp, channel_id in messages:
            unique_authors.add(author)
            if channel_id not in channel_conversations:
                channel_conversations[channel_id] = []
            channel_conversations[channel_id].append(f"{author}: {content}")
        
        if not channel_conversations:
            return "No messages to summarize for today."
        
        # Prepare conversations for each channel
        channel_summaries = {}
        for channel_id, conversation in channel_conversations.items():
            channel_text = "\n".join(conversation)
            
            # Create summary for each channel
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Summarize Discord conversations systematically."
                    },
                    {
                        "role": "user",
                        "content": f"""Analyze conversations in Channel ID {channel_id}:

{channel_text}

Format:
1. Key discussion topics
2. Important decisions
3. Action items
4. Notable quotes
5. Overall sentiment
"""
                    }
                ]
            )
            
            channel_summaries[channel_id] = response.choices[0].message.content
        
        # Create overall activity summary
        overall_summary = f"""Daily Activity Overview:
- Total Messages: {total_messages}
- Active Channels: {len(channel_conversations)}
- Unique Contributors: {len(unique_authors)}

Channel Summaries:
"""
        
        # Combine channel summaries
        for channel_id, summary in channel_summaries.items():
            overall_summary += f"Channel ID: {channel_id}\n{summary}\n\n"
        
        # Generate overall discussion
        all_conversations = "\n".join(" ".join(conv) for conv in channel_conversations.values())
        overall_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "Provide a comprehensive cross-channel summary."
                },
                {
                    "role": "user",
                    "content": f"""Analyze conversations across all channels:

{all_conversations}

Provide a comprehensive overview:
1. Cross-channel themes
2. Interconnected discussions
3. Significant patterns
4. Overall community insights
"""
                }
            ]
        )
        
        # Add overall discussion
        overall_summary += "Overall Discussion:\n"
        overall_summary += overall_response.choices[0].message.content
        
        return overall_summary.strip()
    
    except Exception as e:
        logger.error(f"Error generating summary: {e}", exc_info=True)
        return f"Error generating summary: {str(e)}"

if __name__ == "__main__":
    print("\nGenerating summary...")
    result = generate_summary()
    print("\nSummary:")
    print(result)