import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import AlertBanner from './components/AlertBanner'
import { getState, getHealth } from './api/client'

import Overview       from './pages/Overview'
import MonitoredFiles from './pages/MonitoredFiles'
import EventStream    from './pages/EventStream'
import MicroLedger    from './pages/MicroLedger'
import Verification   from './pages/Verification'
import Alerts         from './pages/Alerts'
import EvidenceExport from './pages/EvidenceExport'
import UserAudit      from './pages/UserAudit'
import Settings       from './pages/Settings'

function Shell() {
  const [state,           setState]           = useState(null)
  const [daemonRunning,   setDaemonRunning]   = useState(false)
  const [bannerDismissed, setBannerDismissed] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const [s, h] = await Promise.all([getState(), getHealth()])
        setState(s)
        setDaemonRunning(h.daemon_running ?? false)
        if (s.health_status === 'healthy') setBannerDismissed(false)
      } catch { /* gateway may not be running yet */ }
    }
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [])

  const showBanner   = !bannerDismissed && state?.health_status && state.health_status !== 'healthy'
  const bannerOffset = showBanner ? 'pt-10' : 'pt-0'

  return (
    <div className="min-h-screen bg-canvas flex">
      <Sidebar state={state} daemonRunning={daemonRunning} />

      <div className="flex-1 main-offset flex flex-col min-h-screen">
        {showBanner && (
          <AlertBanner
            state={state}
            onDismiss={() => setBannerDismissed(true)}
          />
        )}

        <main className={`flex-1 p-6 lg:p-8 ${bannerOffset} overflow-x-hidden overflow-y-auto`}>
          <Routes>
            <Route path="/"             element={<Overview />}       />
            <Route path="/files"        element={<MonitoredFiles />} />
            <Route path="/events"       element={<EventStream />}    />
            <Route path="/ledger"       element={<MicroLedger />}    />
            <Route path="/verification" element={<Verification />}   />
            <Route path="/alerts"       element={<Alerts />}         />
            <Route path="/export"       element={<EvidenceExport />} />
            <Route path="/audit"        element={<UserAudit />}      />
            <Route path="/settings"     element={<Settings />}       />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  )
}
