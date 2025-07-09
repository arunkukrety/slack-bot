"""
AI service for generating responses using OpenRouter.
"""
import os
import json
import logging
import aiohttp
from typing import Optional
from .Supabase import get_message_context, get_thread_context
from .memzero import mem0_service


class AIService:
    """Handles AI-powered responses using OpenRouter."""
    
    def __init__(self, settings=None):
        self.api_key = os.getenv("OPEN_ROUTER_KEY")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.settings = settings
        self.default_model = "meta-llama/llama-3.3-70b-instruct:free" 
        
        if not self.api_key:
            logging.warning("OPEN_ROUTER_KEY not found.")
    
    def get_current_model(self) -> str:
        """Get the current model from settings or default."""
        if self.settings:
            return self.settings.get("llm_model", self.default_model)
        return self.default_model
    
    async def get_response(self, user_message: str, user_id: str = None, thread_ts: str = None) -> Optional[str]:
        if not self.api_key:
            return "Hello World! 🤖 (missing OPEN_ROUTER_KEY)"
        
        try:
            # Parallelize context and memory retrieval
            import asyncio
            # Use thread context if thread_ts is provided, else fallback to channel context
            if thread_ts:
                logging.info(f"[AIService] Using thread context for thread_ts: {thread_ts}")
                context_task = asyncio.create_task(get_thread_context(thread_ts))
            else:
                logging.info("[AIService] Using channel context (no thread_ts provided)")
                context_task = asyncio.create_task(get_message_context())
            memory_task = None
            if user_id and mem0_service.is_available():
                # Wrap sync call in a thread to avoid blocking event loop
                loop = asyncio.get_running_loop()
                memory_task = loop.run_in_executor(None, mem0_service.get_memories, user_id, user_message)
            else:
                memory_task = asyncio.create_task(asyncio.sleep(0, result=""))
            message_context, memory_context = await asyncio.gather(context_task, memory_task)

            if message_context:
                context_type = "thread" if thread_ts else "channel"
                num_messages = len([line for line in message_context.split('\n') if line.strip()])
                logging.info(f"[AIService] Retrieved {num_messages} messages from Supabase for {context_type} context.")
            else:
                context_type = "thread" if thread_ts else "channel"
                logging.warning(f"[AIService] No {context_type} context retrieved from Supabase")

            if memory_context:
                logging.info(f"[AIService] Retrieved memories for user {user_id}:\n{memory_context}")

            system_content = (
                "You are a helpful Slack bot assistant. Your tone should be professional-casual—clear, friendly, "
                "and confident, with a light touch of humor when appropriate. Keep responses concise and workplace-appropriate. "
                "Always format output to look clean and readable in Slack. Be helpful, witty (when it fits), and never robotic."
                "Use slack markdown rules for formatting. Act accordingly as per the context given to you.\n"
            )
            if message_context:
                system_content += f"\n\nRecent Messages:\n{message_context}"
            if memory_context:
                system_content += f"\n\nUser Memory Context:\n{memory_context}"

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
                        "content": system_content
                    },
                    {
                        "role": "user", 
                        "content": user_message
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.7
            }
            logging.info(f"[AIService] Sending payload to OpenRouter: {json.dumps(payload, indent=2)}")
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        logging.debug(f"[AIService] OpenRouter response: {data}")
                        if "choices" not in data:
                            logging.error(f"[AIService] No 'choices' in response: {data}")
                            return "Sorry, I couldn't process the response. Please try again later! 🤔"
                        ai_response = data["choices"][0]["message"]["content"]
                        # Store user message in Mem0 (fire-and-forget)
                        if user_id and mem0_service.is_available():
                            asyncio.create_task(asyncio.to_thread(mem0_service.add_user_message, user_id, user_message))
                        return ai_response.strip()
                    else:
                        error_text = await response.text()
                        logging.error(f"[AIService] OpenRouter API error {response.status}: {error_text}")
                        return "Sorry, I'm having trouble thinking right now. Try again in a moment! 🤔"
        except aiohttp.ClientError as e:
            logging.error(f"Network error calling OpenRouter: {e}")
            return "Hello World! 🌐 (Network issue - please try again)"
        except Exception as e:
            logging.error(f"Unexpected error in AI service: {e}")
            return "Hello World! ⚠️ (Something went wrong)"
    
    def is_available(self) -> bool:
        """Check if AI service is available."""
        return bool(self.api_key)
