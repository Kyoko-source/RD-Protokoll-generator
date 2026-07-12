import secrets
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fpdf import FPDF
from pydantic import BaseModel

from backend.security import expires_at, is_expired, new_token, password_hash, verify_password
from storage import (
    anonymize_finished_case,
    delete_finished_case,
    encrypt_existing_patient_data,
    encryption_status,
    get_finished_case,
    get_app_setting,
    init_database,
    list_audit_events,
    list_finished_cases,
    load_case_draft_store,
    load_employee_store,
    save_case_draft_store,
    save_employee_store,
    save_finished_case,
    set_app_setting,
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


class ProtocolRequest(BaseModel):
    patient: dict


class PrintAuditRequest(BaseModel):
    case_id: str | None = None
    source: str = "draft"


class EmployeeCreateRequest(BaseModel):
    name: str
    role: str = "employee"


class EmployeeUpdateRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    active: bool | None = None
    reset_password: bool = False


class RetentionRequest(BaseModel):
    retention_days: int = 3650


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
        "uebergabe": {},
    }


def valid(value):
    return value not in [None, "", [], {}, "Keine Angabe"]


def add_lines(title, rows):
    documented = [(label, value) for label, value in rows if valid(value)]
    if not documented:
        return ""
    text = f"{title}\n" + ("=" * 50) + "\n"
    for label, value in documented:
        text += f"{label}: {value}\n"
    return text + "\n"


def build_case_summary(patient):
    vital = patient.get("vitalwerte", {})
    amls = patient.get("amls", {})
    samplers = patient.get("samplers", {})
    parts = []
    if valid(vital.get("alter")):
        parts.append(f"{vital.get('alter')} J.")
    if valid(vital.get("geschlecht")):
        parts.append(str(vital.get("geschlecht")))
    if valid(amls.get("arbeitsdiagnose")):
        parts.append(str(amls.get("arbeitsdiagnose")))
    if valid(vital.get("kurzbericht")):
        parts.append(str(vital.get("kurzbericht"))[:80])
    elif valid(samplers.get("symptome")):
        parts.append(str(samplers.get("symptome"))[:80])
    return " · ".join(parts) if parts else "Einsatz ohne Kurzangaben"


