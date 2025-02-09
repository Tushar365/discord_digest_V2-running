# Discord Digest

Discord Digest is a Python bot that summarizes your Discord server's conversations and delivers them to your email inbox.  It uses OpenAI for summarization and provides a Streamlit-based control panel for easy management.

## Features

* Summarizes conversations from specified Discord channels.
* Delivers summaries via email at scheduled intervals.
* Customizable summarization settings (coming soon).
* Streamlit-based web UI for controlling the bot and viewing summaries.

# Create & Update .env :
```
DISCORD_TOKEN=your_discord_bot_token
TARGET_CHANNEL_IDS=your_channel_ids
OPENAI_KEY=your_openai_api_key
EMAIL_USER=your_email
EMAIL_PASSWORD=your_email_password
EMAIL_TO=recipient_email
```
## Installation

1. **Clone the repository:**

   ```cmd
   git clone https://github.com/Tushar365/discord_digest.git
   cd discord_digest
    ```
2. **Create virtual environment :**
```
python -m venv venv
```
**On mac/linux:**
```
source venv/bin/activate
```
**On Windows:**
```
venv\Scripts\activate
```
# Install dependencies :
```
pip install -r requirements.txt
```
# start the bot and initiate database :
```
python discord_bot.py
```
# start the timer shedule manually :
set the timer and zone manually :
scheduler.py (change the code)
then run :
```
python scheduler.py
```
# check next sheduled mail time :
```
python scheduler.py --preview
```
# start the control pannel server to use UI:
```
streamlit run app.py
```



