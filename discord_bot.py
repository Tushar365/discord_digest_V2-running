import discord
from dotenv import load_dotenv
import os
from message_db import store_message, init_db
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='discord_bot.log'
)

load_dotenv()

class MultiChannelClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_running = False
        self._connection_status = False
        
    @property
    def is_connected(self):
        return self._connection_status and self.is_running and not self.is_closed()
        
    async def start(self, *args, **kwargs):
        self.is_running = True
        await super().start(*args, **kwargs)
        
    async def close(self):
        print("Initiating bot shutdown...")
        self.is_running = False
        try:
            # Close any active database connections
            from message_db import close_db_connection
            close_db_connection()
            print("Database connections closed")
        except Exception as e:
            print(f"Error closing database connection: {e}")
        try:
            await self.change_presence(status=discord.Status.offline)
            print("Bot status set to offline")
        except Exception as e:
            print(f"Error changing presence: {e}")
        await super().close()
        print("Bot shutdown complete")
    
    async def on_ready(self):
        self._connection_status = True
        init_db()
        # Split channel IDs from environment variable
        self.target_channels = os.getenv('TARGET_CHANNEL_IDS', '').split(',')
        
        print(f'Logged in as {self.user}')
        print(f"Monitoring channels: {self.target_channels}")

        # Print accessible channels for verification
        for guild in self.guilds:
            print(f"\nGuild: {guild.name}")
            for channel in guild.channels:
                print(f"- {channel.name} (ID: {channel.id})")

    async def on_message(self, message):
        # Check if message is in target channels
        if str(message.channel.id) in self.target_channels:
            print(f"Message in monitored channel: {message.channel.name}")
            store_message(message)

# Configure intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True

client = MultiChannelClient(intents=intents)

def check_connection_status():
    if not client:
        return False
    return client.is_connected

def main():
    import signal
    import asyncio

    def signal_handler(sig, frame):
        print("Shutting down bot...")
        asyncio.create_task(client.close())

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        client.run(os.getenv('DISCORD_TOKEN'))
    except KeyboardInterrupt:
        print("Received keyboard interrupt")
    finally:
        if client.is_running:
            asyncio.run(client.close())

if __name__ == "__main__":
    main()