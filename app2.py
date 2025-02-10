# app.py

import os
import sys
import time
import json
import signal
import logging
import sqlite3
import subprocess
import importlib
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import pytz
import plotly.express as px
from dotenv import load_dotenv, set_key

from summary_engine import generate_summary
from scheduler import DigestScheduler, get_next_email_time
from email_sender import send_email
import discord_bot
from base_config import (
    DISCORD_CONFIG,
    OPENAI_CONFIG,
    EMAIL_CONFIG,
    DB_CONFIG
)

# === Configuration and Setup ===

def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger('DiscordDigest')

def init_streamlit():
    """Initialize Streamlit configuration and session state."""
    st.set_page_config(
        page_title="Discord Digest Control Panel",
        layout="wide"
    )
    
    # Initialize session state variables
    session_vars = ['message_cache', 'last_refresh', 'bot_process', 'scheduler_process']
    for var in session_vars:
        if var not in st.session_state:
            st.session_state[var] = None

# === Bot Management ===

class BotManager:
    @staticmethod
    def check_status():
        """Check if the bot is running and connected."""
        try:
            process_running = (
                st.session_state.bot_process is not None and 
                st.session_state.bot_process.poll() is None
            )
            
            if process_running:
                importlib.reload(discord_bot)
                return discord_bot.check_connection_status()
            return False
        except Exception as e:
            logger.error(f"Error checking bot status: {e}", exc_info=True)
            return False

    @staticmethod
    def start():
        """Start the Discord bot process."""
        try:
            if not BotManager.check_status():
                python_executable = sys.executable
                st.session_state.bot_process = subprocess.Popen(
                    [python_executable, 'discord_bot.py'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                time.sleep(5)
                
                if st.session_state.bot_process.poll() is None:
                    if discord_bot.check_connection_status():
                        return True
                    BotManager.stop()
                else:
                    _, stderr = st.session_state.bot_process.communicate()
                    logger.error(f"Bot failed to start. Error: {stderr}")
                    st.session_state.bot_process = None
            return False
        except Exception as e:
            logger.error(f"Error starting bot: {e}", exc_info=True)
            return False

    @staticmethod
    def stop():
        """Stop the Discord bot process."""
        try:
            if BotManager.check_status():
                st.session_state.bot_process.send_signal(signal.SIGTERM)
                
                for _ in range(10):
                    if st.session_state.bot_process.poll() is not None:
                        break
                    time.sleep(1)
                
                if st.session_state.bot_process.poll() is None:
                    st.session_state.bot_process.kill()
                    st.session_state.bot_process.wait()
                
                st.session_state.bot_process = None
                st.session_state.message_cache = None
                st.session_state.last_refresh = None
                return True
        except Exception as e:
            logger.error(f"Error stopping bot: {e}", exc_info=True)
            if st.session_state.bot_process:
                try:
                    st.session_state.bot_process.kill()
                    st.session_state.bot_process = None
                except:
                    pass
        return False

# === Data Management ===

class DataManager:
    @staticmethod
    def load_messages(days=1):
        """Load messages from the database with caching."""
        try:
            cache_age = (
                datetime.now() - st.session_state.last_refresh 
                if st.session_state.last_refresh else None
            )
            if (st.session_state.message_cache is not None and 
                cache_age and cache_age.seconds < 300):
                return st.session_state.message_cache

            conn = sqlite3.connect('messages.db')
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = """
            SELECT content, author, timestamp, channel_id 
            FROM messages 
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            """
            df = pd.read_sql_query(
                query, 
                conn, 
                params=(cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),)
            )
            conn.close()

            st.session_state.message_cache = df
            st.session_state.last_refresh = datetime.now()
            return df
        except Exception as e:
            logger.error(f"Error loading messages: {e}", exc_info=True)
            return pd.DataFrame(columns=['content', 'author', 'timestamp', 'channel_id'])

# === Page Components ===

class PageComponents:
    @staticmethod
    def show_dashboard():
        """Render the dashboard page."""
        st.title("Discord Digest Dashboard")
        
        if st.button("🔄 Refresh Data"):
            st.session_state.message_cache = None
        
        col1, col2, col3 = st.columns(3)
        
        try:
            df = DataManager.load_messages(1)
            df_week = DataManager.load_messages(7)
            
            with col1:
                st.metric("Messages Today", len(df))
            with col2:
                st.metric("Messages This Week", len(df_week))
            with col3:
                unique_authors = df_week['author'].nunique() if not df_week.empty else 0
                st.metric("Active Users", unique_authors)
            
            PageComponents._render_activity_charts(df_week)
            
        except Exception as e:
            logger.error(f"Error in dashboard: {e}", exc_info=True)
            st.error(f"Error loading dashboard: {str(e)}")

    @staticmethod
    def _render_activity_charts(df_week):
        """Render activity charts for the dashboard."""
        if not df_week.empty:
            df_week['date'] = pd.to_datetime(df_week['timestamp']).dt.date
            daily_counts = df_week.groupby('date').size().reset_index(name='count')
            
            fig = px.line(daily_counts, x='date', y='count', 
                         title='Daily Message Count')
            st.plotly_chart(fig, use_container_width=True)
            
            user_counts = df_week['author'].value_counts().head(5)
            fig2 = px.bar(x=user_counts.index, y=user_counts.values,
                         title='Most Active Users',
                         labels={'x': 'User', 'y': 'Messages'})
            st.plotly_chart(fig2, use_container_width=True)

    @staticmethod
    def show_message_viewer():
        """Render the message viewer page."""
        st.title("Message Viewer")
        
        days = st.slider("Select time range (days)", 1, 30, 1)
        df = DataManager.load_messages(days)
        
        search_term = st.text_input("Search messages")
        if search_term and not df.empty:
            df = df[df['content'].str.contains(search_term, case=False, na=False)]
        
        PageComponents._render_message_table(df)

    @staticmethod
    def _render_message_table(df):
        """Render paginated message table with export option."""
        ROWS_PER_PAGE = 50
        total_pages = (len(df) // ROWS_PER_PAGE) + (1 if len(df) % ROWS_PER_PAGE > 0 else 0)
        
        if total_pages > 0:
            page_num = st.number_input('Page', min_value=1, max_value=total_pages, value=1)
            start_idx = (page_num - 1) * ROWS_PER_PAGE
            end_idx = start_idx + ROWS_PER_PAGE
            
            st.dataframe(df.iloc[start_idx:end_idx], height=500)
            
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

# === Main Application ===

def main():
    """Main application entry point."""
    logger = setup_logging()
    load_dotenv()
    init_streamlit()
    
    # Sidebar setup
    st.sidebar.title("Discord Digest Controls")
    st.sidebar.subheader("Connect to the Discord Server")
    
    if st.sidebar.button("Connect"):
        with st.spinner("Starting bot..."):
            if BotManager.start():
                st.sidebar.success("Bot connected successfully!")
            else:
                st.sidebar.error("Failed to connect bot!")
    
    # Page navigation
    page = st.sidebar.selectbox(
        "Select Page",
        ["Dashboard", "Message Viewer", "Email Controls", "Settings"]
    )
    
    # Page routing
    if page == "Dashboard":
        PageComponents.show_dashboard()
    elif page == "Message Viewer":
        PageComponents.show_message_viewer()
    elif page == "Email Controls":
        PageComponents.show_email_controls()
    elif page == "Settings":
        PageComponents.show_settings()
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("Discord Digest Bot v2.0")

if __name__ == "__main__":
    main()