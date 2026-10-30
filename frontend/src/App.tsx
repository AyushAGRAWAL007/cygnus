import Analytics from './pages/Analytics'
import Retailers from './pages/Retailers'
import OrderDetail from './pages/OrderDetail'
import { useEffect, useMemo } from 'react'
import AppShell from './components/AppShell'
import { parseRoute, sectionOf, useHash } from './lib/router'
import Activity from './pages/Activity'
import Auth from './pages/Auth'
import { useAuth } from './lib/authContext'
import { ErrorState, Loading } from './components/ui/Kit'
import Landing from './pages/Landing'
import Orders from './pages/Orders'
import Overview from './pages/Overview'
import Reschedule from './pages/Reschedule'
import ReturnDetail from './pages/ReturnDetail'
import Returns from './pages/Returns'

export default function App() {
  const auth = useAuth()
  const hash = useHash()
  const route = useMemo(() => parseRoute(hash), [hash])

  useEffect(() => {
    if (hash.startsWith('#/')) window.scrollTo({ top: 0 })
  }, [hash])

  if (route.name === 'login' || route.name === 'register') return <Auth key={route.name} mode={route.name} />

  const section = sectionOf(route)
  if (route.name === 'home' || !section) return <Landing key={auth.user?.id ?? 'public'} />
  if (auth.loading) return <div className="mx-auto max-w-lg px-5 py-20"><Loading label="Checking your session" /></div>
  if (!auth.user && auth.error) return <div className="mx-auto max-w-lg px-5 py-20"><ErrorState message={auth.error} onRetry={() => void auth.refresh()} /></div>
  if (!auth.user) return <Auth mode="login" />

  return (
    <AppShell key={auth.user.id} section={section}>
      {route.name === 'overview' && <Overview />}
      {route.name === 'returns' && <Returns />}
      {route.name === 'return' && <ReturnDetail id={route.id} />}
      {route.name === 'reschedule' && <Reschedule id={route.id} />}
      {route.name === 'activity' && <Activity />}
      {route.name === 'orders' && <Orders />}
      {route.name === 'order' && <OrderDetail key={route.id} id={route.id} />}
      {route.name === 'analytics' && <Analytics />}
      {route.name === 'retailers' && <Retailers />}
    </AppShell>
  )
}
