"""Compatibility layer: serves the `/api/echo/*` contract the ECHO frontend is built against
(docs/echo-api-contract-changes.md) on top of the core domain (referrals, match runs, slots,
consult threads). It adds no second source of truth: everything the core already knows is read
from it. The little the core has no place for (the referral form's reason/specialty/distance,
patient sex and city, the patient's confirmation) lives in the two `echo_*` tables.
"""
