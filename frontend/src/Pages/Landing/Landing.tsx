import { useEffect, useState } from 'react'
import { checkHealth } from '../../api/client'
import './Landing.css'

type ConnectionStatus = 'checking' | 'connected' | 'disconnected'

function Landing() {
  const [status, setStatus] = useState<ConnectionStatus>('checking')

  useEffect(() => {
    checkHealth()
      .then(() => setStatus('connected'))
      .catch(() => setStatus('disconnected'))
  }, [])

  return (
    <div className="landing">
      <h1 className="landing__title">Med RAG Lab</h1>
      <p className="landing__subtitle">
        Compare retrieval mechanisms over a medical Q&amp;A dataset.
      </p>
      <div className={`landing__status landing__status--${status}`}>
        Backend: {status}
      </div>
    </div>
  )
}

export default Landing