def generate_protocol_text(patient):
    vital = patient.get("vitalwerte", {})
    x = patient.get("xabcde", {})
    s = patient.get("samplers", {})
    o = patient.get("opqrst", {})
    measures = patient.get("massnahmen", {})
    handover = patient.get("uebergabe", {})
    amls = patient.get("amls", {})

    text = "NANA RETTUNGSDIENST-PROTOKOLL\n"
    text += "=" * 50 + "\n"
    text += f"Erstellt am {datetime.now().strftime('%d.%m.%Y um %H:%M:%S')} Uhr\n"
    text += "Dokumentationsentwurf: vor Weitergabe fachlich pruefen.\n\n"

    text += add_lines("VITALWERTE & DEMOGRAPHIE", [
        ("Alter", vital.get("alter")),
        ("Geschlecht", vital.get("geschlecht")),
        ("RR", f"{vital.get('rr_sys', '')}/{vital.get('rr_dia', '')} mmHg" if valid(vital.get("rr_sys")) or valid(vital.get("rr_dia")) else ""),
        ("Puls", vital.get("puls")),
        ("SpO2", vital.get("spo2")),
        ("Atemfrequenz", vital.get("af")),
        ("BZ", vital.get("bz")),
        ("Temperatur", vital.get("temperatur")),
        ("GCS", vital.get("gcs")),
        ("Kurzbericht", vital.get("kurzbericht")),
    ])
    text += add_lines("xABCDE", [
        ("X Blutung", x.get("blutung")),
        ("Blutung Lokalisation", x.get("blutung_lokalisation")),
        ("A Atemweg", x.get("atemweg")),
        ("HWS", x.get("hws")),
        ("B Atmung", x.get("atmung")),
        ("Atemgeraeusche", x.get("atemgeraeusche")),
        ("Sauerstoff", x.get("sauerstoff")),
        ("C Hautzeichen", x.get("haut")),
        ("Rekap", x.get("rekap")),
        ("Pulsqualitaet", x.get("pulsqualitaet")),
        ("D AVPU", x.get("avpu")),
        ("Pupillen", x.get("pupillen")),
        ("E Bodycheck", x.get("bodycheck")),
        ("Bodycheck Auffaelligkeiten", x.get("bodycheck_text")),
    ])
    text += add_lines("SAMPLERS", [
        ("Symptome", s.get("symptome")),
        ("Allergien", s.get("allergien")),
        ("Medikamente", s.get("medikamente")),
        ("Vorgeschichte", s.get("vorgeschichte")),
        ("Letzte orale Aufnahme", s.get("letzte_aufnahme")),
        ("Ereignis", s.get("ereignis")),
        ("Risikofaktoren", s.get("risikofaktoren")),
        ("Sonstiges", s.get("sonstiges")),
    ])
    text += add_lines("OPQRST", [
        ("Onset / Beginn", o.get("onset")),
        ("Provocation / Palliation", o.get("provocation")),
        ("Quality", o.get("quality")),
        ("Region / Radiation", o.get("region")),
        ("Severity / NRS", o.get("severity")),
        ("Time / Verlauf", o.get("time")),
    ])
    text += add_lines("VERDACHT & UEBERGABE", [
        ("Arbeitsdiagnose", amls.get("arbeitsdiagnose")),
        ("Uebergabe Ziel", handover.get("ziel")),
        ("Uebergabe Text", handover.get("text")),
    ])

    timeline = measures.get("timeline", [])
    if isinstance(timeline, list) and timeline:
        text += "MASSNAHMEN\n" + ("=" * 50) + "\n"
        for item in timeline:
            if isinstance(item, dict):
                text += f"{item.get('zeit', '')} - {item.get('massnahme', '')}\n"
            elif valid(item):
                text += f"{item}\n"
        text += "\n"

    medication = measures.get("medikation", [])
    if isinstance(medication, list) and medication:
        text += "MEDIKATION\n" + ("=" * 50) + "\n"
        for item in medication:
            if isinstance(item, dict):
                text += f"{item.get('zeit', '')} - {item.get('medikament', '')} {item.get('dosis', '')} {item.get('weg', '')}\n"
            elif valid(item):
                text += f"{item}\n"
        text += "\n"

    return text.strip()


def pdf_safe(value):
    replacements = {
        "ä": "ae", "ö": "oe", "ü": "ue",
        "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
        "ß": "ss", "·": "-", "–": "-", "—": "-",
        "’": "'", "“": '"', "”": '"',
    }
    text = str(value or "")
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text.encode("latin-1", "replace").decode("latin-1")


def write_pdf_line(pdf, line, height=5):
    safe_line = pdf_safe(line)
    if not safe_line.strip():
        pdf.ln(height)
        return
    max_chars = 92
    while safe_line:
        part = safe_line[:max_chars]
        safe_line = safe_line[max_chars:]
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, height, part)


def build_pdf_bytes(title, protocol_text, metadata=None):
    metadata = metadata or {}
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_fill_color(8, 20, 38)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, pdf_safe("NANA Rettungsdienst-Protokoll"), ln=True, fill=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 7, pdf_safe("Notfall-Aufzeichnungs- und Nachbearbeitungs-Assistent"), ln=True, fill=True)

    pdf.ln(5)
    pdf.set_text_color(20, 31, 48)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, pdf_safe(title), ln=True)
    pdf.set_font("Helvetica", "", 9)
    for label, value in metadata.items():
        if valid(value):
            pdf.cell(0, 6, pdf_safe(f"{label}: {value}"), ln=True)

    pdf.ln(4)
    pdf.set_font("Courier", "", 9)
    for line in str(protocol_text or "").splitlines():
        write_pdf_line(pdf, line)

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(
        0,
        5,
        pdf_safe("Hinweis: Dokumentationsentwurf. Vor medizinischer, rechtlicher oder abrechnungsrelevanter Weitergabe fachlich pruefen."),
    )
    data = pdf.output(dest="S")
    if isinstance(data, str):
        return data.encode("latin-1")
    return bytes(data)


def pdf_response(filename, pdf_bytes):
    safe_filename = "".join(char for char in filename if char.isalnum() or char in ["-", "_", "."])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


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


