"""
Slack Slash Commands handler for Vercel
Handles bot configuration commands via HTTP webhooks
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import logging
import hashlib
import hmac
import time
import requests
from urllib.parse import parse_qs

# Import your existing services  
import sys
sys.path.append('..')
from src.llm_models import LLM_MODELS, get_model_display_name
from src.supabase import get_supabase_client

class handler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Get tokens from environment
        self.bot_token = os.environ.get("SLACK_BOT_TOKEN")
        self.signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        """Handle Slack slash commands"""
        try:
            # Verify request is from Slack
            if not self._verify_slack_request():
                self.send_response(403)
                self.end_headers()
                return
            
            # Read request body
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length).decode('utf-8')
            
            # Parse form data
            parsed_data = parse_qs(body)
            command_data = {key: value[0] for key, value in parsed_data.items()}
            
            # Handle the slash command
            response = self._handle_slash_command(command_data)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            logging.error(f"Error handling slash command: {e}")
            self.send_response(500)
            self.end_headers()
    
    def _verify_slack_request(self):
        """Verify request came from Slack using signing secret"""
        if not self.signing_secret:
            return True  # Skip verification if no secret set
        
        timestamp = self.headers.get('X-Slack-Request-Timestamp', '')
        signature = self.headers.get('X-Slack-Signature', '')
        
        if not timestamp or not signature:
            return False
        
        # Check timestamp (prevent replay attacks)
        if abs(time.time() - int(timestamp)) > 60 * 5:  # 5 minutes
            return False
        
        # Read body for verification
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        # Reset file pointer for later reading
        self.rfile = type(self.rfile)(body)
        
        # Create signature
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        computed_signature = 'v0=' + hmac.new(
            self.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, signature)
    
    def _handle_slash_command(self, command_data):
        """Handle different slash commands"""
        command = command_data.get('command', '')
        text = command_data.get('text', '').strip()
        user_id = command_data.get('user_id', '')
        
        if command == '/bot-settings':
            return self._handle_settings_command(text, user_id)
        elif command == '/bot-status':
            return self._handle_status_command()
        elif command == '/bot-help':
            return self._handle_help_command()
        else:
            return {
                "response_type": "ephemeral",
                "text": f"Unknown command: {command}"
            }
    
    def _handle_settings_command(self, text, user_id):
        """Handle bot settings configuration"""
        try:
            if not text:
                return self._show_current_settings()
            
            parts = text.split()
            if len(parts) < 2:
                return {
                    "response_type": "ephemeral",
                    "text": "Usage: `/bot-settings <setting> <value>`\nExample: `/bot-settings model llama-3.1-70b`"
                }
            
            setting = parts[0].lower()
            value = ' '.join(parts[1:])
            
            if setting == 'model':
                return self._set_model(value)
            elif setting == 'mention_only':
                return self._set_mention_only(value)
            elif setting == 'reply_in_thread':
                return self._set_reply_in_thread(value)
            else:
                return {
                    "response_type": "ephemeral",
                    "text": f"Unknown setting: {setting}\nAvailable settings: model, mention_only, reply_in_thread"
                }
        
        except Exception as e:
            logging.error(f"Error in settings command: {e}")
            return {
                "response_type": "ephemeral",
                "text": "Error updating settings. Please try again."
            }
    
    def _show_current_settings(self):
        """Show current bot settings"""
        try:
            supabase = get_supabase_client()
            
            # Get current settings
            result = supabase.table("bot_settings").select("*").limit(1).execute()
            settings = result.data[0] if result.data else {}
            
            current_model = settings.get("llm_model", "meta-llama/llama-3.3-70b-instruct:free")
            mention_only = settings.get("mention_only", True)
            reply_in_thread = settings.get("reply_in_thread", True)
            
            model_display = get_model_display_name(current_model)
            
            settings_text = f"""*Current Bot Settings:*
• Model: `{model_display}`
• Mention Only: `{mention_only}`
• Reply in Thread: `{reply_in_thread}`

*To change settings:*
`/bot-settings model <model_name>`
`/bot-settings mention_only true/false`
`/bot-settings reply_in_thread true/false`

