/** The chosen appointment slot was taken before booking finished (HTTP 409 from the real API). */
export class SlotUnavailableError extends Error {
  constructor() {
    super('That appointment is no longer available')
    this.name = 'SlotUnavailableError'
  }
}

/** No referral with that id (HTTP 404 from the real API). Distinct from a failed load, which can be retried. */
export class ReferralNotFoundError extends Error {
  constructor() {
    super('Referral not found')
    this.name = 'ReferralNotFoundError'
  }
}

/** No consult with that id (HTTP 404 from the real API). */
export class ConsultNotFoundError extends Error {
  constructor() {
    super('Consult not found')
    this.name = 'ConsultNotFoundError'
  }
}
