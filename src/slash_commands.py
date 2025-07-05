"""Slash command handlers for the Slack bot."""

import os
import logging
from slack_sdk.errors import SlackApiError
from .llm_models import LLM_MODELS, get_model_display_name, get_model_options
from .memzero import mem0_service


class SlashCommands:
    """Handles all slash command interactions."""
    
    def __init__(self, bot):
        self.bot = bot
        self.setup_commands()
    
    def setup_commands(self):
        """Register slash command handlers."""
        self.bot.app.command("/bot-settings")(self.handle_settings)
        self.bot.app.command("/bot-help")(self.handle_help)
        self.bot.app.command("/bot-debug")(self.handle_debug)
        self.bot.app.command("/switch-llm")(self.handle_switch_llm)
        self.bot.app.command("/clear-tracked-threads")(self.handle_clear_tracked_threads)
        
        # Handle LLM switch submission
        self.bot.app.view("llm_switch_modal")(self.handle_llm_switch_submission)
        self.bot.app.view("settings_modal")(self.handle_settings_submission)
    
    async def handle_settings(self, ack, body, client):
        """Handle /bot-settings slash command."""
        await ack()
        
        user_id = body.get('user_id')
        channel_id = body.get('channel_id')
        trigger_id = body.get('trigger_id')
        
        if not trigger_id:
            await client.chat_postEphemeral(
                channel=channel_id, user=user_id,
                text=":x: Missing session data. Try the App Home tab."
            )
            return
        
        try:
            await self._open_settings_modal(trigger_id, client, user_id)
        except SlackApiError as modal_error:
            await self._handle_modal_error(modal_error, client, channel_id, user_id)
        except Exception as e:
            logging.error(f"Error in /bot-settings: {e}")
            await client.chat_postEphemeral(
                channel=channel_id, user=user_id,
                text=":x: Settings temporarily unavailable. Try the App Home tab."
            )
    
    async def handle_help(self, ack, body, client):
        """Handle /bot-help slash command."""
        await ack()
        
        help_text = (
            "*🤖 AI Slack Bot Help*\n\n"
            "*What I can do:*\n"
            "• Provide AI-powered responses to your questions\n"
            "• Work in channels and direct messages\n"
            "• Configurable behavior through settings\n\n"
            "*Available Commands:*\n"
            "• `/bot-settings` - Configure bot behavior\n"
            "• `/switch-llm` - Choose your AI model\n"
            "• `/clear-tracked-threads` - Clear mention-only thread tracking\n"
            "• `/bot-help` - Show this help message\n"
            "• `/bot-debug` - Show debug information\n\n"
            "*Mention Only Mode:*\n"
            "• When ON: Bot only replies when mentioned, then continues in that thread\n"
            "• When OFF: Bot replies to all messages in channels\n"
            "• Bot always responds to direct messages\n"
            "• Use `/clear-tracked-threads` to reset thread tracking\n\n"
            "*Getting Started:*\n"
            "1. Invite me to a channel: `/invite @bot_name`\n"
            "2. Ask me anything: `@bot_name what's the weather like?`\n"
            "3. Configure settings: `/bot-settings`\n"
            "4. Switch AI models: `/switch-llm`"
        )
        
        try:
            await client.chat_postEphemeral(
                channel=body["channel_id"],
                user=body["user_id"],
                text=help_text
            )
        except Exception as e:
            logging.error(f"Error in /bot-help: {e}")
    
    async def handle_debug(self, ack, body, client):
        """Handle /bot-debug slash command."""
        await ack()
        
        try:
            trigger_id = body.get("trigger_id", "None")
            # Use self.bot.ai_service if available, else create a local one
            ai_service = getattr(self.bot, 'ai_service', None)
            if ai_service is None:
                from main import AIService
                ai_service = AIService(self.bot.settings)
            ai_status = "✅ Available" if ai_service.is_available() else "❌ Missing OPEN_ROUTER_KEY"
            
            # Check Groq service status
            groq_service = getattr(self.bot.event_handlers, 'groq_service', None)
            groq_status = "✅ Available" if groq_service and groq_service.is_available() else "❌ Missing GROQ_API_KEY"
            
            # Check Mem0 service status
            mem0_status = "✅ Available" if mem0_service.is_available() else "❌ Disabled"
            
            current_model = self.bot.settings.get("llm_model", "meta-llama/llama-3.3-70b-instruct:free")
            model_display = get_model_display_name(current_model)
            
            # Get thread tracking info
            tracked_threads_count = 0
            if hasattr(self.bot, 'event_handlers') and hasattr(self.bot.event_handlers, 'tracked_threads'):
                tracked_threads_count = len(self.bot.event_handlers.tracked_threads)
            
            debug_text = (
                "*🔍 Bot Debug Information*\n\n"
                "*System Status:*\n"
                f"• Bot ID: `{self.bot.bot_id or 'Unknown'}`\n"
                f"• Trigger ID: {'Present' if trigger_id != 'None' else 'Missing'}\n"
                f"• Settings File: {'Found' if os.path.exists('bot_settings.json') else 'Missing'}\n"
                f"• AI Service: {ai_status}\n"
                f"• Groq Classification: {groq_status}\n"
                f"• Memory System: {mem0_status}\n"
                f"• Current Model: {model_display}\n\n"
                "*Current Settings:*\n"
                f"• Reply in Thread: `{self.bot.settings.get('reply_in_thread')}`\n"
                f"• Mention Only: `{self.bot.settings.get('mention_only')}`\n\n"
                "*Thread Tracking:*\n"
                f"• Tracked Threads: `{tracked_threads_count}`\n"
                f"• Use `/clear-tracked-threads` to reset\n\n"
                "*Classification:*\n"
                f"• Messages are classified as important/repliable\n"
                f"• Bot only replies if both are YES\n\n"
                "*Status:* Slash commands are working!"
            )
            
            await client.chat_postEphemeral(
                channel=body["channel_id"],
                user=body["user_id"],
                text=debug_text
            )
        except Exception as e:
            logging.error(f"Error in /bot-debug: {e}")
    
    async def _open_settings_modal(self, trigger_id, client, user_id):
        """Open settings modal with current configuration."""
        settings = self.bot.settings.load_settings()
        
        thread_option = {"text": {"type": "plain_text", "text": "Enable thread replies"}, "value": "reply_in_thread"}
        mention_option = {"text": {"type": "plain_text", "text": "Mention only mode"}, "value": "mention_only"}
        
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Configure your bot preferences:*"}
            }
        ]
        
        # Build setting blocks
        for setting_key, option, label, description in [
            ("reply_in_thread", thread_option, "Reply in Thread", "Reply to messages in threads instead of new messages"),
            ("mention_only", mention_option, "Mention Only", "Only respond when directly mentioned")
        ]:
            block = {
                "type": "section",
                "block_id": f"{setting_key}_block",
                "text": {"type": "mrkdwn", "text": f"*{label}*\n{description}"},
                "accessory": {
                    "type": "checkboxes",
                    "action_id": f"{setting_key}_setting",
                    "options": [option]
                }
            }
            if settings.get(setting_key):
                block["accessory"]["initial_options"] = [option]
            blocks.append(block)
        
        modal_view = {
            "type": "modal",
            "callback_id": "settings_modal",
            "title": {"type": "plain_text", "text": "Bot Settings"},
            "submit": {"type": "plain_text", "text": "Save"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": blocks
        }
        
        await client.views_open(trigger_id=trigger_id, view=modal_view)
        logging.info(f"Settings modal opened for user {user_id}")
    
    async def _handle_modal_error(self, error, client, channel_id, user_id):
        """Handle modal opening errors with appropriate fallbacks."""
        error_msg = str(error).lower()
        
        if "expired_trigger_id" in error_msg:
            text = ":warning: Session expired. Please try again or use the App Home tab."
        elif "missing_scope" in error_msg:
            text = ":x: Permission error. Please verify bot permissions."
        else:
            text = self._get_settings_fallback_text()
        
        await client.chat_postEphemeral(channel=channel_id, user=user_id, text=text)
    
    def _get_settings_fallback_text(self):
        """Get fallback settings text when modal fails."""
        settings = self.bot.settings.settings
        return (
            "*⚙️ Current Bot Settings:*\n"
            f"• Reply in Thread: {'✅' if settings['reply_in_thread'] else '❌'}\n"
            f"• Mention Only: {'✅' if settings['mention_only'] else '❌'}\n\n"
            "Use the App Home tab to change settings."
        )

    async def handle_switch_llm(self, ack, body, client):
        """Handle /switch-llm slash command."""
        await ack()
        
        user_id = body.get('user_id')
        channel_id = body.get('channel_id')
        trigger_id = body.get('trigger_id')
        
        if not trigger_id:
            await client.chat_postEphemeral(
                channel=channel_id, user=user_id,
                text=":x: Session expired. Please try `/switch-llm` again."
            )
            return
        
        try:
            await self._open_llm_switch_modal(trigger_id, client)
        except Exception as e:
            logging.error(f"Error opening LLM switch modal: {e}")
            current_model = self.bot.settings.get("llm_model", "meta-llama/llama-3.3-70b-instruct:free")
            display_name = get_model_display_name(current_model)
            
            await client.chat_postEphemeral(
                channel=channel_id, user=user_id,
                text=f"*🤖 Current AI Model:* {display_name}\n\nModal temporarily unavailable. Try again in a moment."
            )
    
    async def _open_llm_switch_modal(self, trigger_id, client):
        """Open the LLM model selection modal."""
        current_model = self.bot.settings.get("llm_model", "meta-llama/llama-3.3-70b-instruct:free")
        
        # Find current model option for initial selection
        model_options = get_model_options()
        initial_option = None
        for option in model_options:
            if option["value"] == current_model:
                initial_option = option
                break
        
        modal_view = {
            "type": "modal",
            "callback_id": "llm_switch_modal",
            "title": {"type": "plain_text", "text": "Switch AI Model"},
            "submit": {"type": "plain_text", "text": "Switch"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Choose your preferred AI model:*\n\nEach model has different strengths and capabilities."
                    }
                },
                {
                    "type": "section",
                    "block_id": "llm_selection",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Select AI Model:*"
                    },
                    "accessory": {
                        "type": "static_select",
                        "action_id": "selected_model",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Choose a model..."
                        },
                        "options": model_options
                    }
                }
            ]
        }
        
        # Set initial option if found
        if initial_option:
            modal_view["blocks"][1]["accessory"]["initial_option"] = initial_option
        
        await client.views_open(trigger_id=trigger_id, view=modal_view)
    
    async def handle_llm_switch_submission(self, ack, body, client):
        """Handle LLM switch modal submission."""
        await ack()
        
        try:
            values = body["view"]["state"]["values"]
            selected_model = values["llm_selection"]["selected_model"]["selected_option"]["value"]
            
            # Update settings
            self.bot.settings.set("llm_model", selected_model)
            
            # Get display name for confirmation
            display_name = get_model_display_name(selected_model)
            
            # Send confirmation
            user_id = body["user"]["id"]
            confirmation_text = (
                f"*✅ AI Model switched successfully!*\n\n"
                f"*New Model:* {display_name}\n"
                f"*Model ID:* `{selected_model}`\n\n"
                "> The new model will be used for all future responses. Try mentioning me to test it!"
            )
            
            await client.chat_postMessage(
                channel=user_id,
                text=confirmation_text
            )
            
            logging.info(f"User {user_id} switched to model: {selected_model}")
            
        except Exception as e:
            logging.error(f"Error handling LLM switch submission: {e}")
            try:
                user_id = body["user"]["id"]
                await client.chat_postMessage(
                    channel=user_id,
                    text=":x: Error switching model. Please try again."
                )
            except:
                pass
    
    async def handle_settings_submission(self, ack, body, client):
        """Handle settings modal submission and update settings."""
        await ack()
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
        except Exception as e:
            logging.error(f"Error handling settings submission: {e}")
            try:
                user_id = body["user"]["id"]
                await client.chat_postMessage(
                    channel=user_id,
                    text=":x: Error updating settings. Please try again."
                )
            except:
                pass
    
    async def handle_clear_tracked_threads(self, ack, body, client):
        """Handle /clear-tracked-threads slash command."""
        await ack()
        
        user_id = body.get('user_id')
        channel_id = body.get('channel_id')
        
        try:
            # Access the event handlers through the bot instance
            if hasattr(self.bot, 'event_handlers') and hasattr(self.bot.event_handlers, 'tracked_threads'):
                thread_count = len(self.bot.event_handlers.tracked_threads)
                self.bot.event_handlers.tracked_threads.clear()
                self.bot.event_handlers._save_tracked_threads()
                
                response_text = f"✅ Cleared {thread_count} tracked threads. The bot will now only reply to new mentions in 'mention only' mode."
            else:
                response_text = "⚠️ Thread tracking not available or already empty."
            
            await client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=response_text
            )
            logging.info(f"User {user_id} cleared tracked threads")
            
        except Exception as e:
            logging.error(f"Error in /clear-tracked-threads: {e}")
            await client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=":x: Error clearing tracked threads. Please try again."
            )
