# Rakieta-BOT

A versatile Discord bot built with Discord.py that includes AI capabilities via Google's Gemini AI, a ticketing system, and various server management commands.

## Features

- **AI Integration**: Ask questions to Google's Gemini AI directly through Discord using the `/ask` command
- **Ticketing System**: A full-featured ticket management system for user support
- **Custom Presence**: Administrators can change the bot's presence status
- **Moderation Tools**: Commands to help manage the server, including invite cleanup
- **Game System**: 1v1 match system with customizable stakes
- **Economy System**: Virtual currency management with role shop integration

## Setup

### Prerequisites
- Python 3.8+
- Discord Bot Token
- Google Gemini API key

### Installation

1. Clone the repository:
```shell script
git clone https://github.com/yourusername/Rakieta-BOT.git
cd Rakieta-BOT
```


2. Create a virtual environment:
```shell script
python -m venv .venv
```


3. Activate the virtual environment:
```shell script
# On Windows
.venv\Scripts\activate
# On Unix or MacOS
source .venv/bin/activate
```


4. Install dependencies:
```shell script
pip install -r requirements.txt
```


5. Create a `.env` file with the following variables:
```
DISCORD_TOKEN=your_discord_token
GUILD=your_guild_id
TICKET_CHANNEL_ID=your_ticket_channel_id
GEMINI_API_KEY=your_gemini_api_key
```


### Running the Bot

```shell script
python discord_bot.py
```


## Commands

- `/ask [question]` - Ask a question to the Gemini AI
- `/ping` - Check the bot's latency
- `/match_1v1 [stake] [match_type]` - Start a 1v1 match with specified stake
- `/return_role [role]` - Return a purchased role for a 50% refund
- `/change_presence [presence_type] [name]` - Change bot's presence (admin only)
- `/clear_invites` - Remove server invites with less than 5 uses (admin only)
