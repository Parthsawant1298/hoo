"""
ABC+ Fit Banker - Real-Time Agentic AI Chatbot with Streaming
Multi-Agent System with A2A Protocol and Server-Sent Events (SSE)
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, List, AsyncGenerator
import json
from datetime import datetime, timedelta
import asyncpg
import hashlib
import secrets
from openai import AsyncOpenAI
import os
import asyncio
from sse_starlette.sse import EventSourceResponse

app = FastAPI(title="ABC+ Fit Banker AI System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

DATABASE_URL = os.getenv("DATABASE_URL")

from agents.a2a_protocol import A2AChannel, A2AMessage, ChatTranscript
from agents.main_agent import MainAgent
from agents.registration_agent import RegistrationAgent
from agents.login_agent import LoginAgent
from agents.profile_agent import ProfileAgent
from agents.health_agent import HealthAgent
from agents.logout_agent import LogoutAgent

a2a_channel = A2AChannel()
chat_transcript = ChatTranscript()

main_agent = MainAgent(a2a_channel, client, chat_transcript)
registration_agent = RegistrationAgent(a2a_channel, client, chat_transcript, DATABASE_URL)
login_agent = LoginAgent(a2a_channel, client, chat_transcript, DATABASE_URL)
profile_agent = ProfileAgent(a2a_channel, client, chat_transcript, DATABASE_URL)
health_agent = HealthAgent(a2a_channel, client, chat_transcript)
logout_agent = LogoutAgent(a2a_channel, client, chat_transcript, DATABASE_URL)

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

async def get_db():
    return await asyncpg.connect(DATABASE_URL)

async def get_user_from_session(session_id: str) -> Optional[Dict]:
    if not session_id:
        return None
    
    conn = await get_db()
    try:
        user = await conn.fetchrow('''
            SELECT s.user_id, u.name, u.email,
                   EXISTS(SELECT 1 FROM user_profiles WHERE user_id = s.user_id) as has_profile
            FROM sessions s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.session_id = $1 AND s.expires_at > NOW()
        ''', session_id)
        
        if user:
            return {
                "user_id": user["user_id"],
                "name": user["name"],
                "email": user["email"],
                "has_profile": user["has_profile"],
                "authenticated": True
            }
        return None
    finally:
        await conn.close()

@app.on_event("startup")
async def startup():
    conn = await get_db()
    try:
        await conn.execute('DROP TABLE IF EXISTS health_tracking CASCADE')
        await conn.execute('DROP TABLE IF EXISTS sessions CASCADE')
        await conn.execute('DROP TABLE IF EXISTS user_profiles CASCADE')
        await conn.execute('DROP TABLE IF EXISTS users CASCADE')

        await conn.execute('''
            CREATE TABLE users (
                user_id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                phone VARCHAR(20) UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await conn.execute('''
            CREATE TABLE user_profiles (
                profile_id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
                age INTEGER,
                gender VARCHAR(50),
                height_cm FLOAT,
                weight_kg FLOAT,
                activity_level VARCHAR(50),
                diet_preference VARCHAR(100),
                health_goals TEXT[],
                health_conditions TEXT[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await conn.execute('''
            CREATE TABLE sessions (
                session_id VARCHAR(255) PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        ''')

        await conn.execute('''
            CREATE TABLE health_tracking (
                tracking_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
                tracking_type VARCHAR(50),
                data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database error: {e}")
    finally:
        await conn.close()

async def stream_agent_chat(user_message: str, session_id: str) -> AsyncGenerator[str, None]:
    session_data = await get_user_from_session(session_id) if session_id else None
    
    chat_transcript.add_message(session_id, "user", user_message)
    
    yield f"data: {json.dumps({'type': 'user_message', 'message': user_message})}\n\n"
    
    await asyncio.sleep(0.3)
    
    yield f"data: {json.dumps({'type': 'agent_thinking', 'message': '🤔 Processing your request...'})}\n\n"
    
    await asyncio.sleep(0.5)
    
    result = await main_agent.process_with_streaming(user_message, session_data, session_id)
    
    if result.get("stream_messages"):
        for msg in result["stream_messages"]:
            yield f"data: {json.dumps({'type': 'agent_message', 'message': msg['content'], 'agent': msg.get('agent', 'main_agent')})}\n\n"
            await asyncio.sleep(0.6)
    
    if result.get("routed_to"):
        target_agent = result["routed_to"]
        
        messages = a2a_channel.get_messages(target_agent)
        
        for a2a_msg in messages:
            if target_agent == "registration_agent":
                response = await registration_agent.process_with_streaming(a2a_msg)
            elif target_agent == "login_agent":
                response = await login_agent.process_with_streaming(a2a_msg)
            elif target_agent == "profile_agent":
                response = await profile_agent.process_with_streaming(a2a_msg)
            elif target_agent == "health_agent":
                response = await health_agent.process_with_streaming(a2a_msg)
            elif target_agent == "logout_agent":
                response = await logout_agent.process_with_streaming(a2a_msg)
            
            if response.get("stream_messages"):
                for msg in response["stream_messages"]:
                    yield f"data: {json.dumps({'type': 'agent_message', 'message': msg['content'], 'agent': 'main_agent'})}\n\n"
                    await asyncio.sleep(0.6)
            
            if response.get("session_id"):
                yield f"data: {json.dumps({'type': 'session_update', 'session_id': response['session_id']})}\n\n"
    
    yield f"data: {json.dumps({'type': 'done'})}\n\n"

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    return EventSourceResponse(
        stream_agent_chat(request.message, request.session_id),
        media_type="text/event-stream"
    )

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    user_data = await get_user_from_session(session_id)
    if user_data:
        return user_data
    return {"authenticated": False}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "agents": len(a2a_channel.agent_cards)}

@app.get("/")
async def root():
    return {"message": "ABC+ Fit Banker AI Agent System", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
