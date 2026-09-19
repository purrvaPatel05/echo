import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { io } from 'socket.io-client'
import type { Referral } from './client'

// Same-origin; Vite proxies /socket.io to the FastAPI server in dev.
export const socket = io({ path: '/socket.io' })

/** Push live referral status changes into the TanStack Query cache. Mount once. */
export function useReferralRealtime() {
  const qc = useQueryClient()
  useEffect(() => {
    const onUpdate = (updated: Referral) => {
      qc.setQueryData<Referral[]>(['referrals'], (old) =>
        old ? old.map((r) => (r.id === updated.id ? updated : r)) : old,
      )
      qc.invalidateQueries({ queryKey: ['slots'] })
    }
    socket.on('referral:update', onUpdate)
    return () => {
      socket.off('referral:update', onUpdate)
    }
  }, [qc])
}
