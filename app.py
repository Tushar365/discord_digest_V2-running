# app.py
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import pytz
from summary_engine import generate_summary
from scheduler import DigestScheduler, get_next_email_time
from email_sender import send_email
import plotly.express as px
import os
from dotenv import load_dotenv, set_key
import logging
import importlib
import discord_bot
import json
from base_config import (
    DISCORD_CONFIG,
    OPENAI_CONFIG,
    EMAIL_CONFIG,
    DB_CONFIG
)

if 'scheduler_process' not in st.session_state:
    st.session_state.scheduler_process = None

importlib.reload(discord_bot)  # Reload to get fresh status
is_connected = discord_bot.check_connection_status()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DiscordDigest')

load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Discord Digest Control Panel",
    layout="wide"
)

# Initialize session state
if 'message_cache' not in st.session_state:
    st.session_state.message_cache = None
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = None
if 'bot_process' not in st.session_state:
    st.session_state.bot_process = None

def check_bot_status():
    try:
        # First check if process exists and is running
        process_running = (
            st.session_state.bot_process is not None and 
            st.session_state.bot_process.poll() is None
        )
        
        if process_running:
            # Import with reload to get fresh status
            import importlib
            import discord_bot
            importlib.reload(discord_bot)
            return discord_bot.check_connection_status()
        
        return False
    except Exception as e:
        logger.error(f"Error checking bot status: {e}", exc_info=True)
        return False


