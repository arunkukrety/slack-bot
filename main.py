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
from src.groq_service import GroqService
from src.ai_service import AIService

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
        self.groq_service = GroqService()  # Initialize Groq service
        # Track threads where bot was mentioned for "mention only" mode
        self.tracked_threads = set()
        self.threads_file = "tracked_threads.json"
        self._load_tracked_threads()
        self.setup_handlers()
    
    def _load_tracked_threads(self):
        """Load tracked threads from persistent storage."""
        try:
            if os.path.exists(self.threads_file):
                with open(self.threads_file, 'r') as f:
                    data = json.load(f)
                    self.tracked_threads = set(data.get('tracked_threads', []))
                    logging.info(f"[Thread] Loaded {len(self.tracked_threads)} tracked threads from storage")
            else:
                logging.info("[Thread] No tracked threads file found, starting fresh")
        except Exception as e:
            logging.error(f"[Thread] Error loading tracked threads: {e}")
            self.tracked_threads = set()
    
    def _save_tracked_threads(self):
        """Save tracked threads to persistent storage."""
        try:
            data = {'tracked_threads': list(self.tracked_threads)}
            with open(self.threads_file, 'w') as f:
                json.dump(data, f)
            logging.debug(f"[Thread] Saved {len(self.tracked_threads)} tracked threads to storage")
        except Exception as e:
            logging.error(f"[Thread] Error saving tracked threads: {e}")
    
    def _cleanup_old_threads(self, max_age_days=30):
        try:
            # For simplicity, we'll limit the number of tracked threads
            max_threads = 1000
            if len(self.tracked_threads) > max_threads:
                # Convert to list, sort, and keep only the most recent ones
                threads_list = list(self.tracked_threads)
                # Keep the last max_threads/2 entries (arbitrary cleanup strategy)
                self.tracked_threads = set(threads_list[-(max_threads//2):])
                self._save_tracked_threads()
                logging.info(f"[Thread] Cleaned up old threads, now tracking {len(self.tracked_threads)} threads")
        except Exception as e:
            logging.error(f"[Thread] Error during thread cleanup: {e}")
    
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
    
    async def handle_mention(self, event, say):
        """Handle app_mention events."""
        logging.info(f"[Event] Recognized mention event: ts={event.get('ts')}, channel={event.get('channel')}")
        
        # For mentions, ALWAYS reply without classification
        message_text = event.get("text", "")
        
        # Log message without classification (mentions always get replied to)
        asyncio.create_task(log_message_to_supabase(
            event, self.bot.client, self.bot.bot_id, 
            msg_type="incoming",
            important="YES",  # Always YES for mentions
            repliable="YES"   # Always YES for mentions
        ))
        
        # For mention_only mode: track thread when bot is mentioned
        thread_ts = event.get('thread_ts', event.get('ts'))
        if thread_ts not in self.tracked_threads:
            self.tracked_threads.add(thread_ts)
            self._save_tracked_threads()
            logging.debug(f"[Thread] Added thread {thread_ts} to tracked threads (mention_only mode)")
            
            # Periodic cleanup to prevent file from growing too large
            if len(self.tracked_threads) % 100 == 0:  # Every 100 new threads
                self._cleanup_old_threads()
        
        # ALWAYS reply to mentions
        logging.info(f"[Event] Bot mentioned, sending AI response without classification")
        await self._send_ai_response(event, say)
        
        logging.info(f"[Slack] Finished processing mention event: {event.get('ts')}")

    async def handle_message(self, message, say):
        """Handle message events."""
        logging.info(f"[Event] Recognized message event: ts={message.get('ts')}, channel={message.get('channel')}, thread_ts={message.get('thread_ts')}")
        
        # Skip messages with bot mention (handled by handle_mention)
        bot_id = self.bot.bot_id
        text = message.get("text", "")
        bot_mention = bot_id and f"<@{bot_id}>" in text
        if bot_mention:
            logging.debug(f"[Event] Skipping message with bot mention in channel, handled by app_mention: ts={message.get('ts')}")
            return

        # Check if we should reply based on mention_only mode and thread tracking
        settings = self.bot.settings.load_settings()
        mention_only = settings.get("mention_only", False)
        is_dm = message.get("channel_type") == "im"
        thread_ts = message.get('thread_ts', message.get('ts'))
        
        should_reply = False
        should_classify = False
        
        # Always reply in DMs (auto_respond is always true)
        if is_dm:
            should_reply = True
            should_classify = False  # No classification for DMs
            logging.debug(f"[Reply] Replying to DM without classification: ts={message.get('ts')}")
        
        # For channel messages, check mention_only mode
        elif not is_dm:
            if mention_only:
                # Only reply if this thread was previously mentioned
                if thread_ts in self.tracked_threads:
                    should_reply = True
                    should_classify = False  # No classification for tracked threads
                    logging.debug(f"[Reply] Replying to thread message without classification - thread {thread_ts} is tracked: ts={message.get('ts')}")
                else:
                    should_reply = False
                    should_classify = False
                    logging.debug(f"[Reply] Not replying - mention_only mode ON and thread {thread_ts} not tracked: ts={message.get('ts')}")
            else:
                # mention_only is OFF - check classification for channel messages
                should_classify = True
                logging.debug(f"[Reply] Will classify channel message - mention_only mode OFF: ts={message.get('ts')}")
        
        # Classification and logging
        classification = {"important": "NO", "repliable": "NO"}
        if should_classify:
            message_text = message.get("text", "")
            classification = await self.groq_service.classify_message(message_text)
            logging.info(f"[Classification] Result - Important: {classification['important']}, Repliable: {classification['repliable']}")
            
            # Only reply if both important and repliable are YES
            if classification["repliable"] == "YES":
                should_reply = True
                logging.info(f"[Event] Message classified as important and repliable, will send AI response")
            else:
                should_reply = False
                logging.info(f"[Event] Message not classified for reply - Important: {classification['important']}, Repliable: {classification['repliable']}")
        
        # Log message with classification (or default values)
        await log_message_to_supabase(
            message, self.bot.client, self.bot.bot_id, 
            msg_type="incoming",
            important=classification["important"],
            repliable=classification["repliable"]
        )
        
        # Send response if appropriate
        if should_reply:
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
                           f"Mention Only: {'✅' if settings['mention_only'] else '❌'}"
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
            
            self.bot.settings.set("reply_in_thread", reply_in_thread)
            self.bot.settings.set("mention_only", mention_only)
            
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
        text = event.get("text", "")
        
        # Clean up the message text (remove bot mention for processing)
        if self.bot.bot_id and f"<@{self.bot.bot_id}>" in text:
            user_message = text.replace(f"<@{self.bot.bot_id}>", "").strip()
        else:
            user_message = text.strip()
        
        # Skip empty messages
        if not user_message:
            user_message = "Hello!"
        
        # Always get thread_ts for context retrieval (separate from reply_in_thread setting)
        thread_ts_for_context = event.get("thread_ts", event.get("ts"))
        
        # Only set thread_ts for reply if reply_in_thread is enabled
        thread_ts_for_reply = None
        if settings.get("reply_in_thread"):
            thread_ts_for_reply = thread_ts_for_context
        
        try:
            ai_response = await self.ai_service.get_response(user_message, user_id, thread_ts_for_context)
            outgoing_message_data = {
                "ts": str(time.time()),  # Unique timestamp for outgoing message
                "thread_ts": thread_ts_for_reply,
                "user": self.bot.bot_id,
                "channel": event.get("channel"),
                "text": ai_response
            }
            # Log outgoing message without classification (it's a bot response)
            await log_message_to_supabase(
                outgoing_message_data, self.bot.client, self.bot.bot_id, 
                msg_type="outgoing"
            )
            await say(text=ai_response, thread_ts=thread_ts_for_reply)
        except Exception as e:
            logging.error(f"[Event] Error sending AI response: {e}")
            await say(text="Hello World! 🤖 (AI temporarily unavailable)", thread_ts=thread_ts_for_reply)
    
    async def _send_settings_info(self, message, say):
        """Send settings info via DM."""
        settings = self.bot.settings.load_settings()
        
        text = (
            "*⚙️ Bot Settings*\n\n"
            f"• Reply in Thread: {'✅' if settings['reply_in_thread'] else '❌'}\n"
            f"• Mention Only: {'✅' if settings['mention_only'] else '❌'}\n\n"
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