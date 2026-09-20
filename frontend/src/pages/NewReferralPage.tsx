import { Search } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PatientCombobox } from '@/components/echo/PatientCombobox'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { ChoiceGroup, type ChoiceOption } from '@/components/ui/choice-group'
import { Field } from '@/components/ui/field'
import { Input, Textarea } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { useCreateEchoReferral, useEchoPatients, useReferralOptions } from '@/echo/hooks'
import {
  emptyValues,
  fieldLabels,
  requiredFields,
  toInput,
  validate,
  validateField,
  type FormErrors,
  type NewReferralValues,
  type RequiredField,
} from '@/echo/newReferral'
import type { Patient, Urgency } from '@/echo/types'
import { controlA11y } from '@/lib/control-a11y'

const urgencyOptions: ChoiceOption<Urgency>[] = [
  { value: 'routine', label: 'Routine', description: 'No time pressure' },
  { value: 'soon', label: 'Soon', description: 'Sooner than routine' },
  { value: 'urgent', label: 'Urgent', description: 'Earliest available' },
]

const steps = [
  { title: 'ECHO reviews the case', text: 'Fit, insurance, distance, urgency, availability. Not a diagnosis.' },
  { title: 'You compare matches', text: 'Two or three specialists, with the evidence.' },
  { title: 'You approve', text: 'Nothing is booked until you do.' },
]

/** "specialty, referral reason and case details" -> "Specialty, referral reason and case details" */
function sentence(items: string[]): string {
  const text = items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
  return text.charAt(0).toUpperCase() + text.slice(1)
}

const ids = {
  patientId: 'nr-patient',
  patientLocation: 'nr-location',
  insurance: 'nr-insurance',
  specialty: 'nr-specialty',
  subspecialty: 'nr-subspecialty',
  distance: 'nr-distance',
  reason: 'nr-reason',
  details: 'nr-details',
} as const

