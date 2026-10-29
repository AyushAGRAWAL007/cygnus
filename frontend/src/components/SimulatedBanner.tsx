import { FlaskConical } from 'lucide-react'

/** Shown wherever retailer data is not real. Honesty is a product feature. */
export default function SimulatedBanner() {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <FlaskConical size={18} className="mt-0.5 shrink-0" />
      <p>
        <strong>Simulated demo.</strong> Cygnus runs against a simulated shopping platform. No real
        order, pickup, or refund is created, and every simulated action is labelled as such.
      </p>
    </div>
  )
}
