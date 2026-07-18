import secrets
import json
import os
import html
import hashlib
import re
import csv
import io
import urllib.error
import urllib.request
from urllib.parse import urlparse
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fpdf import FPDF

from backend.schemas import (
    AnnouncementItem,
    AnnouncementsRequest,
    DraftRequest,
    EmployeeCreateRequest,
    EmployeeImportRequest,
    EmployeeUpdateRequest,
    FeedbackRequest,
    FeedbackUpdateRequest,
    FirstAdminRequest,
    HospitalSaveRequest,
    IcdLookupRequest,
    IcdSearchRequest,
    InterfaceImportRequest,
    LoginRequest,
    MedicationCalcRequest,
    PasswordChangeRequest,
    PrintAuditRequest,
    ProtocolRequest,
    ReauthRequest,
    RetentionRequest,
)
from backend.security import expires_at, is_expired, new_token, password_hash, verify_password
from device_guides import DEVICE_GUIDES
from hospital_finder import CATEGORIES, HOSPITALS, TOWNS, distance_km
from interfaces import build_fhir_bundle, build_nana_case_export, parse_corpuls_import, parse_dispatch_import
from storage import (
    anonymize_finished_case,
    create_employee_record,
    delete_finished_case,
    delete_auth_failure,
    delete_auth_session,
    delete_employee_record,
    delete_expired_finished_cases,
    delete_password_change_token,
    delete_security_events_before,
    database_health_status,
    encrypt_existing_patient_data,
    encryption_status,
    get_auth_failure,
    get_auth_session,
    get_employee,
    get_finished_case,
    get_app_setting,
    get_password_change_token,
    init_database,
    list_audit_events,
    list_expired_finished_cases,
    list_finished_cases,
    list_login_events,
    load_case_draft_store,
    load_employee_store,
    purge_expired_auth_state,
    save_case_draft_store,
    save_auth_failure,
    save_auth_session,
    save_employee_store,
    save_finished_case,
    save_password_change_token,
    set_app_setting,
    update_employee_record,
    write_audit_event,
    write_login_event,
)

APP_TIMEZONE = ZoneInfo(os.getenv("NANA_TIMEZONE", "Europe/Berlin"))


def local_now():
    return datetime.now(APP_TIMEZONE)


SESSION_MINUTES = 30
PASSWORD_CHANGE_MINUTES = 10
MAX_REQUEST_BODY_BYTES = int(os.getenv("NANA_MAX_REQUEST_BODY_BYTES", str(2 * 1024 * 1024)))
AUTH_COOKIE_NAME = "nana_session"
CSRF_COOKIE_NAME = "nana_csrf"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
NANA_ENV = os.getenv("NANA_ENV", "development").strip().lower()
NANA_RELEASE_SHA = os.getenv("NANA_RELEASE_SHA", "local").strip() or "local"
NANA_RELEASE_DATE = os.getenv("NANA_RELEASE_DATE", "").strip()
MEDICAL_RULESET_VERSION = "NANA-SOP-2026.07"


def production_mode():
    return NANA_ENV in {"production", "prod"}


def release_datetime_label():
    if NANA_RELEASE_DATE and NANA_RELEASE_DATE != "unknown":
        try:
            parsed = datetime.fromisoformat(NANA_RELEASE_DATE.replace("Z", "+00:00"))
            return parsed.astimezone(APP_TIMEZONE).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            return NANA_RELEASE_DATE
    return local_now().strftime("%d.%m.%Y %H:%M")


def release_patch_note_draft():
    release_label = NANA_RELEASE_SHA if NANA_RELEASE_SHA not in {"", "local"} else "lokaler Build"
    return {
        "title": f"Update {release_label}",
        "body": "Neue Version wurde auf dem Server bereitgestellt. Bitte die wichtigsten Änderungen ergänzen.",
        "published_at": release_datetime_label(),
    }


def configured_cors_origins():
    configured = os.getenv("NANA_ALLOWED_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    if production_mode():
        return []
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


def configured_allowed_hosts():
    configured = os.getenv("NANA_ALLOWED_HOSTS", "").strip()
    if configured:
        return [host.strip() for host in configured.split(",") if host.strip()]
    hosts = []
    for origin in configured_cors_origins():
        parsed = urlparse(origin)
        if parsed.hostname:
            hosts.append(parsed.hostname)
    return sorted(set(hosts))


def parse_stored_datetime(value):
    if hasattr(value, "isoformat"):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        try:
            return datetime.fromisoformat(raw.replace(" ", "T"))
        except ValueError:
            return None


if production_mode() and not os.getenv("NANA_DATA_KEY", "").strip():
    raise RuntimeError("NANA_DATA_KEY muss im Produktionsbetrieb gesetzt sein.")

AUTH_MAX_FAILURES = 5
AUTH_LOCK_MINUTES = 15
EMPLOYEE_ROLES = {"employee", "admin", "bufdi", "azubi", "praktikant"}
EMPLOYEE_QUALIFICATIONS = {
    "",
    "Rettungshelfer",
    "Rettungssanitäter",
    "Rettungsassistent",
    "Notfallsanitäter",
    "Notarzt",
}
EMPLOYEE_STATIONS = {"", "Gescher", "Südlohn", "Isselburg", "Schöppingen", "Bocholt"}
EMPLOYEE_VEHICLE_SCOPES = {"", "KTW", "RTW", "KTW/RTW"}

app = FastAPI(title="NANA API", version="0.1.0")
allowed_hosts = configured_allowed_hosts()
if production_mode() and allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_cors_origins(),
    allow_origin_regex=None if production_mode() else r"http://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+):5173",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-NANA-CSRF"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_REQUEST_BODY_BYTES:
        return Response(
            content='{"detail":"Anfrage ist zu groß."}',
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            media_type="application/json",
            headers={"Cache-Control": "no-store"},
        )
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
    csp = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "frame-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "manifest-src 'self'; "
        "worker-src 'self'"
    )
    if production_mode():
        csp = f"{csp}; upgrade-insecure-requests"
    response.headers.setdefault(
        "Content-Security-Policy",
        csp,
    )
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Pragma", "no-cache")
    if production_mode():
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def default_patient_case():
    return {
        "patient": {"patientengruppe": "", "alter_wert": "", "alter_einheit": "Jahre", "pat": {}, "paediatrie": {}},
        "vitalwerte": {},
        "xabcde": {},
        "samplers": {},
        "opqrst": {},
        "psyche": {},
        "einweisung": {},
        "amls": {
            "excluded": [],
            "custom_candidates": [],
            "arbeitsdiagnose": "",
            "leitsymptom": "",
            "notizen": "",
        },
        "massnahmen": {"timeline": [], "medikation": []},
        "reanimation": {"shocks": []},
        "transport": {},
        "einsatz": {},
        "anfahrt": {},
        "uebergabe": {},
    }


def valid(value):
    return value not in [None, "", [], {}, "Keine Angabe", "Selber eintragen"]


def clean_text(value, limit=2000):
    text = str(value or "").strip()
    return text[:limit]


PILOT_BLOCKED_IDENTITY_KEYS = {
    "vorname", "nachname", "name", "geburtsdatum", "geburtsort", "strasse", "straße",
    "hausnummer", "plz", "postleitzahl", "wohnort", "adresse", "krankenkasse",
    "versichertennummer", "telefon", "telefonnummer", "email",
}


def sanitize_pilot_patient(patient):
    """Server-side guard: identity data must not be persisted during the pilot."""
    allowed_location_sections = {"einsatz", "anfahrt"}

    def scrub(value, path=()):
        if isinstance(value, dict):
            section = path[0] if path else ""
            return {
                key: scrub(item, (*path, str(key)))
                for key, item in value.items()
                if section in allowed_location_sections or str(key).strip().lower() not in PILOT_BLOCKED_IDENTITY_KEYS
            }
        if isinstance(value, list):
            return [scrub(item, path) for item in value]
        return value

    return scrub(patient if isinstance(patient, dict) else {})


def announcements_store():
    store = get_app_setting("announcements", {})
    if not isinstance(store, dict):
        store = {}
    patch_notes = store.get("patch_notes") if isinstance(store.get("patch_notes"), list) else []
    planned_updates = store.get("planned_updates") if isinstance(store.get("planned_updates"), list) else []
    feedback = store.get("feedback") if isinstance(store.get("feedback"), list) else []
    return {"patch_notes": patch_notes, "planned_updates": planned_updates, "feedback": feedback}


def save_announcements_store(store):
    safe_store = {
        "patch_notes": store.get("patch_notes", []) if isinstance(store, dict) else [],
        "planned_updates": store.get("planned_updates", []) if isinstance(store, dict) else [],
        "feedback": store.get("feedback", []) if isinstance(store, dict) else [],
    }
    set_app_setting("announcements", safe_store)
    return safe_store


def public_announcement_item(item):
    item = item if isinstance(item, dict) else {}
    return {
        "id": clean_text(item.get("id"), 80),
        "title": clean_text(item.get("title"), 160),
        "body": clean_text(item.get("body"), 4000),
        "published_at": clean_text(item.get("published_at"), 80),
    }


def public_feedback_item(item, include_identity=False):
    item = item if isinstance(item, dict) else {}
    result = {
        "id": clean_text(item.get("id"), 80),
        "kind": clean_text(item.get("kind"), 40),
        "title": clean_text(item.get("title"), 160),
        "message": clean_text(item.get("message"), 4000),
        "status": clean_text(item.get("status") or "offen", 40),
        "answer": clean_text(item.get("answer"), 4000),
        "created_at": clean_text(item.get("created_at"), 80),
        "answered_at": clean_text(item.get("answered_at"), 80),
    }
    if include_identity:
        result["employee_id"] = clean_text(item.get("employee_id"), 80)
        result["employee_name"] = clean_text(item.get("employee_name"), 160)
    return result


def add_lines(title, rows):
    documented = [(label, value) for label, value in rows if valid(value)]
    if not documented:
        return ""
    text = f"{title}\n" + ("=" * 50) + "\n"
    for label, value in documented:
        text += f"{label}: {value}\n"
    return text + "\n"


def compact_join(values, separator=", "):
    return separator.join(str(value).strip() for value in values if valid(value))


def normalize_dispatch_coordinates(value):
    if isinstance(value, dict):
        lat = value.get("lat") or value.get("latitude")
        lng = value.get("lng") or value.get("lon") or value.get("longitude")
        if valid(lat) and valid(lng):
            return f"{lat}, {lng}"
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return f"{value[0]}, {value[1]}"
    return clean_text(value, 120)


def approach_from_dispatch(imported):
    imported = imported if isinstance(imported, dict) else {}
    street = clean_text(imported.get("strasse"), 160)
    house_number = clean_text(imported.get("hausnummer"), 40)
    town = clean_text(imported.get("ort"), 120)
    coordinates = normalize_dispatch_coordinates(imported.get("koordinaten"))
    address = clean_text(imported.get("adresse"), 240)
    if not address:
        street_line = compact_join([street, house_number], " ")
        address = compact_join([street_line, town])
    approach = {
        "street": street,
        "house_number": house_number,
        "town": town,
        "coordinates": coordinates,
        "address": address,
        "source": "dispatch",
    }
    return {key: value for key, value in approach.items() if valid(value)}


def patient_with_dispatch(patient, imported):
    patient = patient if isinstance(patient, dict) else default_patient_case()
    imported = imported if isinstance(imported, dict) else {}
    patient["einsatz"] = {**(patient.get("einsatz") or {}), **imported}
    approach = approach_from_dispatch(imported)
    if approach:
        patient["anfahrt"] = {**(patient.get("anfahrt") or {}), **approach}
    return patient, approach


def pending_dispatch_summary(imported):
    imported = imported if isinstance(imported, dict) else {}
    approach = approach_from_dispatch(imported)
    title = compact_join([imported.get("stichwort"), imported.get("meldebild")], " / ")
    location = approach.get("address") or clean_text(imported.get("adresse"), 240) or compact_join([imported.get("strasse"), imported.get("hausnummer"), imported.get("ort")])
    return {
        "title": title or "Neuer Leitstellen-Einsatz",
        "case_number": clean_text(imported.get("einsatznummer"), 80),
        "keyword": clean_text(imported.get("stichwort"), 120),
        "location": location,
        "coordinates": approach.get("coordinates", ""),
        "alarm_time": clean_text(imported.get("alarmzeit"), 120),
        "vehicle": clean_text(imported.get("fahrzeug"), 120),
        "dispatch_center": clean_text(imported.get("leitstelle"), 120),
    }


def load_employee_pending_dispatch(employee):
    store = load_case_draft_store()
    draft = store.get("drafts", {}).get(employee["id"], {})
    pending = draft.get("pending_dispatch") if isinstance(draft, dict) else None
    return pending if isinstance(pending, dict) else None


def save_employee_pending_dispatch(employee, imported, raw_payload=""):
    store = load_case_draft_store()
    draft = store.setdefault("drafts", {}).setdefault(employee["id"], {})
    created_at = local_now().isoformat(timespec="seconds")
    pending = {
        "id": f"dispatch-{employee['id']}-{created_at}",
        "created_at": created_at,
        "imported": imported,
        "raw_payload": clean_text(raw_payload, 8000),
        "summary": pending_dispatch_summary(imported),
    }
    draft["pending_dispatch"] = pending
    draft.setdefault("updated_at", created_at)
    save_case_draft_store(store)
    return pending


def clear_employee_pending_dispatch(employee):
    store = load_case_draft_store()
    draft = store.get("drafts", {}).get(employee["id"], {})
    if isinstance(draft, dict):
        draft.pop("pending_dispatch", None)
        draft["updated_at"] = local_now().isoformat(timespec="seconds")
        save_case_draft_store(store)


def add_paragraph(title, sentences):
    documented = [str(sentence).strip() for sentence in sentences if valid(sentence)]
    if not documented:
        return ""
    return f"{title}\n" + ("=" * 50) + "\n" + " ".join(documented) + "\n\n"


def format_observation(value, status_value="", unit=""):
    value_text = str(value).strip() if valid(value) else ""
    status_text = str(status_value).strip() if valid(status_value) else ""
    unit_text = f" {unit}" if unit and value_text else ""
    if value_text and status_text:
        return f"{value_text}{unit_text} ({status_text})"
    if value_text:
        return f"{value_text}{unit_text}"
    return status_text


def effective_vital_status(vital, status_key):
    status_value = vital.get(status_key)
    if status_value == "Selber eintragen":
        return vital.get(f"{status_key}_custom")
    return status_value


def format_blood_pressure(vital):
    rr_sys = vital.get("rr_sys")
    rr_dia = vital.get("rr_dia")
    status_value = effective_vital_status(vital, "rr_status")
    if valid(rr_sys) or valid(rr_dia):
        return format_observation(f"{rr_sys or ''}/{rr_dia or ''}", status_value, "mmHg")
    return format_observation("", status_value)


RISK_FACTOR_LABELS = {
    "raucher": "Raucher",
    "alkohol": "Alkoholkonsum",
    "drogen": "Drogen",
    "diabetes": "Diabetes",
    "hypertonie": "Hypertonie",
    "antikoagulation": "Antikoagulation",
    "fruehgeburtlichkeit": "Frühgeburtlichkeit",
    "angeborene_erkrankung": "Angeborene Erkrankung",
    "chronische_erkrankung_kind": "Chronische Erkrankung",
    "immunsuppression_kind": "Immunsuppression",
    "entwicklungsauffaelligkeit": "Entwicklungsauffälligkeit",
    "relevante_exposition": "Relevante Exposition im Umfeld",
}


def format_selected_allergies(s):
    if s.get("allergien") == "Vorhanden" and valid(s.get("allergien_text")):
        return f"Vorhanden: {s.get('allergien_text')}"
    return s.get("allergien")


def format_selected_medication(s):
    if s.get("medikamente_option") == "Medikamente eingeben" and valid(s.get("medikamente")):
        return s.get("medikamente")
    return s.get("medikamente_option") or s.get("medikamente")


def format_last_meal(s):
    if s.get("letzte_mahlzeit") == "Eigene Eingabe" and valid(s.get("letzte_mahlzeit_text")):
        return s.get("letzte_mahlzeit_text")
    return s.get("letzte_mahlzeit") or s.get("letzte_aufnahme")


def format_risk_factors(s):
    risks = [label for key, label in RISK_FACTOR_LABELS.items() if s.get(key)]
    if valid(s.get("risiken_sonstige")):
        risks.append(s.get("risiken_sonstige"))
    if valid(s.get("risikofaktoren")):
        risks.append(s.get("risikofaktoren"))
    return ", ".join(risks)


