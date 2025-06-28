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
```

### 7. Install App to Workspace
Go to **Install App** → **Install to Workspace**

## 🔄 After Configuration Changes

### CRITICAL: You MUST Create Slash Commands in Slack App Settings!

The bot code registers the commands, but Slack requires them to be explicitly created in your app configuration:

1. **Go to Slack API** → **Your App** → **Slash Commands**
2. **Click "Create New Command"** (do this twice - once for each command)
3. **Fill in exactly as shown above** (including the `/` prefix)
4. **Save each command**

### Then:
1. **Reinstall the app** if you made scope changes
2. **Restart your bot**:
   ```bash
   python phase1.py
   ```
3. **Test slash commands** in Slack:
   - Type `/` in any channel
   - Look for `/bot-settings` and `/bot-help`
   - If they don't appear, wait a few minutes and try again

## 🧪 Testing Checklist

After setup, test these features:

### ✅ Slash Commands
- [ ] `/bot-settings` opens settings modal
- [ ] `/bot-help` shows help message
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

## 🚨 URGENT TROUBLESHOOTING

### Slash Commands Still Don't Appear?

**Step 1: Verify Slash Commands Are Created**
1. Go to https://api.slack.com/apps → Your App → **Slash Commands**
2. You should see BOTH commands listed:
   - `/bot-settings`
   - `/bot-help`
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
   python phase1.py
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

---

## 🔧 Common Issues & Solutions

### "Commands don't appear in autocomplete"
- **Cause**: Commands not created in Slack app settings
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

## 📋 Required App Configuration Summary

```
Scopes: app_mentions:read, channels:history, chat:write, im:history, im:write, commands
Slash Commands: /bot-settings, /bot-help  
Features: Socket Mode ✅, App Home ✅, Event Subscriptions ✅
Events: app_mention, message.im
```

## 🎯 Final Verification

Run this command to test everything:
```bash
python phase1.py
```

Look for these log messages:
```
✅ Bot initialized: YourBot (ID: U...)
✅ Phase 1 Slack bot started and waiting for messages  
✅ Event handlers and slash commands registered
```

If you see these logs and followed the setup above, slash commands should work! 🚀
