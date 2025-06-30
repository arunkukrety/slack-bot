#!/usr/bin/env python3
"""
AI Slack Bot - Production Ready

A clean, modular Slack bot powered by OpenRouter AI.
Provides intelligent responses, configurable settings, and health monitoring.

Usage:
    python main.py

Environment Variables:
    SLACK_BOT_TOKEN - Bot token (xoxb-...)
    SLACK_APP_TOKEN - App token (xapp-...)
    OPEN_ROUTER_KEY - OpenRouter API key (sk-or-...)
    PORT - Health server port (default: 8080)
"""

import asyncio
import logging
import os
import time
import json
import aiohttp
from typing import Optional, Tuple, Dict, Any
from aiohttp import web
from aiohttp.web_runner import AppRunner, TCPSite

from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from src.llm_models import LLM_MODELS, get_model_display_name, get_model_options
from src.Supabase import log_message_to_supabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class EnvironmentSetup:
    """Handles environment variable setup and validation."""
    
    @staticmethod
    def load_env_file():
        """Load .env file if it exists (for local development only)."""
        root_dir = os.path.dirname(os.path.abspath(__file__))
        env_file = os.path.join(root_dir, ".env")
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            if key and value:
                                os.environ[key] = value
                logging.info(f"[Env] Loaded environment variables from {env_file}")
            except Exception as e:
                logging.warning(f"[Env] Could not load .env file: {e}")
        else:
            logging.info("[Env] No .env file found, using system environment variables")
    
    @staticmethod
    def validate_environment() -> Tuple[Optional[str], Optional[str]]:
        """Validate environment variables and return tokens."""
        EnvironmentSetup.load_env_file()
        slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
        slack_app_token = os.getenv("SLACK_APP_TOKEN")
        open_router_key = os.getenv("OPEN_ROUTER_KEY")
        logging.info(f"[Env] SLACK_BOT_TOKEN present: {bool(slack_bot_token)}")
        logging.info(f"[Env] SLACK_APP_TOKEN present: {bool(slack_app_token)}")
        logging.info(f"[Env] OPEN_ROUTER_KEY present: {bool(open_router_key)}")
        if not slack_bot_token or not slack_bot_token.startswith("xoxb-"):
            logging.error("[Env] SLACK_BOT_TOKEN is missing or invalid.")
            return None, None
        if not slack_app_token or not slack_app_token.startswith("xapp-"):
            logging.error("[Env] SLACK_APP_TOKEN is missing or invalid.")
            return None, None
        return slack_bot_token, slack_app_token


class BotSettings:
    """Manages bot settings that can be configured through Slack UI."""
    
    def __init__(self, settings_file: str = "bot_settings.json"):
        self.settings_file = settings_file
        self.default_settings = {
            "reply_in_thread": True,
            "mention_only": True,
            "auto_respond": True,
            "llm_model": "meta-llama/llama-3.3-70b-instruct:free"
        }
        self.settings = self.load_settings()
    
    def load_settings(self) -> Dict[str, Any]:
        """Load settings from file or create default settings."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
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
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value with optional default."""
        if default is not None:
            return self.settings.get(key, default)
        return self.settings.get(key, self.default_settings.get(key))
    
    def set(self, key: str, value: Any) -> None:
        """Set a setting value and save."""
        if key in self.default_settings or key == "llm_model":
            self.settings[key] = value
            self.save_settings()
            self.settings = self.load_settings()
            logging.info(f"Setting '{key}' updated to '{value}'")
        else:
            raise ValueError(f"Unknown setting: {key}")


class HealthServer:
    """Handles health check endpoint for deployment monitoring."""
    
    def __init__(self, bot):
        self.bot = bot
        self.app = None
        self.runner = None
        self.setup_server()
    
    def setup_server(self):
        """Setup aiohttp health server."""
        self.app = web.Application()
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/', self.health_check)
    
    async def health_check(self, request):
        """Health check endpoint."""
        health_data = {
            "status": "healthy",
            "timestamp": time.time(),
            "bot_id": self.bot.bot_id,
            "settings": self.bot.settings.load_settings(),
            "uptime": "running"
        }
        return web.json_response(health_data)
    
    async def start(self):
        """Start health server on PORT env var or 8080."""
        port = int(os.getenv('PORT', 8080))
        host = '0.0.0.0'
        
        try:
            self.runner = AppRunner(self.app)
            await self.runner.setup()
            
            site = TCPSite(self.runner, host, port)
            await site.start()
            
            logging.info(f"Health server started on http://{host}:{port}/health")
            return True
        except Exception as e:
            logging.error(f"Failed to start health server: {e}")
            return False
    
    async def cleanup(self):
        """Stop health server."""
        try:
            if self.runner:
                await self.runner.cleanup()
                logging.info("Health server stopped")
        except Exception as e:
            logging.error(f"Error stopping health server: {e}")