def format_pregnancy_status(s):
    if s.get("schwangerschaft") == "Nicht relevant":
        return ""
    return s.get("schwangerschaft")


def amls_item_text(item, secondary_key="hinweis"):
    if isinstance(item, dict):
        name = item.get("diagnose") or item.get("name") or item.get("text") or item.get("value")
        secondary = item.get(secondary_key) or item.get("begruendung") or item.get("rationale") or item.get("status")
        if valid(name) and valid(secondary):
            return f"{name}: {secondary}"
        if valid(name):
            return str(name)
        if valid(secondary):
            return str(secondary)
        return ""
    return str(item) if valid(item) else ""


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


def format_patient_identity(vital):
    parts = []
    if valid(vital.get("geschlecht")):
        parts.append(str(vital.get("geschlecht")))
    if valid(vital.get("alter")):
        parts.append(f"{vital.get('alter')} Jahre")
    return compact_join(parts, ", ") or "Patientendaten nicht vollständig dokumentiert"


def format_symptom_summary(vital, samplers, opqrst):
    if valid(vital.get("kurzbericht")):
        return vital.get("kurzbericht")
    if valid(samplers.get("symptome")):
        return samplers.get("symptome")
    pain_parts = compact_join([
        opqrst.get("region"),
        opqrst.get("quality"),
        f"NRS {opqrst.get('nrs')}/10" if valid(opqrst.get("nrs")) else "",
    ])
    return pain_parts


def format_action_lines(measures):
    lines = []
    for item in measures.get("timeline", []) if isinstance(measures.get("timeline"), list) else []:
        if isinstance(item, dict):
            line = compact_join([item.get("zeit"), item.get("massnahme")], " - ")
        else:
            line = str(item) if valid(item) else ""
        if valid(line):
            lines.append(line)
    for item in measures.get("medikation", []) if isinstance(measures.get("medikation"), list) else []:
        if isinstance(item, dict):
            line = compact_join([
                item.get("zeit"),
                compact_join([item.get("medikament"), item.get("dosis"), item.get("weg")]),
            ], " - ")
        else:
            line = str(item) if valid(item) else ""
        if valid(line):
            lines.append(line)
    return lines


def format_reanimation_lines(reanimation):
    if not isinstance(reanimation, dict):
        return []
    shocks = reanimation.get("shocks", []) if isinstance(reanimation, dict) else []
    lines = [
        "Reanimation durchgeführt" if reanimation.get("active") else "",
        compact_join([
            f"CPR-Beginn {reanimation.get('cpr_start')}" if valid(reanimation.get("cpr_start")) else "",
            f"CPR-Ende/Übergabe {reanimation.get('cpr_end')}" if valid(reanimation.get("cpr_end")) else "",
            f"Initialrhythmus {reanimation.get('initial_rhythm')}" if valid(reanimation.get("initial_rhythm")) else "",
        ], "; "),
        compact_join([
            f"ROSC {reanimation.get('rosc')}" if valid(reanimation.get("rosc")) else "",
            f"ROSC-Zeit {reanimation.get('rosc_time')}" if valid(reanimation.get("rosc_time")) else "",
        ], "; "),
        compact_join([
            f"No-flow {reanimation.get('no_flow')}" if valid(reanimation.get("no_flow")) else "",
            f"Low-flow {reanimation.get('low_flow')}" if valid(reanimation.get("low_flow")) else "",
            "mechanische Reanimationshilfe eingesetzt" if reanimation.get("mechanical_cpr") else "",
        ], "; "),
        f"Atemweg/Beatmung: {reanimation.get('airway')}" if valid(reanimation.get("airway")) else "",
        f"Zugang: {reanimation.get('access')}" if valid(reanimation.get("access")) else "",
        f"Medikamente während CPR: {reanimation.get('meds')}" if valid(reanimation.get("meds")) else "",
        compact_join([
            f"Notarzt alarmiert {reanimation.get('notarzt_alarm')}" if valid(reanimation.get("notarzt_alarm")) else "",
            f"eingetroffen {reanimation.get('notarzt_arrival')}" if valid(reanimation.get("notarzt_arrival")) else "",
            f"Übernahme {reanimation.get('notarzt_takeover')}" if valid(reanimation.get("notarzt_takeover")) else "",
        ], "; "),
        f"Ausgang: {reanimation.get('outcome')}" if valid(reanimation.get("outcome")) else "",
        f"Notizen: {reanimation.get('notes')}" if valid(reanimation.get("notes")) else "",
    ]
    documented = [line for line in lines if valid(line)]
    if isinstance(shocks, list):
        for index, item in enumerate(shocks, start=1):
            if isinstance(item, dict):
                line = compact_join([
                    f"{index}. Schock",
                    item.get("zeit"),
                    f"{item.get('energie')} J" if valid(item.get("energie")) else "",
                    item.get("rhythmus"),
                ], " - ")
            else:
                line = str(item) if valid(item) else ""
            if valid(line):
                documented.append(line)
    return documented


def build_sinnhaft_rows(patient):
    vital = patient.get("vitalwerte", {}) or {}
    x = patient.get("xabcde", {}) or {}
    s = patient.get("samplers", {}) or {}
    o = patient.get("opqrst", {}) or {}
    amls = patient.get("amls", {}) or {}
    measures = patient.get("massnahmen", {}) or {}
    reanimation = patient.get("reanimation", {}) or {}
    if not isinstance(reanimation, dict):
        reanimation = {}
    handover = patient.get("uebergabe", {}) or {}

    priority = compact_join([
        f"RR {format_blood_pressure(vital)}" if valid(format_blood_pressure(vital)) else "",
        f"Puls {format_observation(vital.get('puls'), effective_vital_status(vital, 'puls_status'), '/min')}" if valid(format_observation(vital.get("puls"), effective_vital_status(vital, "puls_status"), "/min")) else "",
        f"SpO2 {format_observation(vital.get('spo2'), effective_vital_status(vital, 'spo2_status'), '%')}" if valid(format_observation(vital.get("spo2"), effective_vital_status(vital, "spo2_status"), "%")) else "",
        f"GCS {format_observation(vital.get('gcs'), effective_vital_status(vital, 'gcs_status'), '/15')}" if valid(format_observation(vital.get("gcs"), effective_vital_status(vital, "gcs_status"), "/15")) else "",
        f"Atemweg {x.get('atemweg')}" if valid(x.get("atemweg")) else "",
        f"Atmung {x.get('atmung')}" if valid(x.get("atmung")) else "",
        f"Kreislauf {x.get('haut')}" if valid(x.get("haut")) else "",
        f"AVPU {x.get('avpu')}" if valid(x.get("avpu")) else "",
    ])
    action_lines = format_action_lines(measures) + format_reanimation_lines(reanimation)
    anamnesis = compact_join([
        f"Allergien: {format_selected_allergies(s)}" if valid(format_selected_allergies(s)) else "",
        f"Medikation: {format_selected_medication(s)}" if valid(format_selected_medication(s)) else "",
        f"Vorgeschichte: {s.get('vorgeschichte')}" if valid(s.get("vorgeschichte")) else "",
        f"Letzte Mahlzeit: {format_last_meal(s)}" if valid(format_last_meal(s)) else "",
        f"Risiken: {format_risk_factors(s)}" if valid(format_risk_factors(s)) else "",
    ], "; ")

    return [
        ("S Start", handover.get("sinnhaft_start") or "Ruhe herstellen, Face-to-Face-Übergabe, Manipulationen am Patienten möglichst pausieren."),
        ("I Identifikation", handover.get("sinnhaft_identifikation") or format_patient_identity(vital)),
        ("N Notfallereignis", handover.get("sinnhaft_notfallereignis") or compact_join([format_symptom_summary(vital, s, o), s.get("ereignis")], "; ")),
        ("N Notfallpriorität", handover.get("sinnhaft_notfallprioritaet") or priority),
        ("H Handlung", handover.get("sinnhaft_handlung") or "; ".join(action_lines)),
        ("A Anamnese", handover.get("sinnhaft_anamnese") or anamnesis),
        ("F Fazit", handover.get("sinnhaft_fazit") or compact_join([amls.get("arbeitsdiagnose"), handover.get("ziel")], " -> ")),
        ("T Teamfragen", handover.get("sinnhaft_teamfragen")),
    ]


def build_narrative_report(patient):
    vital = patient.get("vitalwerte", {}) or {}
    x = patient.get("xabcde", {}) or {}
    s = patient.get("samplers", {}) or {}
    o = patient.get("opqrst", {}) or {}
    amls = patient.get("amls", {}) or {}
    measures = patient.get("massnahmen", {}) or {}
    reanimation = patient.get("reanimation", {}) or {}
    handover = patient.get("uebergabe", {}) or {}

    primary = []
    identity = format_patient_identity(vital)
    symptom = format_symptom_summary(vital, s, o)
    if valid(symptom):
        primary.append(f"Bei {identity} wurde präklinisch folgendes Hauptproblem dokumentiert: {symptom}.")
    else:
        primary.append(f"Bei {identity} wurde ein Rettungsdiensteinsatz dokumentiert; ein Kurzbericht ist noch nicht hinterlegt.")
    if valid(amls.get("arbeitsdiagnose")):
        primary.append(f"Als Arbeitsdiagnose/Verdacht wurde {amls.get('arbeitsdiagnose')} festgehalten.")

    assessment = []
    assessment.append(compact_join([
        f"RR {format_blood_pressure(vital)}" if valid(format_blood_pressure(vital)) else "",
        f"Puls {format_observation(vital.get('puls'), effective_vital_status(vital, 'puls_status'), '/min')}" if valid(format_observation(vital.get("puls"), effective_vital_status(vital, "puls_status"), "/min")) else "",
        f"SpO2 {format_observation(vital.get('spo2'), effective_vital_status(vital, 'spo2_status'), '%')}" if valid(format_observation(vital.get("spo2"), effective_vital_status(vital, "spo2_status"), "%")) else "",
        f"AF {format_observation(vital.get('af'), effective_vital_status(vital, 'af_status'), '/min')}" if valid(format_observation(vital.get("af"), effective_vital_status(vital, "af_status"), "/min")) else "",
        f"GCS {format_observation(vital.get('gcs'), effective_vital_status(vital, 'gcs_status'), '/15')}" if valid(format_observation(vital.get("gcs"), effective_vital_status(vital, "gcs_status"), "/15")) else "",
    ]))
    assessment.append(compact_join([
        f"xABCDE: X {x.get('blutung')}" if valid(x.get("blutung")) else "",
        f"A {x.get('atemweg')}" if valid(x.get("atemweg")) else "",
        f"B {x.get('atmung')}" if valid(x.get("atmung")) else "",
        f"C {x.get('haut')}" if valid(x.get("haut")) else "",
        f"D AVPU {x.get('avpu')}" if valid(x.get("avpu")) else "",
        f"E {x.get('bodycheck')}" if valid(x.get("bodycheck")) else "",
    ]))

    history = []
    history.append(compact_join([
        f"Symptome: {s.get('symptome')}" if valid(s.get("symptome")) else "",
        f"Allergien: {format_selected_allergies(s)}" if valid(format_selected_allergies(s)) else "",
        f"Medikation: {format_selected_medication(s)}" if valid(format_selected_medication(s)) else "",
        f"Vorgeschichte: {s.get('vorgeschichte')}" if valid(s.get("vorgeschichte")) else "",
    ], "; "))
    if o.get("schmerz_vorhanden") == "Ja":
        history.append(compact_join([
            "Schmerzassessment:",
            o.get("onset"),
            o.get("quality"),
            o.get("region"),
            f"Ausstrahlung {o.get('radiation')}" if valid(o.get("radiation")) else "",
            f"NRS {o.get('nrs')}/10" if valid(o.get("nrs")) else "",
            o.get("zeitverlauf"),
        ], " "))

    actions = format_action_lines(measures)
    reanimation_summary = format_reanimation_lines(reanimation)
    handover_sentence = compact_join([
        f"Ziel/Empfänger: {handover.get('ziel')}" if valid(handover.get("ziel")) else "",
        handover.get("text"),
        f"Lagerung/Transfer: {handover.get('lagerung')}" if valid(handover.get("lagerung")) else "",
        f"Wertsachen/Eigentum: {handover.get('wertsachen')}" if valid(handover.get("wertsachen")) else "",
        f"Krankenkassenkarte: {handover.get('krankenkassenkarte')}" if valid(handover.get("krankenkassenkarte")) else "",
    ], " ")

    text = ""
    text += add_paragraph("EINSATZBERICHT", primary)
    text += add_paragraph("ERSTBEFUND UND VERLAUF", [item for item in assessment if valid(item)])
    text += add_paragraph("ANAMNESE UND SCHMERZASSESSMENT", [item for item in history if valid(item)])
    text += add_paragraph("MAßNAHMEN UND WIRKUNG", ["; ".join(actions) if actions else "Keine Maßnahmen/Medikationen dokumentiert."])
    text += add_paragraph("REANIMATION", reanimation_summary)
    text += add_paragraph("ÜBERGABE-KURZFAZIT", [handover_sentence])
    return text


QUALITY_RULES = [
    {"id": "vital_age", "label": "Alter dokumentiert", "severity": "warning", "section": "Vitalwerte"},
    {"id": "vital_gender", "label": "Geschlecht dokumentiert", "severity": "info", "section": "Vitalwerte"},
    {"id": "vital_core", "label": "Puls, SpO2, RR und GCS geprüft", "severity": "warning", "section": "Vitalwerte"},
    {"id": "short_report", "label": "Kurzbericht oder Leitsymptome vorhanden", "severity": "warning", "section": "Anamnese"},
    {"id": "xabcde", "label": "xABCDE Kernfelder dokumentiert", "severity": "warning", "section": "Erstbeurteilung"},
    {"id": "diagnosis", "label": "Arbeitsdiagnose/Verdacht eingetragen", "severity": "warning", "section": "Übergabe"},
    {"id": "target", "label": "Zielklinik ausgewählt", "severity": "warning", "section": "Transport"},
    {"id": "handover", "label": "Übergabeziel oder Übergabetext vorhanden", "severity": "warning", "section": "Übergabe"},
    {"id": "measures", "label": "Maßnahmen/Medikation geprüft", "severity": "info", "section": "Maßnahmen"},
]


def as_number(value):
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def truthy(value):
    return str(value or "").strip().lower() in {"ja", "true", "1", "yes", "on"}


def build_suspicion_assessment(patient):
    vital = patient.get("vitalwerte", {}) or {}
    xabcde = patient.get("xabcde", {}) or {}
    samplers = patient.get("samplers", {}) or {}
    opqrst = patient.get("opqrst", {}) or {}

    text = " ".join([
        str(samplers.get("symptome") or ""),
        str(samplers.get("ereignis") or ""),
        str(samplers.get("trauma_mechanismus") or ""),
        str(samplers.get("sturzhoehe_kategorie") or ""),
        str(samplers.get("vorgeschichte") or ""),
        str(samplers.get("medikamente") or ""),
        str(samplers.get("risiken_sonstige") or ""),
        str(opqrst.get("region") or ""),
        str(opqrst.get("quality") or ""),
        str(vital.get("kurzbericht") or ""),
    ]).lower()
    suspicions = []
    recommendations = []

    def add(suspicion, *steps):
        if suspicion not in suspicions:
            suspicions.append(suspicion)
        for step in steps:
            if step and step not in recommendations:
                recommendations.append(step)

    spo2 = as_number(vital.get("spo2"))
    gcs = as_number(vital.get("gcs"))
    bz = as_number(vital.get("bz"))
    nrs = as_number(opqrst.get("severity") or opqrst.get("nrs"))

    if any(term in text for term in ["atemnot", "dyspnoe", "luftnot"]) or xabcde.get("atmung") in ["Dyspnoe", "Tachypnoe", "Apnoe"] or (spo2 is not None and spo2 < 90):
        add(
            "Respiratorische Insuffizienz / akute Dyspnoe",
            "Atemweg sichern und Atemarbeit engmaschig überwachen",
            "Sauerstofftherapie titriert fortführen",
            "Frühe Zielklinikmeldung bei persistierender Hypoxie",
        )
    if any(term in text for term in ["brust", "thorax", "retrosternal", "druck"]):
        add(
            "Akutes Koronarsyndrom (ACS) als Differenzialdiagnose",
            "12-Kanal-EKG und Verlaufskontrolle",
            "Schmerz- und Kreislaufmonitoring",
            "Zeitkritischen Transport erwägen",
        )
    if xabcde.get("avpu") in ["P", "U", "Pain", "Unresponsive"] or (gcs is not None and gcs <= 8):
        add(
            "Schwere neurologische Beeinträchtigung",
            "Atemwegsschutz priorisieren",
            "Neurologischen Verlauf wiederholt dokumentieren",
            "Zielklinik mit neurologischer Versorgung bevorzugen",
        )
    if any(term in text for term in ["sturz", "unfall", "trauma", "kollision"]) or str(xabcde.get("bodycheck", "")).lower() == "auffällig":
        add(
            "Traumatische Genese / relevante Verletzung möglich",
            "Vollständigen Bodycheck und Blutungskontrolle sichern",
            "Immobilisationsbedarf prüfen",
            "Traumazentrum-Indikation evaluieren",
        )
    if bz is not None and bz < 70:
        add("Hypoglykämie", "Sofortige Glukosegabe gemäß SOP", "Blutzucker nach Intervention kontrollieren")
    elif bz is not None and bz > 250:
        add("Hyperglykäme Stoffwechsellage", "Hydratationsstatus und Vigilanz eng überwachen", "Zeitnahe klinische Abklärung veranlassen")
    if nrs is not None and nrs >= 7:
        add("Akutes Schmerzsyndrom", "Analgesiekonzept dokumentieren und Wirkung nachkontrollieren", "Schmerzverlauf seriell erfassen")

    if not suspicions:
        suspicions.append("Aktuell keine klare Verdachtsdiagnose aus den verfügbaren Angaben ableitbar")
        recommendations.append("Datensatz vervollständigen und Verlauf engmaschig re-evaluieren")
    return suspicions, recommendations


