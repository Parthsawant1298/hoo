"""
Registration Agent - Handles new user account creation
"""

from typing import Dict
import json
import hashlib
import asyncpg
from .a2a_protocol import A2AChannel, A2AMessage, ChatTranscript

class RegistrationAgent:
    def __init__(self, channel: A2AChannel, ai_client, transcript: ChatTranscript, db_url: str):
        self.agent_id = "registration_agent"
        self.channel = channel
        self.ai_client = ai_client
        self.transcript = transcript
        self.db_url = db_url
        
        self.system_prompt = """You are the REGISTRATION SPECIALIST agent.

YOUR JOB:
- Collect email, phone, password, name through conversation
- Create accounts in database when you have all info
- Send MULTIPLE streaming messages for natural flow

STREAMING RULES:
- Always send 2-4 messages per interaction
- Make it feel conversational and real-time

RESPONSE FORMAT (JSON):
{
  "stream_messages": [
    {"content": "Great! Let's create your account"},
    {"content": "I'll need your email address"}
  ],
  "status": "collecting" | "ready" | "created",
  "create_user": {
    "email": "...",
    "phone": "...",
    "password": "...",
    "name": "..."
  }
}

When status is "ready", include create_user with all fields.

Be warm and helpful!"""

        self.card = {
            "agent_id": self.agent_id,
            "name": "Registration Specialist",
            "description": "Handles account creation",
            "capabilities": ["Account creation", "Input validation"]
        }
        channel.register_agent(self.agent_id, self.card)
    
    async def process_with_streaming(self, a2a_message: A2AMessage) -> Dict:
        session = a2a_message.metadata.get("session", {})
        user_msg = a2a_message.metadata.get("original_user_message", "")
        chat_context = a2a_message.metadata.get("chat_context", "")
        session_id = a2a_message.metadata.get("session_id")
        
        context = f"""
MAIN AGENT REQUEST: {a2a_message.content}
USER SAID: {user_msg}
CHAT HISTORY: {chat_context}

Check chat history for email, phone, password, name. If all present, set status to "ready".
"""
        
        response = await self.ai_client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": context}
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        result = response.choices[0].message.content
        
        try:
            decision = json.loads(result)
        except:
            decision = {
                "stream_messages": [{"content": result}],
                "status": "collecting"
            }
        
        if decision.get("status") == "ready" and "create_user" in decision:
            user_data = decision["create_user"]
            
            try:
                conn = await asyncpg.connect(self.db_url)
                password_hash = hashlib.sha256(user_data["password"].encode()).hexdigest()
                
                user_id = await conn.fetchval('''
                    INSERT INTO users (email, phone, password_hash, name)
                    VALUES ($1, $2, $3, $4)
                    RETURNING user_id
                ''', user_data.get("email"), user_data.get("phone"), 
                    password_hash, user_data.get("name"))
                
                await conn.close()
                
                decision["stream_messages"].append({
                    "content": f"✅ Account created successfully! You can now login with your email."
                })
                decision["status"] = "created"
                decision["user_id"] = user_id
                
            except asyncpg.exceptions.UniqueViolationError:
                decision["stream_messages"] = [{
                    "content": "This email is already registered. Would you like to login instead?"
                }]
                decision["status"] = "error"
            except Exception as e:
                decision["stream_messages"] = [{
                    "content": f"Sorry, there was an error creating your account. Please try again."
                }]
                decision["status"] = "error"
        
        for msg in decision.get("stream_messages", []):
            self.transcript.add_message(session_id, "assistant", msg["content"], "main_agent")
        
        return decision