class EventHandlers:
    """Handles Slack events like mentions, messages, and home tab."""
    
    def __init__(self, bot):
        self.bot = bot
        self.ai_service = bot.ai_service
        self.setup_handlers()
    
    def setup_handlers(self):
        """Register event handlers."""
        self.bot.app.event("app_mention")(self.handle_mention)
        self.bot.app.message()(self.handle_message)
        self.bot.app.event("app_home_opened")(self.handle_home_opened)
        
        # Settings UI handlers
        self.bot.app.action("settings_button")(self.handle_settings_button)
        self.bot.app.view("settings_modal")(self.handle_settings_submission)
        self.bot.app.action("reply_in_thread_setting")(self.handle_checkbox_action)
        self.bot.app.action("mention_only_setting")(self.handle_checkbox_action)
        self.bot.app.action("auto_respond_setting")(self.handle_checkbox_action)
    
    async def handle_mention(self, event, say):
        """Handle app_mention events."""
        logging.info(f"[Event] Recognized mention event: ts={event.get('ts')}, channel={event.get('channel')}")
        await log_message_to_supabase(event, self.bot.client, msg_type="incoming")
        await self._send_ai_response(event, say)
        logging.info(f"[Slack] Finished processing mention event: {event.get('ts')}")

    async def handle_message(self, message, say):
        """Handle message events."""
        logging.info(f"[Event] Recognized message event: ts={message.get('ts')}, channel={message.get('channel')}, thread_ts={message.get('thread_ts')}")
        await log_message_to_supabase(message, self.bot.client, msg_type="incoming")
        
        # Only reply if bot is mentioned or in DM with auto_respond enabled
        bot_mention = False
        bot_id = self.bot.bot_id
        text = message.get("text", "")
        if bot_id and f"<@{bot_id}>" in text:
            bot_mention = True
        is_dm = message.get("channel_type") == "im"
        auto_respond = self.bot.settings.get("auto_respond")
        if bot_mention or (is_dm and auto_respond):
            await self._send_ai_response(message, say)
        logging.info(f"[Slack] Finished processing message event: {message.get('ts')}")
    
    async def handle_home_opened(self, event, client):
        """Handle app_home_opened events."""
        logging.info(f"[Event] Home opened event: {event}")
        user_id = event["user"]
        settings = self.bot.settings.settings
        
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🤖 AI Slack Bot"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Welcome! This bot provides AI-powered responses when mentioned."
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Settings:* Reply in Thread: {'✅' if settings['reply_in_thread'] else '❌'} | "
                           f"Mention Only: {'✅' if settings['mention_only'] else '❌'} | "
                           f"Auto Respond: {'✅' if settings['auto_respond'] else '❌'}"
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
            }
        ]
        
        try:
            await client.views_publish(user_id=user_id, view={"type": "home", "blocks": blocks})
        except Exception as e:
            logging.error(f"Error publishing home view: {e}")
    
    async def handle_settings_button(self, ack, body, client):
        """Handle settings button click."""
        await ack()
        logging.info(f"[Event] Settings button clicked: {body}")
        try:
            await self.bot.commands._open_settings_modal(body["trigger_id"], client, body["user"]["id"])
        except Exception as e:
            logging.error(f"[Event] Error opening settings modal: {e}")
    
    async def handle_checkbox_action(self, ack, body):
        """Handle checkbox interactions."""
        await ack()
        logging.info(f"[Event] Checkbox action: {body}")
    
    async def handle_settings_submission(self, ack, body, client):
        """Handle settings modal submission."""
        await ack()
        logging.info(f"[Event] Settings submission: {body}")
        try:
            values = body["view"]["state"]["values"]
            
            reply_in_thread = len(values.get("reply_in_thread_block", {}).get("reply_in_thread_setting", {}).get("selected_options", [])) > 0
            mention_only = len(values.get("mention_only_block", {}).get("mention_only_setting", {}).get("selected_options", [])) > 0
            auto_respond = len(values.get("auto_respond_block", {}).get("auto_respond_setting", {}).get("selected_options", [])) > 0
            
            self.bot.settings.set("reply_in_thread", reply_in_thread)
            self.bot.settings.set("mention_only", mention_only)
            self.bot.settings.set("auto_respond", auto_respond)
            
            user_id = body["user"]["id"]
            await client.chat_postMessage(
                channel=user_id,
                text="✅ Settings updated successfully! Changes take effect immediately."
            )
            
            logging.info(f"[Event] Settings updated for user {user_id}")
        except Exception as e:
            logging.error(f"[Event] Error handling settings submission: {e}")
    
    async def _send_ai_response(self, event, say):
        """Send AI-powered response based on settings."""
        user_id = event.get("user")
        
        if user_id == self.bot.bot_id:
            return
        
        settings = self.bot.settings.load_settings()
        channel_type = event.get("channel_type", "unknown")
        text = event.get("text", "")
        
        # Clean up the message text (remove bot mention for processing)
        if self.bot.bot_id and f"<@{self.bot.bot_id}>" in text:
            user_message = text.replace(f"<@{self.bot.bot_id}>", "").strip()
        else:
            user_message = text.strip()
        
        # Skip empty messages
        if not user_message:
            user_message = "Hello!"
        
        if settings.get("mention_only") and channel_type != "im":
            if not (self.bot.bot_id and f"<@{self.bot.bot_id}>" in text):
                return
        
        thread_ts = None
        if settings.get("reply_in_thread"):
            thread_ts = event.get("thread_ts", event.get("ts"))
        
        try:
            ai_response = await self.ai_service.get_response(user_message, user_id)
            outgoing_message_data = {
                "ts": str(time.time()),  # Unique timestamp for outgoing message
                "thread_ts": thread_ts,
                "user": self.bot.bot_id,
                "channel": event.get("channel"),
                "text": ai_response
            }
            await log_message_to_supabase(outgoing_message_data, self.bot.client, msg_type="outgoing")
            await say(text=ai_response, thread_ts=thread_ts)
        except Exception as e:
            logging.error(f"[Event] Error sending AI response: {e}")
            await say(text="Hello World! 🤖 (AI temporarily unavailable)", thread_ts=thread_ts)
    
    async def _send_settings_info(self, message, say):
        """Send settings info via DM."""
        settings = self.bot.settings.load_settings()
        
        text = (
            "*⚙️ Bot Settings*\n\n"
            f"• Reply in Thread: {'✅' if settings['reply_in_thread'] else '❌'}\n"
            f"• Mention Only: {'✅' if settings['mention_only'] else '❌'}\n"
            f"• Auto Respond: {'✅' if settings['auto_respond'] else '❌'}\n\n"
            "Use `/bot-settings` or the App Home tab to change settings."
        )
        
        try:
            logging.info(f"[Event] Sending settings info: {text}")
            await say(text=text)
        except Exception as e:
            logging.error(f"[Event] Error sending settings info: {e}")
    
    async def _send_help_info(self, message, say):
        """Send help info via DM."""
        ai_status = "✅ Available" if self.ai_service.is_available() else "❌ Unavailable"
        
        text = (
            "*🤖 AI Slack Bot Help*\n\n"
            "*What I can do:*\n"
            "• Provide AI-powered responses to your questions\n"
            "• Work in channels and direct messages\n"
            "• Configurable behavior through settings\n\n"
            "*Commands:*\n"
            "• `/bot-settings` - Configure settings\n"
            "• `/bot-help` - Show help\n"
            "• `/bot-debug` - Debug info\n"
            "• `/switch-llm` - Switch AI model\n\n"
            "*Usage:*\n"
            "• Mention me in channels: `@bot_name your question`\n"
            "• Send me direct messages\n\n"
            f"*AI Service:* {ai_status}"
        )
        
        try:
            logging.info(f"[Event] Sending help info: {text}")
            await say(text=text)
        except Exception as e:
            logging.error(f"[Event] Error sending help info: {e}")


