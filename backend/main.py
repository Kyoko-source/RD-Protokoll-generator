import secrets
import json
from pathlib import Path
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fpdf import FPDF
from pydantic import BaseModel

from backend.security import expires_at, is_expired, new_token, password_hash, verify_password
from device_guides import DEVICE_GUIDES
from hospital_finder import CATEGORIES, HOSPITALS, TOWNS, distance_km
from interfaces import build_fhir_bundle, build_nana_case_export, parse_corpuls_import, parse_dispatch_import
from storage import (
    anonymize_finished_case,
    delete_finished_case,
    delete_expired_finished_cases,
    encrypt_existing_patient_data,
    encryption_status,
    get_finished_case,
    get_app_setting,
    init_database,
    list_audit_events,
    list_expired_finished_cases,
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
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

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
    force_finish: bool = False


class MedicationCalcRequest(BaseModel):
    sop: str = "Anaphylaxie (SOPKB0105)"
    age: float = 30
    weight: float = 70
    pregnant: str = "Nein"
    inputs: dict = {}


class PrintAuditRequest(BaseModel):
    case_id: str | None = None
    source: str = "draft"


class InterfaceImportRequest(BaseModel):
    source: str = "dispatch"
    payload: str


class IcdLookupRequest(BaseModel):
    code: str


class HospitalSaveRequest(BaseModel):
    id: str | None = None
    name: str
    country: str = "DE"
    address: str = ""
    town: str = ""
    phone: str = ""
    categories: list[str] = []
    estimated_minutes: int | None = None
    source: str = ""


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
        "amls": {
            "excluded": [],
            "custom_candidates": [],
            "arbeitsdiagnose": "",
            "leitsymptom": "",
            "notizen": "",
        },
        "massnahmen": {"timeline": [], "medikation": []},
        "transport": {},
        "einsatz": {},
        "uebergabe": {},
    }


def valid(value):
    return value not in [None, "", [], {}, "Keine Angabe", "Selber eintragen"]


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


def build_sinnhaft_rows(patient):
    vital = patient.get("vitalwerte", {}) or {}
    x = patient.get("xabcde", {}) or {}
    s = patient.get("samplers", {}) or {}
    o = patient.get("opqrst", {}) or {}
    amls = patient.get("amls", {}) or {}
    measures = patient.get("massnahmen", {}) or {}
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
    action_lines = format_action_lines(measures)
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
    handover = patient.get("uebergabe", {}) or {}

    primary = []
    identity = format_patient_identity(vital)
    symptom = format_symptom_summary(vital, s, o)
    if valid(symptom):
        primary.append(f"Bei {identity} wurde praeklinisch folgendes Hauptproblem dokumentiert: {symptom}.")
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
    handover_sentence = compact_join([
        f"Ziel/Empfaenger: {handover.get('ziel')}" if valid(handover.get("ziel")) else "",
        handover.get("text"),
    ], " ")

    text = ""
    text += add_paragraph("EINSATZBERICHT", primary)
    text += add_paragraph("ERSTBEFUND UND VERLAUF", [item for item in assessment if valid(item)])
    text += add_paragraph("ANAMNESE UND SCHMERZASSESSMENT", [item for item in history if valid(item)])
    text += add_paragraph("MASSNAHMEN UND WIRKUNG", ["; ".join(actions) if actions else "Keine Maßnahmen/Medikationen dokumentiert."])
    text += add_paragraph("UEBERGABE-KURZFAZIT", [handover_sentence])
    return text


