from fastapi import APIRouter, Depends, HTTPException

from app.db.repository import Repository
from app.deps import get_repo
from app.models.people import Patient, Physician, Specialist

router = APIRouter(tags=["directory"])


@router.get("/physicians", response_model=list[Physician])
async def list_physicians(repo: Repository = Depends(get_repo)):
    return await repo.physicians()


@router.get("/patients", response_model=list[Patient])
async def list_patients(repo: Repository = Depends(get_repo)):
    return await repo.patients()


@router.get("/patients/{patient_id}", response_model=Patient)
async def get_patient(patient_id: str, repo: Repository = Depends(get_repo)):
    patient = await repo.patient(patient_id)
    if patient is None:
        raise HTTPException(404, "Patient not found")
    return patient


@router.get("/specialists", response_model=list[Specialist])
async def list_specialists(repo: Repository = Depends(get_repo)):
    return await repo.specialists()


@router.get("/specialists/{specialist_id}", response_model=Specialist)
async def get_specialist(specialist_id: str, repo: Repository = Depends(get_repo)):
    specialist = await repo.specialist(specialist_id)
    if specialist is None:
        raise HTTPException(404, "Specialist not found")
    return specialist