def start_bot():
    try:
        if not check_bot_status():
            import subprocess
            import sys
            import time
            
            # Get the Python executable path
            python_executable = sys.executable
            
            # Start the bot process with the correct Python interpreter
            st.session_state.bot_process = subprocess.Popen(
                [python_executable, 'discord_bot.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for a moment to let the bot initialize
            time.sleep(5)
            
            # Check if process is still running and connected
            if st.session_state.bot_process.poll() is None:
                # Try to import and check connection
                import discord_bot
                if discord_bot.check_connection_status():
                    return True
                else:
                    logger.error("Bot process started but failed to connect")
                    stop_bot()
            else:
                # If process has terminated, get error output
                _, stderr = st.session_state.bot_process.communicate()
                logger.error(f"Bot failed to start. Error: {stderr}")
                st.session_state.bot_process = None
                
            return False
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        return False

def stop_bot():
    try:
        if check_bot_status():
            import signal
            import time
            
            # First try graceful shutdown
            st.session_state.bot_process.send_signal(signal.SIGTERM)
            
            # Wait for up to 10 seconds for graceful shutdown
            for _ in range(10):
                if st.session_state.bot_process.poll() is not None:
                    break
                time.sleep(1)
            
            # If still running, force kill
            if st.session_state.bot_process.poll() is None:
                st.session_state.bot_process.kill()
                st.session_state.bot_process.wait()
            
            st.session_state.bot_process = None
            
            # Clear message cache to force refresh
            st.session_state.message_cache = None
            st.session_state.last_refresh = None
            
            return True
    except Exception as e:
        logger.error(f"Error stopping bot: {e}", exc_info=True)
        if st.session_state.bot_process:
            try:
                st.session_state.bot_process.kill()  # Force kill as last resort
                st.session_state.bot_process = None
            except:
                pass
        return False
    return False

# Sidebar
st.sidebar.title("Discord Digest Controls")

# Bot Control Section
# Bot Control Section
st.sidebar.subheader("Connect to the Discord Server")

def get_last_logs(n=2):
    try:
        with open('discord_bot.log', 'r') as log_file:
            lines = log_file.readlines()
            last_logs = lines[-n:] if len(lines) >= n else lines
            return ''.join(last_logs)
    except FileNotFoundError:
        return "No logs found"
    except Exception as e:
        return f"Error reading logs: {str(e)}"

if st.sidebar.button("Connect"):
    with st.spinner("Starting bot..."):
        if start_bot():
            st.sidebar.success("Bot connected successfully!")
        else:
            st.sidebar.error("Bot connected successfully!")

# Display last 2 logs
st.sidebar.text_area("Recent Logs", get_last_logs(2), height=100)
st.sidebar.divider()

page = st.sidebar.selectbox(
    "Select Page",
    ["Dashboard", "Message Viewer", "Email Controls", "Settings"]
)


def load_messages(days=1):
    try:
        # Check cache first
        cache_age = datetime.now() - st.session_state.last_refresh if st.session_state.last_refresh else None
        if st.session_state.message_cache is not None and cache_age and cache_age.seconds < 300:  # 5 min cache
            return st.session_state.message_cache

        conn = sqlite3.connect('messages.db')
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = """
        SELECT content, author, timestamp, channel_id 
        FROM messages 
        WHERE timestamp >= ?
        ORDER BY timestamp DESC
        """
        df = pd.read_sql_query(query, conn, params=(cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),))
        conn.close()

        # Update cache
        st.session_state.message_cache = df
        st.session_state.last_refresh = datetime.now()

        return df
    except Exception as e:
        logger.error(f"Error loading messages: {e}", exc_info=True)
        st.error(f"Error loading messages: {str(e)}")
        return pd.DataFrame(columns=['content', 'author', 'timestamp', 'channel_id'])

def generate_and_send_digest():
    try:
        with st.spinner('Generating digest...'):
            summary = generate_summary()
            if summary:
                st.text_area("Preview", summary, height=300)
                if st.button("Send Digest"):
                    try:
                        send_email(summary)
                        st.success("Digest sent successfully!")
                    except Exception as e:
                        logger.error(f"Failed to send digest: {e}", exc_info=True)
                        st.error(f"Failed to send digest: {str(e)}")
            else:
                st.warning("No messages to summarize")
    except Exception as e:
        logger.error(f"Error generating digest: {e}", exc_info=True)
        st.error(f"Error generating digest: {str(e)}")

def show_dashboard():
    st.title("Discord Digest Dashboard")
    
    # Refresh button
    if st.button("🔄 Refresh Data"):
        st.session_state.message_cache = None
    
    # Key Metrics
    col1, col2, col3 = st.columns(3)
    
    try:
        df = load_messages(1)
        df_week = load_messages(7)
        
        with col1:
            st.metric("Messages Today", len(df))
            
        with col2:
            st.metric("Messages This Week", len(df_week))
            
        with col3:
            unique_authors = df_week['author'].nunique() if not df_week.empty else 0
            st.metric("Active Users", unique_authors)
        
        # Message Activity Chart
        st.subheader("Message Activity")
        if not df_week.empty:
            df_week['date'] = pd.to_datetime(df_week['timestamp']).dt.date
            daily_counts = df_week.groupby('date').size().reset_index(name='count')
            fig = px.line(daily_counts, x='date', y='count', title='Daily Message Count')
            st.plotly_chart(fig, use_container_width=True)
        
            # Most Active Users
            st.subheader("Most Active Users")
            user_counts = df_week['author'].value_counts().head(5)
            fig2 = px.bar(x=user_counts.index, y=user_counts.values, 
                         title='Most Active Users',
                         labels={'x': 'User', 'y': 'Messages'})
            st.plotly_chart(fig2, use_container_width=True)
    except Exception as e:
        logger.error(f"Error in dashboard: {e}", exc_info=True)
        st.error(f"Error loading dashboard: {str(e)}")

def show_message_viewer():
    st.title("Message Viewer")
    
    days = st.slider("Select time range (days)", 1, 30, 1)
    df = load_messages(days)
    
    # Message filtering
    search_term = st.text_input("Search messages")
    if search_term and not df.empty:
        df = df[df['content'].str.contains(search_term, case=False, na=False)]
    
    # Display messages with pagination
    ROWS_PER_PAGE = 50
    total_pages = (len(df) // ROWS_PER_PAGE) + (1 if len(df) % ROWS_PER_PAGE > 0 else 0)
    
    if total_pages > 0:
        page_num = st.number_input('Page', min_value=1, max_value=total_pages, value=1)
        start_idx = (page_num - 1) * ROWS_PER_PAGE
        end_idx = start_idx + ROWS_PER_PAGE
        
        st.dataframe(df.iloc[start_idx:end_idx], height=500)
        
        # Export option
        if st.button("Export to CSV"):
            csv = df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                "discord_messages.csv",
                "text/csv"
            )
    else:
        st.info("No messages found")

def show_email_controls():
    st.title("Email Controls")
    
    # Check if required environment variables are set
    required_vars = ['EMAIL_USER', 'EMAIL_PASSWORD', 'EMAIL_TO']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        st.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        st.info("Please set these variables in your .env file")
        return
    
    # Next Mail Time Preview
    if st.button("Preview Next Mail Time"):
        try:
            next_email_info = get_next_email_time()
            if next_email_info:
                st.success(f"Next email will be sent at: {next_email_info['next_email_time']}")
                st.info(f"Time until next email: {next_email_info['time_until_next_email']}")
                st.info(f"Timezone: {next_email_info['timezone']}")
            else:
                st.warning("Could not calculate next email time")
        except Exception as e:
            logger.error(f"Error calculating next mail time: {e}", exc_info=True)
            st.error(f"Error calculating next mail time: {str(e)}")
    
    # Manual digest generation
    st.subheader("Generate Manual Digest")
    try:
        generate_and_send_digest()
    except Exception as e:
        logger.error(f"Error in digest generation: {e}", exc_info=True)
        st.error(f"Failed to generate digest: {str(e)}")
def update_env_file(key, value):
    """Update .env file with new value."""
    try:
        dotenv_file = os.path.join(os.path.dirname(__file__), '.env')
        set_key(dotenv_file, key, value)
        return True
    except Exception as e:
        logger.error(f"Error updating .env file: {e}")
        return False

def save_discord_config(updates):
    """Save Discord configuration updates to a JSON file."""
    try:
        with open('discord_config.json', 'w') as f:
            json.dump(updates, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving Discord configuration: {e}")
        return False

def load_discord_config():
    """Load Discord configuration from JSON file."""
    try:
        if os.path.exists('discord_config.json'):
            with open('discord_config.json', 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading Discord configuration: {e}")
    return {}


def show_settings():
    st.title("Essential Settings")
    
    # Load current configurations
    discord_config = load_discord_config()
    
    with st.form("settings_form"):
        st.subheader("Schedule Settings")
        
        # Timezone selection
        timezones = pytz.all_timezones
        current_tz = discord_config.get('DEFAULT_TIMEZONE', DISCORD_CONFIG['DEFAULT_TIMEZONE'])
        new_tz = st.selectbox(
            "Timezone",
            timezones,
            index=timezones.index(current_tz),
            help="Select your local timezone"
        )
        
        # Time settings
        col1, col2 = st.columns(2)
        with col1:
            hour = st.number_input(
                "Hour (24-hour)",
                min_value=0,
                max_value=23,
                value=discord_config.get('DEFAULT_HOUR', DISCORD_CONFIG['DEFAULT_HOUR']),
                help="Hour to send the daily digest (24-hour format)"
            )
        with col2:
            minute = st.number_input(
                "Minute",
                min_value=0,
                max_value=59,
                value=discord_config.get('DEFAULT_MINUTE', DISCORD_CONFIG['DEFAULT_MINUTE']),
                help="Minute to send the daily digest"
            )
        
        st.divider()
        st.subheader("Discord Settings")
        
        # Channel IDs
        channel_ids = st.text_input(
            "Channel IDs",
            value=','.join(map(str, discord_config.get('TARGET_CHANNEL_IDS', DISCORD_CONFIG['TARGET_CHANNEL_IDS']))),
            help="Enter channel IDs separated by commas (e.g., 123456789,987654321)"
        )
        
        # Discord Token
        current_token = os.getenv('DISCORD_TOKEN', '')
        new_token = st.text_input(
            "Discord Token",
            value=current_token,
            type="password",
            help="Your Discord bot token"
        )
        
        st.divider()
        st.subheader("Email Settings")
        
        # Receiver Email
        current_email = os.getenv('EMAIL_TO', '')
        new_email = st.text_input(
            "Receiver Email",
            value=current_email,
            help="Email address to receive the daily digest"
        )
        
        # Submit button
        submitted = st.form_submit_button("Save All Settings")
        
        if submitted:
            # Update Discord configuration
            discord_updates = {
                'DEFAULT_TIMEZONE': new_tz,
                'DEFAULT_HOUR': hour,
                'DEFAULT_MINUTE': minute,
                'TARGET_CHANNEL_IDS': [int(id.strip()) for id in channel_ids.split(',') if id.strip()]
            }
            
            # Save Discord config
            discord_saved = save_discord_config(discord_updates)
            
            # Update environment variables
            env_updates = []
            if new_token != current_token:
                env_updates.append(('DISCORD_TOKEN', new_token))
            if new_email != current_email:
                env_updates.append(('EMAIL_TO', new_email))
            
            # Apply environment updates
            env_saved = all(update_env_file(key, value) for key, value in env_updates)
            
            if discord_saved and env_saved:
                st.success("All settings saved successfully!")
                st.info("Please restart the application for changes to take effect.")
            else:
                st.error("Failed to save some settings. Please try again.")

    # Display current schedule information
    st.divider()
    if st.button("Show Next Scheduled Digest"):
        try:
            next_email_info = get_next_email_time(new_tz, hour, minute)
            st.info(f"Next digest will be sent at: {next_email_info['next_email_time']}")
            st.info(f"Time until next digest: {next_email_info['time_until_next_email']}")
        except Exception as e:
            st.error(f"Error calculating next digest time: {str(e)}")
# Main content
if page == "Dashboard":
    show_dashboard()
elif page == "Message Viewer":
    show_message_viewer()
elif page == "Email Controls":
    show_email_controls()
elif page == "Settings":
    show_settings()

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Discord Digest Bot v2.0")
