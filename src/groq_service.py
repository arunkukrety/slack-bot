"""
Groq service for message classification.
"""
import os
import json
import logging
from typing import Optional, Dict
from groq import Groq


class GroqService:
    """Handles message classification using Groq API."""
    
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_KEY")
        self.client = None
        self.model = "llama3-70b-8192"
        
        if not self.api_key:
            logging.warning("[GroqService] GROQ_API_KEY not found.")
        else:
            try:
                self.client = Groq(api_key=self.api_key)
                logging.info("[GroqService] Groq client initialized successfully.")
            except Exception as e:
                logging.error(f"[GroqService] Failed to initialize Groq client: {e}")
                self.client = None
    
    def is_available(self) -> bool:
        """Check if Groq service is available."""
        return bool(self.client)
    
    async def classify_message(self, message_text: str) -> Dict[str, str]:
        """
        Classify a message as important/repliable using Groq API.
        
        Args:
            message_text: The message content to classify
            
        Returns:
            Dict with 'important' and 'repliable' keys (YES/NO values)
        """
        if not self.client:
            logging.error("[GroqService] Groq client not available.")
            return {"important": "NO", "repliable": "NO"}
        
        if not message_text or not message_text.strip():
            logging.warning("[GroqService] Empty message text provided.")
            return {"important": "NO", "repliable": "NO"}
        
        try:
            # Create classification prompt
            prompt = self._create_classification_prompt(message_text.strip())
            
            # Call Groq API
            completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=0.3,
                max_tokens=100,
                top_p=1,
                stream=False,
                stop=None,
            )
            
            response_content = completion.choices[0].message.content
            logging.debug(f"[GroqService] Raw response: {response_content}")
            
            return self._parse_classification_response(response_content)
            
        except Exception as e:
            logging.error(f"[GroqService] Error during classification: {e}")
            return {"important": "NO", "repliable": "NO"}
    
    def _create_classification_prompt(self, message_text: str) -> str:
        """Create the classification prompt for Groq."""
        return f"""Classify the following Slack message as:
- Important: YES if the message requires attention, asks questions, mentions urgent matters, or contains actionable content. NO for casual chat, greetings, or low-priority messages.
- Repliable: YES if the message seems to expect or would benefit from a response. NO for statements that don't need replies, automated messages, or messages that are purely informational.

Respond ONLY in valid JSON format: {{"important": "YES/NO", "repliable": "YES/NO"}}

Message: "{message_text}"
"""
    
    def _parse_classification_response(self, response_content: str) -> Dict[str, str]:
        """
        Parse the JSON response from Groq.
        
        Args:
            response_content: Raw response from Groq API
            
        Returns:
            Dict with 'important' and 'repliable' keys
        """
        try:
            # Try to extract JSON from the response
            response_content = response_content.strip()
            
            # Look for JSON in the response
            start = response_content.find('{')
            end = response_content.rfind('}') + 1
            
            if start != -1 and end > start:
                json_str = response_content[start:end]
                classification = json.loads(json_str)
                
                # Validate the response
                important = classification.get("important", "NO").upper()
                repliable = classification.get("repliable", "NO").upper()
                
                # Ensure values are YES or NO
                important = "YES" if important == "YES" else "NO"
                repliable = "YES" if repliable == "YES" else "NO"
                
                logging.debug(f"[GroqService] Parsed classification: important={important}, repliable={repliable}")
                return {"important": important, "repliable": repliable}
            else:
                logging.warning(f"[GroqService] No JSON found in response: {response_content}")
                return {"important": "NO", "repliable": "NO"}
                
        except json.JSONDecodeError:
            logging.error(f"[GroqService] Failed to parse JSON response: {response_content}")
            return {"important": "NO", "repliable": "NO"}
        except Exception as e:
            logging.error(f"[GroqService] Error parsing response: {e}")
            return {"important": "NO", "repliable": "NO"}
