
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
from dotenv import load_dotenv
import logging

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
        if st.session_state.bot_process:
            return st.session_state.bot_process.poll() is None
        return False
    except:
        return False

def start_bot():
    try:
        if not check_bot_status():
            import subprocess
            st.session_state.bot_process = subprocess.Popen(['python', 'discord_bot.py'])
            return True
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        return False
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
st.sidebar.subheader("Bot Control")

# Check if bot client exists and is connected
import discord_bot
is_connected = discord_bot.check_connection_status()

# Status indicator
status_color = "🟢" if is_connected else "🔴"
st.sidebar.markdown(f"### {status_color} Bot Status: {'Connected' if is_connected else 'Disconnected'}")

if not is_connected:
    if st.sidebar.button("Connect Bot"):
        try:
            # Import subprocess here to ensure it's available
            import subprocess
            import time
            
            # Start the bot process
            st.session_state.bot_process = subprocess.Popen(['python', 'discord_bot.py'])
            
            # Wait for a moment to let the bot connect
            time.sleep(2)
            
            # Check if process is still running
            if st.session_state.bot_process.poll() is None:
                st.sidebar.success("Bot started successfully!")
                st.rerun()
            else:
                st.sidebar.error("Bot failed to start")
                st.session_state.bot_process = None
        except Exception as e:
            st.sidebar.error(f"Connection error: {str(e)}")
            if hasattr(st.session_state, 'bot_process') and st.session_state.bot_process:
                st.session_state.bot_process.kill()
                st.session_state.bot_process = None
else:
    if st.sidebar.button("Disconnect"):
        if stop_bot():
            st.sidebar.success("Bot disconnected successfully!")
            st.rerun()
        else:
            st.sidebar.error("Failed to disconnect bot")

st.sidebar.divider()

page = st.sidebar.selectbox(
    "Select Page",
    ["Dashboard", "Message Viewer", "Email Controls"]
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

# Main content
if page == "Dashboard":
    show_dashboard()
elif page == "Message Viewer":
    show_message_viewer()
elif page == "Email Controls":
    show_email_controls()

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Discord Digest Bot v1.0")