def admin_employee(employee):
    public = public_employee(employee)
    public.update({
        "active": bool(employee.get("active", True)),
        "created_at": employee.get("created_at", ""),
        "password_changed_at": employee.get("password_changed_at", ""),
    })
    return public


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
    encrypt_existing_patient_data()


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


@app.post("/api/protocol/preview")
def protocol_preview(payload: ProtocolRequest, employee=Depends(current_employee)):
    protocol_text = generate_protocol_text(payload.patient)
    audit("api_protocol_generated", employee=employee, entity_type="case_draft")
    return {"protocol_text": protocol_text, "summary": build_case_summary(payload.patient)}


@app.post("/api/protocol/pdf")
def protocol_pdf(payload: ProtocolRequest, employee=Depends(current_employee)):
    protocol_text = generate_protocol_text(payload.patient)
    summary = build_case_summary(payload.patient)
    created_at = datetime.now().isoformat(timespec="seconds")
    pdf_bytes = build_pdf_bytes(
        "Laufender Einsatz",
        protocol_text,
        {
            "Exportiert am": created_at,
            "Mitarbeiter": employee.get("name", ""),
            "Zusammenfassung": summary,
            "Quelle": "laufender Entwurf",
        },
    )
    audit(
        "api_protocol_pdf_exported",
        employee=employee,
        entity_type="case_draft",
        details={"summary": summary, "format": "pdf"},
    )
    return pdf_response(f"nana-entwurf-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf", pdf_bytes)


@app.post("/api/cases/finish")
def finish_case(payload: ProtocolRequest, employee=Depends(current_employee)):
    protocol_text = generate_protocol_text(payload.patient)
    completed_at = datetime.now().isoformat(timespec="seconds")
    retention_days = int(get_app_setting("retention_days", 3650) or 3650)
    retention_until = (datetime.now() + timedelta(days=max(1, retention_days))).date().isoformat()
    case_id = secrets.token_hex(10)
    save_finished_case({
        "id": case_id,
        "employee_id": employee.get("id", ""),
        "employee_name": employee.get("name", ""),
        "completed_at": completed_at,
        "summary": build_case_summary(payload.patient),
        "patient": payload.patient,
        "protocol_text": protocol_text,
        "retention_until": retention_until,
    })

    store = load_case_draft_store()
    if employee.get("id") in store.get("drafts", {}):
        store["drafts"].pop(employee.get("id"), None)
        save_case_draft_store(store)

    audit("api_case_finished", employee=employee, entity_type="finished_case", entity_id=case_id)
    return {"status": "finished", "case_id": case_id, "protocol_text": protocol_text}


