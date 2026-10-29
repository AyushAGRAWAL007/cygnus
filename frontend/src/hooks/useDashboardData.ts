import { useEffect, useState } from 'react'
import { fetchActivity, fetchOrders, fetchReturns, type ActivityEvent, type Order, type ReturnCase } from '../lib/api'

type DashboardData = {
  orders: Order[]
  returns: ReturnCase[]
  activity: ActivityEvent[]
}

type State =
  | { phase: 'loading' }
  | { phase: 'ready'; data: DashboardData }
  | { phase: 'error'; message: string }

export function useDashboardData() {
  const [state, setState] = useState<State>({ phase: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      fetchOrders(controller.signal),
      fetchReturns(controller.signal),
      fetchActivity(controller.signal),
    ])
      .then(([orders, returns, activity]) => {
        setState({
          phase: 'ready',
          data: { orders: orders.items, returns: returns.items, activity: activity.items },
        })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setState({
          phase: 'error',
          message: error instanceof Error ? error.message : 'Unknown error',
        })
      })
    return () => controller.abort()
  }, [attempt])

  return {
    state,
    retry: () => {
      setState({ phase: 'loading' })
      setAttempt((value) => value + 1)
    },
  }
}