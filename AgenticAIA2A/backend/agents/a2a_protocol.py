"""
A2A (Agent-to-Agent) Communication Protocol
Enables intelligent agents to collaborate and communicate
"""

from datetime import datetime
from typing import Dict, List, Optional
import json

class A2AMessage:
    def __init__(self, sender: str, receiver: str, content: str, 
                 message_type: str = "request", metadata: Dict = None):
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.message_type = message_type
        self.timestamp = datetime.utcnow().isoformat()
        self.metadata = metadata or {}
        self.message_id = f"{sender}-{int(datetime.utcnow().timestamp() * 1000)}"
    
    def to_dict(self) -> Dict:
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "timestamp": self.timestamp,
            "type": self.message_type,
            "content": self.content,
            "metadata": self.metadata
        }

class A2AChannel:
    def __init__(self):
        self.agent_cards: Dict[str, Dict] = {}
        self.message_queue: Dict[str, List[A2AMessage]] = {}
        self.conversation_history: Dict[str, List[Dict]] = {}
    
    def register_agent(self, agent_id: str, card: Dict):
        self.agent_cards[agent_id] = card
        self.message_queue[agent_id] = []
        self.conversation_history[agent_id] = []
        print(f"✅ Registered: {card['name']}")
    
    async def send(self, message: A2AMessage):
        if message.receiver in self.message_queue:
            self.message_queue[message.receiver].append(message)
            self.conversation_history[message.receiver].append({
                "from": message.sender,
                "to": message.receiver,
                "content": message.content,
                "timestamp": message.timestamp,
                "metadata": message.metadata
            })
            print(f"📨 A2A: {message.sender} → {message.receiver}")
    
    def get_messages(self, agent_id: str) -> List[A2AMessage]:
        messages = self.message_queue.get(agent_id, [])
        self.message_queue[agent_id] = []
        return messages
    
    def get_conversation_context(self, agent_id: str) -> str:
        history = self.conversation_history.get(agent_id, [])
        if not history:
            return "No previous agent conversations."
        
        context = "AGENT CONVERSATION HISTORY:\n"
        for msg in history[-5:]:
            context += f"{msg['from']} → {msg['to']}: {msg['content']}\n"
        return context

class ChatTranscript:
    def __init__(self):
        self.transcripts: Dict[str, List[Dict]] = {}
    
    def add_message(self, session_id: str, role: str, message: str, agent: str = None):
        if not session_id:
            session_id = "guest"
        
        if session_id not in self.transcripts:
            self.transcripts[session_id] = []
        
        self.transcripts[session_id].append({
            "timestamp": datetime.utcnow().isoformat(),
            "role": role,
            "message": message,
            "agent": agent
        })
        
        if len(self.transcripts[session_id]) > 20:
            self.transcripts[session_id] = self.transcripts[session_id][-20:]
    
    def get_context(self, session_id: str) -> str:
        if not session_id:
            session_id = "guest"
        
        if session_id not in self.transcripts:
            return "No previous conversation."
        
        context = "PREVIOUS CONVERSATION:\n"
        for msg in self.transcripts[session_id][-10:]:
            role = "USER" if msg["role"] == "user" else "AI"
            agent_info = f" ({msg['agent']})" if msg.get("agent") else ""
            context += f"{role}{agent_info}: {msg['message']}\n"
        
        return context
