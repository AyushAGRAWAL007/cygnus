import { useEffect, useState } from 'react'
import Nav, { type Route } from './components/Nav'
import Dashboard from './pages/Dashboard'
import Landing from './pages/Landing'

// Tiny hash router: "#/dashboard" shows the dashboard. No extra library needed yet.
const read = (): Route => (window.location.hash.startsWith('#/dashboard') ? 'dashboard' : 'home')

export default function App() {
  const [route, setRoute] = useState<Route>(read)
  useEffect(() => {
    const on = () => setRoute(read())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return (
    <>
      <Nav route={route} />
      {route === 'home' ? <Landing /> : <Dashboard />}
      <footer className="mx-auto max-w-6xl px-5 py-8 text-xs text-slate-500">
        Cygnus · Nebius × NVIDIA Global AI Hackathon 2026 · Simulated retailer demo
      </footer>
    </>
  )
}
