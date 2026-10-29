import { useEffect, useMemo } from 'react'
import AppShell from './components/AppShell'
import { parseRoute, sectionOf, useHash } from './lib/router'
import Activity from './pages/Activity'
import Landing from './pages/Landing'
import Orders from './pages/Orders'
import Overview from './pages/Overview'
import Reschedule from './pages/Reschedule'
import ReturnDetail from './pages/ReturnDetail'
import Returns from './pages/Returns'

export default function App() {
  const hash = useHash()
  const route = useMemo(() => parseRoute(hash), [hash])

  useEffect(() => {
    if (hash.startsWith('#/')) window.scrollTo({ top: 0 })
  }, [hash])

  const section = sectionOf(route)
  if (route.name === 'home' || !section) return <Landing />

  return (
    <AppShell section={section}>
      {route.name === 'overview' && <Overview />}
      {route.name === 'returns' && <Returns />}
      {route.name === 'return' && <ReturnDetail id={route.id} />}
      {route.name === 'reschedule' && <Reschedule id={route.id} />}
      {route.name === 'activity' && <Activity />}
      {route.name === 'orders' && <Orders />}
    </AppShell>
  )
}