def build_amls_candidates(patient):
    patient_data = patient.get("patient", {}) or {}
    is_child = patient_data.get("patientengruppe") == "Kind"
    vital = patient.get("vitalwerte", {}) or {}
    xabcde = patient.get("xabcde", {}) or {}
    samplers = patient.get("samplers", {}) or {}
    opqrst = patient.get("opqrst", {}) or {}
    amls = patient.get("amls", {}) or {}
    text = " ".join([
        str(samplers.get("symptome") or ""),
        str(samplers.get("ereignis") or ""),
        str(opqrst.get("region") or ""),
        str(opqrst.get("quality") or ""),
        str(vital.get("kurzbericht") or ""),
    ]).lower()
    candidates = []

    def add(name, category, rationale):
        if name and not any(item["name"] == name for item in candidates):
            candidates.append({"name": name, "category": category, "rationale": rationale})

    af = as_number(vital.get("af"))
    spo2 = as_number(vital.get("spo2"))
    pulse = as_number(vital.get("puls"))
    rr_sys = as_number(vital.get("rr_sys"))
    temp = as_number(vital.get("temperatur"))
    gcs = as_number(vital.get("gcs"))
    bz = as_number(vital.get("bz"))

    if not is_child and af is not None and af > 20:
        add("Lungenarterienembolie", "Kardiopulmonal", f"Tachypnoe mit AF {af:g}/min")
        add("Sepsis / schwere Infektion", "Infektiös", f"Tachypnoe mit AF {af:g}/min")
        add("Schock", "Kreislauf", f"Tachypnoe mit AF {af:g}/min als Kompensationszeichen")
    if spo2 is not None and spo2 < 95:
        add("Respiratorische Insuffizienz", "Respiratorisch", f"SpO2 {spo2:g} %")
        add("Pneumonie", "Infektiös", f"SpO2 {spo2:g} %")
        add("Kardiales Lungenödem", "Kardiopulmonal", f"SpO2 {spo2:g} %")
    if not is_child and pulse is not None and pulse > 100:
        add("Tachyarrhythmie", "Kardial", f"Puls {pulse:g}/min")
        add("Schmerz-/Stressreaktion", "Sonstige", f"Puls {pulse:g}/min")
    if not is_child and rr_sys is not None and rr_sys < 90:
        add("Schock", "Kreislauf", f"Hypotonie mit RR syst. {rr_sys:g} mmHg")
        add("Blutung / Volumenmangel", "Kreislauf", f"Hypotonie mit RR syst. {rr_sys:g} mmHg")
    if temp is not None and temp >= 38:
        add("Sepsis / schwere Infektion", "Infektiös", f"Fieber mit {temp:g} Grad C")
    if gcs is not None and gcs < 15:
        add("Intrakranielle Ursache", "Neurologisch", f"GCS {gcs:g}")
        add("Intoxikation", "Toxikologisch", f"GCS {gcs:g}")
    if bz is not None and bz < 70:
        add("Hypoglykämie", "Metabolisch", f"BZ {bz:g} mg/dL")
    if is_child:
        pat = patient_data.get("pat", {}) or {}
        if pat.get("atemarbeit") == "auffällig":
            add("Respiratorische Erkrankung im Kindesalter", "Pädiatrisch/Respiratorisch", "PAT: Atemarbeit auffällig")
        if pat.get("hautdurchblutung") == "auffällig":
            add("Kreislaufbeeinträchtigung im Kindesalter", "Pädiatrisch/Kreislauf", "PAT: Hautdurchblutung auffällig")
        if pat.get("erscheinungsbild") == "auffällig":
            add("Schwer erkranktes Kind / neurologische oder metabolische Ursache", "Pädiatrisch", "PAT: Erscheinungsbild auffällig")
    if any(term in text for term in ["brust", "thorax", "retrosternal"]):
        add("Akutes Koronarsyndrom", "Kardial", "Thoraxbeschwerden dokumentiert")
        add("Aortensyndrom / Aortendissektion", "Vaskulär", "Zeitkritische Ursache bei Thoraxschmerz")
        add("Pneumothorax", "Respiratorisch", "Thoraxschmerz kann pleuropulmonal bedingt sein")
    if any(term in text for term in ["atemnot", "dyspnoe", "luftnot"]):
        add("Asthma/COPD-Exazerbation", "Respiratorisch", "Dyspnoe dokumentiert")
    if any(term in text for term in ["bauch", "abdomen", "kolik", "flanke"]):
        add("Akutes Abdomen", "Abdominell", "Abdominelle Beschwerden dokumentiert")
        add("Atypisches akutes Koronarsyndrom", "Kardial", "Oberbauchbeschwerden können kardial bedingt sein")
    if samplers.get("diabetes") or "diabetes" in text:
        add("Diabetische Stoffwechselentgleisung", "Metabolisch", "Diabetes in der Vorgeschichte/Risikoangabe")
    if samplers.get("antikoagulation") or any(term in text for term in ["antikoag", "marcumar", "apixaban", "rivaroxaban"]):
        add("Blutung unter Antikoagulation", "Hämatologisch", "Antikoagulation dokumentiert")
    if samplers.get("chronische_erkrankung_kind") or samplers.get("angeborene_erkrankung"):
        add("Dekompensation der Grunderkrankung", "Pädiatrisch", "Relevante kindliche Vor- oder Grunderkrankung dokumentiert")
    if samplers.get("immunsuppression_kind"):
        add("Schwere Infektion bei Immunsuppression", "Pädiatrisch/Infektiös", "Immunsuppression als Risikofaktor dokumentiert")
    if samplers.get("fruehgeburtlichkeit"):
        add("Komplikation bei Frühgeburtlichkeit", "Pädiatrisch", "Frühgeburtlichkeit dokumentiert")

    if len(candidates) < 4:
        for name, category in [
            ("Kardiale Ursache / Rhythmusstörung", "Kardial"),
            ("Respiratorische Ursache", "Respiratorisch"),
            ("Neurologische Ursache", "Neurologisch"),
            ("Metabolische Entgleisung", "Metabolisch"),
            ("Infektion / Sepsis", "Infektiös"),
            ("Intoxikation", "Toxikologisch"),
        ]:
            add(name, category, "Breiter Sicherheitscheck bei unspezifischer Datenlage")

    for item in amls.get("custom_candidates", []):
        name = item.get("diagnose") if isinstance(item, dict) else item
        if valid(name):
            add(str(name), "Eigene Ergänzung", "Manuell zur Diagnosehilfe hinzugefügt")

    excluded_names = {
        str(item.get("diagnose") or item.get("name") or "").strip() if isinstance(item, dict) else str(item).strip()
        for item in amls.get("excluded", [])
        if valid(item)
    }
    for item in candidates:
        conflicts = [] if item["category"] == "Eigene Ergänzung" else amls_candidate_conflicts(item["name"], patient)
        item["conflicts"] = conflicts
        item["excluded"] = item["name"] in excluded_names
        item["status"] = "excluded" if item["excluded"] else "check" if conflicts else "matching"
    return candidates


def amls_candidate_conflicts(candidate_name, patient):
    vital = patient.get("vitalwerte", {}) or {}
    xabcde = patient.get("xabcde", {}) or {}
    name = str(candidate_name or "").lower()
    conflicts = []
    spo2 = as_number(vital.get("spo2"))
    rr_sys = as_number(vital.get("rr_sys"))
    pulse = as_number(vital.get("puls"))
    temp = as_number(vital.get("temperatur"))
    gcs = as_number(vital.get("gcs"))
    bz = as_number(vital.get("bz"))

    if any(term in name for term in ["pneumonie", "respirator", "asthma", "copd", "lungenembolie", "lungenödem", "lungenoedem", "pneumothorax"]):
        if spo2 is not None and spo2 >= 95 and str(xabcde.get("atmung", "")).lower() in ["unauffällig", "frei"]:
            conflicts.append("SpO2/Atmung bislang unauffällig dokumentiert")
    if any(term in name for term in ["schock", "blutung", "volumenmangel", "sepsis"]):
        if rr_sys is not None and rr_sys >= 100 and pulse is not None and pulse <= 100:
            conflicts.append("RR/Puls sprechen aktuell nicht für Schock")
    if "sepsis" in name or "infektion" in name:
        if temp is not None and temp < 38:
            conflicts.append("Kein Fieber dokumentiert")
    if any(term in name for term in ["intrakraniell", "neurolog", "schlaganfall", "tia"]):
        if gcs is not None and gcs == 15 and xabcde.get("avpu") in ["Alert", "A", ""]:
            conflicts.append("Vigilanz aktuell unauffällig")
    if "hypogly" in name and bz is not None and bz >= 70:
        conflicts.append("BZ nicht im hypoglykämischen Bereich")
    return conflicts


def calculate_medication(payload):
    sop = payload.sop
    age = float(payload.age or 0)
    weight = max(1.0, float(payload.weight or 1))
    inputs = payload.inputs or {}
    meds = []
    actions = ["Basismaßnahmen nach xABCDE, Monitoring und Verlaufskontrolle"]
    notes = []

    if sop.startswith("Anaphylaxie"):
        if age >= 12:
            adrenalin = 0.5
            clemastin = 2.0
            pred = 250
            salbutamol = "2,5 mg"
        elif age >= 6:
            adrenalin = 0.3
            clemastin = round(0.03 * weight, 2)
            pred = round(2.0 * weight, 1)
            salbutamol = "1,25 mg"
        else:
            adrenalin = 0.15
            clemastin = round(0.03 * weight, 2)
            pred = round(2.0 * weight, 1)
            salbutamol = "keine SOP-Angabe <4 Jahre"
        meds = [f"Adrenalin i.m. {adrenalin} mg pur", f"Clemastin i.v. {clemastin} mg", f"Prednisolon i.v. {pred} mg", f"Vollelektrolyt {int(20 * weight)} ml", f"Salbutamol vernebelt {salbutamol}"]
        actions.append("Bei fehlender Stabilisierung Adrenalin i.m. alle 5 Minuten wiederholen")
        notes.append("Adrenalin-Verneblung bei Stridor/Dysphonie/Uvulaschwellung: 4 mg pur vernebelt")
    elif sop.startswith("Asthma"):
        if age < 4:
            meds.append("Adrenalin 4 mg pur vernebelt")
        elif age <= 6:
            meds.append("Salbutamol 1,25 mg vernebelt")
        else:
            meds.extend(["Salbutamol 2,5 mg vernebelt", "Ipratropiumbromid 500 mcg vernebelt"])
        meds.append("Prednisolon 100 mg i.v." if age > 12 else f"Prednisolon {round(2 * weight, 1)} mg i.v.")
        actions.extend(["Oberkörper hoch, beruhigen, Sauerstoff titrieren", "Nach 5 Minuten Wirkung re-evaluieren"])
    elif sop == "Hypoglykämie":
        bz = float(inputs.get("bz", 55) or 55)
        if bz < 60:
            meds.append("Glucose bis zu 16 g i.v. bei Bewusstseinsstörung, sonst oral")
        else:
            notes.append("Aktueller BZ liegt nicht unter dem Standard-Schwellenwert 60 mg/dl")
        actions.append("BZ nach Intervention kontrollieren")
    elif sop == "Krampfanfall":
        iv_dose = round(0.05 * weight, 2)
        meds.append(f"Midazolam {iv_dose} mg i.v. langsam titrieren bei i.v.-Zugang")
        meds.append("Alternativ nasal: 2,5 mg bis 10 kg, 5 mg bis 20 kg, 10 mg ab 20 kg")
        actions.append("Bei anhaltendem Anfall Notarztruf und Kliniktransport priorisieren")
    elif sop == "Schlaganfall":
        rr = float(inputs.get("rr_sys", 170) or 170)
        if rr < 120:
            meds.append("Vollelektrolyt 500 ml i.v.")
        elif rr > 220:
            meds.append("Urapidil 5-15 mg langsam i.v., titrierend")
        else:
            notes.append("Keine primäre RR-Senkung im Standardfenster 120-220 mmHg")
        actions.extend(["Last-Seen-Well sichern", "Stroke-Unit-Voranmeldung priorisieren"])
    elif sop == "Kardiales Lungenödem":
        rr = float(inputs.get("rr_sys", 160) or 160)
        if rr > 120:
            meds.append("Glyceroltrinitrat 0,4-0,8 mg s.l.")
        meds.append("Furosemid 20 mg i.v. langsam, ggf. einmalige Repetition")
        actions.append("CPAP/NIV frühzeitig erwägen")
    elif sop == "Starke Schmerzen":
        nrs = float(inputs.get("nrs", 7) or 7)
        if nrs >= 3:
            meds.append(f"Paracetamol {int(round(15 * min(weight, 50), 0))} mg i.v. falls geeignet")
        if nrs >= 6 and weight > 30:
            meds.append(f"Esketamin {round(0.125 * weight, 2)} mg i.v. oder Fentanyl nach SOP")
        actions.append("Schmerzverlauf dokumentieren und Wirkung nachkontrollieren")
    else:
        notes.append("Dieser SOP-Pfad ist als Kurzreferenz angelegt; Detailrechner wird schrittweise erweitert.")

    if payload.pregnant == "Ja":
        notes.append("Schwangerschaft: frühe ärztliche Rücksprache einplanen.")
    return {
        "sop": sop,
        "medications": meds,
        "actions": actions,
        "notes": notes,
        "ruleset_version": MEDICAL_RULESET_VERSION,
    }


def quality_item(rule_id, status_value, message, severity="warning"):
    rule = next((item for item in QUALITY_RULES if item["id"] == rule_id), {})
    return {
        "id": rule_id,
        "label": rule.get("label", rule_id),
        "section": rule.get("section", ""),
        "severity": severity or rule.get("severity", "warning"),
        "status": status_value,
        "message": message,
    }


