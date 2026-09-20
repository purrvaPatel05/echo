import type { Referral, Trial, TrialCriteria, TrialSearchOptions, TrialStatus } from '@/echo/types'

export const DEFAULT_TRIAL_DISTANCE = 100
const SOURCE = 'ClinicalTrials.gov'

type Seed = Omit<Trial, 'url' | 'distanceMiles'> & { distanceMiles: number }
const t = (s: Seed): Trial => ({ ...s, url: `https://clinicaltrials.gov/study/${s.nctId}` })

/** The condition the search uses for a referral: display text, keyed by subspecialty (a mock stand-in for the backend). */
const CONDITIONS: Record<string, string> = {
  Knee: 'Meniscal tear, knee',
  'Heart failure': 'Heart failure, reduced ejection fraction',
  Migraine: 'Migraine with aura',
  'Breast cancer': 'Breast lesion, abnormal screening mammogram',
  Arrhythmia: 'Atrial fibrillation',
  Epilepsy: 'Epilepsy, new-onset seizures',
  Spine: 'Chronic low back pain',
}

/**
 * Sample ClinicalTrials.gov records by subspecialty. `relevance` is one plain factual sentence about the condition;
 * nothing here scores, ranks by fit or says anything about the patient's eligibility.
 */
const CATALOG: Record<string, Trial[]> = {
  Knee: [
    t({ nctId: 'NCT05123456', title: 'Arthroscopic Partial Meniscectomy vs Physical Therapy for Degenerative Meniscal Tear', condition: 'Meniscal tear', intervention: 'Procedure: partial meniscectomy vs. physical therapy', location: 'Roanoke, VA', distanceMiles: 8, status: 'recruiting', relevance: 'Studies meniscal tear, the reported condition.' }),
    t({ nctId: 'NCT04987654', title: 'Rehabilitation Protocols After Meniscal Repair', condition: 'Meniscal injury', intervention: 'Behavioral: structured rehabilitation', location: 'Blacksburg, VA', distanceMiles: 40, status: 'not_yet_recruiting', relevance: 'Studies meniscal injury, a related condition.' }),
    t({ nctId: 'NCT05234567', title: 'Biologic Injection for Knee Osteoarthritis With Meniscal Involvement', condition: 'Knee osteoarthritis', intervention: 'Drug: intra-articular injection', location: 'Charlottesville, VA', distanceMiles: 65, status: 'recruiting', relevance: 'Studies knee osteoarthritis with meniscal involvement.' }),
    t({ nctId: 'NCT04321987', title: 'Bracing and Exercise for Knee Instability After Meniscal Injury', condition: 'Meniscal injury', intervention: 'Device: functional knee brace', location: 'Christiansburg, VA', distanceMiles: 30, status: 'active_not_recruiting', relevance: 'Studies meniscal injury; not currently recruiting.' }),
    t({ nctId: 'NCT04765432', title: 'Long-Term Outcomes After Meniscal Surgery', condition: 'Meniscal tear', intervention: 'Observational: post-surgical follow-up', location: 'Richmond, VA', distanceMiles: 168, status: 'active_not_recruiting', relevance: 'Studies meniscal tear; not currently recruiting.' }),
  ],
  'Heart failure': [
    t({ nctId: 'NCT05310011', title: 'Remote Monitoring to Reduce Readmission in Heart Failure', condition: 'Heart failure', intervention: 'Device: remote monitoring', location: 'Roanoke, VA', distanceMiles: 6, status: 'recruiting', relevance: 'Studies heart failure, the reported condition.' }),
    t({ nctId: 'NCT05122298', title: 'SGLT2 Inhibitor Dosing in Reduced Ejection Fraction', condition: 'Heart failure, reduced ejection fraction', intervention: 'Drug: SGLT2 inhibitor', location: 'Richmond, VA', distanceMiles: 168, status: 'recruiting', relevance: 'Studies reduced ejection fraction, as reported.' }),
    t({ nctId: 'NCT04871230', title: 'Exercise Rehabilitation in Chronic Heart Failure', condition: 'Chronic heart failure', intervention: 'Behavioral: supervised exercise', location: 'Salem, VA', distanceMiles: 12, status: 'active_not_recruiting', relevance: 'Studies chronic heart failure; not currently recruiting.' }),
  ],
  Migraine: [
    t({ nctId: 'NCT05401177', title: 'CGRP Antagonist for Migraine With Aura', condition: 'Migraine with aura', intervention: 'Drug: CGRP receptor antagonist', location: 'Durham, NC', distanceMiles: 180, status: 'recruiting', relevance: 'Studies migraine with aura, the reported condition.' }),
    t({ nctId: 'NCT05288140', title: 'Neuromodulation for Chronic Migraine', condition: 'Chronic migraine', intervention: 'Device: neuromodulation', location: 'Roanoke, VA', distanceMiles: 9, status: 'not_yet_recruiting', relevance: 'Studies chronic migraine, a related condition.' }),
  ],
  'Breast cancer': [
    t({ nctId: 'NCT05199845', title: 'Abbreviated MRI for Dense Breast Screening', condition: 'Dense breast tissue', intervention: 'Procedure: abbreviated breast MRI', location: 'Charlottesville, VA', distanceMiles: 65, status: 'recruiting', relevance: 'Studies breast imaging after an abnormal screening result.' }),
    t({ nctId: 'NCT05077712', title: 'Biopsy Pathways for BI-RADS 4 Lesions', condition: 'Breast lesion', intervention: 'Procedure: image-guided biopsy', location: 'Roanoke, VA', distanceMiles: 7, status: 'not_yet_recruiting', relevance: 'Studies BI-RADS 4 lesions, the reported finding.' }),
  ],
  Arrhythmia: [
    t({ nctId: 'NCT05244460', title: 'Early Rhythm Control in New-Onset Atrial Fibrillation', condition: 'Atrial fibrillation', intervention: 'Drug: antiarrhythmic therapy', location: 'Roanoke, VA', distanceMiles: 8, status: 'recruiting', relevance: 'Studies new-onset atrial fibrillation, the reported condition.' }),
    t({ nctId: 'NCT05011983', title: 'Wearable ECG Detection After a First AF Episode', condition: 'Atrial fibrillation', intervention: 'Device: wearable ECG patch', location: 'Blacksburg, VA', distanceMiles: 40, status: 'recruiting', relevance: 'Studies atrial fibrillation follow-up.' }),
  ],
  Epilepsy: [
    t({ nctId: 'NCT05355021', title: 'First-Line Monotherapy in New-Onset Focal Seizures', condition: 'Focal epilepsy', intervention: 'Drug: antiseizure monotherapy', location: 'Roanoke, VA', distanceMiles: 8, status: 'recruiting', relevance: 'Studies new-onset seizures, the reported condition.' }),
    t({ nctId: 'NCT05140072', title: 'Home EEG Monitoring After a First Seizure', condition: 'Seizure', intervention: 'Device: ambulatory EEG', location: 'Winston-Salem, NC', distanceMiles: 95, status: 'not_yet_recruiting', relevance: 'Studies first seizures, a related condition.' }),
  ],
  Spine: [
    t({ nctId: 'NCT05266190', title: 'Cognitive Functional Therapy for Chronic Low Back Pain', condition: 'Chronic low back pain', intervention: 'Behavioral: cognitive functional therapy', location: 'Roanoke, VA', distanceMiles: 8, status: 'recruiting', relevance: 'Studies chronic low back pain, the reported condition.' }),
    t({ nctId: 'NCT05033814', title: 'Epidural Steroid Injection vs Physical Therapy', condition: 'Lumbar radiculopathy', intervention: 'Drug: epidural steroid injection', location: 'Salem, VA', distanceMiles: 14, status: 'recruiting', relevance: 'Studies lumbar pain with nerve involvement, a related condition.' }),
    t({ nctId: 'NCT04998210', title: 'Long-Term Follow-Up After Lumbar Fusion', condition: 'Degenerative disc disease', intervention: 'Observational: post-surgical follow-up', location: 'Charlottesville, VA', distanceMiles: 65, status: 'active_not_recruiting', relevance: 'Studies degenerative lumbar conditions; not currently recruiting.' }),
  ],
}

