import os
import logging
from typing import Dict, List, Optional

try:
   from mem0 import MemoryClient
   MEM0_AVAILABLE = True
except ImportError:
   MEM0_AVAILABLE = False
   MemoryClient = None

class Mem0Service:
   """Mem0 memory management service"""
   
   def __init__(self):
       self.api_key = os.getenv("MEM0_KEY")
       self.client = None
       
       if not MEM0_AVAILABLE:
           logging.warning("[Mem0] mem0ai package not available")
           return
           
       if self.api_key:
           try:
               self.client = MemoryClient(api_key=self.api_key)
               logging.info("[Mem0] Client initialized successfully")
           except Exception as e:
               logging.error(f"[Mem0] Failed to initialize: {e}")
       else:
           logging.warning("[Mem0] MEM0_KEY not found")
   
   def is_available(self) -> bool:
       """Check if Mem0 service is available"""
       return self.client is not None
   
   def add_user_message(self, user_id: str, user_message: str) -> bool:
       """Store user message in memory"""
       if not self.is_available():
           return False
           
       try:
           messages = [
               {"role": "user", "content": user_message}
           ]
           self.client.add(messages, user_id=user_id)
           logging.info(f"[Mem0] Stored user message for user {user_id}")
           return True
       except Exception as e:
           logging.error(f"[Mem0] Failed to store user message: {e}")
           return False
   
   def get_memories(self, user_id: str, query: str) -> str:
       """Retrieve relevant memories for user based on query using Mem0 v2 search API"""
       if not self.is_available():
           return ""
           
       if not query or query.strip() == "":
           return ""
           
       try:
           # Use v2 search API with filters for user_id
           result = self.client.search(
               query=query,
               version="v2",
               filters={
                   "user_id": user_id
               },
               threshold=0.5
           )
           
           if result and len(result) > 0:
               memories = []
               for item in result:
                   # Handle different response formats
                   if isinstance(item, dict):
                       # Check for 'memory' key first
                       if 'memory' in item:
                           memories.append(item['memory'])
                       # Check for 'text' key as alternative
                       elif 'text' in item:
                           memories.append(item['text'])
                       # Check for 'content' key as alternative
                       elif 'content' in item:
                           memories.append(item['content'])
                       # If it's a dict with no expected keys, convert to string
                       else:
                           memories.append(str(item))
                   elif isinstance(item, str):
                       memories.append(item)
                   else:
                       # Handle any other type by converting to string
                       memories.append(str(item))
               
               if memories:
                   context = "\n".join(f"• {memory}" for memory in memories[:5])  # Limit to 5 most relevant
                   logging.info(f"[Mem0] Retrieved {len(memories)} relevant memories for user {user_id} with query: {query}")
                   return context
       except Exception as e:
           logging.error(f"[Mem0] Failed to retrieve memories: {e}")
       
       return ""

# Global service instance
mem0_service = Mem0Service()

# Test function
def test_mem0():
   """Test Mem0 integration"""
   print(f"[Mem0 Test] Available: {mem0_service.is_available()}")
   if mem0_service.is_available():
       success = mem0_service.add_user_message("test_user", "Hello, this is a test message.")
       print(f"[Mem0 Test] Add user message: {success}")
       memories = mem0_service.get_memories("test_user", "hello")
       print(f"[Mem0 Test] Retrieved memories: {len(memories) > 0}")

# Run test if executed directly
if __name__ == "__main__":
   test_mem0()