# Phase 1 - Complete Slack Bot

A single-file Slack bot that responds with "Hello World!" and includes full settings management with slash commands.

## Quick Start

1. **Run the bot:**
   ```bash
   python main.py
   ```

2. **First time setup:**
   - The script will auto-install required packages
   - It will create a `.env` file template if missing
   - Add your Slack tokens to the `.env` file
   - Run `python main.py` again

3. **Test the bot:**
   - Mention it in a channel: `@your_bot hello`
   - Send it a DM
   - Use slash commands: `/bot-settings` or `/bot-help`

## Features

- ✅ Hello World responses when mentioned
- ⚙️ Configurable settings via Slack UI
- 🏠 App Home tab with settings
- ⚡ Slash commands: `/bot-settings`, `/bot-help`, `/bot-debug`
- 💬 DM support for settings and help
- 🔧 Auto-dependency installation
- 📋 Environment validation

## Settings

Configure via Slack UI:
- **Reply in Thread:** Thread vs new message replies
- **Mention Only:** Respond only when mentioned vs any message
- **Auto Respond:** Enable/disable automatic responses

## Files

- `main.py` - Complete bot implementation (single file)
- `.env` - Your tokens (auto-created template)
- `bot_settings.json` - Settings storage (auto-created)

## Usage

```bash
# Just run it!
python main.py

# The bot will:
# 1. Check and install dependencies
# 2. Validate environment
# 3. Start and connect to Slack
# 4. Be ready to respond!
```

---

# 🔧 Slack App Setup Guide - Fix Slash Commands

## Problem: Slash Commands Not Visible in Slack UI

If `/bot-settings` and `/bot-help` commands don't appear when you type `/` in Slack, follow this setup guide.

## ✅ Complete Slack App Configuration

### 1. Go to Your Slack App Settings
- Visit: https://api.slack.com/apps
- Select your app (e.g., "SlackBot Test")

### 2. Configure Bot Token Scopes
Go to **OAuth & Permissions** → **Scopes** → **Bot Token Scopes** and add:

```
✅ app_mentions:read    - Read messages mentioning the bot
✅ channels:history     - Read messages in channels
✅ chat:write          - Send messages  
✅ im:history          - Read direct messages
✅ im:write            - Send direct messages
✅ commands            - Use slash commands (REQUIRED!)
```

### 3. Configure Slash Commands
Go to **Slash Commands** → **Create New Command**:

#### Command 1: `/bot-settings`
```
Command: /bot-settings
Request URL: (leave blank - using Socket Mode)
Short Description: Configure bot behavior and settings
Usage Hint: Configure the bot's response settings
```

#### Command 2: `/bot-help`
```
Command: /bot-help  
Request URL: (leave blank - using Socket Mode)
Short Description: Show bot help and usage information
Usage Hint: Get help with bot commands and features
```

#### Command 3: `/bot-debug`
```
Command: /bot-debug
Request URL: (leave blank - using Socket Mode)
Short Description: Show debug information and troubleshooting
Usage Hint: Debug bot status and configuration
```

### 4. Enable App Home
Go to **App Home** → **Show Tabs**:
```
✅ Home Tab (Enable this!)
✅ Messages Tab (optional)
```

### 5. Enable Socket Mode
Go to **Socket Mode**:
```
✅ Enable Socket Mode
```

### 6. Enable Event Subscriptions
Go to **Event Subscriptions**:
```
✅ Enable Events
```

**Subscribe to bot events:**
```
✅ app_mention
✅ message.im
✅ app_home_opened
```

### 7. Install App to Workspace
Go to **Install App** → **Install to Workspace**

## 🔄 After Configuration Changes

### CRITICAL: You MUST Create Slash Commands in Slack App Settings!

The bot code registers the commands, but Slack requires them to be explicitly created in your app configuration:

1. **Go to Slack API** → **Your App** → **Slash Commands**
2. **Click "Create New Command"** (do this three times - once for each command)
3. **Fill in exactly as shown above** (including the `/` prefix)
4. **Save each command**

