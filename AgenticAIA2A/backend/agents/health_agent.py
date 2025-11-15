"""
Health Agent - Provides health tips and answers questions
"""

from typing import Dict
import json
from .a2a_protocol import A2AChannel, A2AMessage, ChatTranscript

class HealthAgent:
    def __init__(self, channel: A2AChannel, ai_client, transcript: ChatTranscript):
        self.agent_id = "health_agent"
        self.channel = channel
        self.ai_client = ai_client
        self.transcript = transcript
        
        self.system_prompt = """You are the HEALTH SPECIALIST agent for ABC+ Fit Banker.

YOUR JOB:
- Answer health, nutrition, fitness questions
- Provide evidence-based advice
- Send MULTIPLE streaming messages

KNOWLEDGE AREAS:
- Nutrition (proteins, carbs, fats, vitamins, minerals)
- Exercise (cardio, strength, yoga, walking)
- Sleep and stress management
- Hydration and meal timing
- Indian diet options (vegetarian, non-veg)

RESPONSE FORMAT (JSON):
{
  "stream_messages": [
    {"content": "Great question! Let me help with that."},
    {"content": "For protein, you can try lentils, chickpeas, paneer..."},
    {"content": "Aim for 1g per kg of body weight daily."}
  ],
  "status": "answered"
}

RULES:
- Be evidence-based but accessible
- Suggest Indian food options
- Add disclaimers for medical advice
- Be warm and supportive

Generate 2-4 streaming messages per response."""

        self.card = {
            "agent_id": self.agent_id,
            "name": "Health Specialist",
            "description": "Provides health tips and advice",
            "capabilities": ["Health advice", "Nutrition guidance", "Fitness tips"]
        }
        channel.register_agent(self.agent_id, self.card)
    
    async def process_with_streaming(self, a2a_message: A2AMessage) -> Dict:
        session = a2a_message.metadata.get("session", {})
        user_msg = a2a_message.metadata.get("original_user_message", "")
        chat_context = a2a_message.metadata.get("chat_context", "")
        session_id = a2a_message.metadata.get("session_id")
        
        if not session or not session.get("user_id"):
            return {
                "stream_messages": [{
                    "content": "You need to be logged in to get personalized health advice."
                }],
                "status": "auth_required"
            }
        
        context = f"""
MAIN AGENT REQUEST: {a2a_message.content}
USER QUESTION: {user_msg}
CHAT HISTORY: {chat_context}

Provide helpful health advice. Generate 2-4 streaming messages for natural flow.
"""
        
        response = await self.ai_client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": context}
            ],
            temperature=0.7,
            max_tokens=400
        )
        
        result = response.choices[0].message.content
        
        try:
            decision = json.loads(result)
        except:
            decision = {
                "stream_messages": [{"content": result}],
                "status": "answered"
            }
        
        for msg in decision.get("stream_messages", []):
            self.transcript.add_message(session_id, "assistant", msg["content"], "main_agent")
        
        return decision
