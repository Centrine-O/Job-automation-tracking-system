import React, { useState, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './globals.css'

import Layout   from '@/components/Layout'
import Overview from '@/pages/Overview'
import Queue    from '@/pages/Queue'
import History  from '@/pages/History'
import System   from '@/pages/System'
import { getStats } from '@/lib/api'

function App() {
  const [dryRun, setDryRun] = useState(false)

  useEffect(() => {
    getStats().then(s => setDryRun(s.dry_run)).catch(() => {})
  }, [])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout dryRun={dryRun} />}>
          <Route index         element={<Overview />} />
          <Route path="queue"   element={<Queue />} />
          <Route path="history" element={<History />} />
          <Route path="system"  element={<System />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />)
