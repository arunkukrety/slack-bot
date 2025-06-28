#!/usr/bin/env python3
"""
Phase 1 - Complete Slack Bot with Settings and Slash Commands

A comprehensive Slack bot that:
- Responds with "Hello World" when mentioned
- Includes configurable settings via Slack UI
- Supports slash commands for settings and help
- Auto-verifies setup and dependencies
- Single file - just run and go!

Usage:
    python phase1.py

Requirements:
    - SLACK_BOT_TOKEN and SLACK_APP_TOKEN in .env file
    - slack-bolt and python-dotenv packages
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from typing import Dict, Any, Optional

# Setup verification and dependency installation
def verify_and_install_dependencies():
    """Verify and install required dependencies."""
    required_packages = {
        'slack_bolt': 'slack-bolt>=1.15.0',
        'dotenv': 'python-dotenv>=0.19.0'
    }
    
    missing_packages = []
    
    for package, pip_name in required_packages.items():
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(pip_name)
    
    if missing_packages:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to install packages: {e}")
            sys.exit(1)

# Verify dependencies first
verify_and_install_dependencies()

# Now import the packages
from dotenv import load_dotenv
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables
load_dotenv()


class EnvironmentSetup:
    """Handles environment setup and validation."""
    
    @staticmethod
    def create_env_file_if_missing():
        """Create .env file with template if it doesn't exist."""
        env_file = ".env"
        if not os.path.exists(env_file):
            env_template = """# Slack Bot Tokens - Replace with your actual tokens
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
"""
            with open(env_file, 'w') as f:
                f.write(env_template)
            return False
        return True
    
    @staticmethod
    def validate_environment() -> tuple[Optional[str], Optional[str]]:
        """Validate environment variables and return tokens."""
        slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
        slack_app_token = os.getenv("SLACK_APP_TOKEN")
        
        if not slack_bot_token or slack_bot_token == "xoxb-your-bot-token-here":
            logging.error("SLACK_BOT_TOKEN not set or using template value")
            return None, None
            
        if not slack_app_token or slack_app_token == "xapp-your-app-token-here":
            logging.error("SLACK_APP_TOKEN not set or using template value")
            return None, None
        
        return slack_bot_token, slack_app_token