@app.get("/api/cases/{case_id}/pdf")
def case_pdf(case_id: str, employee=Depends(current_employee)):
    item = get_finished_case(case_id)
    if not item or item.get("status") == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Einsatz nicht gefunden.")
    if item.get("status") == "anonymized":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Anonymisierte Einsätze sind für PDF-Export gesperrt.")
    if employee.get("role") != "admin" and item.get("employee_id") != employee.get("id"):
        audit("api_case_export_denied", employee=employee, entity_type="finished_case", entity_id=case_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nicht freigegeben.")

    pdf_bytes = build_pdf_bytes(
        f"Einsatz {case_id}",
        item.get("protocol_text", ""),
        {
            "Einsatz-ID": case_id,
            "Abgeschlossen am": item.get("completed_at", ""),
            "Mitarbeiter": item.get("employee_name", ""),
            "Zusammenfassung": item.get("summary", ""),
            "Aufbewahrung bis": item.get("retention_until", ""),
        },
    )
    audit(
        "api_case_pdf_exported",
        employee=employee,
        entity_type="finished_case",
        entity_id=case_id,
        details={"format": "pdf", "summary": item.get("summary", "")},
    )
    return pdf_response(f"nana-einsatz-{case_id}.pdf", pdf_bytes)


@app.post("/api/protocol/print-audit")
def print_audit(payload: PrintAuditRequest, employee=Depends(current_employee)):
    entity_type = "finished_case" if payload.case_id else "case_draft"
    entity_id = payload.case_id or ""
    audit(
        "api_protocol_print_started",
        employee=employee,
        entity_type=entity_type,
        entity_id=entity_id,
        details={"source": payload.source},
    )
    return {"status": "logged"}


@app.get("/api/admin/audit")
def audit_log(employee=Depends(require_admin)):
    return {"events": list_audit_events(limit=100)}


@app.get("/api/admin/privacy")
def admin_privacy(employee=Depends(require_admin)):
    return {
        "encryption": encryption_status(),
        "retention_days": int(get_app_setting("retention_days", 3650) or 3650),
        "session_minutes": SESSION_MINUTES,
        "audit_events": len(list_audit_events(limit=500)),
    }


@app.put("/api/admin/privacy")
def update_privacy(payload: RetentionRequest, employee=Depends(require_admin)):
    days = max(1, min(int(payload.retention_days or 3650), 36500))
    set_app_setting("retention_days", days)
    audit("api_privacy_settings_updated", employee=employee, details={"retention_days": days})
    return {"status": "saved", "retention_days": days}


@app.get("/api/admin/employees")
def admin_employees(employee=Depends(require_admin)):
    store = load_employee_store()
    return {"employees": [admin_employee(item) for item in store.get("employees", [])]}


@app.post("/api/admin/employees")
def create_employee(payload: EmployeeCreateRequest, employee=Depends(require_admin)):
    name = payload.name.strip()
    role = payload.role if payload.role in ["employee", "admin"] else "employee"
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name fehlt.")

    store = load_employee_store()
    temp_password = secrets.token_urlsafe(9)
    new_employee = {
        "id": new_token()[:16],
        "name": name,
        "role": role,
        "active": True,
        "password_hash": "",
        "temp_password_hash": password_hash(temp_password),
        "must_change_password": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "password_changed_at": "",
    }
    store.setdefault("employees", []).append(new_employee)
    save_employee_store(store)
    audit(
        "api_employee_created",
        employee=employee,
        entity_type="employee",
        entity_id=new_employee["id"],
        details={"role": role},
    )
    return {"employee": admin_employee(new_employee), "temporary_password": temp_password}


@app.put("/api/admin/employees/{employee_id}")
def update_employee(employee_id: str, payload: EmployeeUpdateRequest, employee=Depends(require_admin)):
    store = load_employee_store()
    target = None
    for item in store.get("employees", []):
        if item.get("id") == employee_id:
            target = item
            break
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mitarbeiter nicht gefunden.")

    if payload.name is not None and payload.name.strip():
        target["name"] = payload.name.strip()
    if payload.role in ["employee", "admin"]:
        target["role"] = payload.role
    if payload.active is not None:
        if target.get("id") == employee.get("id") and payload.active is False:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Eigenes Admin-Profil kann nicht deaktiviert werden.")
        target["active"] = bool(payload.active)

    temp_password = ""
    if payload.reset_password:
        temp_password = secrets.token_urlsafe(9)
        target["password_hash"] = ""
        target["temp_password_hash"] = password_hash(temp_password)
        target["must_change_password"] = True
        target["password_changed_at"] = ""

    save_employee_store(store)
    audit(
        "api_employee_updated",
        employee=employee,
        entity_type="employee",
        entity_id=employee_id,
        details={"reset_password": payload.reset_password},
    )
    response = {"employee": admin_employee(target)}
    if temp_password:
        response["temporary_password"] = temp_password
    return response


@app.post("/api/admin/cases/{case_id}/anonymize")
def admin_anonymize_case(case_id: str, employee=Depends(require_admin)):
    item = get_finished_case(case_id)
    if not item or item.get("status") == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Einsatz nicht gefunden.")
    timestamp = datetime.now().isoformat(timespec="seconds")
    anonymize_finished_case(case_id, timestamp)
    audit("api_case_anonymized", employee=employee, entity_type="finished_case", entity_id=case_id)
    return {"status": "anonymized", "case_id": case_id}


@app.delete("/api/admin/cases/{case_id}")
def admin_delete_case(case_id: str, employee=Depends(require_admin)):
    item = get_finished_case(case_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Einsatz nicht gefunden.")
    timestamp = datetime.now().isoformat(timespec="seconds")
    delete_finished_case(case_id, timestamp)
    audit("api_case_deleted", employee=employee, entity_type="finished_case", entity_id=case_id)
    return {"status": "deleted", "case_id": case_id}