def assess_protocol_quality(patient):
    patient_data = patient.get("patient", {}) or {}
    is_child = patient_data.get("patientengruppe") == "Kind"
    vital = patient.get("vitalwerte", {}) or {}
    xabcde = patient.get("xabcde", {}) or {}
    samplers = patient.get("samplers", {}) or {}
    amls = patient.get("amls", {}) or {}
    transport = patient.get("transport", {}) or {}
    handover = patient.get("uebergabe", {}) or {}
    measures = patient.get("massnahmen", {}) or {}

    items = []
    age_documented = valid(patient_data.get("alter_wert")) if is_child else valid(vital.get("alter"))
    items.append(quality_item(
        "vital_age",
        "ok" if age_documented else "warning",
        "Alter ist dokumentiert." if age_documented else "Alter fehlt.",
    ))
    items.append(quality_item(
        "vital_gender",
        "ok" if valid(vital.get("geschlecht")) else "info",
        "Geschlecht ist dokumentiert." if valid(vital.get("geschlecht")) else "Geschlecht fehlt.",
        "info",
    ))

    paediatrie = patient_data.get("paediatrie", {}) or {}
    pediatric_gcs_complete = all(valid(paediatrie.get(key)) for key in ("gcs_augen", "gcs_verbal", "gcs_motorik"))
    core_vital_groups = [
        ("Puls", ["puls", "puls_status", "puls_status_custom"]),
        ("SpO2", ["spo2", "spo2_status", "spo2_status_custom"]),
        ("RR", ["rr_sys", "rr_dia", "rr_status", "rr_status_custom"]),
    ]
    missing_core = [label for label, keys in core_vital_groups if not any(valid(vital.get(key)) for key in keys)]
    if is_child:
        if not pediatric_gcs_complete:
            missing_core.append("Kinder-GCS")
    elif not any(valid(vital.get(key)) for key in ("gcs", "gcs_status", "gcs_status_custom")):
        missing_core.append("GCS")
    items.append(quality_item(
        "vital_core",
        "ok" if not missing_core else "warning",
        "Kernvitalwerte sind vollständig." if not missing_core else "Fehlende Kernvitalwerte: " + ", ".join(missing_core),
    ))

    has_report = valid(vital.get("kurzbericht")) or valid(samplers.get("symptome"))
    items.append(quality_item(
        "short_report",
        "ok" if has_report else "warning",
        "Kurzbericht/Leitsymptome vorhanden." if has_report else "Kurzbericht oder Leitsymptome fehlen.",
    ))

    x_required = ["atemweg", "atmung", "haut", "avpu"]
    missing_x = [key for key in x_required if not valid(xabcde.get(key))]
    items.append(quality_item(
        "xabcde",
        "ok" if not missing_x else "warning",
        "xABCDE Kernfelder sind dokumentiert." if not missing_x else "Fehlende xABCDE-Felder: " + ", ".join(missing_x),
    ))

    diagnosis_ok = (
        valid(amls.get("arbeitsdiagnose"))
        or valid(amls.get("leitsymptom"))
        or bool(amls.get("custom_candidates"))
        or valid(patient.get("einweisung", {}).get("diagnose"))
    )
    items.append(quality_item(
        "diagnosis",
        "ok" if diagnosis_ok else "warning",
        "Arbeitsdiagnose/Verdacht vorhanden." if diagnosis_ok else "Arbeitsdiagnose oder Verdacht fehlt.",
    ))

    items.append(quality_item(
        "target",
        "ok" if valid(transport.get("hospital_name")) else "warning",
        "Zielklinik ist ausgewählt." if valid(transport.get("hospital_name")) else "Zielklinik fehlt.",
    ))

    handover_ok = valid(handover.get("ziel")) or valid(handover.get("text")) or any(
        valid(handover.get(key))
        for key in (
            "sinnhaft_start",
            "sinnhaft_identifikation",
            "sinnhaft_notfallereignis",
            "sinnhaft_notfallprioritaet",
            "sinnhaft_handlung",
            "sinnhaft_anamnese",
            "sinnhaft_fazit",
            "sinnhaft_teamfragen",
        )
    )
    items.append(quality_item(
        "handover",
        "ok" if handover_ok else "warning",
        "Übergabe ist vorbereitet." if handover_ok else "Übergabeziel oder Übergabetext fehlt.",
    ))

    has_measures = bool(measures.get("timeline")) or bool(measures.get("medikation"))
    items.append(quality_item(
        "measures",
        "ok" if has_measures else "info",
        "Maßnahmen/Medikation dokumentiert." if has_measures else "Keine Maßnahmen oder Medikation dokumentiert.",
        "info",
    ))

    criticals = []
    spo2 = as_number(vital.get("spo2"))
    gcs = as_number(vital.get("gcs"))
    rr_sys = as_number(vital.get("rr_sys"))
    pulse = as_number(vital.get("puls"))
    af = as_number(vital.get("af"))
    if spo2 is not None and spo2 < 92:
        criticals.append("SpO2 unter 92 Prozent")
    if gcs is not None and gcs < 15:
        criticals.append("GCS unter 15")
    if not is_child:
        if rr_sys is not None and (rr_sys < 90 or rr_sys > 200):
            criticals.append("RR systolisch außerhalb 90-200 mmHg")
        if pulse is not None and (pulse < 45 or pulse > 130):
            criticals.append("Puls außerhalb 45-130/min")
        if af is not None and (af < 8 or af > 30):
            criticals.append("Atemfrequenz außerhalb 8-30/min")

    for index, message in enumerate(criticals, start=1):
        items.append({
            "id": f"critical_{index}",
            "label": "Kritischer Vitalwert",
            "section": "Plausibilität",
            "severity": "critical",
            "status": "critical",
            "message": message,
        })

    warning_count = len([item for item in items if item["status"] == "warning"])
    critical_count = len([item for item in items if item["status"] == "critical"])
    info_count = len([item for item in items if item["status"] == "info"])
    ok_count = len([item for item in items if item["status"] == "ok"])
    base_items = [item for item in items if not item["id"].startswith("critical_")]
    score = max(0, min(100, round((ok_count / max(1, len(base_items))) * 100) - critical_count * 10))
    if critical_count:
        level = "critical"
    elif warning_count:
        level = "warning"
    else:
        level = "ok"
    return {
        "score": score,
        "level": level,
        "ok_count": ok_count,
        "warning_count": warning_count,
        "critical_count": critical_count,
        "info_count": info_count,
        "items": items,
        "rules": QUALITY_RULES,
    }


def generate_protocol_text(patient):
    patient_data = patient.get("patient", {}) or {}
    crew = patient.get("besatzung", {}) or {}
    vital = patient.get("vitalwerte", {})
    x = patient.get("xabcde", {})
    s = patient.get("samplers", {})
    o = patient.get("opqrst", {})
    psyche = patient.get("psyche", {}) or {}
    measures = patient.get("massnahmen", {})
    reanimation = patient.get("reanimation", {}) or {}
    if not isinstance(reanimation, dict):
        reanimation = {}
    handover = patient.get("uebergabe", {})
    amls = patient.get("amls", {})

    text = "RD-PROTOKOLL - DOKUMENTATIONSENTWURF\n"
    text += "=" * 50 + "\n"
    text += f"Erstellt am {local_now().strftime('%d.%m.%Y um %H:%M:%S')} Uhr\n"
    text += "Enthält ausschließlich dokumentierte Angaben; vor Verwendung vollständig prüfen.\n\n"
    text += build_narrative_report(patient)

    text += add_lines("BESATZUNG / SCHICHT", [
        ("Transportführer/in", crew.get("verantwortlicher")),
        ("Fahrer/in", crew.get("fahrer")),
        ("Azubi", crew.get("azubi")),
        ("Praktikant/in", crew.get("praktikant")),
    ])

    pat = patient_data.get("pat", {}) or {}
    paediatrie = patient_data.get("paediatrie", {}) or {}
    gcs_parts = [as_number(paediatrie.get(key)) for key in ("gcs_augen", "gcs_verbal", "gcs_motorik")]
    pediatric_gcs_total = sum(gcs_parts) if all(value is not None for value in gcs_parts) else ""
    apgar_details = paediatrie.get("apgar_details", {}) or {}
    trauma_findings = x.get("trauma_befunde", []) if isinstance(x.get("trauma_befunde"), list) else []

    def apgar_total(minute):
        details = apgar_details.get(str(minute), {}) or {}
        values = [as_number(details.get(key)) for key in ("herzfrequenz", "atmung", "muskeltonus", "reflexe", "hautkolorit")]
        return int(sum(values)) if all(value is not None for value in values) else ""

    text += add_lines("PATIENT / PÄDIATRIE", [
        ("Patientengruppe", patient_data.get("patientengruppe")),
        ("Alter", f"{patient_data.get('alter_wert')} {patient_data.get('alter_einheit')}" if valid(patient_data.get("alter_wert")) else ""),
        ("PAT Erscheinungsbild", pat.get("erscheinungsbild")),
        ("PAT Atemarbeit", pat.get("atemarbeit")),
        ("PAT Hautdurchblutung", pat.get("hautdurchblutung")),
        ("PAT Beobachtung", pat.get("notiz")),
        ("Kinder-GCS Augen", paediatrie.get("gcs_augen")),
        ("Kinder-GCS Verbal", paediatrie.get("gcs_verbal")),
        ("Kinder-GCS Motorisch", paediatrie.get("gcs_motorik")),
        ("Kinder-GCS Summe", f"{int(pediatric_gcs_total)}/15" if pediatric_gcs_total != "" else ""),
        ("APGAR 1 Minute", apgar_total(1)),
        ("APGAR 5 Minuten", apgar_total(5)),
        ("APGAR 10 Minuten", apgar_total(10)),
    ])
    text += add_lines("VITALWERTE & DEMOGRAPHIE", [
        ("Alter", vital.get("alter")),
        ("Geschlecht", vital.get("geschlecht")),
        ("RR", format_blood_pressure(vital)),
        ("Puls", format_observation(vital.get("puls"), effective_vital_status(vital, "puls_status"), "/min")),
        ("SpO2", format_observation(vital.get("spo2"), effective_vital_status(vital, "spo2_status"), "%")),
        ("Atemfrequenz", format_observation(vital.get("af"), effective_vital_status(vital, "af_status"), "/min")),
        ("BZ", format_observation(vital.get("bz"), effective_vital_status(vital, "bz_status"), "mg/dL")),
        ("Temperatur", format_observation(vital.get("temperatur"), effective_vital_status(vital, "temperatur_status"), "°C")),
        ("GCS", format_observation(vital.get("gcs"), effective_vital_status(vital, "gcs_status"), "/15")),
        ("Kurzbericht", vital.get("kurzbericht")),
    ])
    text += add_lines("xABCDE", [
        ("X Blutung", x.get("blutung")),
        ("Blutung Lokalisation", x.get("blutung_lokalisation")),
        ("A Atemweg", x.get("atemweg")),
        ("HWS", x.get("hws")),
        ("B Atmung", x.get("atmung")),
        ("Atemgeräusche", x.get("atemgeraeusche")),
        ("Sauerstoff", x.get("sauerstoff")),
        ("C Hautzeichen", x.get("haut")),
        ("Rekap", x.get("rekap")),
        ("Pulsqualität", x.get("pulsqualitaet")),
        ("D AVPU", x.get("avpu")),
        ("Pupillen", x.get("pupillen")),
        ("BE-FAST Balance", x.get("befast_balance")),
        ("BE-FAST Eyes", x.get("befast_eyes")),
        ("BE-FAST Face", x.get("befast_face")),
        ("BE-FAST Arms", x.get("befast_arms")),
        ("BE-FAST Speech", x.get("befast_speech")),
        ("BE-FAST Time", x.get("befast_time")),
        ("E Bodycheck", x.get("bodycheck")),
        ("Bodycheck Auffälligkeiten", x.get("bodycheck_text")),
        ("Unterkühlung", "Ja" if x.get("unterkuehlung") else ""),
        ("Verbrennung", "Ja" if x.get("verbrennung") else ""),
    ])
    if trauma_findings:
        text += "TRAUMA-LOKALISATIONEN\n" + ("=" * 50) + "\n"
        for finding in trauma_findings:
            if not isinstance(finding, dict):
                continue
            injuries = compact_join(finding.get("verletzungsarten", []))
            detail = compact_join([injuries, f"Blutung: {finding.get('blutung')}" if valid(finding.get("blutung")) else "", finding.get("notiz")], "; ")
            text += f"- {finding.get('region', '')} ({finding.get('side', '')}): {detail or 'markiert'}\n"
        text += "\n"
    text += add_lines("SAMPLERS", [
        ("Symptome", s.get("symptome")),
        ("Allergien", format_selected_allergies(s)),
        ("Medikamente", format_selected_medication(s)),
        ("Vorgeschichte", s.get("vorgeschichte")),
        ("Letzte Mahlzeit", format_last_meal(s)),
        ("Letzte Medikamenteneinnahme", s.get("letzte_medikamenteneinnahme")),
        ("Letzter Stuhlgang", s.get("letzter_stuhlgang")),
        ("Letzte Miktion", s.get("letzte_miktion")),
        ("Letztes Erbrechen", s.get("letztes_erbrechen")),
        ("Ereignis", s.get("ereignis")),
        ("Traumamechanismus", s.get("trauma_mechanismus")),
        ("Sturzhöhe Kategorie", s.get("sturzhoehe_kategorie")),
        ("Sturzhöhe Meter", s.get("sturzhoehe_meter")),
        ("Aufprallfläche", s.get("aufprallflaeche")),
        ("Aufprallrichtung/Körperposition", s.get("aufprallrichtung")),
        ("Schutzsysteme", s.get("schutzsysteme")),
        ("Trauma-Besonderheiten", s.get("trauma_besonderheiten")),
        ("Risikofaktoren", format_risk_factors(s)),
        ("Schwangerschaft", format_pregnancy_status(s)),
        ("Sonstiges", s.get("sonstiges")),
    ])
    text += add_lines("OPQRST", [
        ("Schmerz vorhanden", o.get("schmerz_vorhanden")),
        ("Onset / Beginn", o.get("onset")),
        ("Onset Zusatz", o.get("onset_text")),
        ("Provocation / Palliation", o.get("provocation")),
        ("Provocation Zusatz", o.get("provocation_text")),
        ("Quality", o.get("quality")),
        ("Quality Zusatz", o.get("quality_text")),
        ("Region / Radiation", o.get("region")),
        ("Ausstrahlung", o.get("radiation")),
        ("NRS", o.get("nrs") or o.get("severity")),
        ("Severity Beschreibung", o.get("severity_desc")),
        ("Time / Verlauf", o.get("zeitverlauf") or o.get("time")),
        ("Dauer", o.get("dauer")),
    ])
    text += add_lines("PSYCHE / PSYCHKG NRW", [
        ("Psychischer Zustand", psyche.get("zustand")),
        ("Orientierung", psyche.get("orientierung")),
        ("Verhalten / Kooperation", psyche.get("kooperation")),
        ("Suizidalität", psyche.get("suizidalitaet")),
        ("Eigengefährdung", psyche.get("eigengefaehrdung")),
        ("Fremdgefährdung", psyche.get("fremdgefaehrdung")),
        ("Einwilligungsfähigkeit", psyche.get("einwilligungsfaehigkeit")),
        ("Aufnahme / Unterbringungsweg", psyche.get("unterbringungsweg")),
        ("Veranlasst durch", psyche.get("veranlasst_durch")),
        ("Ärztliches Zeugnis / Beschluss", psyche.get("nachweis")),
        ("Zielklinik", psyche.get("zielklinik")),
        ("Begleitung / Sicherung", psyche.get("begleitung")),
        ("Begründung / konkrete Beobachtungen", psyche.get("begruendung")),
        ("Weitere Notizen", psyche.get("notizen")),
    ])
    text += add_lines("DIAGNOSEHILFE / VERDACHTSDIAGNOSTIK", [
        ("Leitsymptom", amls.get("leitsymptom")),
        ("Arbeitsdiagnose", amls.get("arbeitsdiagnose")),
        ("Notizen / Begründung", amls.get("notizen")),
    ])

    candidates = amls.get("custom_candidates", [])
    if isinstance(candidates, list) and candidates:
        lines = [amls_item_text(item, "hinweis") for item in candidates]
        lines = [line for line in lines if valid(line)]
        if lines:
            text += "Differenzialdiagnosen / Kandidaten\n" + ("=" * 50) + "\n"
            for line in lines:
                text += f"- {line}\n"
            text += "\n"

    excluded = amls.get("excluded", [])
    if isinstance(excluded, list) and excluded:
        lines = [amls_item_text(item, "begruendung") for item in excluded]
        lines = [line for line in lines if valid(line)]
        if lines:
            text += "Zurückgestellte Diagnosen\n" + ("=" * 50) + "\n"
            for line in lines:
                text += f"- {line}\n"
            text += "\n"

    text += add_lines("SINNHAFT-ÜBERGABE", build_sinnhaft_rows(patient))
    text += add_lines("ÜBERGABE FREITEXT", [
        ("Übergabe Ziel", handover.get("ziel")),
        ("Übergabe Text", handover.get("text")),
        ("Lagerung / Transfertechnik", handover.get("lagerung")),
        ("Wertsachen / Eigentum", handover.get("wertsachen")),
        ("Krankenkassenkarte", handover.get("krankenkassenkarte")),
        ("Patientenunterlagen / Medikamente", handover.get("unterlagen")),
        ("Begleitperson / Angehörige", handover.get("begleitperson")),
        ("Besonderheiten bei Übergabe", handover.get("besonderheiten")),
    ])

    timeline = measures.get("timeline", [])
    if isinstance(timeline, list) and timeline:
        text += "MAßNAHMEN\n" + ("=" * 50) + "\n"
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

    text += add_lines("REANIMATION", [
        ("Durchgeführt", "Ja" if reanimation.get("active") else ""),
        ("CPR-Beginn", reanimation.get("cpr_start")),
        ("CPR-Ende / Übergabe", reanimation.get("cpr_end")),
        ("Initialrhythmus", reanimation.get("initial_rhythm")),
        ("ROSC", reanimation.get("rosc")),
        ("ROSC-Zeit", reanimation.get("rosc_time")),
        ("No-flow-Zeit", reanimation.get("no_flow")),
        ("Low-flow-Zeit", reanimation.get("low_flow")),
        ("Mechanische Reanimationshilfe", "Ja" if reanimation.get("mechanical_cpr") else ""),
        ("Atemweg / Beatmung", reanimation.get("airway")),
        ("Zugang", reanimation.get("access")),
        ("Medikamente während CPR", reanimation.get("meds")),
        ("Notarzt alarmiert", reanimation.get("notarzt_alarm")),
        ("Notarzt eingetroffen", reanimation.get("notarzt_arrival")),
        ("Notarzt übernimmt", reanimation.get("notarzt_takeover")),
        ("Ausgang", reanimation.get("outcome")),
        ("Notizen", reanimation.get("notes")),
    ])

    shocks = reanimation.get("shocks", [])
    if isinstance(shocks, list) and shocks:
        text += "DEFIBRILLATIONEN\n" + ("=" * 50) + "\n"
        for index, item in enumerate(shocks, start=1):
            if isinstance(item, dict):
                line = compact_join([
                    f"{index}. Schock",
                    item.get("zeit"),
                    f"{item.get('energie')} J" if valid(item.get("energie")) else "",
                    item.get("rhythmus"),
                ], " - ")
                if valid(line):
                    text += f"- {line}\n"
            elif valid(item):
                text += f"- {item}\n"
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


