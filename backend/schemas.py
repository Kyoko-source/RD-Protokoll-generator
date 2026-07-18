from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    employee_id: str
    password: str
    device_id: str = ""
    device_name: str = ""
    user_agent: str = ""


class ReauthRequest(LoginRequest):
    restore_shift: bool = True


class PasswordChangeRequest(BaseModel):
    token: str
    new_password: str
    device_id: str = ""
    device_name: str = ""
    user_agent: str = ""


class FirstAdminRequest(BaseModel):
    name: str
    password: str
    device_id: str = ""
    device_name: str = ""
    user_agent: str = ""


class DraftRequest(BaseModel):
    patient: dict


class ProtocolRequest(BaseModel):
    patient: dict
    force_finish: bool = False


class MedicationCalcRequest(BaseModel):
    sop: str = "Anaphylaxie (SOPKB0105)"
    age: float = 30
    weight: float = 70
    pregnant: str = "Nein"
    inputs: dict = Field(default_factory=dict)


class PrintAuditRequest(BaseModel):
    case_id: str | None = None
    source: str = "draft"


class InterfaceImportRequest(BaseModel):
    source: str = "dispatch"
    payload: str


class IcdLookupRequest(BaseModel):
    code: str


class IcdSearchRequest(BaseModel):
    query: str = ""
    limit: int = 80


class HospitalSaveRequest(BaseModel):
    id: str | None = None
    name: str
    country: str = "DE"
    address: str = ""
    town: str = ""
    phone: str = ""
    categories: list[str] = Field(default_factory=list)
    estimated_minutes: int | None = None
    source: str = ""


class EmployeeCreateRequest(BaseModel):
    name: str
    role: str = "employee"
    qualification: str = ""


class EmployeeUpdateRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    qualification: str | None = None
    active: bool | None = None
    reset_password: bool = False


class AnnouncementItem(BaseModel):
    title: str = ""
    body: str = ""
    published_at: str = ""


class AnnouncementsRequest(BaseModel):
    patch_notes: list[AnnouncementItem] = Field(default_factory=list)
    planned_updates: list[AnnouncementItem] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    kind: str = "Bug"
    title: str = ""
    message: str = ""


class FeedbackUpdateRequest(BaseModel):
    status: str = "offen"
    answer: str = ""


class RetentionRequest(BaseModel):
    retention_days: int = 3650
    security_log_retention_days: int = 180
    external_maps_enabled: bool = False