*Available models:* {', '.join([f'`{name}`' for name in LLM_MODELS.keys()])}"""
            
            return {
                "response_type": "ephemeral",
                "text": settings_text
            }
        
        except Exception as e:
            logging.error(f"Error showing settings: {e}")
            return {
                "response_type": "ephemeral", 
                "text": "Error retrieving settings. Please try again."
            }
    
    def _set_model(self, model_name):
        """Set the AI model"""
        try:
            if model_name not in LLM_MODELS:
                available_models = ', '.join([f'`{name}`' for name in LLM_MODELS.keys()])
                return {
                    "response_type": "ephemeral",
                    "text": f"Unknown model: `{model_name}`\nAvailable models: {available_models}"
                }
            
            full_model_name = LLM_MODELS[model_name]
            supabase = get_supabase_client()
            
            # Update settings
            supabase.table("bot_settings").upsert({
                "id": 1,
                "llm_model": full_model_name,
                "updated_at": "now()"
            }).execute()
            
            return {
                "response_type": "ephemeral",
                "text": f"✅ Model updated to: `{get_model_display_name(full_model_name)}`"
            }
        
        except Exception as e:
            logging.error(f"Error setting model: {e}")
            return {
                "response_type": "ephemeral",
                "text": "Error updating model. Please try again."
            }
    
    def _set_mention_only(self, value):
        """Set mention only mode"""
        try:
            bool_value = value.lower() in ['true', '1', 'yes', 'on']
            supabase = get_supabase_client()
            
            supabase.table("bot_settings").upsert({
                "id": 1,
                "mention_only": bool_value,
                "updated_at": "now()"
            }).execute()
            
            mode = "ON" if bool_value else "OFF"
            return {
                "response_type": "ephemeral",
                "text": f"✅ Mention only mode: `{mode}`"
            }
        
        except Exception as e:
            logging.error(f"Error setting mention_only: {e}")
            return {
                "response_type": "ephemeral",
                "text": "Error updating mention_only setting. Please try again."
            }
    
    def _set_reply_in_thread(self, value):
        """Set reply in thread mode"""
        try:
            bool_value = value.lower() in ['true', '1', 'yes', 'on']
            supabase = get_supabase_client()
            
            supabase.table("bot_settings").upsert({
                "id": 1,
                "reply_in_thread": bool_value,
                "updated_at": "now()"
            }).execute()
            
            mode = "ON" if bool_value else "OFF" 
            return {
                "response_type": "ephemeral",
                "text": f"✅ Reply in thread: `{mode}`"
            }
        
        except Exception as e:
            logging.error(f"Error setting reply_in_thread: {e}")
            return {
                "response_type": "ephemeral",
                "text": "Error updating reply_in_thread setting. Please try again."
            }
    
    def _handle_status_command(self):
        """Handle bot status check"""
        try:
            # Check API keys
            openrouter_key = bool(os.getenv("OPEN_ROUTER_KEY"))
            groq_key = bool(os.getenv("GROQ_API_KEY") or os.getenv("GROQ_KEY"))
            supabase_url = bool(os.getenv("SUPABASE_URL"))
            supabase_key = bool(os.getenv("SUPABASE_ANON_KEY"))
            
            # Test Supabase connection
            try:
                supabase = get_supabase_client()
                supabase.table("bot_settings").select("id").limit(1).execute()
                supabase_status = "✅ Connected"
            except Exception:
                supabase_status = "❌ Error"
            
            # Test OpenRouter
            try:
                if openrouter_key:
                    headers = {"Authorization": f"Bearer {os.getenv('OPEN_ROUTER_KEY')}"}
                    response = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=5)
                    openrouter_status = "✅ Connected" if response.status_code == 200 else "❌ Error"
                else:
                    openrouter_status = "❌ No API key"
            except Exception:
                openrouter_status = "❌ Error"
            
            status_text = f"""*Bot Status:*
• OpenRouter: {openrouter_status}
• Groq API: {'✅ Key found' if groq_key else '❌ No API key'}
• Supabase: {supabase_status}

*Environment:*
• Supabase URL: {'✅ Set' if supabase_url else '❌ Missing'}
• Supabase Key: {'✅ Set' if supabase_key else '❌ Missing'}"""
            
            return {
                "response_type": "ephemeral",
                "text": status_text
            }
        
        except Exception as e:
            logging.error(f"Error in status command: {e}")
            return {
                "response_type": "ephemeral",
                "text": "Error checking status. Please try again."
            }
    
    def _handle_help_command(self):
        """Handle help command"""
        help_text = """*AI Slack Bot Help* 🤖

*Slash Commands:*
• `/bot-settings` - View/change bot settings
• `/bot-status` - Check bot health and API connections
• `/bot-help` - Show this help message

*Usage:*
• Mention the bot: `@Bot hello` 
• Send DM for private conversation
• Use settings to control behavior

*Settings:*
• `model` - Choose AI model
• `mention_only` - Only respond to mentions
• `reply_in_thread` - Reply in threads vs channel

*Examples:*
`/bot-settings model llama-3.1-70b`
`/bot-settings mention_only false`
`/bot-settings reply_in_thread true`

Need help? Contact your administrator."""
        
        return {
            "response_type": "ephemeral",
            "text": help_text
        }