QUALITY_RULES = [
    {"id": "vital_age", "label": "Alter dokumentiert", "severity": "warning", "section": "Vitalwerte"},
    {"id": "vital_gender", "label": "Geschlecht dokumentiert", "severity": "info", "section": "Vitalwerte"},
    {"id": "vital_core", "label": "Puls, SpO2, RR und GCS geprüft", "severity": "warning", "section": "Vitalwerte"},
    {"id": "short_report", "label": "Kurzbericht oder Leitsymptome vorhanden", "severity": "warning", "section": "Anamnese"},
    {"id": "xabcde", "label": "xABCDE Kernfelder dokumentiert", "severity": "warning", "section": "Erstbeurteilung"},
    {"id": "diagnosis", "label": "Arbeitsdiagnose/Verdacht eingetragen", "severity": "warning", "section": "Abschluss"},
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
            "Atemweg sichern und Atemarbeit engmaschig ueberwachen",
            "Sauerstofftherapie titriert fortfuehren",
            "Fruehe Zielklinikmeldung bei persistierender Hypoxie",
        )
    if any(term in text for term in ["brust", "thorax", "retrosternal", "druck"]):
        add(
            "Akutes Koronarsyndrom (ACS) als Differenzialdiagnose",
            "12-Kanal-EKG und Verlaufskontrolle",
            "Schmerz- und Kreislaufmonitoring",
            "Zeitkritischen Transport erwaegen",
        )
    if xabcde.get("avpu") in ["P", "U", "Pain", "Unresponsive"] or (gcs is not None and gcs <= 8):
        add(
            "Schwere neurologische Beeintraechtigung",
            "Atemwegsschutz priorisieren",
            "Neurologischen Verlauf wiederholt dokumentieren",
            "Zielklinik mit neurologischer Versorgung bevorzugen",
        )
    if any(term in text for term in ["sturz", "unfall", "trauma", "kollision"]) or str(xabcde.get("bodycheck", "")).lower() == "auffällig":
        add(
            "Traumatische Genese / relevante Verletzung moeglich",
            "Vollstaendigen Bodycheck und Blutungskontrolle sichern",
            "Immobilisationsbedarf pruefen",
            "Traumazentrum-Indikation evaluieren",
        )
    if bz is not None and bz < 70:
        add("Hypoglykaemie", "Sofortige Glukosegabe gemaess SOP", "Blutzucker nach Intervention kontrollieren")
    elif bz is not None and bz > 250:
        add("Hyperglykaeme Stoffwechsellage", "Hydratationsstatus und Vigilanz eng ueberwachen", "Zeitnahe klinische Abklaerung veranlassen")
    if nrs is not None and nrs >= 7:
        add("Akutes Schmerzsyndrom", "Analgesiekonzept dokumentieren und Wirkung nachkontrollieren", "Schmerzverlauf seriell erfassen")

    if not suspicions:
        suspicions.append("Aktuell keine klare Verdachtsdiagnose aus den verfuegbaren Angaben ableitbar")
        recommendations.append("Datensatz vervollstaendigen und Verlauf engmaschig re-evaluieren")
    return suspicions, recommendations


