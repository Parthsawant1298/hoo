"""
Logout Agent - Handles user logout
"""

from typing import Dict
import json
import asyncpg
from .a2a_protocol import A2AChannel, A2AMessage, ChatTranscript

class LogoutAgent:
    def __init__(self, channel: A2AChannel, ai_client, transcript: ChatTranscript, db_url: str):
        self.agent_id = "logout_agent"
        self.channel = channel
        self.ai_client = ai_client
        self.transcript = transcript
        self.db_url = db_url
        
        self.system_prompt = """You are the LOGOUT SPECIALIST agent.

YOUR JOB:
- Handle logout requests
- Clear sessions
- Send friendly goodbye messages

RESPONSE FORMAT (JSON):
{
  "stream_messages": [
    {"content": "Logging you out..."},
    {"content": "You've been logged out successfully. See you soon!"}
  ],
  "status": "logged_out"
}

Be warm and encouraging!"""

        self.card = {
            "agent_id": self.agent_id,
            "name": "Logout Specialist",
            "description": "Handles logout",
            "capabilities": ["Session termination"]
        }
        channel.register_agent(self.agent_id, self.card)
    
    async def process_with_streaming(self, a2a_message: A2AMessage) -> Dict:
        session_id = a2a_message.metadata.get("session_id")
        
        decision = {
            "stream_messages": [
                {"content": "Logging you out..."},
                {"content": "✅ You've been logged out successfully. Take care!"}
            ],
            "status": "logged_out"
        }
        
        if session_id:
            try:
                conn = await asyncpg.connect(self.db_url)
                await conn.execute('DELETE FROM sessions WHERE session_id = $1', session_id)
                await conn.close()
            except Exception:
                pass
        
        for msg in decision.get("stream_messages", []):
            self.transcript.add_message(session_id, "assistant", msg["content"], "main_agent")
        
        return decision
