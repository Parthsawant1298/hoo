"""
Profile Agent - Manages user health profiles
"""

from typing import Dict
import json
import asyncpg
from .a2a_protocol import A2AChannel, A2AMessage, ChatTranscript

class ProfileAgent:
    def __init__(self, channel: A2AChannel, ai_client, transcript: ChatTranscript, db_url: str):
        self.agent_id = "profile_agent"
        self.channel = channel
        self.ai_client = ai_client
        self.transcript = transcript
        self.db_url = db_url
        
        self.system_prompt = """You are the PROFILE SPECIALIST agent.

YOUR JOB:
- Manage health profiles (create/update/view)
- Collect age, gender, height, weight, goals, conditions
- Send MULTIPLE streaming messages

RESPONSE FORMAT (JSON):
{
  "stream_messages": [
    {"content": "Let's set up your health profile!"},
    {"content": "First, what's your age?"}
  ],
  "status": "collecting" | "ready" | "created",
  "profile_data": {
    "age": 30,
    "gender": "female",
    "height_cm": 165,
    "weight_kg": 60,
    "activity_level": "moderate",
    "diet_preference": "vegetarian",
    "health_goals": ["weight_loss", "energy"],
    "health_conditions": []
  }
}

Be supportive and health-focused!"""

        self.card = {
            "agent_id": self.agent_id,
            "name": "Profile Specialist",
            "description": "Manages health profiles",
            "capabilities": ["Profile management", "Health data collection"]
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
                    "content": "You need to be logged in to manage your profile."
                }],
                "status": "auth_required"
            }
        
        context = f"""
MAIN AGENT REQUEST: {a2a_message.content}
USER SAID: {user_msg}
CHAT HISTORY: {chat_context}

Extract profile data from chat. Generate 2-3 streaming messages.
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
        
        if decision.get("status") == "ready" and "profile_data" in decision:
            profile_data = decision["profile_data"]
            
            try:
                conn = await asyncpg.connect(self.db_url)
                
                await conn.execute('''
                    INSERT INTO user_profiles 
                    (user_id, age, gender, height_cm, weight_kg, activity_level, 
                     diet_preference, health_goals, health_conditions)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (user_id) DO UPDATE SET
                        age = EXCLUDED.age,
                        gender = EXCLUDED.gender,
                        height_cm = EXCLUDED.height_cm,
                        weight_kg = EXCLUDED.weight_kg,
                        activity_level = EXCLUDED.activity_level,
                        diet_preference = EXCLUDED.diet_preference,
                        health_goals = EXCLUDED.health_goals,
                        health_conditions = EXCLUDED.health_conditions,
                        updated_at = CURRENT_TIMESTAMP
                ''', session["user_id"], profile_data.get("age"), 
                    profile_data.get("gender"), profile_data.get("height_cm"),
                    profile_data.get("weight_kg"), profile_data.get("activity_level"),
                    profile_data.get("diet_preference"), 
                    profile_data.get("health_goals", []),
                    profile_data.get("health_conditions", []))
                
                await conn.close()
                
                decision["stream_messages"].append({
                    "content": "✅ Your health profile has been updated!"
                })
                decision["status"] = "created"
                
            except Exception as e:
                decision["stream_messages"] = [{
                    "content": "Sorry, there was an error saving your profile."
                }]
                decision["status"] = "error"
        
        for msg in decision.get("stream_messages", []):
            self.transcript.add_message(session_id, "assistant", msg["content"], "main_agent")
        
        return decision