class AIService:
    """Handles AI-powered responses using OpenRouter."""
    
    def __init__(self, settings=None):
        self.api_key = os.getenv("OPEN_ROUTER_KEY")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.settings = settings
        self.default_model = "meta-llama/llama-3.3-70b-instruct:free" 
        if not self.api_key:
            logging.warning("[AIService] OPEN_ROUTER_KEY not found or empty!")
        else:
            logging.info(f"[AIService] OPEN_ROUTER_KEY loaded: {self.api_key[:8]}...{'*' * (len(self.api_key)-12)}...{self.api_key[-4:]}")
    
    def get_current_model(self) -> str:
        if self.settings:
            return self.settings.get("llm_model", self.default_model)
        return self.default_model
    
    async def get_response(self, user_message: str, user_id: str = None) -> Optional[str]:
        if not self.api_key:
            logging.error("[AIService] OPEN_ROUTER_KEY is missing at get_response!")
            return "Hello World! 🤖 (missing OPEN_ROUTER_KEY)"
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Title": "Slack Bot"
            }
            payload = {
                "model": self.get_current_model(),
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful Slack bot assistant. Keep responses concise, "
                            "friendly, and appropriate for workplace communication. "
                            "Use emojis sparingly and professionally."
                        )
                    },
                    {
                        "role": "user", 
                        "content": user_message
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.7
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        ai_response = data["choices"][0]["message"]["content"]
                        return ai_response.strip()
                    else:
                        error_text = await response.text()
                        logging.error(f"OpenRouter API error {response.status}: {error_text}")
                        return "Sorry, I'm having trouble thinking right now. Try again in a moment! 🤔"
        except aiohttp.ClientError as e:
            logging.error(f"Network error calling OpenRouter: {e}")
            return "Hello World! 🌐 (Network issue - please try again)"
        except Exception as e:
            logging.error(f"Unexpected error in AI service: {e}")
            return "Hello World! ⚠️ (Something went wrong)"
    
    def is_available(self) -> bool:
        return bool(self.api_key)


class SlackBot:
    """Main Slack bot class with modular architecture."""
    
    def __init__(self, slack_bot_token: str, slack_app_token: str):
        self.app = AsyncApp(token=slack_bot_token)
        self.socket_mode_handler = AsyncSocketModeHandler(self.app, slack_app_token)
        self.client = AsyncWebClient(token=slack_bot_token)
        self.settings = BotSettings()
        self.bot_id = None
        self.bot_name = "Unknown"
        self.ai_service = AIService(self.settings)
        
        # Initialize modules
        from src.slash_commands import SlashCommands
        self.commands = SlashCommands(self)
        self.events = EventHandlers(self)
        self.health = HealthServer(self)
    
    async def initialize_bot_info(self):
        """Get bot ID and info from Slack."""
        try:
            auth_info = await self.client.auth_test()
            self.bot_id = auth_info["user_id"]
            self.bot_name = auth_info.get("user", "Unknown")
            logging.info(f"Bot initialized: {self.bot_name} (ID: {self.bot_id})")
        except Exception as e:
            logging.error(f"Failed to get bot info: {e}")
            self.bot_id = None
    
    async def start(self):
        """Start the bot and health server."""
        await self.initialize_bot_info()
        logging.info("Starting Slack bot...")
        
        await self.health.start()
        asyncio.create_task(self.socket_mode_handler.start_async())
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            if hasattr(self, "socket_mode_handler"):
                await self.socket_mode_handler.close_async()
        except Exception as e:
            logging.error(f"Error closing socket handler: {e}")
        
        await self.health.cleanup()


EnvironmentSetup.load_env_file()


def main():
    """Main entry point."""
    slack_bot_token, slack_app_token = EnvironmentSetup.validate_environment()
    if not slack_bot_token or not slack_app_token:
        logging.error("Environment validation failed. Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN.")
        return
    
    logging.info("Starting AI Slack Bot...")
    
    async def run_bot():
        """Run the bot with error handling."""
        bot = SlackBot(slack_bot_token, slack_app_token)
        
        try:
            await bot.start()
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logging.info("Shutting down...")
        except Exception as e:
            logging.error(f"Bot error: {e}")
        finally:
            await bot.cleanup()
    
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}")


if __name__ == "__main__":
    main()