class NanaPDF(FPDF):
    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(92, 106, 122)
        self.cell(0, 5, pdf_safe(f"NANA Dokumentationsentwurf · Seite {self.page_no()}"), align="C")


def write_pdf_line(pdf, line, height=5):
    safe_line = pdf_safe(line)
    if not safe_line.strip():
        pdf.ln(2)
        return
    if len(safe_line) >= 10 and set(safe_line.strip()) == {"="}:
        return
    max_chars = 92
    while safe_line:
        part = safe_line[:max_chars]
        safe_line = safe_line[max_chars:]
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, height, part)


def write_pdf_section_title(pdf, title):
    if pdf.get_y() > 250:
        pdf.add_page()
    pdf.ln(2)
    pdf.set_fill_color(225, 236, 249)
    pdf.set_text_color(8, 20, 38)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 8, pdf_safe(title), ln=True, fill=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(24, 37, 52)


def write_pdf_protocol_text(pdf, protocol_text):
    lines = str(protocol_text or "").splitlines()
    for index, line in enumerate(lines):
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if line.strip() and len(next_line.strip()) >= 10 and set(next_line.strip()) == {"="}:
            write_pdf_section_title(pdf, line.strip())
            continue
        if len(line.strip()) >= 10 and set(line.strip()) == {"="}:
            continue
        if line.startswith("- "):
            pdf.set_text_color(34, 62, 92)
            write_pdf_line(pdf, f"  {line}", 4.8)
            pdf.set_text_color(24, 37, 52)
            continue
        if ": " in line:
            label, value = line.split(": ", 1)
            pdf.set_font("Helvetica", "B", 8.7)
            pdf.set_text_color(8, 20, 38)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(46, 4.8, pdf_safe(label))
            y_after_label = pdf.get_y()
            pdf.set_xy(pdf.l_margin + 48, y_after_label - 4.8)
            pdf.set_font("Helvetica", "", 8.7)
            pdf.set_text_color(24, 37, 52)
            pdf.multi_cell(0, 4.8, pdf_safe(value))
            continue
        pdf.set_font("Helvetica", "", 8.7)
        write_pdf_line(pdf, line, 4.8)


def write_pdf_metadata(pdf, metadata):
    documented_metadata = [(label, value) for label, value in metadata.items() if valid(value)]
    if not documented_metadata:
        return

    pdf.ln(2)
    for label, value in documented_metadata:
        if pdf.get_y() > 250:
            pdf.add_page()

        width = pdf.w - pdf.l_margin - pdf.r_margin
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(68, 82, 98)
        pdf.cell(31, 4.8, pdf_safe(f"{label}:"))

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(20, 31, 48)
        pdf.multi_cell(width - 31, 4.8, pdf_safe(str(value)))


def build_pdf_bytes(title, protocol_text, metadata=None):
    metadata = metadata or {}
    pdf = NanaPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_fill_color(8, 20, 38)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 13, pdf_safe("NANA"), ln=True, fill=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 7, pdf_safe("Notfall-Aufzeichnungs- und Nachbearbeitungs-Assistent · Rettungsdienst-Protokoll"), ln=True, fill=True)

    pdf.ln(4)
    pdf.set_text_color(20, 31, 48)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, pdf_safe(title), ln=True)

    pdf.set_fill_color(246, 249, 252)
    pdf.set_font("Helvetica", "", 9)
    write_pdf_metadata(pdf, metadata)

    pdf.ln(4)
    write_pdf_protocol_text(pdf, protocol_text)

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(92, 106, 122)
    pdf.multi_cell(
        0,
        5,
        pdf_safe("Hinweis: Dokumentationsentwurf. Vor medizinischer, rechtlicher oder abrechnungsrelevanter Weitergabe fachlich prüfen."),
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
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


def json_attachment(filename, payload):
    safe_filename = "".join(char for char in filename if char.isalnum() or char in ["-", "_", "."])
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


ICD10_BFARM_BASE_URL = "https://klassifikationen.bfarm.de/icd-10-gm/kode-suche/htmlgm2026/"
ICD10_STATIC_CATALOG_PATH = Path(__file__).resolve().parents[1] / "assets" / "icd10_gm_2026.json"
ICD10_CATALOG_CACHE = {"loaded_at": None, "entries": [], "source": "Fallback", "error": ""}
ICD10_FALLBACK_ENTRIES = [
    {"code": "A00-B99", "diagnosis": "Bestimmte infektiöse und parasitäre Krankheiten"},
    {"code": "C00-D48", "diagnosis": "Neubildungen"},
    {"code": "D50-D90", "diagnosis": "Krankheiten des Blutes und der blutbildenden Organe sowie Immunstörungen"},
    {"code": "E00-E90", "diagnosis": "Endokrine, Ernährungs- und Stoffwechselkrankheiten"},
    {"code": "F00-F99", "diagnosis": "Psychische und Verhaltensstörungen"},
    {"code": "G00-G99", "diagnosis": "Krankheiten des Nervensystems"},
    {"code": "H00-H59", "diagnosis": "Krankheiten des Auges und der Augenanhangsgebilde"},
    {"code": "H60-H95", "diagnosis": "Krankheiten des Ohres und des Warzenfortsatzes"},
    {"code": "I00-I99", "diagnosis": "Krankheiten des Kreislaufsystems"},
    {"code": "J00-J99", "diagnosis": "Krankheiten des Atmungssystems"},
    {"code": "K00-K93", "diagnosis": "Krankheiten des Verdauungssystems"},
    {"code": "L00-L99", "diagnosis": "Krankheiten der Haut und der Unterhaut"},
    {"code": "M00-M99", "diagnosis": "Krankheiten des Muskel-Skelett-Systems und des Bindegewebes"},
    {"code": "N00-N99", "diagnosis": "Krankheiten des Urogenitalsystems"},
    {"code": "O00-O99", "diagnosis": "Schwangerschaft, Geburt und Wochenbett"},
    {"code": "P00-P96", "diagnosis": "Bestimmte Zustände mit Ursprung in der Perinatalperiode"},
    {"code": "Q00-Q99", "diagnosis": "Angeborene Fehlbildungen, Deformitäten und Chromosomenanomalien"},
    {"code": "R00-R99", "diagnosis": "Symptome und abnorme klinische und Laborbefunde"},
    {"code": "S00-T98", "diagnosis": "Verletzungen, Vergiftungen und andere Folgen äußerer Ursachen"},
    {"code": "U00-U99", "diagnosis": "Schlüsselnummern für besondere Zwecke"},
    {"code": "V01-Y84", "diagnosis": "Äußere Ursachen von Morbidität und Mortalität"},
    {"code": "Z00-Z99", "diagnosis": "Faktoren, die den Gesundheitszustand beeinflussen"},
]
ICD10_LOCAL = {
    "I21": "Akuter Myokardinfarkt",
    "I20": "Angina pectoris",
    "I63": "Hirninfarkt",
    "I64": "Schlaganfall, nicht als Blutung oder Infarkt bezeichnet",
    "G40": "Epilepsie",
    "R07": "Hals- und Brustschmerzen",
    "R55": "Synkope und Kollaps",
    "J44": "Sonstige chronische obstruktive Lungenkrankheit",
    "J45": "Asthma bronchiale",
    "E11": "Diabetes mellitus, Typ 2",
    "S06": "Intrakranielle Verletzung",
    "T14": "Verletzung an einer nicht näher bezeichneten Körperregion",
    "O80": "Spontangeburt eines Einlings",
    "F10": "Psychische und Verhaltensstörungen durch Alkohol",
    "F45": "Somatoforme Störungen",
}


def normalize_icd_code(value):
    code = re.sub(r"\s+", "", str(value or "")).upper()
    code = code.rstrip("!+*#")
    if code.endswith(".-"):
        return code[:-2]
    if code.endswith("-"):
        return code[:-1]
    return code


def clean_icd_title(value):
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def load_static_icd10_catalog(now):
    if not ICD10_STATIC_CATALOG_PATH.exists():
        return None
    try:
        payload = json.loads(ICD10_STATIC_CATALOG_PATH.read_text(encoding="utf-8"))
        entries = [
            {
                "code": normalize_icd_code(item.get("code", "")),
                "diagnosis": str(item.get("diagnosis", "")).strip(),
                "source_url": item.get("source_url", ""),
            }
            for item in payload.get("entries", [])
            if item.get("code") and item.get("diagnosis")
        ]
        entries = sorted(entries, key=lambda item: item["code"])
        if entries:
            return {
                "loaded_at": now,
                "entries": entries,
                "source": payload.get("source") or "BfArM ICD-10-GM 2026",
                "error": "",
            }
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return {"loaded_at": now, "entries": [], "source": "Fallback", "error": str(exc)}
    return None


def load_icd10_catalog(force=False):
    now = datetime.utcnow()
    loaded_at = ICD10_CATALOG_CACHE.get("loaded_at")
    if (
        not force
        and loaded_at
        and ICD10_CATALOG_CACHE.get("entries")
        and now - loaded_at < timedelta(days=7)
    ):
        return ICD10_CATALOG_CACHE

    static_catalog = load_static_icd10_catalog(now)
    if static_catalog and static_catalog.get("entries"):
        ICD10_CATALOG_CACHE.update(static_catalog)
        return ICD10_CATALOG_CACHE
    if static_catalog and static_catalog.get("error"):
        ICD10_CATALOG_CACHE.update(static_catalog)

    try:
        request = urllib.request.Request(ICD10_BFARM_BASE_URL, headers={"User-Agent": "NANA-RD-Protokoll/1.0"})
        with urllib.request.urlopen(request, timeout=12) as response:
            index_page = response.read().decode("utf-8", errors="replace")
        block_files = sorted(set(re.findall(r'href="(block-[a-z0-9-]+\.htm)"', index_page, flags=re.IGNORECASE)))
        entries_by_code = {}
        for block_file in block_files:
            block_url = ICD10_BFARM_BASE_URL + block_file
            block_request = urllib.request.Request(block_url, headers={"User-Agent": "NANA-RD-Protokoll/1.0"})
            with urllib.request.urlopen(block_request, timeout=12) as response:
                block_page = response.read().decode("utf-8", errors="replace")
            for match in re.finditer(
                r'<(?:h[4-6]|li)[^>]*>\s*<a(?=[^>]*class="code")[^>]*>\s*([A-Z][0-9]{2}(?:\.[0-9A-Z]{0,2})?-?)\s*</a>\s*<span(?=[^>]*class="label")[^>]*>(.*?)</span>\s*</(?:h[4-6]|li)>',
                block_page,
                flags=re.IGNORECASE | re.DOTALL,
            ):
                code = normalize_icd_code(match.group(1))
                diagnosis = clean_icd_title(match.group(2))
                if code and diagnosis:
                    entries_by_code[code] = {"code": code, "diagnosis": diagnosis, "source_url": block_url}
        entries = sorted(entries_by_code.values(), key=lambda item: item["code"])
        if entries:
            ICD10_CATALOG_CACHE.update({"loaded_at": now, "entries": entries, "source": "BfArM ICD-10-GM 2026", "error": ""})
            return ICD10_CATALOG_CACHE
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        ICD10_CATALOG_CACHE.update({"loaded_at": now, "entries": [], "source": "Fallback", "error": str(exc)})

    fallback = [{"code": code, "diagnosis": diagnosis, "source_url": ""} for code, diagnosis in ICD10_LOCAL.items()]
    ICD10_CATALOG_CACHE["entries"] = ICD10_FALLBACK_ENTRIES + fallback
    return ICD10_CATALOG_CACHE


def search_icd_catalog(query="", limit=80):
    catalog = load_icd10_catalog()
    entries = catalog.get("entries") or []
    raw_query = str(query or "").strip()
    if not raw_query:
        return entries[:limit], catalog

    normalized_query = normalize_icd_code(raw_query)
    words = [word.casefold() for word in re.split(r"\s+", raw_query) if word]
    results = []
    for entry in entries:
        code = entry.get("code", "")
        diagnosis = entry.get("diagnosis", "")
        haystack = f"{code} {diagnosis}".casefold()
        if normalized_query and code.startswith(normalized_query):
            results.append(entry)
        elif words and all(word in haystack for word in words):
            results.append(entry)
        if len(results) >= limit:
            break
    return results, catalog


def lookup_icd_local(code):
    normalized = normalize_icd_code(code)
    if not normalized:
        return {"code": "", "diagnosis": "", "found": False}
    entries, catalog = search_icd_catalog(normalized, limit=200)
    for entry in entries:
        if entry.get("code") == normalized:
            return {
                "code": normalized,
                "matched_code": entry.get("code"),
                "diagnosis": entry.get("diagnosis", ""),
                "found": True,
                "source": catalog.get("source"),
                "source_url": entry.get("source_url", ""),
            }
    candidates = [normalized]
    if "." in normalized:
        candidates.append(normalized.split(".", 1)[0])
    candidates.append(normalized[:3])
    for candidate in candidates:
        if candidate in ICD10_LOCAL:
            return {"code": normalized, "matched_code": candidate, "diagnosis": ICD10_LOCAL[candidate], "found": True, "source": "Fallback"}
    return {"code": normalized, "matched_code": normalized[:3], "diagnosis": "Nicht im ICD10-Katalog gefunden", "found": False, "source": catalog.get("source")}


def serialize_hospital(hospital):
    item = dict(hospital)
    item["categories"] = sorted(list(item.get("categories", [])))
    coords = item.get("coords")
    if coords:
        item["coords"] = list(coords)
    return item


def hospital_records():
    custom = get_app_setting("custom_hospitals", []) or []
    defaults = [serialize_hospital(item) for item in HOSPITALS]
    return defaults + [item for item in custom if isinstance(item, dict)]


def ranked_hospitals(town, category):
    origin = TOWNS.get(town)
    matches = []
    for hospital in hospital_records():
        categories = hospital.get("categories", [])
        if category and category not in categories:
            continue
        item = dict(hospital)
        if origin and item.get("coords"):
            item["distance_km"] = round(distance_km(origin, tuple(item["coords"])), 1)
        else:
            item["distance_km"] = None
        if item.get("estimated_minutes") is None and item.get("distance_km") is not None:
            item["estimated_minutes"] = max(5, int(round(item["distance_km"] * 1.4)))
        matches.append(item)
    return sorted(matches, key=lambda item: item.get("distance_km") if item.get("distance_km") is not None else 9999)


def load_employee_patient_draft(employee):
    store = load_case_draft_store()
    draft = store.get("drafts", {}).get(employee["id"], {})
    patient = default_patient_case()
    if isinstance(draft.get("patient"), dict):
        patient.update(draft["patient"])
    return patient


def save_employee_patient_draft(employee, patient):
    store = load_case_draft_store()
    existing_draft = store.get("drafts", {}).get(employee["id"], {})
    pending_dispatch = existing_draft.get("pending_dispatch") if isinstance(existing_draft, dict) else None
    store.setdefault("drafts", {})[employee["id"]] = {
        "updated_at": local_now().isoformat(timespec="seconds"),
        "patient": patient,
        "seite": "Schnittstellen",
        "visited_pages": ["Schnittstellen"],
        "workflow_manual_completion": {},
        "protocol_generated": False,
        "generated_protocol_text": "",
        "xabcde_selected": "A",
    }
    if isinstance(pending_dispatch, dict):
        store["drafts"][employee["id"]]["pending_dispatch"] = pending_dispatch
    save_case_draft_store(store)
    return store["drafts"][employee["id"]]["updated_at"]


def audit(action, employee=None, entity_type="", entity_id="", details=None):
    employee = employee or {}
    write_audit_event({
        "timestamp": local_now().isoformat(timespec="seconds"),
        "employee_id": employee.get("id", ""),
        "employee_name": employee.get("name", ""),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": redact_audit_details(details or {}),
    })


def redact_audit_details(details):
    if not isinstance(details, dict):
        return {}
    allowed_keys = {
        "approach_fields",
        "case_ids",
        "count",
        "critical_count",
        "criticals",
        "cutoff",
        "date",
        "deleted",
        "external_maps_enabled",
        "fields",
        "force_finish",
        "format",
        "had_pending",
        "kind",
        "level",
        "locked_until",
        "patch_notes",
        "pending_id",
        "quality_score",
        "qualification",
        "reset_password",
        "restore_shift",
        "retention_days",
        "role",
        "score",
        "security_log_retention_days",
        "source",
        "status",
        "warning_count",
        "warnings",
    }
    redacted = {}
    for key, value in details.items():
        if key not in allowed_keys:
            continue
        if isinstance(value, str):
            redacted[key] = short_text(value, 160)
        elif hasattr(value, "isoformat"):
            redacted[key] = value.isoformat()
        elif isinstance(value, list):
            redacted[key] = [short_text(item, 80) for item in value[:30]]
        elif isinstance(value, (bool, int, float)) or value is None:
            redacted[key] = value
        else:
            redacted[key] = short_text(value, 160)
    return redacted


def short_text(value, limit=240):
    return str(value or "").strip()[:limit]


def hashed_identifier(value, length=20):
    raw = str(value or "").strip()
    if not raw:
        return ""
    salt = os.getenv("NANA_LOG_SALT", os.getenv("NANA_DATA_KEY", "nana-local-log-salt"))
    digest = hashlib.sha256(f"{salt}:{raw}".encode("utf-8")).hexdigest()
    return digest[:length]


def session_cookie_secure():
    return production_mode()


def set_session_cookie(response: Response, token, csrf_token=""):
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=SESSION_MINUTES * 60,
        httponly=True,
        secure=session_cookie_secure(),
        samesite="strict" if production_mode() else "lax",
        path="/",
    )
    if csrf_token:
        response.set_cookie(
            CSRF_COOKIE_NAME,
            csrf_token,
            max_age=SESSION_MINUTES * 60,
            httponly=False,
            secure=session_cookie_secure(),
            samesite="strict" if production_mode() else "lax",
            path="/",
        )


