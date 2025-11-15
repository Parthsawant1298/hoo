"""
Main Agent - The Boss
Coordinates all specialist agents and manages user interaction with streaming responses
"""

from typing import Dict, List
import json
from .a2a_protocol import A2AChannel, A2AMessage, ChatTranscript

class MainAgent:
    def __init__(self, channel: A2AChannel, ai_client, transcript: ChatTranscript):
        self.agent_id = "main_agent"
        self.channel = channel
        self.ai_client = ai_client
        self.transcript = transcript
        
        self.system_prompt = """You are the MAIN BOSS AGENT for ABC+ Fit Banker health chatbot.

YOUR ROLE:
- You are the ONLY agent that talks directly to users
- You coordinate a team of specialist agents via A2A protocol
- You send MULTIPLE progressive messages to keep users engaged
- You make the conversation feel natural and real-time

YOUR TEAM:
1. registration_agent - New account creation
2. login_agent - User authentication
3. profile_agent - Health profile management
4. health_agent - Health tips and advice
5. logout_agent - Logout handling

STREAMING RESPONSE RULES:
🔥 CRITICAL: Send 2-4 progressive messages for ANY action
- First message: Acknowledge ("Got it! Let me help with that...")
- Middle messages: Progress updates ("Checking...", "Verifying...")
- Final message: Result ("Done!" or next question)

Example for login:
Message 1: "Let me log you in! 🔐"
Message 2: "Verifying your credentials..."
Message 3: "Login successful! Welcome back!"

Example for registration:
Message 1: "Great! Let's create your account 🎉"
Message 2: "I'll need your email address first."

ROUTING LOGIC:
- Registration keywords → registration_agent
- Login keywords → login_agent  
- Profile keywords → profile_agent (auth required)
- Health questions → health_agent (auth required)
- Logout → logout_agent

AUTH CHECK:
- session_info contains user_id if logged in
- Block health_agent & profile_agent without auth

RESPONSE FORMAT (JSON):
{
  "action": "route" | "respond",
  "to_agent": "agent_id",
  "stream_messages": [
    {"content": "first message"},
    {"content": "second message"}
  ],
  "reasoning": "why"
}

PERSONALITY: Friendly, warm, encouraging. Use emojis sparingly."""

        self.card = {
            "agent_id": self.agent_id,
            "name": "Main Boss Agent",
            "description": "Primary coordinator with streaming responses",
            "capabilities": ["User interaction", "Agent coordination", "Stream management"]
        }
        channel.register_agent(self.agent_id, self.card)
    
    async def process_with_streaming(self, user_message: str, session_data: Dict, session_id: str = None) -> Dict:
        session_info = json.dumps(session_data, indent=2) if session_data else "No active session"
        chat_context = self.transcript.get_context(session_id)
        
        context = f"""
USER MESSAGE: {user_message}

SESSION: {session_info}

CHAT HISTORY: {chat_context}

Decide what to do and generate 2-4 progressive streaming messages.
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
        
        decision_text = response.choices[0].message.content
        
        try:
            decision = json.loads(decision_text)
        except:
            decision = {
                "action": "respond",
                "stream_messages": [{"content": decision_text}]
            }
        
        if not decision.get("stream_messages"):
            decision["stream_messages"] = [{"content": decision.get("message", "I'm here to help!")}]
        
        for msg in decision["stream_messages"]:
            self.transcript.add_message(session_id, "assistant", msg["content"], "main_agent")
        
        if decision["action"] == "route":
            target_agent = decision["to_agent"]
            
            a2a_msg = A2AMessage(
                sender=self.agent_id,
                receiver=target_agent,
                content=decision.get("message", user_message),
                metadata={
                    "session": session_data,
                    "original_user_message": user_message,
                    "chat_context": chat_context,
                    "session_id": session_id
                }
            )
            
            await self.channel.send(a2a_msg)
            
            return {
                "routed_to": target_agent,
                "stream_messages": decision["stream_messages"]
            }
        
        return {
            "stream_messages": decision["stream_messages"],
            "from_agent": "main_agent"
        }
