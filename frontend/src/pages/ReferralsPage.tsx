import { useBook, useCases, useReferrals, useSlots, useSpecialists } from '@/api/hooks'
import type { Referral } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const statusVariant = {
  pending: 'warning',
  accepted: 'success',
  scheduled: 'default',
  declined: 'destructive',
} as const

function SlotPicker({ referral }: { referral: Referral }) {
  const { data: slots } = useSlots(referral.specialist_id)
  const book = useBook()
  return (
    <div className="flex flex-wrap gap-2 pt-2">
      {slots?.map((s) => (
        <Button
          key={s.id}
          size="sm"
          variant="outline"
          disabled={book.isPending}
          onClick={() => book.mutate({ referralId: referral.id, slotId: s.id })}
        >
          {new Date(s.starts_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
        </Button>
      ))}
      {slots?.length === 0 && <span className="text-sm text-muted-foreground">No open slots.</span>}
    </div>
  )
}

export default function ReferralsPage() {
  const { data: referrals } = useReferrals()
  const { data: specialists } = useSpecialists()
  const { data: cases } = useCases()

  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Referrals</h1>
      <p className="text-sm text-muted-foreground">Status updates arrive live over Socket.IO.</p>
      {referrals?.length === 0 && <p className="text-sm text-muted-foreground">No referrals yet — refer a case first.</p>}
      {referrals?.map((r) => {
        const spec = specialists?.find((s) => s.id === r.specialist_id)
        const c = cases?.find((x) => x.id === r.case_id)
        return (
          <Card key={r.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{spec?.name ?? r.specialist_id}</CardTitle>
                <Badge variant={statusVariant[r.status]}>{r.status}</Badge>
              </div>
              <CardDescription>{c?.title ?? r.case_id}</CardDescription>
            </CardHeader>
            <CardContent>
              {r.status === 'accepted' && (
                <>
                  <p className="text-sm">Accepted — pick an appointment:</p>
                  <SlotPicker referral={r} />
                </>
              )}
              {r.status === 'scheduled' && (
                <p className="text-sm text-muted-foreground">Appointment booked ({r.appointment_slot_id}).</p>
              )}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
