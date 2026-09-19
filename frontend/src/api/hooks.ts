import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'

export const useMe = () => useQuery({ queryKey: ['me'], queryFn: api.me })
export const useSpecialists = () => useQuery({ queryKey: ['specialists'], queryFn: api.specialists })
export const useSlots = (specialistId: string, enabled = true) =>
  useQuery({ queryKey: ['slots', specialistId], queryFn: () => api.slots(specialistId), enabled })
export const useCases = () => useQuery({ queryKey: ['cases'], queryFn: api.cases })
export const useCase = (id: string) => useQuery({ queryKey: ['case', id], queryFn: () => api.case(id) })
// Matching is a POST but idempotent. In production it becomes a Celery job:
// swap this for a job-status query with `refetchInterval` until it's done.
export const useMatch = (id: string) => useQuery({ queryKey: ['match', id], queryFn: () => api.match(id) })
export const useReferrals = () => useQuery({ queryKey: ['referrals'], queryFn: api.referrals })
export const useConsults = () => useQuery({ queryKey: ['consults'], queryFn: api.consults })
export const useMessages = (consultId: string) =>
  useQuery({ queryKey: ['messages', consultId], queryFn: () => api.messages(consultId) })

export function useCreateCase() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.createCase,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cases'] }),
  })
}

export function useCreateReferral() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.createReferral,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['referrals'] }),
  })
}

export function useBook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ referralId, slotId }: { referralId: string; slotId: string }) => api.book(referralId, slotId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['referrals'] })
      qc.invalidateQueries({ queryKey: ['slots'] })
    },
  })
}