def clear_session_cookie(response: Response):
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


def new_session_for_employee(response: Response, employee):
    token = new_token()
    csrf_token = new_token()
    save_auth_session(token, employee["id"], expires_at(SESSION_MINUTES), csrf_token=csrf_token)
    set_session_cookie(response, token, csrf_token)
    return token


def assert_cookie_csrf(request: Request, session):
    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    expected = session.get("csrf_token", "")
    supplied_cookie = request.cookies.get(CSRF_COOKIE_NAME, "")
    supplied_header = request.headers.get("x-nana-csrf", "")
    if (
        not expected
        or not secrets.compare_digest(supplied_cookie, expected)
        or not secrets.compare_digest(supplied_header, expected)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF-Schutz fehlgeschlagen.")


def coarse_user_agent(value):
    raw = short_text(value, 180)
    if not raw:
        return ""
    browser = "Browser"
    if "Edg/" in raw:
        browser = "Edge"
    elif "Chrome/" in raw:
        browser = "Chrome"
    elif "Firefox/" in raw:
        browser = "Firefox"
    elif "Safari/" in raw:
        browser = "Safari"
    os_label = "Unbekannt"
    if "Windows" in raw:
        os_label = "Windows"
    elif "Android" in raw:
        os_label = "Android"
    elif "iPhone" in raw or "iPad" in raw:
        os_label = "iOS"
    elif "Mac OS" in raw:
        os_label = "macOS"
    return f"{browser} / {os_label}"


def client_ip(request: Request):
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return short_text(anonymize_ip(forwarded_for.split(",")[0]), 80)
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return hashed_identifier(anonymize_ip(real_ip))
    return hashed_identifier(anonymize_ip(request.client.host if request.client else ""))


def anonymize_ip(value):
    ip = str(value or "").strip()
    if not ip:
        return ""
    if ":" in ip:
        parts = ip.split(":")
        return ":".join(parts[:4] + ["0000"] * max(0, 8 - len(parts[:4])))
    parts = ip.split(".")
    if len(parts) == 4 and all(part.isdigit() for part in parts):
        return ".".join(parts[:3] + ["0"])
    return short_text(ip, 24)


def auth_failure_key(employee_id, request: Request):
    return f"{short_text(employee_id, 80).lower()}:{client_ip(request)}"


def assert_auth_not_locked(employee_id, request: Request):
    key = auth_failure_key(employee_id, request)
    entry = get_auth_failure(key)
    if not entry:
        return
    locked_until = parse_stored_datetime(entry.get("locked_until"))
    if locked_until and not is_expired(locked_until):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Zu viele Fehlversuche. Bitte später erneut versuchen.",
        )
    if locked_until:
        delete_auth_failure(key)


def register_auth_failure(employee_id, request: Request):
    key = auth_failure_key(employee_id, request)
    entry = get_auth_failure(key) or {"count": 0, "first_failed_at": local_now().isoformat(timespec="seconds")}
    entry["count"] = int(entry.get("count", 0)) + 1
    entry["last_failed_at"] = local_now().isoformat(timespec="seconds")
    if entry["count"] >= AUTH_MAX_FAILURES:
        entry["locked_until"] = expires_at(AUTH_LOCK_MINUTES)
    save_auth_failure(key, entry)
    return entry


def clear_auth_failures(employee_id, request: Request):
    delete_auth_failure(auth_failure_key(employee_id, request))


def record_login_event(employee, payload, request: Request, source="login"):
    user_agent = coarse_user_agent(getattr(payload, "user_agent", "") or request.headers.get("user-agent", ""))
    write_login_event({
        "timestamp": local_now().isoformat(timespec="seconds"),
        "employee_id": employee.get("id", ""),
        "employee_name": employee.get("name", ""),
        "device_id": hashed_identifier(getattr(payload, "device_id", "")),
        "device_name": short_text(getattr(payload, "device_name", ""), 160),
        "user_agent": user_agent,
        "ip_address": client_ip(request),
        "source": short_text(source, 40),
    })


