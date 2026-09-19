import { ExternalLink, MapPin } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useCase, useCreateReferral, useMatch, useReferrals } from '@/api/hooks'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default function CaseDetailPage() {
  const { caseId = '' } = useParams()
  const navigate = useNavigate()
  const { data: c } = useCase(caseId)
  const { data: match, isLoading: matching } = useMatch(caseId)
  const { data: referrals } = useReferrals()
  const refer = useCreateReferral()

  if (!c) return <p className="text-sm text-muted-foreground">Loading…</p>

  return (
    <div className="space-y-6">
      <Link to="/" className="text-sm text-muted-foreground hover:underline">
        ← Cases
      </Link>
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{c.title}</CardTitle>
          <CardDescription>
            {c.patient_age}y {c.patient_sex} · {c.urgency}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm">{c.notes}</p>
          {match && (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted-foreground">Parsed:</span>
              <Badge variant="default">{match.parsed.specialty}</Badge>
              <Badge>{match.parsed.condition}</Badge>
              {match.parsed.keywords.map((k) => (
                <Badge key={k} variant="secondary">
                  {k}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <section className="space-y-3">
        <h2 className="font-semibold">Recommended specialists</h2>
        {matching && <p className="text-sm text-muted-foreground">Matching…</p>}
        {match?.specialists.length === 0 && (
          <p className="text-sm text-muted-foreground">No specialists passed the clinical guardrails.</p>
        )}
        {match?.specialists.map((m) => {
          const already = referrals?.some((r) => r.case_id === c.id && r.specialist_id === m.specialist.id)
          return (
            <Card key={m.specialist.id}>
              <CardContent className="flex items-center justify-between gap-4 pt-5">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 font-medium">
                    {m.specialist.name}
                    <Badge variant="success">{Math.round(m.score * 100)}% fit</Badge>
                  </div>
                  <div className="flex items-center gap-1 text-sm text-muted-foreground">
                    <MapPin className="size-3.5" />
                    {m.specialist.hospital}, {m.specialist.city} · {m.distance_km} km
                  </div>
                  <p className="text-sm">{m.rationale}</p>
                  {m.next_slot && (
                    <p className="text-xs text-muted-foreground">
                      Next opening: {new Date(m.next_slot.starts_at).toLocaleString()}
                    </p>
                  )}
                </div>
                <Button
                  disabled={already || refer.isPending}
                  onClick={() =>
                    refer.mutate(
                      { case_id: c.id, specialist_id: m.specialist.id, note: '' },
                      { onSuccess: () => navigate('/referrals') },
                    )
                  }
                >
                  {already ? 'Referred' : 'Refer'}
                </Button>
              </CardContent>
            </Card>
          )
        })}
      </section>

      {!!match?.trials.length && (
        <section className="space-y-3">
          <h2 className="font-semibold">Potential clinical trials</h2>
          {match.trials.map((t) => (
            <Card key={t.nct_id}>
              <CardContent className="flex items-center justify-between gap-4 pt-5">
                <div>
                  <div className="font-medium">{t.title}</div>
                  <div className="text-sm text-muted-foreground">
                    {t.nct_id} · {t.phase} · {t.location}
                  </div>
                </div>
                <Button variant="outline" size="sm" asChild>
                  <a href={t.url} target="_blank" rel="noreferrer">
                    View <ExternalLink className="size-3.5" />
                  </a>
                </Button>
              </CardContent>
            </Card>
          ))}
        </section>
      )}
    </div>
  )
}