export default function NewReferralPage() {
  const navigate = useNavigate()
  const { data: patients } = useEchoPatients()
  const { data: options } = useReferralOptions()
  const create = useCreateEchoReferral()
  const [values, setValues] = useState<NewReferralValues>(emptyValues)
  const [errors, setErrors] = useState<FormErrors>({})

  // Update values, and drop an error as soon as its field becomes valid (errors only appear on submit).
  const update = (patch: Partial<NewReferralValues>) => {
    const next = { ...values, ...patch }
    setValues(next)
    setErrors((prev) => {
      const remaining = { ...prev }
      for (const f of Object.keys(prev) as RequiredField[]) if (!validateField(f, next)) delete remaining[f]
      return remaining
    })
  }

  // Choosing a patient fills location and insurance from their record; both stay editable.
  const selectPatient = (p: Patient) => update({ patientId: p.id, patientLocation: p.location, insurance: p.insurance })

  const subspecialties = options?.specialties.find((s) => s.name === values.specialty)?.subspecialties ?? []
  const insurers = [...new Set([...(options?.insurers ?? []), values.insurance].filter(Boolean))]
  const errorCount = Object.keys(errors).length

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const found = validate(values)
    setErrors(found)
    const first = requiredFields.find((f) => found[f])
    if (first) {
      document.getElementById(ids[first])?.focus()
      return
    }
    create.mutate(toInput(values), { onSuccess: (referral) => navigate(`/referral/${referral.id}/analysis`) })
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <nav aria-label="Breadcrumb">
          <ol className="flex items-center gap-1 text-xs">
            <li>
              <Link to="/" className="text-primary hover:underline">
                Dashboard
              </Link>
            </li>
            <li aria-hidden className="text-muted-foreground">
              /
            </li>
            <li aria-current="page" className="text-muted-foreground">
              New Referral
            </li>
          </ol>
        </nav>
        <h1 className="text-[1.75rem] leading-9 font-semibold">New Referral</h1>
        <p className="text-body-sm text-muted-foreground">You review and approve every match before anything is booked.</p>
      </div>

      {errorCount > 0 && (
        <Alert tone="destructive" title={`${errorCount} ${errorCount === 1 ? 'field needs' : 'fields need'} attention`}>
          {sentence(Object.keys(errors).map((f) => fieldLabels[f as RequiredField]))} {errorCount === 1 ? 'is' : 'are'} required.
        </Alert>
      )}
      {create.isError && (
        <Alert tone="destructive" title="Couldn't create the referral">
          Something went wrong. Your entries are still here, so you can try again.
        </Alert>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_376px]">
        <form noValidate onSubmit={onSubmit} className="overflow-hidden rounded-3xl border bg-card">
          <div className="flex flex-col gap-4 px-6 py-5">
            <section aria-labelledby="sec-patient" className="flex flex-col gap-3">
              <h2 id="sec-patient" className="text-sm font-semibold">
                Patient
              </h2>
              <div className="grid items-start gap-4 md:grid-cols-3">
                <Field id={ids.patientId} label="Patient" error={errors.patientId}>
                  <PatientCombobox
                    patients={patients}
                    value={values.patientId}
                    onSelect={selectPatient}
                    {...controlA11y(ids.patientId, errors.patientId)}
                  />
                </Field>
                <Field id={ids.patientLocation} label="Location" error={errors.patientLocation}>
                  <Input
                    placeholder="City or ZIP code"
                    autoComplete="off"
                    value={values.patientLocation}
                    onChange={(e) => update({ patientLocation: e.target.value })}
                    {...controlA11y(ids.patientLocation, errors.patientLocation)}
                  />
                </Field>
                <Field id={ids.insurance} label="Insurance" error={errors.insurance}>
                  <NativeSelect
                    value={values.insurance}
                    onChange={(e) => update({ insurance: e.target.value })}
                    {...controlA11y(ids.insurance, errors.insurance)}
                  >
                    <option value="">Select insurance</option>
                    {insurers.map((i) => (
                      <option key={i}>{i}</option>
                    ))}
                  </NativeSelect>
                </Field>
              </div>
            </section>

            <hr />

            <section aria-labelledby="sec-referral" className="flex flex-col gap-3">
              <h2 id="sec-referral" className="text-sm font-semibold">
                Referral
              </h2>
              <div className="grid items-start gap-4 md:grid-cols-3">
                <Field id={ids.specialty} label="Specialty" error={errors.specialty}>
                  <NativeSelect
                    value={values.specialty}
                    onChange={(e) => update({ specialty: e.target.value, subspecialty: '' })}
                    {...controlA11y(ids.specialty, errors.specialty)}
                  >
                    <option value="">Select specialty</option>
                    {options?.specialties.map((s) => (
                      <option key={s.name}>{s.name}</option>
                    ))}
                  </NativeSelect>
                </Field>
                <Field id={ids.subspecialty} label="Subspecialty (optional)">
                  <NativeSelect
                    id={ids.subspecialty}
                    value={values.subspecialty}
                    onChange={(e) => update({ subspecialty: e.target.value })}
                  >
                    <option value="">Any subspecialty</option>
                    {subspecialties.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </NativeSelect>
                </Field>
                <Field id={ids.distance} label="Travel distance">
                  <NativeSelect
                    id={ids.distance}
                    value={values.distance}
                    onChange={(e) => update({ distance: e.target.value })}
                  >
                    {(options?.distancesMiles ?? [25]).map((d) => (
                      <option key={d} value={d}>
                        Within {d} miles
                      </option>
                    ))}
                  </NativeSelect>
                </Field>
              </div>
              <ChoiceGroup
                legend="Urgency"
                name="urgency"
                options={urgencyOptions}
                value={values.urgency}
                onChange={(urgency) => update({ urgency })}
              />
            </section>

            <hr />

            <section aria-labelledby="sec-case" className="flex flex-col gap-3">
              <h2 id="sec-case" className="text-sm font-semibold">
                Case details
              </h2>
              <Field id={ids.reason} label="Referral reason" error={errors.reason}>
                <Input
                  placeholder="One-line reason"
                  autoComplete="off"
                  value={values.reason}
                  onChange={(e) => update({ reason: e.target.value })}
                  {...controlA11y(ids.reason, errors.reason)}
                />
              </Field>
              <Field id={ids.details} label="Symptoms and history" error={errors.details}>
                <Textarea
                  className="h-20 min-h-20 resize-y"
                  placeholder="Symptoms, duration, history, findings"
                  value={values.details}
                  onChange={(e) => update({ details: e.target.value })}
                  {...controlA11y(ids.details, errors.details)}
                />
              </Field>
            </section>
          </div>

          <div className="flex justify-end gap-2 border-t bg-canvas px-6 py-4">
            <Button asChild variant="outline">
              <Link to="/">Cancel</Link>
            </Button>
            <Button type="submit" disabled={create.isPending} aria-busy={create.isPending}>
              <Search className="size-4" aria-hidden /> Find Specialist Matches
            </Button>
          </div>
        </form>

        <aside aria-labelledby="next-heading" className="flex flex-col gap-4 rounded-3xl border bg-card p-5">
          <h2 id="next-heading" className="text-sm font-semibold">
            What happens next
          </h2>
          <ol className="flex flex-col gap-4">
            {steps.map((s, i) => (
              <li key={s.title} className="flex items-start gap-3">
                <span
                  aria-hidden
                  className="grid size-6 shrink-0 place-items-center rounded-full border border-primary-border bg-primary-subtle text-xs font-medium text-primary-subtle-foreground"
                >
                  {i + 1}
                </span>
                <div>
                  <div className="text-body-sm font-medium">{s.title}</div>
                  <div className="text-xs text-muted-foreground">{s.text}</div>
                </div>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </div>
  )
}
