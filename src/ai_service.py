"""
AI service for generating responses using OpenRouter.
"""
import os
import json
import logging
import aiohttp
from typing import Optional
from .Supabase import get_message_context
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
    
    async def get_response(self, user_message: str, user_id: str = None) -> Optional[str]:
        if not self.api_key:
            return "Hello World! 🤖 (missing OPEN_ROUTER_KEY)"
        
        try:
            # Parallelize context and memory retrieval
            import asyncio
            context_task = asyncio.create_task(get_message_context())
            memory_task = None
            if user_id and mem0_service.is_available():
                # Wrap sync call in a thread to avoid blocking event loop
                loop = asyncio.get_running_loop()
                memory_task = loop.run_in_executor(None, mem0_service.get_memories, user_id, user_message)
            else:
                memory_task = asyncio.create_task(asyncio.sleep(0, result=""))
            message_context, memory_context = await asyncio.gather(context_task, memory_task)

            if memory_context:
                logging.info(f"[AIService] Retrieved memories for user {user_id}:\n{memory_context}")

            # Build system prompt with context
            system_content = (
                "You are a helpful Slack bot assistant. Keep responses concise, "
                "friendly, and appropriate for workplace communication. "
                "Use emojis sparingly and professionally."
            )
            if memory_context:
                system_content += f"\n\nUser Memory Context:\n{memory_context}"
            # if message_context:
            #     system_content += f"\n\nRecent Messages:\n{message_context}"

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
