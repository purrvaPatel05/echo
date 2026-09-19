import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { CaseCreate } from '@/api/client'
import { useCases, useCreateCase } from '@/api/hooks'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input, Select, Textarea } from '@/components/ui/input'

const empty: CaseCreate = { title: '', patient_age: 50, patient_sex: 'F', urgency: 'routine', notes: '' }

export default function CasesPage() {
  const { data: cases, isLoading } = useCases()
  const create = useCreateCase()
  const [form, setForm] = useState<CaseCreate>(empty)
  const set = <K extends keyof CaseCreate>(k: K, v: CaseCreate[K]) => setForm((f) => ({ ...f, [k]: v }))

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_20rem]">
      <section className="space-y-3">
        <h1 className="text-xl font-semibold">Cases</h1>
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {cases?.map((c) => (
          <Link key={c.id} to={`/cases/${c.id}`} className="block">
            <Card className="transition-shadow hover:shadow-md">
              <CardHeader>
                <div className="flex items-center justify-between gap-2">
                  <CardTitle>{c.title}</CardTitle>
                  <Badge variant={c.urgency === 'routine' ? 'secondary' : 'warning'}>{c.urgency}</Badge>
                </div>
                <CardDescription className="line-clamp-2">{c.notes}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </section>

      <Card className="h-fit">
        <CardHeader>
          <CardTitle>New case</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              create.mutate(form, { onSuccess: () => setForm(empty) })
            }}
          >
            <Input required placeholder="Title" value={form.title} onChange={(e) => set('title', e.target.value)} />
            <div className="flex gap-2">
              <Input
                type="number"
                min={0}
                value={form.patient_age}
                onChange={(e) => set('patient_age', Number(e.target.value))}
              />
              <Select value={form.patient_sex} onChange={(e) => set('patient_sex', e.target.value as CaseCreate['patient_sex'])}>
                <option>F</option>
                <option>M</option>
                <option>X</option>
              </Select>
            </div>
            <Select value={form.urgency} onChange={(e) => set('urgency', e.target.value as CaseCreate['urgency'])}>
              <option value="routine">Routine</option>
              <option value="urgent">Urgent</option>
              <option value="emergent">Emergent</option>
            </Select>
            <Textarea required placeholder="Clinical notes…" value={form.notes} onChange={(e) => set('notes', e.target.value)} />
            <Button type="submit" className="w-full" disabled={create.isPending}>
              Create case
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