const key = (r: Referral) => r.subspecialty || r.specialty
const RECRUITING: TrialStatus[] = ['recruiting', 'not_yet_recruiting']

/** Resolves the options the search really uses: default 100 miles, recruiting or not yet recruiting. */
function resolve(options?: TrialSearchOptions) {
  const distanceMiles = options?.distanceMiles === undefined ? DEFAULT_TRIAL_DISTANCE : options.distanceMiles
  return { distanceMiles, allStatuses: !!options?.allStatuses }
}

export function trialCriteriaFor(r: Referral, options?: TrialSearchOptions): TrialCriteria {
  const { distanceMiles, allStatuses } = resolve(options)
  return {
    condition: CONDITIONS[key(r)] ?? r.reason,
    patient: `${r.patient.age}y ${r.patient.sex}`,
    location: distanceMiles === null ? 'Any location' : `Within ${distanceMiles} miles of ${r.patient.location}`,
    status: allStatuses ? 'Recruiting, not yet recruiting, or active' : 'Recruiting or not yet recruiting',
    source: SOURCE,
    distanceMiles,
    allStatuses,
  }
}

export function searchTrials(r: Referral, options?: TrialSearchOptions): Trial[] {
  const { distanceMiles, allStatuses } = resolve(options)
  return (CATALOG[key(r)] ?? [])
    .filter((x) => distanceMiles === null || (x.distanceMiles ?? Infinity) <= distanceMiles)
    .filter((x) => allStatuses || RECRUITING.includes(x.status))
    .sort((a, b) => (a.distanceMiles ?? Infinity) - (b.distanceMiles ?? Infinity))
}
