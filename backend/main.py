from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.security import expires_at, is_expired, new_token, password_hash, verify_password
from storage import (
    get_finished_case,
    init_database,
    list_audit_events,
    list_finished_cases,
    load_case_draft_store,
    load_employee_store,
    save_case_draft_store,
    save_employee_store,
    write_audit_event,
)


SESSION_MINUTES = 30
PASSWORD_CHANGE_MINUTES = 10

sessions = {}
password_change_tokens = {}

app = FastAPI(title="NANA API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    employee_id: str
    password: str


class PasswordChangeRequest(BaseModel):
    token: str
    new_password: str


class FirstAdminRequest(BaseModel):
    name: str
    password: str


class DraftRequest(BaseModel):
    patient: dict


def default_patient_case():
    return {
        "vitalwerte": {},
        "xabcde": {},
        "samplers": {},
        "opqrst": {},
        "einweisung": {},
        "amls": {"excluded": [], "custom_candidates": [], "arbeitsdiagnose": ""},
        "massnahmen": {"timeline": [], "medikation": []},
        "transport": {},
        "einsatz": {},
    }


def audit(action, employee=None, entity_type="", entity_id="", details=None):
    employee = employee or {}
    write_audit_event({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "employee_id": employee.get("id", ""),
        "employee_name": employee.get("name", ""),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details or {},
    })


def public_employee(employee):
    return {
        "id": employee.get("id", ""),
        "name": employee.get("name", ""),
        "role": employee.get("role", "employee"),
        "must_change_password": bool(employee.get("must_change_password")),
    }


def find_employee(employee_id):
    store = load_employee_store()
    for employee in store.get("employees", []):
        if employee.get("id") == employee_id and employee.get("active", True):
            return employee
    return None


def current_employee(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nicht angemeldet.")

    token = authorization.removeprefix("Bearer ").strip()
    session = sessions.get(token)
    if not session or is_expired(session.get("expires_at")):
        sessions.pop(token, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sitzung abgelaufen.")

    employee = find_employee(session.get("employee_id"))
    if not employee:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Profil nicht gefunden.")

    session["expires_at"] = expires_at(SESSION_MINUTES)
    return employee


def require_admin(employee=Depends(current_employee)):
    if employee.get("role") != "admin":
        audit("api_admin_access_denied", employee=employee)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nur fuer Admins freigegeben.")
    return employee


@app.on_event("startup")
def startup():
    init_database()


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "NANA"}


@app.get("/api/auth/employees")
def employees():
    store = load_employee_store()
    active = [employee for employee in store.get("employees", []) if employee.get("active", True)]
    return {"employees": [public_employee(employee) for employee in active]}


@app.post("/api/auth/login")
def login(payload: LoginRequest):
    employee = find_employee(payload.employee_id)
    if not employee:
        audit("api_login_failed", details={"reason": "unknown_employee"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Anmeldung fehlgeschlagen.")

    if employee.get("must_change_password"):
        if not verify_password(payload.password, employee.get("temp_password_hash")):
            audit("api_login_failed", employee=employee, details={"reason": "wrong_temporary_password"})
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Einmalpasswort ist falsch.")
        change_token = new_token()
        password_change_tokens[change_token] = {
            "employee_id": employee["id"],
            "expires_at": expires_at(PASSWORD_CHANGE_MINUTES),
        }
        audit("api_temporary_password_accepted", employee=employee)
        return {"status": "password_change_required", "token": change_token, "employee": public_employee(employee)}

    if not verify_password(payload.password, employee.get("password_hash")):
        audit("api_login_failed", employee=employee, details={"reason": "wrong_password"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Passwort ist falsch.")

    token = new_token()
    sessions[token] = {"employee_id": employee["id"], "expires_at": expires_at(SESSION_MINUTES)}
    audit("api_login_success", employee=employee, details={"role": employee.get("role", "employee")})
    return {"status": "authenticated", "token": token, "employee": public_employee(employee)}


@app.post("/api/auth/setup-first-admin")
def setup_first_admin(payload: FirstAdminRequest):
    store = load_employee_store()
    if store.get("employees"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Erster Admin existiert bereits.")
    if not payload.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name fehlt.")
    if len(payload.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwort muss mindestens 8 Zeichen haben.")

    employee = {
        "id": new_token()[:16],
        "name": payload.name.strip(),
        "role": "admin",
        "active": True,
        "password_hash": password_hash(payload.password),
        "temp_password_hash": "",
        "must_change_password": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "password_changed_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_employee_store({"employees": [employee]})

    token = new_token()
    sessions[token] = {"employee_id": employee["id"], "expires_at": expires_at(SESSION_MINUTES)}
    audit("api_first_admin_created", employee=employee)
    audit("api_login_success", employee=employee, details={"role": "admin"})
    return {"status": "authenticated", "token": token, "employee": public_employee(employee)}


@app.post("/api/auth/set-password")
def set_password(payload: PasswordChangeRequest):
    pending = password_change_tokens.get(payload.token)
    if not pending or is_expired(pending.get("expires_at")):
        password_change_tokens.pop(payload.token, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Passwortwechsel ist abgelaufen.")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwort muss mindestens 8 Zeichen haben.")

    store = load_employee_store()
    employee = None
    for item in store.get("employees", []):
        if item.get("id") == pending["employee_id"]:
            employee = item
            break
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profil nicht gefunden.")

    employee["password_hash"] = password_hash(payload.new_password)
    employee["temp_password_hash"] = ""
    employee["must_change_password"] = False
    employee["password_changed_at"] = datetime.now().isoformat(timespec="seconds")
    save_employee_store(store)
    password_change_tokens.pop(payload.token, None)

    token = new_token()
    sessions[token] = {"employee_id": employee["id"], "expires_at": expires_at(SESSION_MINUTES)}
    audit("api_initial_password_set", employee=employee)
    audit("api_login_success", employee=employee, details={"role": employee.get("role", "employee")})
    return {"status": "authenticated", "token": token, "employee": public_employee(employee)}


@app.post("/api/auth/logout")
def logout(employee=Depends(current_employee), authorization: str | None = Header(default=None)):
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    sessions.pop(token, None)
    audit("api_logout", employee=employee)
    return {"status": "ok"}


@app.get("/api/me")
def me(employee=Depends(current_employee)):
    return {"employee": public_employee(employee)}


@app.get("/api/dashboard")
def dashboard(employee=Depends(current_employee)):
    tiles = [
        {"id": "protocol", "label": "Protokoll", "subtitle": "Einsatz dokumentieren"},
        {"id": "hospital", "label": "Krankenhaus Finder", "subtitle": "Geeignete Zielklinik"},
        {"id": "icd10", "label": "ICD10 Code", "subtitle": "Code dekodieren"},
        {"id": "devices", "label": "Geraete", "subtitle": "Kurzreferenzen"},
    ]
    if employee.get("role") == "admin":
        tiles.append({"id": "interfaces", "label": "Schnittstellen", "subtitle": "Import und Export"})
        tiles.append({"id": "admin", "label": "Admin", "subtitle": "Sicherheit und Verwaltung"})
    return {"employee": public_employee(employee), "tiles": tiles}


@app.get("/api/cases")
def cases(employee=Depends(current_employee)):
    employee_id = None if employee.get("role") == "admin" else employee.get("id")
    return {"cases": list_finished_cases(employee_id=employee_id, limit=100)}


@app.get("/api/cases/{case_id}")
def case_detail(case_id: str, employee=Depends(current_employee)):
    item = get_finished_case(case_id)
    if not item or item.get("status") == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Einsatz nicht gefunden.")
    if employee.get("role") != "admin" and item.get("employee_id") != employee.get("id"):
        audit("api_case_access_denied", employee=employee, entity_type="finished_case", entity_id=case_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nicht freigegeben.")
    return {"case": item}


@app.get("/api/draft")
def get_draft(employee=Depends(current_employee)):
    store = load_case_draft_store()
    draft = store.get("drafts", {}).get(employee["id"], {})
    patient = default_patient_case()
    if isinstance(draft.get("patient"), dict):
        patient.update(draft["patient"])
    return {"patient": patient, "updated_at": draft.get("updated_at", "")}


@app.put("/api/draft")
def save_draft(payload: DraftRequest, employee=Depends(current_employee)):
    store = load_case_draft_store()
    store.setdefault("drafts", {})[employee["id"]] = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "patient": payload.patient,
        "seite": "❤️ Vitalwerte",
        "visited_pages": ["❤️ Vitalwerte"],
        "workflow_manual_completion": {},
        "protocol_generated": False,
        "generated_protocol_text": "",
        "xabcde_selected": "A",
    }
    save_case_draft_store(store)
    audit("api_case_draft_saved", employee=employee, entity_type="case_draft")
    return {"status": "saved", "updated_at": store["drafts"][employee["id"]]["updated_at"]}


@app.get("/api/admin/audit")
def audit_log(employee=Depends(require_admin)):
    return {"events": list_audit_events(limit=100)}