def build_amls_candidates(patient):
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

    if af is not None and af > 20:
        add("Lungenarterienembolie", "Kardiopulmonal", f"Tachypnoe mit AF {af:g}/min")
        add("Sepsis / schwere Infektion", "Infektioes", f"Tachypnoe mit AF {af:g}/min")
        add("Schock", "Kreislauf", f"Tachypnoe mit AF {af:g}/min als Kompensationszeichen")
    if spo2 is not None and spo2 < 95:
        add("Respiratorische Insuffizienz", "Respiratorisch", f"SpO2 {spo2:g} %")
        add("Pneumonie", "Infektioes", f"SpO2 {spo2:g} %")
        add("Kardiales Lungenoedem", "Kardiopulmonal", f"SpO2 {spo2:g} %")
    if pulse is not None and pulse > 100:
        add("Tachyarrhythmie", "Kardial", f"Puls {pulse:g}/min")
        add("Schmerz-/Stressreaktion", "Sonstige", f"Puls {pulse:g}/min")
    if rr_sys is not None and rr_sys < 90:
        add("Schock", "Kreislauf", f"Hypotonie mit RR syst. {rr_sys:g} mmHg")
        add("Blutung / Volumenmangel", "Kreislauf", f"Hypotonie mit RR syst. {rr_sys:g} mmHg")
    if temp is not None and temp >= 38:
        add("Sepsis / schwere Infektion", "Infektioes", f"Fieber mit {temp:g} Grad C")
    if gcs is not None and gcs < 15:
        add("Intrakranielle Ursache", "Neurologisch", f"GCS {gcs:g}")
        add("Intoxikation", "Toxikologisch", f"GCS {gcs:g}")
    if bz is not None and bz < 70:
        add("Hypoglykaemie", "Metabolisch", f"BZ {bz:g} mg/dL")
    if any(term in text for term in ["brust", "thorax", "retrosternal"]):
        add("Akutes Koronarsyndrom", "Kardial", "Thoraxbeschwerden dokumentiert")
        add("Aortensyndrom / Aortendissektion", "Vaskulaer", "Zeitkritische Ursache bei Thoraxschmerz")
        add("Pneumothorax", "Respiratorisch", "Thoraxschmerz kann pleuropulmonal bedingt sein")
    if any(term in text for term in ["atemnot", "dyspnoe", "luftnot"]):
        add("Asthma/COPD-Exazerbation", "Respiratorisch", "Dyspnoe dokumentiert")
    if any(term in text for term in ["bauch", "abdomen", "kolik", "flanke"]):
        add("Akutes Abdomen", "Abdominell", "Abdominelle Beschwerden dokumentiert")
        add("Atypisches akutes Koronarsyndrom", "Kardial", "Oberbauchbeschwerden koennen kardial bedingt sein")

    if len(candidates) < 4:
        for name, category in [
            ("Kardiale Ursache / Rhythmusstoerung", "Kardial"),
            ("Respiratorische Ursache", "Respiratorisch"),
            ("Neurologische Ursache", "Neurologisch"),
            ("Metabolische Entgleisung", "Metabolisch"),
            ("Infektion / Sepsis", "Infektioes"),
            ("Intoxikation", "Toxikologisch"),
        ]:
            add(name, category, "Breiter AMLS-Sicherheitscheck bei unspezifischer Datenlage")

    for item in amls.get("custom_candidates", []):
        name = item.get("diagnose") if isinstance(item, dict) else item
        if valid(name):
            add(str(name), "Eigene Ergaenzung", "Manuell zum Trichter hinzugefuegt")

    excluded_names = {
        str(item.get("diagnose") or item.get("name") or "").strip() if isinstance(item, dict) else str(item).strip()
        for item in amls.get("excluded", [])
        if valid(item)
    }
    for item in candidates:
        conflicts = [] if item["category"] == "Eigene Ergaenzung" else amls_candidate_conflicts(item["name"], patient)
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

    if any(term in name for term in ["pneumonie", "respirator", "asthma", "copd", "lungenembolie", "lungenoedem", "pneumothorax"]):
        if spo2 is not None and spo2 >= 95 and str(xabcde.get("atmung", "")).lower() in ["unauffällig", "frei"]:
            conflicts.append("SpO2/Atmung bislang unauffaellig dokumentiert")
    if any(term in name for term in ["schock", "blutung", "volumenmangel", "sepsis"]):
        if rr_sys is not None and rr_sys >= 100 and pulse is not None and pulse <= 100:
            conflicts.append("RR/Puls sprechen aktuell nicht fuer Schock")
    if "sepsis" in name or "infektion" in name:
        if temp is not None and temp < 38:
            conflicts.append("Kein Fieber dokumentiert")
    if any(term in name for term in ["intrakraniell", "neurolog", "schlaganfall", "tia"]):
        if gcs is not None and gcs == 15 and xabcde.get("avpu") in ["Alert", "A", ""]:
            conflicts.append("Vigilanz aktuell unauffaellig")
    if "hypogly" in name and bz is not None and bz >= 70:
        conflicts.append("BZ nicht im hypoglykaemen Bereich")
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
        actions.extend(["Oberkoerper hoch, beruhigen, Sauerstoff titrieren", "Nach 5 Minuten Wirkung re-evaluieren"])
    elif sop == "Hypoglykaemie" or sop == "Hypoglykämie":
        bz = float(inputs.get("bz", 55) or 55)
        if bz < 60:
            meds.append("Glucose bis zu 16 g i.v. bei Bewusstseinsstoerung, sonst oral")
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
            notes.append("Keine primaere RR-Senkung im Standardfenster 120-220 mmHg")
        actions.extend(["Last-Seen-Well sichern", "Stroke-Unit-Voranmeldung priorisieren"])
    elif sop == "Kardiales Lungenoedem" or sop == "Kardiales Lungenödem":
        rr = float(inputs.get("rr_sys", 160) or 160)
        if rr > 120:
            meds.append("Glyceroltrinitrat 0,4-0,8 mg s.l.")
        meds.append("Furosemid 20 mg i.v. langsam, ggf. einmalige Repetition")
        actions.append("CPAP/NIV fruehzeitig erwaegen")
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
        notes.append("Schwangerschaft: fruehe aerztliche Ruecksprache einplanen.")
    return {"sop": sop, "medications": meds, "actions": actions, "notes": notes}


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
    vital = patient.get("vitalwerte", {}) or {}
    xabcde = patient.get("xabcde", {}) or {}
    samplers = patient.get("samplers", {}) or {}
    amls = patient.get("amls", {}) or {}
    transport = patient.get("transport", {}) or {}
    handover = patient.get("uebergabe", {}) or {}
    measures = patient.get("massnahmen", {}) or {}

    items = []
    items.append(quality_item(
        "vital_age",
        "ok" if valid(vital.get("alter")) else "warning",
        "Alter ist dokumentiert." if valid(vital.get("alter")) else "Alter fehlt.",
    ))
    items.append(quality_item(
        "vital_gender",
        "ok" if valid(vital.get("geschlecht")) else "info",
        "Geschlecht ist dokumentiert." if valid(vital.get("geschlecht")) else "Geschlecht fehlt.",
        "info",
    ))

    core_vital_groups = [
        ("Puls", ["puls", "puls_status", "puls_status_custom"]),
        ("SpO2", ["spo2", "spo2_status", "spo2_status_custom"]),
        ("RR", ["rr_sys", "rr_dia", "rr_status", "rr_status_custom"]),
        ("GCS", ["gcs", "gcs_status", "gcs_status_custom"]),
    ]
    missing_core = [label for label, keys in core_vital_groups if not any(valid(vital.get(key)) for key in keys)]
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
    vital = patient.get("vitalwerte", {})
    x = patient.get("xabcde", {})
    s = patient.get("samplers", {})
    o = patient.get("opqrst", {})
    measures = patient.get("massnahmen", {})
    handover = patient.get("uebergabe", {})
    amls = patient.get("amls", {})

    text = "RD-PROTOKOLL - DOKUMENTATIONSENTWURF\n"
    text += "=" * 50 + "\n"
    text += f"Erstellt am {datetime.now().strftime('%d.%m.%Y um %H:%M:%S')} Uhr\n"
    text += "Enthaelt ausschliesslich dokumentierte Angaben; vor Verwendung vollstaendig pruefen.\n\n"
    text += build_narrative_report(patient)

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
        ("Atemgeraeusche", x.get("atemgeraeusche")),
        ("Sauerstoff", x.get("sauerstoff")),
        ("C Hautzeichen", x.get("haut")),
        ("Rekap", x.get("rekap")),
        ("Pulsqualitaet", x.get("pulsqualitaet")),
        ("D AVPU", x.get("avpu")),
        ("Pupillen", x.get("pupillen")),
        ("BE-FAST Balance", x.get("befast_balance")),
        ("BE-FAST Eyes", x.get("befast_eyes")),
        ("BE-FAST Face", x.get("befast_face")),
        ("BE-FAST Arms", x.get("befast_arms")),
        ("BE-FAST Speech", x.get("befast_speech")),
        ("BE-FAST Time", x.get("befast_time")),
        ("E Bodycheck", x.get("bodycheck")),
        ("Bodycheck Auffaelligkeiten", x.get("bodycheck_text")),
        ("Unterkuehlung", "Ja" if x.get("unterkuehlung") else ""),
        ("Verbrennung", "Ja" if x.get("verbrennung") else ""),
    ])
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
    text += add_lines("AMLS / VERDACHTSDIAGNOSTIK", [
        ("Leitsymptom", amls.get("leitsymptom")),
        ("Arbeitsdiagnose", amls.get("arbeitsdiagnose")),
        ("Notizen / Begruendung", amls.get("notizen")),
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
            text += "AMLS-Ausschluesse / zurueckgestellte Diagnosen\n" + ("=" * 50) + "\n"
            for line in lines:
                text += f"- {line}\n"
            text += "\n"

    text += add_lines("SINNHAFT-UEBERGABE", build_sinnhaft_rows(patient))
    text += add_lines("UEBERGABE FREITEXT", [
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


def json_attachment(filename, payload):
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
}


def normalize_icd_code(value):
    return str(value or "").strip().upper().replace(" ", "")


def lookup_icd_local(code):
    normalized = normalize_icd_code(code)
    if not normalized:
        return {"code": "", "diagnosis": "", "found": False}
    candidates = [normalized]
    if "." in normalized:
        candidates.append(normalized.split(".", 1)[0])
    candidates.append(normalized[:3])
    for candidate in candidates:
        if candidate in ICD10_LOCAL:
            return {"code": normalized, "matched_code": candidate, "diagnosis": ICD10_LOCAL[candidate], "found": True}
    return {"code": normalized, "matched_code": normalized[:3], "diagnosis": "Nicht im lokalen Grundkatalog gefunden", "found": False}


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
    store.setdefault("drafts", {})[employee["id"]] = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "patient": patient,
        "seite": "Schnittstellen",
        "visited_pages": ["Schnittstellen"],
        "workflow_manual_completion": {},
        "protocol_generated": False,
        "generated_protocol_text": "",
        "xabcde_selected": "A",
    }
    save_case_draft_store(store)
    return store["drafts"][employee["id"]]["updated_at"]


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
    updated_at = save_employee_patient_draft(employee, payload.patient)
    audit("api_case_draft_saved", employee=employee, entity_type="case_draft")
    return {"status": "saved", "updated_at": updated_at}


@app.post("/api/protocol/preview")
def protocol_preview(payload: ProtocolRequest, employee=Depends(current_employee)):
    protocol_text = generate_protocol_text(payload.patient)
    audit("api_protocol_generated", employee=employee, entity_type="case_draft")
    return {"protocol_text": protocol_text, "summary": build_case_summary(payload.patient)}


@app.post("/api/protocol/suspicion")
def protocol_suspicion(payload: ProtocolRequest, employee=Depends(current_employee)):
    suspicions, recommendations = build_suspicion_assessment(payload.patient)
    return {"suspicions": suspicions, "recommendations": recommendations}


@app.post("/api/protocol/amls-candidates")
def protocol_amls_candidates(payload: ProtocolRequest, employee=Depends(current_employee)):
    return {"candidates": build_amls_candidates(payload.patient)}


@app.post("/api/protocol/medication-calculator")
def protocol_medication_calculator(payload: MedicationCalcRequest, employee=Depends(current_employee)):
    return calculate_medication(payload)


@app.post("/api/protocol/quality")
def protocol_quality(payload: ProtocolRequest, employee=Depends(current_employee)):
    result = assess_protocol_quality(payload.patient)
    audit(
        "api_protocol_quality_checked",
        employee=employee,
        entity_type="case_draft",
        details={"score": result["score"], "level": result["level"], "warnings": result["warning_count"], "criticals": result["critical_count"]},
    )
    return result


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
    quality = assess_protocol_quality(payload.patient)
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

    finish_action = "api_case_finished_with_warnings" if quality["warning_count"] or quality["critical_count"] else "api_case_finished"
    audit(
        finish_action,
        employee=employee,
        entity_type="finished_case",
        entity_id=case_id,
        details={"quality_score": quality["score"], "warnings": quality["warning_count"], "criticals": quality["critical_count"], "force_finish": payload.force_finish},
    )
    return {"status": "finished", "case_id": case_id, "protocol_text": protocol_text, "quality": quality}


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


@app.get("/api/admin/quality-rules")
def admin_quality_rules(employee=Depends(require_admin)):
    return {"rules": QUALITY_RULES}


@app.post("/api/admin/interfaces/import")
def admin_interface_import(payload: InterfaceImportRequest, employee=Depends(require_admin)):
    source = payload.source.lower().strip()
    patient = load_employee_patient_draft(employee)
    if source == "dispatch":
        imported = parse_dispatch_import(payload.payload)
        patient["einsatz"] = {**(patient.get("einsatz") or {}), **imported}
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
        details={"source": source, "fields": sorted(imported.keys())},
    )
    return {"status": "imported", "source": source, "imported": imported, "patient": patient, "updated_at": updated_at}


@app.get("/api/admin/interfaces/export/draft/{export_format}")
def admin_export_draft(export_format: str, employee=Depends(require_admin)):
    patient = load_employee_patient_draft(employee)
    protocol_text = generate_protocol_text(patient)
    metadata = {
        "case_id": "draft",
        "employee": employee.get("name", ""),
        "exported_by": employee.get("id", ""),
        "source": "admin_draft",
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
    today = datetime.now().date().isoformat()
    expired_cases = list_expired_finished_cases(today)
    retention_days = int(get_app_setting("retention_days", 3650) or 3650)
    audit_count = len(list_audit_events(limit=500))
    encryption = encryption_status()
    return {
        "encryption": encryption,
        "retention_days": retention_days,
        "session_minutes": SESSION_MINUTES,
        "audit_events": audit_count,
        "expired_cases": len(expired_cases),
        "checklist": [
            {"label": "Verschluesselung Patientendaten", "status": "ok" if encryption.get("enabled") else "warning", "detail": encryption.get("provider", "")},
            {"label": "Externer Datenschluessel", "status": "ok" if encryption.get("key_source") == "environment" else "warning", "detail": encryption.get("production_hint", "")},
            {"label": "Rollenbasierter Admin-Zugriff", "status": "ok", "detail": "Admin-Endpunkte sind rollenbeschraenkt."},
            {"label": "Sitzungssperre", "status": "ok", "detail": f"Backend {SESSION_MINUTES} Minuten, Oberflaeche 20 Minuten."},
            {"label": "Aufbewahrungsfrist", "status": "ok" if retention_days <= 3650 else "warning", "detail": f"{retention_days} Tage konfiguriert."},
            {"label": "Faellige Loeschungen", "status": "ok" if not expired_cases else "warning", "detail": f"{len(expired_cases)} Einsatz/Einsaetze abgelaufen."},
            {"label": "Audit-Trail", "status": "ok" if audit_count else "info", "detail": f"{audit_count} Ereignisse einsehbar."},
        ],
    }


@app.put("/api/admin/privacy")
def update_privacy(payload: RetentionRequest, employee=Depends(require_admin)):
    days = max(1, min(int(payload.retention_days or 3650), 36500))
    set_app_setting("retention_days", days)
    audit("api_privacy_settings_updated", employee=employee, details={"retention_days": days})
    return {"status": "saved", "retention_days": days}


@app.post("/api/admin/privacy/purge-expired")
def purge_expired_cases(employee=Depends(require_admin)):
    today = datetime.now().date().isoformat()
    timestamp = datetime.now().isoformat(timespec="seconds")
    expired = delete_expired_finished_cases(today, timestamp)
    audit(
        "api_expired_cases_purged",
        employee=employee,
        entity_type="finished_case",
        details={"count": len(expired), "date": today},
    )
    return {"status": "purged", "count": len(expired), "case_ids": [item["id"] for item in expired]}


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


if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")


@app.get("/")
@app.get("/{full_path:path}")
def serve_frontend(full_path: str = ""):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API-Endpunkt nicht gefunden.")
    if not FRONTEND_DIST.exists():
        return HTMLResponse(
            "<h1>NANA Backend laeuft</h1>"
            "<p>Das Frontend wurde noch nicht gebaut. Bitte im Ordner frontend <code>npm run build</code> ausfuehren "
            "oder die App ueber <code>http://127.0.0.1:5173</code> starten.</p>",
            status_code=200,
        )
    requested = (FRONTEND_DIST / full_path).resolve()
    if requested.is_file() and FRONTEND_DIST.resolve() in requested.parents:
        return FileResponse(requested)
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>NANA Frontend nicht gefunden</h1>", status_code=404)
