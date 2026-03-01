from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Patient(BaseModel):
    id: int
    first_name: str
    last_name: str
    dob: str
    mrn: str
    diagnosis: str
    medications: str
    allergies: str
    last_visit: str
    phone: str
    insurance: str
    deleted: bool = False
    deleted_at: Optional[str] = None


class PatientUpdate(BaseModel):
    field: str
    value: str


class AuditAction(BaseModel):
    id: str
    timestamp: str
    action_type: str
    payload: dict
    prev_hash: str
    agent_id: str
    hash: str
    signature: str
    verified: bool = True


class ChainVerification(BaseModel):
    intact: bool
    total_actions: int
    last_verified: Optional[str] = None
    broken_at: Optional[int] = None
    error: Optional[str] = None


class AgentTask(BaseModel):
    task: str
