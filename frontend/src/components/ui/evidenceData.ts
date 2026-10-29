import type { Evidence } from '../../lib/types'

export const EVIDENCE_COPY: Record<Evidence, { label: string; meaning: string }> = {
  recorded: { label: 'Recorded', meaning: 'Written to Cygnus demo history; not an external confirmation.' },
  confirmed: { label: 'Confirmed', meaning: 'Backed by an external record.' },
  pending: { label: 'Pending', meaning: 'Requested, waiting for the other side to respond.' },
  unverified: { label: 'Unverified', meaning: 'Reported, but Cygnus has not seen proof yet.' },
  failed: { label: 'Failed', meaning: 'An action did not go through. Cygnus retries or tells you.' },
  not_started: { label: 'Not started', meaning: 'This step has not begun.' },
}