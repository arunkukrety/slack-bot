import os
import logging
from supabase import create_client, Client
from datetime import datetime, timezone
from slack_sdk.web.async_client import AsyncWebClient

logging.basicConfig(level=logging.INFO)

supabase_client: Client | None = None
user_cache: dict = {}  # In-memory cache for user_id -> user_name

async def get_user_name(client: AsyncWebClient, user_id: str) -> str:
    """Fetch user name from Slack API or cache."""
    if not user_id or user_id == "unknown":
        return "unknown"
    if user_id in user_cache:
        logging.debug(f"[Supabase] Retrieved user name from cache: {user_id} -> {user_cache[user_id]}")
        return user_cache[user_id]

    try:
        response = await client.users_info(user=user_id)
        if response["ok"]:
            user_name = response["user"].get("name") or response["user"].get("real_name") or "unknown"
            user_cache[user_id] = user_name
            logging.debug(f"[Supabase] Fetched user name: {user_id} -> {user_name}")
            return user_name
        else:
            logging.error(f"[Supabase] Failed to fetch user info for {user_id}: {response['error']}")
            return "unknown"
    except Exception as e:
        logging.error(f"[Supabase] Error fetching user name for {user_id}: {e}")
        return "unknown"

def get_supabase_client() -> Client | None:
    """Initializes and returns the Supabase client."""
    global supabase_client
    if supabase_client:
        return supabase_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        logging.error("[Supabase] SUPABASE_URL or SUPABASE_KEY not set. Cannot initialize client.")
        return None
    
    try:
        supabase_client = create_client(url, key)
        logging.info("[Supabase] Supabase client initialized.")
        return supabase_client
    except Exception as e:
        logging.error(f"[Supabase] Failed to create Supabase client: {e}")
        return None

def slack_ts_to_iso(ts: str) -> str:
    """Convert Slack ts (string float) to ISO 8601 timestamp (UTC)."""
    try:
        if not ts:
            logging.error("[Supabase] Timestamp is empty or None.")
            return None
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        iso_time = dt.isoformat()
        logging.debug(f"[Supabase] Converted ts '{ts}' to ISO: {iso_time}")
        return iso_time
    except ValueError as ve:
        logging.error(f"[Supabase] Invalid timestamp format '{ts}': {ve}")
        return None
    except Exception as e:
        logging.error(f"[Supabase] Failed to convert ts '{ts}' to ISO: {e}")
        return None

async def get_message_context() -> str:
    """Fetch recent messages from Supabase for LLM context."""
    supabase = get_supabase_client()
    if not supabase:
        logging.error("[Supabase] Supabase client not available. Cannot fetch message context.")
        return ""
    
    try:
        # Fetch messages ordered by timestamp (most recent first), limit to avoid token overflow
        response = supabase.table("messages").select("content, user_name, timestamp").order("timestamp", desc=True).limit(50).execute()
        
        if hasattr(response, "data") and response.data:
            formatted_messages = format_messages_for_context(response.data)
            logging.info(f"[Supabase] Retrieved {len(response.data)} messages for context.")
            return formatted_messages
        else:
            logging.warning("[Supabase] No messages found in database.")
            return ""
            
    except Exception as e:
        logging.error(f"[Supabase] Failed to fetch message context: {e}")
        return ""

def format_messages_for_context(messages: list) -> str:
    """Format messages for inclusion in LLM system prompt."""
    if not messages:
        return ""
    
    formatted_lines = []
    for msg in reversed(messages):  # Reverse to show chronological order
        content = msg.get("content", "").strip()
        user_name = msg.get("user_name", "unknown")
        timestamp = msg.get("timestamp", "")
        
        if content:  # Only include messages with actual content
            # Format: [timestamp] username: message
            formatted_lines.append(f"[{timestamp}] {user_name}: {content}")
    
    return "\n".join(formatted_lines)

async def log_message_to_supabase(msg: dict, client: AsyncWebClient, bot_id: str, msg_type: str = "incoming", important: str = None, repliable: str = None):
    """Log a Slack message to Supabase, including user name and classification."""
    logging.debug(f"Raw message: {msg}")
    supabase = get_supabase_client()
    if not supabase:
        logging.error("[Supabase] Supabase client not available. Message not logged.")
        return

    ts = msg.get("ts")
    if not ts:
        logging.error("[Supabase] Message missing timestamp. Cannot log.")
        return

    user_id = msg.get("user") or "unknown"
    user_name = await get_user_name(client, bot_id if msg_type == "outgoing" else user_id)

    logging.info(f"[Supabase] Logging message: ts={ts}, type={msg_type}, channel={msg.get('channel')}, user={user_name}, important={important}, repliable={repliable}")
    iso_timestamp = slack_ts_to_iso(ts)
    if not iso_timestamp:
        logging.error(f"[Supabase] Failed to convert timestamp for message {ts}. Skipping.")
        return

    data = {
        "id": ts,
        "thread_ts": msg.get("thread_ts") or None,
        "user_id": user_id,
        "user_name": user_name or "unknown",
        "channel_id": msg.get("channel") or "unknown",
        "content": msg.get("text", ""),
        "timestamp": iso_timestamp,
        "message_type": msg_type,
        "important": important,
        "repliable": repliable
    }
    try:
        resp = supabase.table("messages").upsert(data, on_conflict="id").execute()
        if hasattr(resp, "data") and resp.data:
            logging.info(f"[Supabase] Message {data['id']} logged successfully.")
        else:
            logging.error(f"[Supabase] Upsert failed: {resp}")
    except Exception as e:
        logging.error(f"[Supabase] Failed to log message {ts}: {e}")