def public_employee(employee):
    return {
        "id": employee.get("id", ""),
        "name": employee.get("name", ""),
        "role": employee.get("role", "employee"),
        "qualification": employee.get("qualification", ""),
        "station": employee.get("station", ""),
        "vehicle_scope": employee.get("vehicle_scope", ""),
        "on_shift": bool(employee.get("on_shift")),
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
    return get_employee(employee_id, active_only=True)


def current_employee(request: Request, response: Response, authorization: str | None = Header(default=None)):
    token = ""
    cookie_authenticated = False
    bearer_allowed = not production_mode() or os.getenv("NANA_ENABLE_BEARER_AUTH", "").strip() == "1"
    if bearer_allowed and authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    if not token:
        token = request.cookies.get(AUTH_COOKIE_NAME, "").strip()
        cookie_authenticated = bool(token)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nicht angemeldet.")

    session = get_auth_session(token)
    session_expires_at = parse_stored_datetime(session.get("expires_at")) if session else None
    if not session or not session_expires_at or is_expired(session_expires_at):
        delete_auth_session(token)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sitzung abgelaufen.")
    if cookie_authenticated:
        assert_cookie_csrf(request, session)

    employee = find_employee(session.get("employee_id"))
    if not employee:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Profil nicht gefunden.")

    save_auth_session(token, employee["id"], expires_at(SESSION_MINUTES))
    set_session_cookie(response, token, session.get("csrf_token", ""))
    return employee


def require_admin(employee=Depends(current_employee)):
    if employee.get("role") != "admin":
        audit("api_admin_access_denied", employee=employee)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nur für Admins freigegeben.")
    return employee


def normalize_employee_role(role):
    return role if role in EMPLOYEE_ROLES else "employee"


def normalize_employee_qualification(qualification):
    value = (qualification or "").strip()
    return value if value in EMPLOYEE_QUALIFICATIONS else ""


def normalize_employee_station(station):
    value = short_text(station, 120).strip()
    return value if value in EMPLOYEE_STATIONS else ""


def normalize_employee_vehicle_scope(vehicle_scope):
    value = (vehicle_scope or "").strip()
    return value if value in EMPLOYEE_VEHICLE_SCOPES else ""


def parse_bool_flag(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "ja", "yes", "y", "aktiv", "dienst"}


def employee_csv_response(employees):
    output = io.StringIO()
    fieldnames = ["id", "name", "role", "qualification", "station", "vehicle_scope", "on_shift", "active"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for item in employees:
        writer.writerow({
            "id": item.get("id", ""),
            "name": item.get("name", ""),
            "role": item.get("role", "employee"),
            "qualification": item.get("qualification", ""),
            "station": item.get("station", ""),
            "vehicle_scope": item.get("vehicle_scope", ""),
            "on_shift": "1" if item.get("on_shift") else "0",
            "active": "1" if item.get("active", True) else "0",
        })
    return Response(
        output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="nana-mitarbeiter.csv"'},
    )


def password_policy_errors(password):
    value = str(password or "")
    errors = []
    if len(value) < 14:
        errors.append("mindestens 14 Zeichen")
    if not re.search(r"[a-zäöüß]", value):
        errors.append("Kleinbuchstaben")
    if not re.search(r"[A-ZÄÖÜ]", value):
        errors.append("Grossbuchstaben")
    if not re.search(r"\d", value):
        errors.append("Zahlen")
    if not re.search(r"[^A-Za-zÄÖÜäöüß0-9]", value):
        errors.append("Sonderzeichen")
    return errors


def assert_strong_password(password):
    errors = password_policy_errors(password)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Passwort muss enthalten: {', '.join(errors)}.",
        )


@app.on_event("startup")
def startup():
    init_database()
    purge_expired_auth_state(local_now().isoformat(timespec="seconds"))
    encrypt_existing_patient_data()


@app.get("/api/health")
def health():
    database = database_health_status()
    frontend_ready = (FRONTEND_DIST / "index.html").exists()
    encryption = encryption_status()
    bearer_allowed = not production_mode() or os.getenv("NANA_ENABLE_BEARER_AUTH", "").strip() == "1"
    return {
        "status": "ok" if database.get("ok") else "degraded",
        "app": "NANA",
        "environment": NANA_ENV,
        "release": clean_text(NANA_RELEASE_SHA, 80),
        "database": database,
        "frontend_ready": frontend_ready,
        "encryption": {
            "enabled": bool(encryption.get("enabled")),
            "key_source": encryption.get("key_source", ""),
        },
        "security": {
            "bearer_auth_enabled": bearer_allowed,
            "trusted_hosts_configured": bool(allowed_hosts),
            "max_request_body_bytes": MAX_REQUEST_BODY_BYTES,
        },
        "ruleset_version": MEDICAL_RULESET_VERSION,
    }


@app.get("/api/auth/employees")
def employees():
    store = load_employee_store()
    active = [employee for employee in store.get("employees", []) if employee.get("active", True)]
    return {"employees": [public_employee(employee) for employee in active]}


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, response: Response):
    assert_auth_not_locked(payload.employee_id, request)
    employee = find_employee(payload.employee_id)
    if not employee:
        register_auth_failure(payload.employee_id, request)
        audit("api_login_failed", details={"reason": "unknown_employee"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Anmeldung fehlgeschlagen.")

    if employee.get("must_change_password"):
        if not verify_password(payload.password, employee.get("temp_password_hash")):
            failure = register_auth_failure(payload.employee_id, request)
            audit("api_login_failed", employee=employee, details={"reason": "wrong_temporary_password"})
            if failure.get("locked_until"):
                audit("api_login_locked", employee=employee, details={"locked_until": failure["locked_until"]})
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Einmalpasswort ist falsch.")
        change_token = new_token()
        save_password_change_token(change_token, employee["id"], expires_at(PASSWORD_CHANGE_MINUTES))
        clear_auth_failures(payload.employee_id, request)
        audit("api_temporary_password_accepted", employee=employee)
        return {"status": "password_change_required", "token": change_token, "employee": public_employee(employee)}

    if not verify_password(payload.password, employee.get("password_hash")):
        failure = register_auth_failure(payload.employee_id, request)
        audit("api_login_failed", employee=employee, details={"reason": "wrong_password"})
        if failure.get("locked_until"):
            audit("api_login_locked", employee=employee, details={"locked_until": failure["locked_until"]})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Passwort ist falsch.")

    clear_auth_failures(payload.employee_id, request)
    new_session_for_employee(response, employee)
    record_login_event(employee, payload, request, source="login")
    audit("api_login_success", employee=employee, details={"role": employee.get("role", "employee")})
    return {"status": "authenticated", "employee": public_employee(employee)}


@app.post("/api/auth/reauth")
def reauth(payload: ReauthRequest, request: Request, response: Response):
    assert_auth_not_locked(payload.employee_id, request)
    employee = find_employee(payload.employee_id)
    if not employee:
        register_auth_failure(payload.employee_id, request)
        audit("api_reauth_failed", details={"reason": "unknown_employee"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Schicht konnte nicht wiederhergestellt werden.")

    if employee.get("must_change_password"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bitte einmal vollständig mit dem Einmalpasswort anmelden.")

    if not verify_password(payload.password, employee.get("password_hash")):
        failure = register_auth_failure(payload.employee_id, request)
        audit("api_reauth_failed", employee=employee, details={"reason": "wrong_password"})
        if failure.get("locked_until"):
            audit("api_reauth_locked", employee=employee, details={"locked_until": failure["locked_until"]})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Passwort ist falsch.")

    clear_auth_failures(payload.employee_id, request)
    new_session_for_employee(response, employee)
    record_login_event(employee, payload, request, source="reauth")
    audit("api_reauth_success", employee=employee, details={"restore_shift": bool(payload.restore_shift)})
    return {"status": "authenticated", "employee": public_employee(employee), "restored": True}


@app.post("/api/auth/setup-first-admin")
def setup_first_admin(payload: FirstAdminRequest, request: Request, response: Response):
    store = load_employee_store()
    if store.get("employees"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Erster Admin existiert bereits.")
    if not payload.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name fehlt.")
    assert_strong_password(payload.password)

    employee = {
        "id": new_token()[:16],
        "name": payload.name.strip(),
        "role": "admin",
        "active": True,
        "password_hash": password_hash(payload.password),
        "temp_password_hash": "",
        "must_change_password": False,
        "created_at": local_now().isoformat(timespec="seconds"),
        "password_changed_at": local_now().isoformat(timespec="seconds"),
    }
    save_employee_store({"employees": [employee]})

    new_session_for_employee(response, employee)
    record_login_event(employee, payload, request, source="first_admin")
    audit("api_first_admin_created", employee=employee)
    audit("api_login_success", employee=employee, details={"role": "admin"})
    return {"status": "authenticated", "employee": public_employee(employee)}


@app.post("/api/auth/set-password")
def set_password(payload: PasswordChangeRequest, request: Request, response: Response):
    pending = get_password_change_token(payload.token)
    pending_expires_at = parse_stored_datetime(pending.get("expires_at")) if pending else None
    if not pending or not pending_expires_at or is_expired(pending_expires_at):
        delete_password_change_token(payload.token)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Passwortwechsel ist abgelaufen.")
    assert_strong_password(payload.new_password)

    employee = get_employee(pending["employee_id"])
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profil nicht gefunden.")

    employee = update_employee_record(employee["id"], {
        "password_hash": password_hash(payload.new_password),
        "temp_password_hash": "",
        "must_change_password": False,
        "password_changed_at": local_now().isoformat(timespec="seconds"),
    })
    delete_password_change_token(payload.token)

    new_session_for_employee(response, employee)
    record_login_event(employee, payload, request, source="password_set")
    audit("api_initial_password_set", employee=employee)
    audit("api_login_success", employee=employee, details={"role": employee.get("role", "employee")})
    return {"status": "authenticated", "employee": public_employee(employee)}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, employee=Depends(current_employee), authorization: str | None = Header(default=None)):
    bearer_allowed = not production_mode() or os.getenv("NANA_ENABLE_BEARER_AUTH", "").strip() == "1"
    token = authorization.removeprefix("Bearer ").strip() if bearer_allowed and authorization else request.cookies.get(AUTH_COOKIE_NAME, "").strip()
    delete_auth_session(token)
    clear_session_cookie(response)
    audit("api_logout", employee=employee)
    return {"status": "ok"}


@app.get("/api/me")
def me(employee=Depends(current_employee)):
    return {"employee": public_employee(employee)}


@app.get("/api/privacy/settings")
def privacy_settings(employee=Depends(current_employee)):
    return {"external_maps_enabled": bool(get_app_setting("external_maps_enabled", False))}


@app.get("/api/dashboard")
def dashboard(employee=Depends(current_employee)):
    tiles = [
        {"id": "protocol", "label": "Dokumentation", "subtitle": "Einsatz dokumentieren"},
        {"id": "refusal", "label": "Verweigerung", "subtitle": "Behandlungs-/Transportablehnung"},
        {"id": "cancelled", "label": "Einsatz abgebrochen", "subtitle": "Abbruch / Nichtdurchführung"},
        {"id": "approach", "label": "Anfahrt & Lage", "subtitle": "Karten, Street View, Tempolimit"},
        {"id": "hospital", "label": "Krankenhaus Finder", "subtitle": "Geeignete Zielklinik"},
        {"id": "icd10", "label": "ICD10 Code", "subtitle": "Code dekodieren"},
        {"id": "devices", "label": "Geräte", "subtitle": "Kurzreferenzen"},
    ]
    if employee.get("role") == "admin":
        tiles.append({"id": "interfaces", "label": "Schnittstellen", "subtitle": "Import und Export"})
        tiles.append({"id": "admin", "label": "Admin", "subtitle": "Sicherheit und Verwaltung"})
    return {"employee": public_employee(employee), "tiles": tiles}


@app.get("/api/dispatch/pending")
def pending_dispatch(employee=Depends(current_employee)):
    return {"pending": load_employee_pending_dispatch(employee)}


@app.post("/api/dispatch/pending/accept")
def accept_pending_dispatch(employee=Depends(current_employee)):
    pending = load_employee_pending_dispatch(employee)
    if not pending:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kein wartender Leitstellen-Einsatz vorhanden.")
    patient = load_employee_patient_draft(employee)
    patient, approach = patient_with_dispatch(patient, pending.get("imported", {}))
    updated_at = save_employee_patient_draft(employee, sanitize_pilot_patient(patient))
    clear_employee_pending_dispatch(employee)
    audit(
        "api_dispatch_pending_accepted",
        employee=employee,
        entity_type="case_draft",
        details={
            "fields": sorted((pending.get("imported") or {}).keys()),
            "approach_fields": sorted(approach.keys()),
        },
    )
    return {
        "status": "accepted",
        "patient": patient,
        "approach": approach,
        "updated_at": updated_at,
    }


@app.delete("/api/dispatch/pending")
def dismiss_pending_dispatch(employee=Depends(current_employee)):
    pending = load_employee_pending_dispatch(employee)
    clear_employee_pending_dispatch(employee)
    audit(
        "api_dispatch_pending_dismissed",
        employee=employee,
        entity_type="case_draft",
        details={"had_pending": bool(pending)},
    )
    return {"status": "dismissed"}


@app.get("/api/announcements")
def announcements(employee=Depends(current_employee)):
    store = announcements_store()
    own_feedback = [
        public_feedback_item(item)
        for item in store.get("feedback", [])
        if item.get("employee_id") == employee.get("id")
    ]
    return {
        "patch_notes": [public_announcement_item(item) for item in store.get("patch_notes", [])],
        "planned_updates": [public_announcement_item(item) for item in store.get("planned_updates", [])],
        "feedback": own_feedback,
    }


@app.post("/api/feedback")
def create_feedback(payload: FeedbackRequest, employee=Depends(current_employee)):
    title = clean_text(payload.title, 160)
    message = clean_text(payload.message, 4000)
    kind = clean_text(payload.kind, 40) or "Bug"
    if kind not in {"Bug", "Wunsch"}:
        kind = "Bug"
    if not title or not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Titel und Beschreibung sind erforderlich.")

    store = announcements_store()
    item = {
        "id": new_token()[:16],
        "kind": kind,
        "title": title,
        "message": message,
        "status": "offen",
        "answer": "",
        "created_at": local_now().isoformat(timespec="seconds"),
        "answered_at": "",
        "employee_id": employee.get("id", ""),
        "employee_name": employee.get("name", ""),
    }
    store.setdefault("feedback", []).insert(0, item)
    save_announcements_store(store)
    audit("api_feedback_created", employee=employee, entity_type="feedback", entity_id=item["id"], details={"kind": kind})
    return {"status": "created", "item": public_feedback_item(item)}


@app.get("/api/admin/announcements")
def admin_announcements(employee=Depends(require_admin)):
    store = announcements_store()
    return {
        "patch_notes": [public_announcement_item(item) for item in store.get("patch_notes", [])],
        "planned_updates": [public_announcement_item(item) for item in store.get("planned_updates", [])],
        "feedback": [public_feedback_item(item, include_identity=True) for item in store.get("feedback", [])],
    }


@app.get("/api/admin/release")
def admin_release(employee=Depends(require_admin)):
    draft = release_patch_note_draft()
    return {
        "sha": clean_text(NANA_RELEASE_SHA, 80),
        "deployed_at": clean_text(NANA_RELEASE_DATE, 80),
        "label": clean_text(draft["published_at"], 80),
        "patch_note": draft,
    }


@app.put("/api/admin/announcements")
def update_announcements(payload: AnnouncementsRequest, employee=Depends(require_admin)):
    store = announcements_store()

    def normalize_items(items):
        normalized = []
        for item in items:
            title = clean_text(item.title, 160)
            body = clean_text(item.body, 4000)
            published_at = clean_text(item.published_at, 80)
            if not title and not body:
                continue
            normalized.append({
                "id": new_token()[:16],
                "title": title or "Ohne Titel",
                "body": body,
                "published_at": published_at or local_now().isoformat(timespec="seconds"),
            })
        return normalized[:50]

    store["patch_notes"] = normalize_items(payload.patch_notes)
    store["planned_updates"] = normalize_items(payload.planned_updates)
    save_announcements_store(store)
    audit("api_announcements_updated", employee=employee, details={"patch_notes": len(store["patch_notes"]), "planned_updates": len(store["planned_updates"])})
    return {
        "status": "saved",
        "patch_notes": [public_announcement_item(item) for item in store["patch_notes"]],
        "planned_updates": [public_announcement_item(item) for item in store["planned_updates"]],
    }


@app.put("/api/admin/feedback/{feedback_id}")
def update_feedback(feedback_id: str, payload: FeedbackUpdateRequest, employee=Depends(require_admin)):
    store = announcements_store()
    target = None
    for item in store.get("feedback", []):
        if item.get("id") == feedback_id:
            target = item
            break
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meldung nicht gefunden.")

    status_value = clean_text(payload.status, 40) or "offen"
    if status_value not in {"offen", "in Arbeit", "beantwortet", "erledigt", "abgelehnt"}:
        status_value = "offen"
    target["status"] = status_value
    target["answer"] = clean_text(payload.answer, 4000)
    target["answered_at"] = local_now().isoformat(timespec="seconds") if target["answer"] else ""
    save_announcements_store(store)
    audit("api_feedback_updated", employee=employee, entity_type="feedback", entity_id=feedback_id, details={"status": status_value})
    return {"status": "saved", "item": public_feedback_item(target, include_identity=True)}


@app.get("/api/hospitals")
def hospitals(town: str = "Borken", category: str = "Allgemeine Notaufnahme", employee=Depends(current_employee)):
    selected_town = town if town in TOWNS else "Borken"
    selected_category = category if category in CATEGORIES else "Allgemeine Notaufnahme"
    return {
        "towns": sorted(TOWNS.keys()),
        "categories": CATEGORIES,
        "town": selected_town,
        "category": selected_category,
        "hospitals": ranked_hospitals(selected_town, selected_category),
    }


@app.post("/api/admin/hospitals")
def admin_save_hospital(payload: HospitalSaveRequest, employee=Depends(require_admin)):
    hospital_id = payload.id or new_token()[:12]
    existing = get_app_setting("custom_hospitals", []) or []
    next_hospital = {
        "id": hospital_id,
        "name": payload.name.strip(),
        "country": payload.country.strip().upper() or "DE",
        "address": payload.address.strip(),
        "town": payload.town.strip(),
        "phone": payload.phone.strip(),
        "categories": [item for item in payload.categories if item in CATEGORIES],
        "estimated_minutes": payload.estimated_minutes,
        "source": payload.source.strip(),
    }
    if not next_hospital["name"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Klinikname fehlt.")
    updated = [item for item in existing if item.get("id") != hospital_id]
    updated.append(next_hospital)
    set_app_setting("custom_hospitals", updated)
    audit("api_hospital_saved", employee=employee, entity_type="hospital", entity_id=hospital_id)
    return {"status": "saved", "hospital": next_hospital}


@app.get("/api/devices")
def devices(employee=Depends(current_employee)):
    return {
        "devices": [
            {
                "name": name,
                "icon": guide.get("icon", ""),
                "model_note": guide.get("model_note", ""),
                "source_label": guide.get("source_label", ""),
                "source_url": guide.get("source_url", ""),
                "topics": guide.get("topics", {}),
                "topic_actions": guide.get("topic_actions", {}),
            }
            for name, guide in DEVICE_GUIDES.items()
        ]
    }


@app.post("/api/icd10/lookup")
def icd10_lookup(payload: IcdLookupRequest, employee=Depends(current_employee)):
    result = lookup_icd_local(payload.code)
    audit("api_icd10_lookup", employee=employee, details={"code": result.get("code"), "found": result.get("found")})
    return result


@app.post("/api/icd10/search")
def icd10_search(payload: IcdSearchRequest, employee=Depends(current_employee)):
    limit = max(1, min(int(payload.limit or 80), 120))
    entries, catalog = search_icd_catalog(payload.query, limit=limit)
    audit("api_icd10_search", employee=employee, details={"query": payload.query, "count": len(entries), "source": catalog.get("source")})
    return {
        "entries": entries,
        "source": catalog.get("source"),
        "count": len(entries),
        "catalog_size": len(catalog.get("entries") or []),
        "error": catalog.get("error", ""),
    }


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
    updated_at = save_employee_patient_draft(employee, sanitize_pilot_patient(payload.patient))
    audit("api_case_draft_saved", employee=employee, entity_type="case_draft")
    return {"status": "saved", "updated_at": updated_at}


@app.post("/api/protocol/preview")
def protocol_preview(payload: ProtocolRequest, employee=Depends(current_employee)):
    patient = sanitize_pilot_patient(payload.patient)
    protocol_text = generate_protocol_text(patient)
    audit("api_protocol_generated", employee=employee, entity_type="case_draft")
    return {"protocol_text": protocol_text, "summary": build_case_summary(patient)}


@app.post("/api/protocol/suspicion")
def protocol_suspicion(payload: ProtocolRequest, employee=Depends(current_employee)):
    suspicions, recommendations = build_suspicion_assessment(sanitize_pilot_patient(payload.patient))
    return {"suspicions": suspicions, "recommendations": recommendations}


@app.post("/api/protocol/amls-candidates")
def protocol_amls_candidates(payload: ProtocolRequest, employee=Depends(current_employee)):
    return {"candidates": build_amls_candidates(sanitize_pilot_patient(payload.patient))}


@app.post("/api/protocol/medication-calculator")
def protocol_medication_calculator(payload: MedicationCalcRequest, employee=Depends(current_employee)):
    return calculate_medication(payload)


@app.post("/api/protocol/quality")
def protocol_quality(payload: ProtocolRequest, employee=Depends(current_employee)):
    result = assess_protocol_quality(sanitize_pilot_patient(payload.patient))
    result["ruleset_version"] = MEDICAL_RULESET_VERSION
    audit(
        "api_protocol_quality_checked",
        employee=employee,
        entity_type="case_draft",
        details={"score": result["score"], "level": result["level"], "warnings": result["warning_count"], "criticals": result["critical_count"]},
    )
    return result


@app.post("/api/protocol/pdf")
def protocol_pdf(payload: ProtocolRequest, employee=Depends(current_employee)):
    patient = sanitize_pilot_patient(payload.patient)
    protocol_text = generate_protocol_text(patient)
    summary = build_case_summary(patient)
    created_at = local_now().isoformat(timespec="seconds")
    pdf_bytes = build_pdf_bytes(
        "Laufender Einsatz",
        protocol_text,
        {
            "Exportiert am": created_at,
            "Mitarbeiter": employee.get("name", ""),
            "Zusammenfassung": summary,
            "Quelle": "laufender Entwurf",
            "Regelstand": MEDICAL_RULESET_VERSION,
        },
    )
    audit(
        "api_protocol_pdf_exported",
        employee=employee,
        entity_type="case_draft",
        details={"summary": summary, "format": "pdf"},
    )
    return pdf_response(f"nana-entwurf-{local_now().strftime('%Y%m%d-%H%M%S')}.pdf", pdf_bytes)


@app.post("/api/cases/finish")
def finish_case(payload: ProtocolRequest, employee=Depends(current_employee)):
    patient = sanitize_pilot_patient(payload.patient)
    protocol_text = generate_protocol_text(patient)
    quality = assess_protocol_quality(patient)
    completed_at = local_now().isoformat(timespec="seconds")
    retention_days = int(get_app_setting("retention_days", 3650) or 3650)
    retention_until = (local_now() + timedelta(days=max(1, retention_days))).date().isoformat()
    case_id = secrets.token_hex(10)
    save_finished_case({
        "id": case_id,
        "employee_id": employee.get("id", ""),
        "employee_name": employee.get("name", ""),
        "completed_at": completed_at,
        "summary": build_case_summary(patient),
        "patient": patient,
        "protocol_text": protocol_text,
        "retention_until": retention_until,
        "ruleset_version": MEDICAL_RULESET_VERSION,
    })

    store = load_case_draft_store()
    if employee.get("id") in store.get("drafts", {}):
        store["drafts"].pop(employee.get("id"), None)
        save_case_draft_store(store)

    finish_action = "api_case_finished_with_warnings" if quality["warning_count"] or quality["critical_count"] else "api_case_finished"
    audit(
        finish_action,
        employee=employee,
        entity_type="finished_case",
        entity_id=case_id,
        details={"quality_score": quality["score"], "warnings": quality["warning_count"], "criticals": quality["critical_count"], "force_finish": payload.force_finish},
    )
    return {
        "status": "finished",
        "case_id": case_id,
        "protocol_text": protocol_text,
        "quality": quality,
        "ruleset_version": MEDICAL_RULESET_VERSION,
    }


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
            "Regelstand": item.get("ruleset_version", MEDICAL_RULESET_VERSION),
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


@app.get("/api/admin/login-events")
def admin_login_events(employee=Depends(require_admin)):
    return {"events": list_login_events(limit=100)}


@app.get("/api/admin/quality-rules")
def admin_quality_rules(employee=Depends(require_admin)):
    return {"rules": QUALITY_RULES, "ruleset_version": MEDICAL_RULESET_VERSION}


@app.post("/api/admin/interfaces/import")
def admin_interface_import(payload: InterfaceImportRequest, employee=Depends(require_admin)):
    source = payload.source.lower().strip()
    patient = load_employee_patient_draft(employee)
    if source == "dispatch":
        imported = parse_dispatch_import(payload.payload)
        pending = save_employee_pending_dispatch(employee, imported, payload.payload)
        audit(
            "api_dispatch_pending_received",
            employee=employee,
            entity_type="case_draft",
            details={"source": source, "fields": sorted(imported.keys()), "pending_id": pending.get("id", "")},
        )
        return {
            "status": "pending",
            "source": source,
            "imported": imported,
            "pending": pending,
            "approach": approach_from_dispatch(imported),
        }
    elif source == "corpuls":
        imported = parse_corpuls_import(payload.payload)
        patient["vitalwerte"] = {**(patient.get("vitalwerte") or {}), **imported}
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unbekannte Schnittstelle.")

    updated_at = save_employee_patient_draft(employee, patient)
    audit(
        "api_interface_imported",
        employee=employee,
        entity_type="case_draft",
        details={"source": source, "fields": sorted(imported.keys()), "approach_fields": sorted((patient.get("anfahrt") or {}).keys()) if source == "dispatch" else []},
    )
    return {
        "status": "imported",
        "source": source,
        "imported": imported,
        "approach": patient.get("anfahrt", {}) if source == "dispatch" else {},
        "patient": patient,
        "updated_at": updated_at,
    }


@app.get("/api/admin/interfaces/export/draft/{export_format}")
def admin_export_draft(export_format: str, employee=Depends(require_admin)):
    patient = load_employee_patient_draft(employee)
    protocol_text = generate_protocol_text(patient)
    metadata = {
        "case_id": "draft",
        "employee": employee.get("name", ""),
        "exported_by": employee.get("id", ""),
        "source": "admin_draft",
        "ruleset_version": MEDICAL_RULESET_VERSION,
    }
    if export_format == "nana":
        payload = build_nana_case_export(patient, protocol_text, metadata)
    elif export_format == "fhir":
        payload = build_fhir_bundle(patient, protocol_text, metadata)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exportformat nicht verfügbar.")

    audit(
        "api_interface_exported",
        employee=employee,
        entity_type="case_draft",
        details={"format": export_format, "source": "draft"},
    )
    return json_attachment(f"nana-draft-{export_format}.json", payload)


@app.get("/api/admin/interfaces/export/cases/{case_id}/{export_format}")
def admin_export_case(case_id: str, export_format: str, employee=Depends(require_admin)):
    item = get_finished_case(case_id)
    if not item or item.get("status") == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Einsatz nicht gefunden.")
    if item.get("status") == "anonymized":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Anonymisierte Einsätze sind für Schnittstellenexport gesperrt.")

    metadata = {
        "case_id": case_id,
        "employee": item.get("employee_name", ""),
        "completed_at": item.get("completed_at", ""),
        "exported_by": employee.get("id", ""),
        "source": "finished_case",
        "ruleset_version": item.get("ruleset_version", MEDICAL_RULESET_VERSION),
    }
    if export_format == "nana":
        payload = build_nana_case_export(item.get("patient", {}), item.get("protocol_text", ""), metadata)
    elif export_format == "fhir":
        payload = build_fhir_bundle(item.get("patient", {}), item.get("protocol_text", ""), metadata)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exportformat nicht verfügbar.")

    audit(
        "api_interface_exported",
        employee=employee,
        entity_type="finished_case",
        entity_id=case_id,
        details={"format": export_format, "source": "case"},
    )
    return json_attachment(f"nana-case-{case_id}-{export_format}.json", payload)


@app.get("/api/admin/privacy")
def admin_privacy(employee=Depends(require_admin)):
    today = local_now().date().isoformat()
    expired_cases = list_expired_finished_cases(today)
    retention_days = int(get_app_setting("retention_days", 3650) or 3650)
    security_log_retention_days = int(get_app_setting("security_log_retention_days", 180) or 180)
    external_maps_enabled = bool(get_app_setting("external_maps_enabled", False))
    audit_count = len(list_audit_events(limit=500))
    encryption = encryption_status()
    bearer_allowed = not production_mode() or os.getenv("NANA_ENABLE_BEARER_AUTH", "").strip() == "1"
    return {
        "encryption": encryption,
        "retention_days": retention_days,
        "security_log_retention_days": security_log_retention_days,
        "external_maps_enabled": external_maps_enabled,
        "session_minutes": SESSION_MINUTES,
        "audit_events": audit_count,
        "expired_cases": len(expired_cases),
        "checklist": [
            {"label": "Verschlüsselung Patientendaten", "status": "ok" if encryption.get("enabled") else "warning", "detail": encryption.get("provider", "")},
            {"label": "Externer Datenschlüssel", "status": "ok" if encryption.get("key_source") == "environment" else "warning", "detail": encryption.get("production_hint", "")},
            {"label": "Rollenbasierter Admin-Zugriff", "status": "ok", "detail": "Admin-Endpunkte sind rollenbeschränkt."},
            {"label": "Host-Whitelist", "status": "ok" if allowed_hosts else "warning", "detail": ", ".join(allowed_hosts) if allowed_hosts else "NANA_ALLOWED_ORIGINS oder NANA_ALLOWED_HOSTS setzen."},
            {"label": "Bearer-Token", "status": "warning" if bearer_allowed and production_mode() else "ok", "detail": "aktiviert" if bearer_allowed else "in Produktion deaktiviert"},
            {"label": "Login-Schutz", "status": "ok", "detail": f"{AUTH_MAX_FAILURES} Fehlversuche, dann {AUTH_LOCK_MINUTES} Minuten Sperre."},
            {"label": "Sitzungssperre", "status": "ok", "detail": f"Backend {SESSION_MINUTES} Minuten, Oberfläche 20 Minuten."},
            {"label": "Aufbewahrungsfrist", "status": "ok" if retention_days <= 3650 else "warning", "detail": f"{retention_days} Tage konfiguriert."},
            {"label": "Log-Aufbewahrung", "status": "ok" if security_log_retention_days <= 180 else "warning", "detail": f"{security_log_retention_days} Tage für Audit/Login-Metadaten."},
            {"label": "Externe Kartenanbieter", "status": "warning" if external_maps_enabled else "ok", "detail": "aktiviert" if external_maps_enabled else "standardmäßig deaktiviert"},
            {"label": "Fällige Löschungen", "status": "ok" if not expired_cases else "warning", "detail": f"{len(expired_cases)} Einsatz/Einsätze abgelaufen."},
            {"label": "Audit-Trail", "status": "ok" if audit_count else "info", "detail": f"{audit_count} Ereignisse einsehbar."},
        ],
    }


@app.put("/api/admin/privacy")
def update_privacy(payload: RetentionRequest, employee=Depends(require_admin)):
    days = max(1, min(int(payload.retention_days or 3650), 36500))
    log_days = max(1, min(int(payload.security_log_retention_days or 180), 3650))
    set_app_setting("retention_days", days)
    set_app_setting("security_log_retention_days", log_days)
    set_app_setting("external_maps_enabled", bool(payload.external_maps_enabled))
    audit("api_privacy_settings_updated", employee=employee, details={
        "retention_days": days,
        "security_log_retention_days": log_days,
        "external_maps_enabled": bool(payload.external_maps_enabled),
    })
    return {
        "status": "saved",
        "retention_days": days,
        "security_log_retention_days": log_days,
        "external_maps_enabled": bool(payload.external_maps_enabled),
    }


@app.post("/api/admin/privacy/purge-expired")
def purge_expired_cases(employee=Depends(require_admin)):
    today = local_now().date().isoformat()
    timestamp = local_now().isoformat(timespec="seconds")
    expired = delete_expired_finished_cases(today, timestamp)
    audit(
        "api_expired_cases_purged",
        employee=employee,
        entity_type="finished_case",
        details={"count": len(expired), "date": today},
    )
    return {"status": "purged", "count": len(expired), "case_ids": [item["id"] for item in expired]}


@app.post("/api/admin/privacy/purge-security-events")
def purge_security_events(employee=Depends(require_admin)):
    days = max(1, min(int(get_app_setting("security_log_retention_days", 180) or 180), 3650))
    cutoff = (local_now() - timedelta(days=days)).isoformat(timespec="seconds")
    deleted = delete_security_events_before(cutoff)
    audit(
        "api_security_events_purged",
        employee=employee,
        details={"cutoff": cutoff, "deleted": deleted},
    )
    return {"status": "purged", "cutoff": cutoff, "deleted": deleted}


@app.get("/api/admin/employees")
def admin_employees(employee=Depends(require_admin)):
    store = load_employee_store()
    return {"employees": [admin_employee(item) for item in store.get("employees", [])]}


@app.get("/api/admin/employees/export")
def export_employees(employee=Depends(require_admin)):
    store = load_employee_store()
    audit("api_employees_exported", employee=employee, details={"count": len(store.get("employees", []))})
    return employee_csv_response([admin_employee(item) for item in store.get("employees", [])])


@app.post("/api/admin/employees/import")
def import_employees(payload: EmployeeImportRequest, employee=Depends(require_admin)):
    csv_text = (payload.csv_text or "").strip()
    if not csv_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV fehlt.")
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames or "name" not in {field.strip() for field in reader.fieldnames if field}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV braucht mindestens die Spalte name.")

    store = load_employee_store()
    employees = store.get("employees", [])
    by_id = {item.get("id", ""): item for item in employees if item.get("id")}
    by_name = {item.get("name", "").strip().lower(): item for item in employees if item.get("name")}
    created = 0
    updated = 0
    temporary_passwords = []
    for raw_row in reader:
        row = {(key or "").strip(): value for key, value in raw_row.items()}
        name = (row.get("name") or "").strip()
        if not name:
            continue
        target = by_id.get((row.get("id") or "").strip()) or by_name.get(name.lower())
        active_raw = row.get("active")
        changes = {
            "name": name,
            "role": normalize_employee_role((row.get("role") or "employee").strip()),
            "qualification": normalize_employee_qualification(row.get("qualification")),
            "station": normalize_employee_station(row.get("station")),
            "vehicle_scope": normalize_employee_vehicle_scope(row.get("vehicle_scope")),
            "on_shift": parse_bool_flag(row.get("on_shift")),
            "active": True if active_raw is None or str(active_raw).strip() == "" else parse_bool_flag(active_raw),
        }
        if target:
            update_employee_record(target["id"], changes)
            updated += 1
            continue
        temp_password = secrets.token_urlsafe(18)
        new_employee = {
            "id": new_token()[:16],
            **changes,
            "password_hash": "",
            "temp_password_hash": password_hash(temp_password),
            "must_change_password": True,
            "created_at": local_now().isoformat(timespec="seconds"),
            "password_changed_at": "",
        }
        create_employee_record(new_employee)
        by_id[new_employee["id"]] = new_employee
        by_name[new_employee["name"].strip().lower()] = new_employee
        temporary_passwords.append({"name": new_employee["name"], "temporary_password": temp_password})
        created += 1

    audit("api_employees_imported", employee=employee, details={"created": created, "updated": updated})
    return {"created": created, "updated": updated, "temporary_passwords": temporary_passwords}


@app.post("/api/admin/employees")
def create_employee(payload: EmployeeCreateRequest, employee=Depends(require_admin)):
    name = payload.name.strip()
    role = normalize_employee_role(payload.role)
    qualification = normalize_employee_qualification(payload.qualification)
    station = normalize_employee_station(payload.station)
    vehicle_scope = normalize_employee_vehicle_scope(payload.vehicle_scope)
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name fehlt.")

    temp_password = secrets.token_urlsafe(18)
    new_employee = {
        "id": new_token()[:16],
        "name": name,
        "role": role,
        "qualification": qualification,
        "station": station,
        "vehicle_scope": vehicle_scope,
        "on_shift": bool(payload.on_shift),
        "active": True,
        "password_hash": "",
        "temp_password_hash": password_hash(temp_password),
        "must_change_password": True,
        "created_at": local_now().isoformat(timespec="seconds"),
        "password_changed_at": "",
    }
    create_employee_record(new_employee)
    audit(
        "api_employee_created",
        employee=employee,
        entity_type="employee",
        entity_id=new_employee["id"],
        details={"role": role, "qualification": qualification, "station": station, "vehicle_scope": vehicle_scope, "on_shift": bool(payload.on_shift)},
    )
    return {"employee": admin_employee(new_employee), "temporary_password": temp_password}


@app.put("/api/admin/employees/{employee_id}")
def update_employee(employee_id: str, payload: EmployeeUpdateRequest, employee=Depends(require_admin)):
    target = get_employee(employee_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mitarbeiter nicht gefunden.")

    changes = {}
    if payload.name is not None and payload.name.strip():
        changes["name"] = payload.name.strip()
    if payload.role is not None:
        changes["role"] = normalize_employee_role(payload.role)
    if payload.qualification is not None:
        changes["qualification"] = normalize_employee_qualification(payload.qualification)
    if payload.station is not None:
        changes["station"] = normalize_employee_station(payload.station)
    if payload.vehicle_scope is not None:
        changes["vehicle_scope"] = normalize_employee_vehicle_scope(payload.vehicle_scope)
    if payload.on_shift is not None:
        changes["on_shift"] = bool(payload.on_shift)
    if payload.active is not None:
        if target.get("id") == employee.get("id") and payload.active is False:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Eigenes Admin-Profil kann nicht deaktiviert werden.")
        changes["active"] = bool(payload.active)

    temp_password = ""
    if payload.reset_password:
        temp_password = secrets.token_urlsafe(18)
        changes.update({
            "password_hash": "",
            "temp_password_hash": password_hash(temp_password),
            "must_change_password": True,
            "password_changed_at": "",
        })

    target = update_employee_record(employee_id, changes) or target
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


@app.delete("/api/admin/employees/{employee_id}")
def delete_employee(employee_id: str, employee=Depends(require_admin)):
    if employee_id == employee.get("id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Eigenes Admin-Profil kann nicht gelöscht werden.")

    store = load_employee_store()
    employees = store.get("employees", [])
    target = next((item for item in employees if item.get("id") == employee_id), None)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mitarbeiter nicht gefunden.")

    remaining_admins = [
        item for item in employees
        if item.get("id") != employee_id and item.get("role") == "admin" and item.get("active", True)
    ]
    if target.get("role") == "admin" and not remaining_admins:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Der letzte aktive Admin kann nicht gelöscht werden.")

    delete_employee_record(employee_id)
    audit(
        "api_employee_deleted",
        employee=employee,
        entity_type="employee",
        entity_id=employee_id,
        details={"name": target.get("name", ""), "role": target.get("role", "")},
    )
    return {"status": "deleted", "employee_id": employee_id}


@app.post("/api/admin/cases/{case_id}/anonymize")
def admin_anonymize_case(case_id: str, employee=Depends(require_admin)):
    item = get_finished_case(case_id)
    if not item or item.get("status") == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Einsatz nicht gefunden.")
    timestamp = local_now().isoformat(timespec="seconds")
    anonymize_finished_case(case_id, timestamp)
    audit("api_case_anonymized", employee=employee, entity_type="finished_case", entity_id=case_id)
    return {"status": "anonymized", "case_id": case_id}


@app.delete("/api/admin/cases/{case_id}")
def admin_delete_case(case_id: str, employee=Depends(require_admin)):
    item = get_finished_case(case_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Einsatz nicht gefunden.")
    timestamp = local_now().isoformat(timespec="seconds")
    delete_finished_case(case_id, timestamp)
    audit("api_case_deleted", employee=employee, entity_type="finished_case", entity_id=case_id)
    return {"status": "deleted", "case_id": case_id}


if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")


@app.get("/")
@app.get("/{full_path:path}")
def serve_frontend(full_path: str = ""):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API-Endpunkt nicht gefunden.")
    if not FRONTEND_DIST.exists():
        return HTMLResponse(
            "<h1>NANA Backend läuft</h1>"
            "<p>Das Frontend wurde noch nicht gebaut. Bitte im Ordner frontend <code>npm run build</code> ausführen "
            "oder die App über <code>http://127.0.0.1:5173</code> starten.</p>",
            status_code=200,
        )
    requested = (FRONTEND_DIST / full_path).resolve()
    if requested.is_file() and FRONTEND_DIST.resolve() in requested.parents:
        return FileResponse(requested)
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>NANA Frontend nicht gefunden</h1>", status_code=404)
