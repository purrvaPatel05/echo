from pydantic import BaseModel


class GeoPoint(BaseModel):
    lat: float
    lng: float


class InsurancePlan(BaseModel):
    payer: str
    plan_name: str


class Patient(BaseModel):
    """Synthetic patient. Never put real PHI here."""

    id: str
    display_name: str
    age: int
    zip_code: str
    location: GeoPoint
    insurance: InsurancePlan


class Specialist(BaseModel):
    id: str
    name: str
    specialty: str
    subspecialties: list[str]
    practice_name: str
    address: str
    location: GeoPoint


class Physician(BaseModel):
    """A referring physician (synthetic). Stands in for the authenticated user until auth lands."""

    id: str
    name: str
    specialty: str
    practice_name: str
