# ABC+ Fit Banker - AI Health Assistant

## Project Overview
Real-time agentic AI chatbot system with streaming responses for health and wellness assistance. Uses multi-agent architecture with Agent-to-Agent (A2A) communication protocol.

## Architecture

### Backend (FastAPI + Python)
- **Location**: `backend/`
- **Port**: 8000
- **Features**:
  - Real-time streaming via Server-Sent Events (SSE)
  - Multi-agent system with 6 AI agents
  - PostgreSQL database for users, profiles, sessions
  - OpenRouter AI integration for intelligent responses

### Frontend (React + TypeScript + Vite)
- **Location**: `frontend/`
- **Port**: 5000
- **Features**:
  - Real-time chat interface with SSE
  - Streaming message display
  - Session management with localStorage
  - Clean, responsive UI

## Agent System

### Main Agent (Boss)
- Coordinates all specialist agents
- Only agent that talks to users
- Routes requests to appropriate specialist agents
- Sends multiple progressive messages for natural conversation flow

### Specialist Agents
1. **Registration Agent** - New account creation
2. **Login Agent** - User authentication  
3. **Profile Agent** - Health profile management
4. **Health Agent** - Health tips and Q&A
5. **Logout Agent** - Session termination

## Key Features Implemented

✅ Real-time streaming chat (no waiting for complete responses)
✅ Multi-agent A2A communication (agents collaborate behind the scenes)
✅ Progressive message updates ("Verifying...", "Done!", etc.)
✅ User authentication (register, login, logout)
✅ Health profile creation
✅ Session persistence
✅ PostgreSQL database with proper schema
✅ Hidden inter-agent communication (users only see Main Agent)

## Environment Variables
- `DATABASE_URL` - PostgreSQL connection
- `OPENROUTER_API_KEY` - AI model access
- `OPENAI_API_KEY` - Alternative AI access

## How It Works

1. User sends message → Frontend
2. Frontend streams request to Backend `/api/chat/stream`
3. Main Agent analyzes user intent
4. Main Agent sends progressive messages ("Got it!", "Checking...")
5. Main Agent routes to specialist agent via A2A
6. Specialist processes and responds
7. Main Agent relays response to user
8. All messages stream in real-time to frontend

## Testing

- Backend API: http://localhost:8000/health
- Frontend App: http://localhost:5000
- Both workflows running and tested

## Recent Changes
- Database schema with unique constraint on user_profiles.user_id
- Vite config with `allowedHosts: true` for Replit domains
- Removed Tailwind CSS, using vanilla CSS for compatibility
- Fixed frontend root directory in vite.config.ts