### Then:
1. **Reinstall the app** if you made scope changes
2. **Restart your bot**:
   ```bash
   python main.py
   ```
3. **Test slash commands** in Slack:
   - Type `/` in any channel
   - Look for `/bot-settings`, `/bot-help`, and `/bot-debug`
   - If they don't appear, wait a few minutes and try again

## 🧪 Testing Checklist

After setup, test these features:

### ✅ Slash Commands
- [ ] `/bot-settings` opens settings modal
- [ ] `/bot-help` shows help message
- [ ] `/bot-debug` shows debug information
- [ ] Commands appear in autocomplete when typing `/`

### ✅ Mentions  
- [ ] `@your_bot hello` triggers Hello World response
- [ ] Response appears in thread (if enabled)

### ✅ Settings
- [ ] Click bot name → Home tab → Configure Settings works
- [ ] Settings save and apply correctly
- [ ] DM with "settings" shows configuration info

### ✅ Direct Messages
- [ ] Send any DM to bot gets response (if auto-respond enabled)
- [ ] Send "help" shows help information

## 🚨 Common Issues

### "Commands not appearing in autocomplete"
- **Cause**: Missing `commands` scope or slash commands not configured
- **Fix**: Add `commands` scope and create slash commands in app settings

### "Bot doesn't respond to commands" 
- **Cause**: Socket Mode not enabled or bot not running
- **Fix**: Enable Socket Mode and restart bot

### "Permission errors"
- **Cause**: Missing required scopes
- **Fix**: Add all required scopes and reinstall app

### "Settings modal doesn't open"
- **Cause**: App Home not enabled
- **Fix**: Enable App Home tab in app settings

## 🚨 URGENT TROUBLESHOOTING

### Slash Commands Still Don't Appear?

**Step 1: Verify Slash Commands Are Created**
1. Go to https://api.slack.com/apps → Your App → **Slash Commands**
2. You should see ALL commands listed:
   - `/bot-settings`
   - `/bot-help`
   - `/bot-debug`
3. If they're missing, click **"Create New Command"** for each one

**Step 2: Check Command Configuration**
Each command should have:
- ✅ Command name (with `/` prefix)
- ✅ Short description
- ✅ Request URL can be blank (using Socket Mode)

**Step 3: Force Refresh**
1. **Reinstall your app** to the workspace:
   - Go to **Install App** → **Reinstall to Workspace**
2. **Restart your bot**:
   ```bash
   python main.py
   ```
3. **Clear Slack cache**:
   - Desktop: Help → Troubleshooting → Clear Cache and Restart
   - Web: Hard refresh (Ctrl+F5 or Cmd+Shift+R)

**Step 4: Test in Different Locations**
- Try commands in different channels
- Try in DMs with the bot
- Try typing just `/` to see all available commands

### Still Not Working?

1. **Check bot logs** when running the bot for any error messages
2. **Verify tokens** in your `.env` file are correct
3. **Try creating a simple test command** in Slack app settings to see if the problem is general

## 📋 Required App Configuration Summary

```
Scopes: app_mentions:read, channels:history, chat:write, im:history, im:write, commands
Slash Commands: /bot-settings, /bot-help, /bot-debug
Features: Socket Mode ✅, App Home ✅, Event Subscriptions ✅
Events: app_mention, message.im, app_home_opened
```

## 🎯 Final Verification

Run this command to test everything:
```bash
python main.py
```

Look for these log messages:
```
Bot initialized: YourBot (ID: U...)
Starting Slack bot...
```

If you see these logs and followed the setup above, slash commands should work! 🚀

## 🔧 Alternative Access Methods

If slash commands still don't work, you can always use:

1. **App Home Tab**: Click bot name → Home tab → ⚙️ Configure Settings
2. **Direct Message**: Send "settings" or "help" to the bot via DM
3. **Manual Configuration**: Edit `bot_settings.json` file directly

---

That's it! Everything is handled automatically. 🚀