class BotSettings:
    """Manages bot settings that can be configured through Slack UI."""
    
    def __init__(self, settings_file: str = "bot_settings.json"):
        self.settings_file = settings_file
        self.default_settings = {
            "reply_in_thread": True,  # Whether to reply in thread or as new message
            "mention_only": True,     # Whether to respond only when mentioned or in any thread
            "auto_respond": True      # Whether the bot should respond automatically
        }
        self.settings = self.load_settings()
    
    def load_settings(self) -> Dict[str, Any]:
        """Load settings from file or create default settings."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                # Ensure all default keys exist
                for key, value in self.default_settings.items():
                    if key not in settings:
                        settings[key] = value
                return settings
            else:
                return self.default_settings.copy()
        except Exception as e:
            logging.error(f"Error loading settings: {e}")
            return self.default_settings.copy()
    
    def save_settings(self) -> None:
        """Save current settings to file."""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            logging.info("Settings saved successfully")
        except Exception as e:
            logging.error(f"Error saving settings: {e}")
    
    def get(self, key: str) -> Any:
        """Get a setting value."""
        return self.settings.get(key, self.default_settings.get(key))
    
    def set(self, key: str, value: Any) -> None:
        """Set a setting value and save."""
        if key in self.default_settings:
            self.settings[key] = value
            self.save_settings()
            # Reload settings to ensure they're in sync with the file
            self.settings = self.load_settings()
            logging.info(f"Setting '{key}' updated to '{value}' and reloaded from file")
        else:
            raise ValueError(f"Unknown setting: {key}")


class Phase1SlackBot:
    """A complete Phase 1 Slack bot with Hello World responses and configurable settings."""
    
    def __init__(self, slack_bot_token: str, slack_app_token: str):
        self.app = AsyncApp(token=slack_bot_token)
        self.socket_mode_handler = AsyncSocketModeHandler(self.app, slack_app_token)
        self.client = AsyncWebClient(token=slack_bot_token)
        self.settings = BotSettings()
        self.bot_id = None
        
        # Set up event handlers
        self.app.event("app_mention")(self.handle_mention)
        self.app.message()(self.handle_message)
        self.app.event("app_home_opened")(self.handle_home_opened)
        
        # Settings management
        self.app.action("settings_button")(self.handle_settings_button)
        self.app.view("settings_modal")(self.handle_settings_submission)
        
        # Block actions for checkbox interactions in modal
        self.app.action("reply_in_thread_setting")(self.handle_checkbox_action)
        self.app.action("mention_only_setting")(self.handle_checkbox_action)
        self.app.action("auto_respond_setting")(self.handle_checkbox_action)
        
        # Slash commands
        self.app.command("/bot-settings")(self.handle_settings_command)
        self.app.command("/bot-help")(self.handle_help_command)
        self.app.command("/bot-debug")(self.handle_debug_command)
    
    async def initialize_bot_info(self) -> None:
        """Get the bot's ID and other info."""
        try:
            auth_info = await self.client.auth_test()
            self.bot_id = auth_info["user_id"]
            bot_name = auth_info.get("user", "Unknown")
            logging.info(f"Bot initialized: {bot_name} (ID: {self.bot_id})")
        except Exception as e:
            logging.error(f"Failed to get bot info: {e}")
            self.bot_id = None
    
    async def handle_mention(self, event, say):
        """Handle mentions of the bot in channels."""
        await self._send_hello_world(event, say)
    
    async def handle_message(self, message, say):
        """Handle direct messages to the bot."""
        # Only process direct messages
        if (message.get("channel_type") == "im" and 
            not message.get("subtype")):
            
            text = message.get("text", "").lower().strip()
            
            # Check if user is asking for settings
            if any(keyword in text for keyword in ["settings", "config", "configure", "setup", "preferences"]):
                await self._send_settings_info(message, say)
                return
            
            # Check if user is asking for help
            if any(keyword in text for keyword in ["help", "commands", "what can you do", "capabilities"]):
                await self._send_help_info(message, say)
                return
            
            # Regular Hello World response
            if self.settings.get("auto_respond"):
                await self._send_hello_world(message, say)
    
    async def _send_hello_world(self, event, say):
        """Send Hello World response based on settings."""
        user_id = event.get("user")
        channel_type = event.get("channel_type", "unknown")
        text = event.get("text", "")
        
        # Skip messages from the bot itself
        if user_id == self.bot_id:
            return
        
        # Reload settings to ensure we have the latest values
        self.settings.settings = self.settings.load_settings()
        
        # Check settings
        mention_only = self.settings.get("mention_only")
        auto_respond = self.settings.get("auto_respond")
        reply_in_thread = self.settings.get("reply_in_thread")
        
        # Check if we should only respond to mentions
        if mention_only:
            # For channels, only respond if mentioned
            if channel_type != "im":
                if not (hasattr(self, "bot_id") and self.bot_id and f"<@{self.bot_id}>" in text):
                    return
        
        # Check if auto_respond is enabled
        if not auto_respond:
            return
        
        # Determine thread_ts based on settings
        thread_ts = None
        if reply_in_thread:
            thread_ts = event.get("thread_ts", event.get("ts"))
        
        try:
            await say(text="*Hello World!* :wave:", thread_ts=thread_ts)
        except Exception as e:
            logging.error(f"Error sending Hello World: {e}")
    
    async def _send_settings_info(self, message, say):
        """Send settings information and options via DM."""
        # Reload settings to ensure we show the latest values
        self.settings.settings = self.settings.load_settings()
        settings = self.settings.settings

        settings_text = (
            "*⚙️ Bot Settings*\n\n"
            "*Current Configuration:*\n"
            f"* Reply in Thread: {'*✅ Enabled*' if settings['reply_in_thread'] else '*❌ Disabled*'}\n"
            f"* Mention Only: {'*✅ Enabled*' if settings['mention_only'] else '*❌ Disabled*'}\n"
            f"* Auto Respond: {'*✅ Enabled*' if settings['auto_respond'] else '*❌ Disabled*'}\n\n"
            "*To Change Settings:*\n"
            "1. *App Home Tab*: Click on my name in the sidebar → Home tab → Configure Settings\n"
            "2. *Slash Command*: Type `/bot-settings` in any channel\n"
            "3. *Direct Message*: Just ask me about `settings` or `config`\n\n"
            "*What each setting does:*\n"
            "> *Reply in Thread*: Controls whether I reply in threads or send new messages\n"
            "> *Mention Only*: If enabled, I only respond when @mentioned\n"
            "> *Auto Respond*: If disabled, I won't respond to any messages\n\n"
            "Type `help` for more information! :wave:"
        )

        try:
            await say(text=settings_text)
        except Exception as e:
            logging.error(f"Error sending settings info: {e}")

    async def _send_help_info(self, message, say):
        """Send help information via DM."""
        help_text = (
            "*🤖 Phase 1 Bot Help*\n\n"
            "*What I can do:*\n"
            "* Respond with `Hello World!` when mentioned\n"
            "* Work in channels and direct messages\n"
            "* Configurable behavior through settings\n\n"
            "*Available Commands:*\n"
            "* `/bot-settings` - Configure bot behavior\n"
            "* `/bot-help` - Show this help message\n"
            "* Just mention me with `@bot_name` in any channel\n"
            "* Send me a DM with `settings` or `help`\n\n"
            "*Settings Options:*\n"
            "> *Reply in Thread*: Toggle thread vs new message replies\n"
            "> *Mention Only*: Control when I respond (mention vs any message)\n"
            "> *Auto Respond*: Enable/disable automatic responses\n\n"
            "*Getting Started:*\n"
            "1. Invite me to a channel: `/invite @bot_name`\n"
            "2. Mention me: `@bot_name hello`\n"
            "3. Configure settings: `/bot-settings`\n\n"
            "> Need more help? Just ask! :rocket:"
        )

        try:
            await say(text=help_text)
        except Exception as e:
            logging.error(f"Error sending help info: {e}")

    async def handle_home_opened(self, event, client):
        """Handle when a user opens the App Home tab."""
        user_id = event["user"]
        
        # Get current settings for display
        settings = self.settings.settings
        
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🤖 Phase 1 Bot - Hello World!"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Welcome! This bot responds with `Hello World!` when mentioned. Configure the settings below to customize behavior:"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Current Settings:*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"* Reply in Thread: {'*✅ Yes*' if settings['reply_in_thread'] else '*❌ No*'}\n* Mention Only: {'*✅ Yes*' if settings['mention_only'] else '*❌ No*'}\n* Auto Respond: {'*✅ Yes*' if settings['auto_respond'] else '*❌ No*'}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "⚙️ Configure Settings"},
                        "action_id": "settings_button",
                        "style": "primary"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Available Commands:*\n* `/bot-settings` - Open settings\n* `/bot-help` - Show help\n* Mention me in any channel\n* Send me a direct message"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Quick Start:*\n1. Invite me to a channel: `/invite @bot_name`\n2. Mention me: `@bot_name hello`\n3. I'll respond with `Hello World!` :wave:"
                }
            }
        ]
        
        try:
            await client.views_publish(
                user_id=user_id,
                view={"type": "home", "blocks": blocks}
            )
        except Exception as e:
            logging.error(f"Error publishing home view: {e}")
    
    async def handle_settings_command(self, ack, body, client):
        """Handle /bot-settings slash command."""
        await ack()
        
        user_id = body.get('user_id')
        channel_id = body.get('channel_id')
        trigger_id = body.get('trigger_id')
        
        if not trigger_id:
            await client.chat_postEphemeral(
                channel=channel_id, user=user_id,
                text=":x: *Command error*: Missing session data. Please try the App Home tab for settings."
            )
            return
        
        try:
            await self._open_settings_modal_fast(trigger_id, client, user_id)
        except SlackApiError as modal_error:
            error_msg = str(modal_error).lower()
            logging.error(f"Modal error: {modal_error}")
            
            if "expired_trigger_id" in error_msg or "invalid_trigger" in error_msg:
                text = ":warning: *Session expired*. Please try `/bot-settings` again or use the App Home tab."
            elif "missing_scope" in error_msg or "not_allowed" in error_msg:
                text = ":x: *Permission error*. Please contact admin to verify bot permissions."
            elif "invalid_arguments" in error_msg:
                text = ":x: *Settings modal unavailable*. Try the App Home tab or mention me for help."
            else:
                text = (
                    "*⚙️ Current Bot Settings:*\n"
                    f"* Reply in Thread: {'*✅*' if self.settings.get('reply_in_thread') else '*❌*'}\n"
                    f"* Mention Only: {'*✅*' if self.settings.get('mention_only') else '*❌*'}\n"
                    f"* Auto Respond: {'*✅*' if self.settings.get('auto_respond') else '*❌*'}\n\n"
                    "Use the App Home tab to change settings."
                )
            await client.chat_postEphemeral(channel=channel_id, user=user_id, text=text)
        except Exception as e:
            logging.error(f"Unexpected error in /bot-settings command: {e}")
            await client.chat_postEphemeral(
                channel=channel_id, user=user_id,
                text=":x: *Settings temporarily unavailable*. Try mentioning me or check the App Home tab."
            )
    
    async def handle_help_command(self, ack, body, client):
        """Handle /bot-help slash command."""
        await ack()
        
        try:
            help_text = (
                "*🤖 Phase 1 Bot Help*\n\n"
                "*What I can do:*\n"
                "* Respond with `Hello World!` when mentioned\n"
                "* Work in channels and direct messages\n"
                "* Configurable behavior through settings\n\n"
                "*Available Commands:*\n"
                "* `/bot-settings` - Configure bot behavior\n"
                "* `/bot-help` - Show this help message\n"
                "* Just mention me with `@bot_name` in any channel\n"
                "* Send me a DM with `settings` or `help`\n\n"
                "*Settings Options:*\n"
                "> *Reply in Thread*: Toggle thread vs new message replies\n"
                "> *Mention Only*: Control when I respond (mention vs any message)\n"
                "> *Auto Respond*: Enable/disable automatic responses\n\n"
                "*Getting Started:*\n"
                "1. Invite me to a channel: `/invite @bot_name`\n"
                "2. Mention me: `@bot_name hello`\n"
                "3. Configure settings: `/bot-settings`\n\n"
                "> Need more help? Just ask! :rocket:"
            )
            
            await client.chat_postEphemeral(
                channel=body["channel_id"],
                user=body["user_id"],
                text=help_text
            )
        except Exception as e:
            logging.error(f"Error handling help command: {e}")
            try:
                await client.chat_postEphemeral(
                    channel=body["channel_id"],
                    user=body["user_id"],
                    text=":x: Error showing help. You can mention me or send a DM for assistance!"
                )
            except Exception:
                pass
    
    async def handle_debug_command(self, ack, body, client):
        """Handle /bot-debug slash command for troubleshooting."""
        await ack()
        
        try:
            logging.info(f"Received /bot-debug command from user {body.get('user_id')}")
            
            # Reload settings to show current values
            self.settings.settings = self.settings.load_settings()
            
            # Get debug information
            trigger_id = body.get("trigger_id", "None")
            
            debug_text = (
                "*🔍 Bot Debug Information*\n\n"
                "*System Status:*\n"
                f"* Bot ID: `{self.bot_id or 'Unknown'}`\n"
                f"* Trigger ID Present: {'*Yes*' if trigger_id != 'None' else '*No*'}\n"
                f"* Settings File: {'*Found*' if os.path.exists('bot_settings.json') else '*Missing*'}\n\n"
                "*Current Settings (reloaded from file):*\n"
                f"* Reply in Thread: `{self.settings.get('reply_in_thread')}`\n"
                f"* Mention Only: `{self.settings.get('mention_only')}`\n"
                f"* Auto Respond: `{self.settings.get('auto_respond')}`\n\n"
                "*Slash Command Test:*\n"
                "> If you can see this message, slash commands are working!\n\n"
                "*Troubleshooting:*\n"
                "> If `/bot-settings` fails: Use App Home tab\n"
                "> If modal doesn't open: Try command again quickly\n"
                "> If persistent issues: Check Slack app configuration\n\n"
                "*Next Steps:*\n"
                "1. Try `/bot-settings` now\n"
                "2. If it fails, use the App Home tab\n"
                "3. Check logs for any error messages"
            )
            
            await client.chat_postEphemeral(
                channel=body["channel_id"],
                user=body["user_id"],
                text=debug_text
            )
            logging.info(f"Sent debug info to user {body['user_id']}")
        except Exception as e:
            logging.error(f"Error handling debug command: {e}")
            try:
                await client.chat_postEphemeral(
                    channel=body["channel_id"],
                    user=body["user_id"],
                    text=f":x: Debug command error: {str(e)}"
                )
            except Exception as fallback_error:
                logging.error(f"Error in debug command fallback: {fallback_error}")
    
    async def handle_settings_button(self, ack, body, client):
        """Handle the settings button click to open modal."""
        await ack()
        
        try:
            # Use the helper method to open settings modal
            await self._open_settings_modal(body["trigger_id"], client)
        except Exception as e:
            logging.error(f"Error opening settings modal: {e}")
    
    async def _open_settings_modal_fast(self, trigger_id, client, user_id):
        """Optimized helper to open settings modal quickly to avoid trigger_id expiration."""
        try:
            # Reload settings from file to ensure we have the latest values
            self.settings.settings = self.settings.load_settings()
            settings = self.settings.settings
            logging.info(f"Opening modal with current settings: {settings}")
            
            # Define option objects once and reuse them for initial_options
            thread_option = {"text": {"type": "plain_text", "text": "Enable thread replies"}, "value": "reply_in_thread"}
            mention_option = {"text": {"type": "plain_text", "text": "Mention only mode"}, "value": "mention_only"}
            auto_respond_option = {"text": {"type": "plain_text", "text": "Enable auto response"}, "value": "auto_respond"}
            
            # Build blocks with properly matching initial_options
            blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Configure your bot preferences:*"}
                }
            ]
            
            # Reply in Thread setting
            thread_block = {
                "type": "section",
                "block_id": "reply_in_thread_block",
                "text": {"type": "mrkdwn", "text": "*Reply in Thread*\nReply to messages in threads instead of new messages"},
                "accessory": {
                    "type": "checkboxes",
                    "action_id": "reply_in_thread_setting",
                    "options": [thread_option]
                }
            }
            if settings.get("reply_in_thread"):
                thread_block["accessory"]["initial_options"] = [thread_option]
            blocks.append(thread_block)
            
            # Mention Only setting
            mention_block = {
                "type": "section", 
                "block_id": "mention_only_block",
                "text": {"type": "mrkdwn", "text": "*Mention Only*\nOnly respond when directly mentioned"},
                "accessory": {
                    "type": "checkboxes",
                    "action_id": "mention_only_setting",
                    "options": [mention_option]
                }
            }
            if settings.get("mention_only"):
                mention_block["accessory"]["initial_options"] = [mention_option]
            blocks.append(mention_block)
            
            # Auto Respond setting
            auto_respond_block = {
                "type": "section",
                "block_id": "auto_respond_block",
                "text": {"type": "mrkdwn", "text": "*Auto Respond*\nAutomatically respond to messages"},
                "accessory": {
                    "type": "checkboxes",
                    "action_id": "auto_respond_setting", 
                    "options": [auto_respond_option]
                }
            }
            if settings.get("auto_respond"):
                auto_respond_block["accessory"]["initial_options"] = [auto_respond_option]
            blocks.append(auto_respond_block)
            
            # Create a minimal, fast-loading modal
            modal_view = {
                "type": "modal",
                "callback_id": "settings_modal",
                "title": {"type": "plain_text", "text": "Bot Settings"},
                "submit": {"type": "plain_text", "text": "Save"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": blocks
            }
            
            # Open modal immediately - this must complete within 3 seconds of slash command
            await client.views_open(trigger_id=trigger_id, view=modal_view)
            logging.info(f"Modal opened successfully for user {user_id}")
            
        except Exception as e:
            logging.error(f"Error opening settings modal: {e}")
            # Re-raise to allow calling function to handle fallback
            raise

    async def _open_settings_modal(self, trigger_id, client):
        """Legacy modal helper - now calls optimized version."""
        await self._open_settings_modal_fast(trigger_id, client, "legacy_call")
    
    async def _send_settings_fallback(self, body, client):
        """Send settings information as fallback when modal fails."""
        settings = self.settings.settings
        
        settings_text = (
            "*⚙️ Bot Settings* (Modal unavailable, showing current settings)\n\n"
            "*Current Configuration:*\n"
            f"* Reply in Thread: {'*✅ Enabled*' if settings['reply_in_thread'] else '*❌ Disabled*'}\n"
            f"* Mention Only: {'*✅ Enabled*' if settings['mention_only'] else '*❌ Disabled*'}\n"
            f"* Auto Respond: {'*✅ Enabled*' if settings['auto_respond'] else '*❌ Disabled*'}\n\n"
            "*To Change Settings:*\n"
            "1. *App Home Tab*: Click on my name in the sidebar → Home tab → ⚙️ Configure Settings\n"
            "2. *Direct Message*: Send me `settings` via DM for interactive setup\n"
            "3. *Try Again*: Wait a moment and try `/bot-settings` again\n\n"
            "> *Tip*: The App Home tab is the most reliable way to access settings!"
        )
        
        try:
            await client.chat_postEphemeral(
                channel=body["channel_id"],
                user=body["user_id"],
                text=settings_text
            )
        except Exception as e:
            logging.error(f"Error sending settings fallback: {e}")
    
    async def handle_checkbox_action(self, ack, body):
        """Handle checkbox interactions in the settings modal"""
        await ack()
        # This just acknowledges the checkbox click - no need to do anything else
        # The actual saving happens when the modal is submitted

    async def handle_settings_submission(self, ack, body, client):
        """Handle settings modal submission."""
        await ack()
        
        try:
            # Extract values from the modal submission
            values = body["view"]["state"]["values"]
            
            # Debug: log the structure we received
            logging.info(f"Modal submission values structure: {values}")
            
            # Update settings based on checkbox selections
            # The structure is values[block_id][action_id]["selected_options"]
            reply_in_thread = len(values.get("reply_in_thread_block", {}).get("reply_in_thread_setting", {}).get("selected_options", [])) > 0
            mention_only = len(values.get("mention_only_block", {}).get("mention_only_setting", {}).get("selected_options", [])) > 0
            auto_respond = len(values.get("auto_respond_block", {}).get("auto_respond_setting", {}).get("selected_options", [])) > 0
            
            # Save settings (this will automatically reload them from file)
            self.settings.set("reply_in_thread", reply_in_thread)
            self.settings.set("mention_only", mention_only)
            self.settings.set("auto_respond", auto_respond)
            
            # Verify settings were saved by reading them back
            current_settings = self.settings.load_settings()
            
            # Send detailed confirmation message
            user_id = body["user"]["id"]
            confirmation_text = (
                "*✅ Settings updated successfully!*\n\n"
                "*New Configuration:*\n"
                f"* Reply in Thread: {'*✅ Enabled*' if current_settings['reply_in_thread'] else '*❌ Disabled*'}\n"
                f"* Mention Only: {'*✅ Enabled*' if current_settings['mention_only'] else '*❌ Disabled*'}\n"
                f"* Auto Respond: {'*✅ Enabled*' if current_settings['auto_respond'] else '*❌ Disabled*'}\n\n"
                "> *Changes take effect immediately!* Try mentioning me to test the new settings."
            )
            
            await client.chat_postMessage(
                channel=user_id,
                text=confirmation_text
            )
            
            logging.info(f"Settings updated by user {user_id}: reply_in_thread={reply_in_thread}, mention_only={mention_only}, auto_respond={auto_respond}")
            logging.info(f"Verified saved settings: {current_settings}")
        except Exception as e:
            logging.error(f"Error handling settings submission: {e}")
            try:
                user_id = body["user"]["id"]
                await client.chat_postMessage(
                    channel=user_id,
                    text=":x: Error updating settings. Please try again or use the App Home tab."
                )
            except:
                pass
    
    async def start(self) -> None:
        """Start the Slack bot."""
        await self.initialize_bot_info()
        logging.info("Starting Slack bot...")
        # Start Socket Mode handler in background
        asyncio.create_task(self.socket_mode_handler.start_async())
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if hasattr(self, "socket_mode_handler"):
                await self.socket_mode_handler.close_async()
        except Exception as e:
            logging.error(f"Error closing socket mode handler: {e}")


def main():
    """Main function to setup and run the bot."""
    # Setup environment
    env_setup = EnvironmentSetup()
    
    # Create .env if missing
    if not env_setup.create_env_file_if_missing():
        logging.error("Please edit the .env file with your Slack tokens and run again.")
        logging.info("Get tokens from: https://api.slack.com/apps → Your App")
        return
    
    # Validate environment
    slack_bot_token, slack_app_token = env_setup.validate_environment()
    if not slack_bot_token or not slack_app_token:
        logging.error("Environment validation failed. Please check your .env file.")
        return
    
    logging.info("Starting Phase 1 Slack Bot...")
    
    async def run_bot():
        """Run the bot with proper error handling."""
        bot = Phase1SlackBot(slack_bot_token, slack_app_token)
        
        try:
            await bot.start()
            # Keep the main task alive until interrupted
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logging.info("Shutting down...")
        except Exception as e:
            logging.error(f"Bot error: {e}")
        finally:
            await bot.cleanup()
    
    # Run the bot
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}")


if __name__ == "__main__":
    main()