import { useState, useEffect } from 'react'
import ChatInterface from './components/ChatInterface'
import './App.css'

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)

  useEffect(() => {
    const stored = localStorage.getItem('session_id')
    if (stored) {
      setSessionId(stored)
    }
  }, [])

  const handleSessionUpdate = (newSessionId: string) => {
    setSessionId(newSessionId)
    localStorage.setItem('session_id', newSessionId)
  }

  return (
    <div style={{ minHeight: '100vh' }}>
      <div className="container">
        <header className="chat-header">
          <h1>ABC+ Fit Banker</h1>
          <p>Your AI Health Assistant 🏥</p>
        </header>
        
        <ChatInterface 
          sessionId={sessionId} 
          onSessionUpdate={handleSessionUpdate}
        />
      </div>
    </div>
  )
}

export default App
