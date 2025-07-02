"""
Slack Events API handler for Vercel
Handles mentions, messages, and other Slack events via HTTP webhooks
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
from src.services.ai_service import get_ai_response_sync
from src.groq_service import classify_message_sync
from src.supabase import log_message_to_supabase_sync, get_supabase_client

class handler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Get tokens from environment
        self.bot_token = os.environ.get("SLACK_BOT_TOKEN")
        self.signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        """Handle Slack webhook events"""
        try:
            # Verify request is from Slack
            if not self._verify_slack_request():
                self.send_response(403)
                self.end_headers()
                return
            
            # Read request body
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length).decode('utf-8')
            
            try:
                event_data = json.loads(body)
            except json.JSONDecodeError:
                # Handle URL encoded data (for some Slack events)
                parsed_data = parse_qs(body)
                if 'payload' in parsed_data:
                    event_data = json.loads(parsed_data['payload'][0])
                else:
                    self.send_error(400, "Invalid JSON")
                    return
            
            # Handle URL verification challenge
            if event_data.get("type") == "url_verification":
                self._handle_url_verification(event_data)
                return
            
            # Handle actual events
            if event_data.get("type") == "event_callback":
                self._handle_event_callback(event_data)
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            
        except Exception as e:
            logging.error(f"Error handling Slack event: {e}")
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
    
    def _handle_url_verification(self, event_data):
        """Handle Slack URL verification challenge"""
        challenge = event_data.get("challenge", "")
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(challenge.encode('utf-8'))
    
    def _handle_event_callback(self, event_data):
        """Handle Slack event callbacks"""
        event = event_data.get("event", {})
        event_type = event.get("type")
        
        if event_type == "app_mention":
            self._handle_mention(event)
        elif event_type == "message":
            # Skip bot messages and threaded replies to avoid loops
            if not event.get("bot_id") and not event.get("thread_ts"):
                self._handle_message(event)
    
    def _handle_mention(self, event):
        """Handle bot mentions"""
        try:
            # Log mention
            log_message_to_supabase_sync(
                event, self.bot_token, self._get_bot_id(),
                msg_type="incoming", important="YES", repliable="YES"
            )
            
            # Get AI response
            text = event.get("text", "")
            user_message = self._clean_message_text(text)
            settings = self._get_bot_settings()
            ai_response = get_ai_response_sync(user_message, settings)
            
            # Send response
            self._send_slack_message(
                channel=event.get("channel"),
                text=ai_response,
                thread_ts=event.get("thread_ts", event.get("ts"))
            )
            
        except Exception as e:
            logging.error(f"Error handling mention: {e}")
    
    def _handle_message(self, event):
        """Handle regular message events with classification"""
        try:
            # Skip bot messages and messages with mentions (handled separately)
            bot_id = self._get_bot_id()
            if event.get("user") == bot_id:
                return
            
            if self._has_bot_mention(event.get("text", "")):
                return
            
            # Get settings from environment or defaults
            settings = self._get_bot_settings()
            
            # Check if we should reply based on settings
            should_reply = False
            should_classify = False
            
            # DM logic
            if event.get("channel_type") == "im":
                should_reply = True
                should_classify = True
            else:
                # Channel logic based on settings
                if not settings.get("mention_only", True):
                    should_reply = True
                should_classify = True
            
            # Classify message using Groq if available
            classification = {"important": "NO", "repliable": "NO"}
            if should_classify:
                try:
                    classification = classify_message_sync(event.get("text", ""))
                except Exception as e:
                    logging.error(f"Error classifying message: {e}")
                
                # Override based on channel type and settings
                if event.get("channel_type") == "im":
                    classification["repliable"] = "YES"
                elif not settings.get("mention_only", True):
                    classification["repliable"] = "YES" if classification["repliable"] == "YES" else "NO"
                else:
                    classification["repliable"] = "NO"
            
            # Log message with classification
            if should_classify:
                log_message_to_supabase_sync(
                    event, self.bot_token, bot_id,
                    msg_type="incoming", 
                    important=classification["important"], 
                    repliable=classification["repliable"]
                )
            
            # Send response if appropriate
            if should_reply and classification["repliable"] == "YES":
                ai_response = get_ai_response_sync(event.get("text", ""), settings)
                self._send_slack_message(
                    channel=event.get("channel"),
                    text=ai_response,
                    thread_ts=event.get("thread_ts") if settings.get("reply_in_thread") else None
                )
            
        except Exception as e:
            logging.error(f"Error handling message: {e}")
    
    def _get_bot_id(self):
        """Get bot ID from Slack API"""
        try:
            headers = {"Authorization": f"Bearer {self.bot_token}"}
            response = requests.get("https://slack.com/api/auth.test", headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("user_id")
        except Exception as e:
            logging.error(f"Error getting bot ID: {e}")
            return None
    
    def _clean_message_text(self, text):
        """Remove bot mentions from message text"""
        import re
        return re.sub(r'<@[UW][A-Z0-9]{8,}>', '', text).strip()
    
    def _has_bot_mention(self, text):
        """Check if message contains bot mention"""
        bot_id = self._get_bot_id()
        return bot_id and f"<@{bot_id}>" in text
    
    def _get_bot_settings(self):
        """Get bot settings from environment or defaults"""
        return {
            "reply_in_thread": os.environ.get("REPLY_IN_THREAD", "true").lower() == "true",
            "mention_only": os.environ.get("MENTION_ONLY", "true").lower() == "true",
            "llm_model": os.environ.get("LLM_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
        }
    
    def _send_slack_message(self, channel, text, thread_ts=None):
        """Send message to Slack"""
        try:
            headers = {
                "Authorization": f"Bearer {self.bot_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "channel": channel,
                "text": text
            }
            if thread_ts:
                payload["thread_ts"] = thread_ts
            
            response = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers=headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("ok"):
                # Log outgoing message
                outgoing_message = {
                    "ts": data["ts"],
                    "channel": channel,
                    "text": text,
                    "thread_ts": thread_ts,
                    "user": self._get_bot_id()
                }
                log_message_to_supabase_sync(
                    outgoing_message, self.bot_token, self._get_bot_id(),
                    msg_type="outgoing"
                )
            else:
                logging.error(f"Slack API error: {data.get('error')}")
            
        except Exception as e:
            logging.error(f"Error sending Slack message: {e}")
