"""
Login Agent - Handles user authentication with streaming responses
"""

from typing import Dict
import json
import hashlib
import secrets
import asyncpg
from datetime import datetime, timedelta
from .a2a_protocol import A2AChannel, A2AMessage, ChatTranscript

class LoginAgent:
    def __init__(self, channel: A2AChannel, ai_client, transcript: ChatTranscript, db_url: str):
        self.agent_id = "login_agent"
        self.channel = channel
        self.ai_client = ai_client
        self.transcript = transcript
        self.db_url = db_url
        
        self.system_prompt = """You are the LOGIN SPECIALIST agent.

YOUR JOB:
- Collect email/phone and password through conversation
- Verify credentials and create sessions
- Send MULTIPLE streaming messages for engaging flow

STREAMING RULES:
- Send 3-4 progressive messages during login
- Example flow:
  Message 1: "Let me log you in!"
  Message 2: "Checking your credentials..."
  Message 3: "Login successful! Welcome back!"

RESPONSE FORMAT (JSON):
{
  "stream_messages": [
    {"content": "Let me log you in! 🔐"},
    {"content": "Verifying credentials..."},
    {"content": "Success!"}
  ],
  "status": "collecting" | "verifying" | "success" | "failed",
  "verify_credentials": {
    "identifier": "email or phone",
    "password": "password"
  }
}

When status is "verifying", include verify_credentials.

Be encouraging!"""

        self.card = {
            "agent_id": self.agent_id,
            "name": "Login Specialist",
            "description": "Handles authentication with streaming",
            "capabilities": ["Authentication", "Session management"]
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

Check if you have email/phone and password. If yes, set status to "verifying".
Generate 3-4 streaming messages for engaging login flow.
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
        
        if decision.get("status") == "verifying" and "verify_credentials" in decision:
            creds = decision["verify_credentials"]
            
            try:
                conn = await asyncpg.connect(self.db_url)
                password_hash = hashlib.sha256(creds["password"].encode()).hexdigest()
                
                user = await conn.fetchrow('''
                    SELECT user_id, name, email FROM users
                    WHERE (email = $1 OR phone = $1) AND password_hash = $2
                ''', creds["identifier"], password_hash)
                
                if user:
                    new_session_id = secrets.token_urlsafe(32)
                    expires_at = datetime.utcnow() + timedelta(days=30)
                    
                    await conn.execute('''
                        INSERT INTO sessions (session_id, user_id, expires_at)
                        VALUES ($1, $2, $3)
                    ''', new_session_id, user["user_id"], expires_at)
                    
                    await conn.close()
                    
                    decision["stream_messages"].append({
                        "content": f"✅ Login successful! Welcome back, {user['name'] or 'there'}! 🎉"
                    })
                    decision["status"] = "success"
                    decision["session_id"] = new_session_id
                    decision["user_id"] = user["user_id"]
                else:
                    await conn.close()
                    decision["stream_messages"] = [
                        {"content": "❌ Invalid credentials. Please check your email and password."}
                    ]
                    decision["status"] = "failed"
                    
            except Exception as e:
                decision["stream_messages"] = [{
                    "content": "Sorry, there was an error during login. Please try again."
                }]
                decision["status"] = "failed"
        
        for msg in decision.get("stream_messages", []):
            self.transcript.add_message(session_id, "assistant", msg["content"], "main_agent")
        
        return decision
