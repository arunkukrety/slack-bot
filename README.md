# Phase 1 - Complete Slack Bot

A single-file Slack bot that responds with "Hello World!" and includes full settings management.

## Quick Start

1. **Run the bot:**
   ```bash
   python phase1.py
   ```

2. **First time setup:**
   - The script will auto-install required packages
   - It will create a `.env` file template if missing
   - Add your Slack tokens to the `.env` file
   - Run `python phase1.py` again

3. **Test the bot:**
   - Mention it in a channel: `@your_bot hello`
   - Send it a DM
   - Use slash commands: `/bot-settings` or `/bot-help`

## Features

- ✅ Hello World responses when mentioned
- ⚙️ Configurable settings via Slack UI
- 🏠 App Home tab with settings
- ⚡ Slash commands: `/bot-settings`, `/bot-help`
- 💬 DM support for settings and help
- 🔧 Auto-dependency installation
- 📋 Environment validation

## Settings

Configure via Slack UI:
- **Reply in Thread:** Thread vs new message replies
- **Mention Only:** Respond only when mentioned vs any message
- **Auto Respond:** Enable/disable automatic responses

## Troubleshooting

### Slash Commands Not Working?
If `/bot-settings` and `/bot-help` don't appear:

1. **Missing `commands` scope:** Add to Bot Token Scopes
2. **Commands not configured:** Create in Slash Commands section
3. **Need reinstall:** Reinstall app after scope changes

📋 **See `SLASH_COMMANDS_SETUP.md` for complete setup guide**

## Required Slack App Configuration

Your Slack app needs:
- App Home enabled
- Socket Mode enabled
- Bot scopes: `app_mentions:read`, `channels:history`, `chat:write`, `im:history`, `im:write`, `commands`
- Slash commands: `/bot-settings`, `/bot-help`

## Files

- `phase1.py` - Complete bot implementation (single file)
- `.env.example` - Environment template
- `.env` - Your tokens (auto-created)
- `bot_settings.json` - Settings storage (auto-created)
- `SLASH_COMMANDS_SETUP.md` - Detailed setup guide

## Usage

```bash
# Just run it!
python phase1.py

# The bot will:
# 1. Check and install dependencies
# 2. Validate environment
# 3. Start and connect to Slack
# 4. Be ready to respond!
```

That's it! Everything is handled automatically. 🚀
