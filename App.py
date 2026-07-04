import streamlit as st
import streamlit.components.v1 as components
from io import BytesIO
from fpdf import FPDF
from datetime import datetime
import html
import json
import os
import re
import urllib.error
import urllib.request
from copy import deepcopy


def add_line(text, value):
    """
    Fügt nur Zeilen hinzu, wenn ein Wert vorhanden ist.
    """
    if value not in ["", "Keine Angabe", 0, None]:
        return text + value + "\n"
    return text


def categorize_temperature(temp):
    try:
        t = float(temp)
    except Exception:
        return "Unbekannt", None
    if t < 36.0:
        return "Unterkühlung", t
    if t < 37.5:
        return "Normal", t
    if t < 38.0:
        return "Erhöht (subfebril)", t
    return "Fieber", t


def categorize_puls(p):
    try:
        p = int(p)
    except Exception:
        return "Unbekannt", None
    if p < 50:
        return "Bradykardie", p
    if p <= 100:
        return "Normal", p
    if p <= 120:
        return "Tachykardie", p
    return "Starke Tachykardie", p


def categorize_spo2(s):
    try:
        s = int(s)
    except Exception:
        return "Unbekannt", None
    if s >= 95:
        return "Normal", s
    if s >= 90:
        return "Leicht erniedrigt", s
    return "Kritisch erniedrigt", s


def categorize_af(af):
    try:
        af = int(af)
    except Exception:
        return "Unbekannt", None
    if af < 10:
        return "Bradypnoe", af
    if af <= 20:
        return "Normal", af
    if af <= 30:
        return "Tachypnoe", af
    return "Schwere Tachypnoe", af


def categorize_bz(bz):
    try:
        bz = float(bz)
    except Exception:
        return "Unbekannt", None
    if bz < 70:
        return "Hypoglykämie", bz
    if bz <= 140:
        return "Normal", bz
    return "Hyperglykämie", bz


def categorize_rr(sys, dia):
    try:
        s = int(sys)
        d = int(dia)
    except Exception:
        return "Unbekannt", None
    if s < 90:
        return "Hypotonie", (s, d)
    if s < 120:
        return "Normal", (s, d)
    if s < 140:
        return "Leicht erhöht", (s, d)
    if s < 180:
        return "Hypertonie", (s, d)
    return "Hypertensive Krise", (s, d)


def set_current_time(state_key):
    st.session_state[state_key] = datetime.now().strftime("%H:%M")


def reset_patient_case():
    preserved = {
        key: st.session_state[key]
        for key in ("sop_admin_config", "admin_unlocked")
        if key in st.session_state
    }
    st.session_state.clear()
    st.session_state.update(preserved)
    st.session_state["patient"] = {
        "vitalwerte": {},
        "xabcde": {},
        "samplers": {},
        "opqrst": {},
        "einweisung": {},
        "amls": {"excluded": [], "custom_candidates": [], "arbeitsdiagnose": ""},
        "massnahmen": {"timeline": [], "medikation": []},
    }
    st.session_state["seite"] = "❤️ Vitalwerte"
    st.session_state["xabcde_selected"] = "A"
    st.session_state["visited_pages"] = set()
    st.session_state["workflow_manual_completion"] = {}
    st.session_state["protocol_generated"] = False
    st.session_state["generated_protocol_text"] = ""


def normalize_icd10_code(value):
    code = re.sub(r"\s+", "", str(value or "")).upper()
    code = code.rstrip("!+*#")
    if not re.fullmatch(r"[A-Z][0-9]{2}(?:\.[0-9A-Z]{1,2})?", code):
        return None
    return code


@st.cache_data(ttl=86400, show_spinner=False)
def lookup_icd10_diagnosis(code):
    normalized = normalize_icd10_code(code)
    if not normalized:
        return {"ok": False, "error": "Bitte einen gültigen Code eingeben, z. B. J45 oder I63.9."}

    slug = normalized.lower().replace(".", "-")
    source_url = f"https://gesund.bund.de/icd-code-suche/{slug}"
    request = urllib.request.Request(
        source_url,
        headers={"User-Agent": "RD-Protokoll-Generator/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            page = response.read().decode("utf-8", errors="replace")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return {
            "ok": False,
            "code": normalized,
            "error": "ICD-Suche derzeit nicht erreichbar. Bitte Verbindung prüfen und erneut versuchen.",
        }

    title_match = re.search(r"<title>(.*?)</title>", page, flags=re.IGNORECASE | re.DOTALL)
    title = html.unescape(re.sub(r"\s+", " ", title_match.group(1))).strip() if title_match else ""
    prefix = "ICD-10-Code:"
    if not title.startswith(prefix):
        return {
            "ok": False,
            "code": normalized,
            "error": "Für diesen ICD-10-GM-Code wurde keine eindeutige Diagnose gefunden.",
        }

    diagnosis = title[len(prefix):].strip()
    return {
        "ok": True,
        "code": normalized,
        "diagnosis": diagnosis,
        "source_url": source_url,
    }


def build_protocol_narrative(patient_data):
    v = patient_data.get("vitalwerte", {})
    x = patient_data.get("xabcde", {})
    s = patient_data.get("samplers", {})
    o = patient_data.get("opqrst", {})
    e = patient_data.get("einweisung", {})
    amls = patient_data.get("amls", {})
    m = patient_data.get("massnahmen", {})

    def present(value):
        return value not in [None, "", 0, "Keine Angabe"]

    def clean(value):
        return str(value).strip().rstrip(". ")

    def join_items(items):
        items = [item for item in items if item]
        if len(items) < 2:
            return "".join(items)
        return ", ".join(items[:-1]) + " und " + items[-1]

    sex = v.get("geschlecht")
    subject = "Die Patientin" if sex == "weiblich" else "Der Patient" if sex == "männlich" else "Die behandelte Person"
    paragraphs = []

    intro = subject
    has_intro_data = False
    if present(v.get("alter")):
        has_intro_data = True
        intro += f" war {int(v.get('alter'))} Jahre alt"
    if present(v.get("auffindesituation")):
        has_intro_data = True
        found_text = clean(v.get("auffindesituation"))
        if "vorgefunden" not in found_text.lower() and "angetroffen" not in found_text.lower():
            found_text += " angetroffen"
        intro += (" und wurde " if present(v.get("alter")) else " wurde ") + found_text
    intro += "."
    if present(s.get("ereignis")):
        has_intro_data = True
        intro += f" Als Ereignis wurde dokumentiert: {clean(s.get('ereignis'))}."
    if present(s.get("symptome")):
        has_intro_data = True
        intro += f" Als aktuelle Beschwerden wurden {clean(s.get('symptome'))} angegeben."
    if has_intro_data:
        paragraphs.append(intro)

    primary = []
    if present(x.get("atemweg")):
        primary.append(f"Der Atemweg wurde als {clean(x.get('atemweg')).lower()} beurteilt")
    if present(x.get("hws")):
        primary.append(f"hinsichtlich der HWS wurde „{clean(x.get('hws'))}“ dokumentiert")
    if primary:
        paragraphs.append(". ".join(primary) + ".")

    breathing = []
    if present(x.get("atmung")):
        breathing.append(f"die Atmung wurde als {clean(x.get('atmung')).lower()} eingeschätzt")
    if present(v.get("af")):
        af_cat, _ = categorize_af(v.get("af"))
        breathing.append(f"die Atemfrequenz betrug {v.get('af')}/min ({af_cat})")
    if present(v.get("spo2")):
        spo2_cat, _ = categorize_spo2(v.get("spo2"))
        breathing.append(f"die Sauerstoffsättigung lag bei {v.get('spo2')} % ({spo2_cat})")
    if present(x.get("atemgeraeusche")):
        breathing.append(f"die Atemgeräusche wurden als „{clean(x.get('atemgeraeusche'))}“ dokumentiert")
    if present(x.get("sauerstoff")) and x.get("sauerstoff") != "Keine":
        breathing.append(f"eine Sauerstoffgabe erfolgte mit {clean(x.get('sauerstoff'))}")
    if breathing:
        paragraphs.append("Respiratorisch zeigte sich folgender Befund: " + "; ".join(breathing) + ".")

    circulation = []
    if present(v.get("rr_sys")) and present(v.get("rr_dia")):
        rr_cat, _ = categorize_rr(v.get("rr_sys"), v.get("rr_dia"))
        circulation.append(f"Blutdruck {v.get('rr_sys')}/{v.get('rr_dia')} mmHg ({rr_cat})")
    if present(v.get("puls")):
        pulse_cat, _ = categorize_puls(v.get("puls"))
        circulation.append(f"Puls {v.get('puls')}/min ({pulse_cat})")
    if present(x.get("haut")):
        circulation.append(f"Haut {clean(x.get('haut')).lower()}")
    if present(x.get("rekap")):
        circulation.append(f"Rekapillarisierungszeit {clean(x.get('rekap'))}")
    if present(x.get("pulsqualitaet")):
        circulation.append(f"Pulsqualität {clean(x.get('pulsqualitaet')).lower()}")
    if circulation:
        paragraphs.append("Kreislaufseitig wurden " + join_items(circulation) + " erhoben.")

    neuro = []
    avpu_text = {"A": "wach und ansprechbar", "V": "auf Ansprache reagierend", "P": "auf Schmerzreiz reagierend", "U": "nicht ansprechbar"}
    if present(x.get("avpu")):
        neuro.append(f"AVPU {x.get('avpu')} ({avpu_text.get(x.get('avpu'), clean(x.get('avpu')))})")
    if present(v.get("gcs")):
        neuro.append(f"GCS {v.get('gcs')}/15")
    if present(x.get("pupillen")):
        neuro.append(f"Pupillen {clean(x.get('pupillen')).lower()}")
    if present(v.get("bz")):
        bz_cat, _ = categorize_bz(v.get("bz"))
        neuro.append(f"Blutzucker {v.get('bz')} mg/dL ({bz_cat})")
    if neuro:
        paragraphs.append("Neurologisch wurden " + join_items(neuro) + " dokumentiert.")

    befast = []
    for label, key in (("Balance", "befast_balance"), ("Eyes", "befast_eyes"), ("Face", "befast_face"), ("Arms", "befast_arms"), ("Speech", "befast_speech"), ("Time", "befast_time")):
        if present(x.get(key)):
            befast.append(f"{label}: {clean(x.get(key))}")
    if befast:
        paragraphs.append("Im BE-FAST-Screening wurden folgende Angaben erhoben: " + "; ".join(befast) + ".")

    exposure = []
    if present(x.get("bodycheck")):
        exposure.append(f"Bodycheck {clean(x.get('bodycheck')).lower()}")
    if present(x.get("bodycheck_text")):
        exposure.append(f"Auffälligkeiten: {clean(x.get('bodycheck_text'))}")
    if present(v.get("temperatur")):
        temp_cat, _ = categorize_temperature(v.get("temperatur"))
        exposure.append(f"Körpertemperatur {v.get('temperatur')} °C ({temp_cat})")
    if x.get("unterkuehlung"):
        exposure.append("Unterkühlung dokumentiert")
    if x.get("verbrennung"):
        exposure.append("Verbrennung dokumentiert")
    if exposure:
        paragraphs.append("Im Rahmen der weiteren Untersuchung wurden " + join_items(exposure) + " festgehalten.")

    history = []
    if present(s.get("allergien")):
        if s.get("allergien") == "Keine bekannt":
            history.append("keine bekannten Allergien")
        elif s.get("allergien") == "Vorhanden" and present(s.get("allergien_text")):
            history.append(f"folgende Allergien: {clean(s.get('allergien_text'))}")
        else:
            history.append(f"Allergiestatus: {clean(s.get('allergien'))}")
    if s.get("medikamente_option") == "Siehe Medikamentenplan":
        history.append("Medikation gemäß Medikamentenplan")
    elif s.get("medikamente_option") == "Medikamente eingeben" and present(s.get("medikamente")):
        history.append(f"Dauermedikation: {clean(s.get('medikamente'))}")
    if present(s.get("vorgeschichte")):
        history.append(f"Vorgeschichte: {clean(s.get('vorgeschichte'))}")
    if history:
        paragraphs.append("Anamnestisch wurden folgende Angaben dokumentiert: " + "; ".join(history) + ".")

    risk_labels = {
        "raucher": "Nikotinabusus",
        "alkohol": "Alkoholkonsum",
        "drogen": "Drogenkonsum",
        "diabetes": "Diabetes mellitus",
        "hypertonie": "arterielle Hypertonie",
        "antikoagulation": "Antikoagulation",
    }
    risks = [label for key, label in risk_labels.items() if s.get(key)]
    if present(s.get("risiken_sonstige")):
        risks.append(clean(s.get("risiken_sonstige")))
    if risks:
        paragraphs.append("Als Risikofaktoren wurden " + join_items(risks) + " erfasst.")
    if present(s.get("schwangerschaft")) and s.get("schwangerschaft") != "Nicht relevant":
        paragraphs.append(f"Zum Schwangerschaftsstatus wurde „{clean(s.get('schwangerschaft'))}“ angegeben.")

    last_events = []
    last_meal = s.get("letzte_mahlzeit_text") if s.get("letzte_mahlzeit") == "Eigene Eingabe" else s.get("letzte_mahlzeit")
    for label, value in (
        ("letzte Nahrungsaufnahme", last_meal),
        ("letzte Medikamenteneinnahme", s.get("letzte_medikamenteneinnahme")),
        ("letzter Stuhlgang", s.get("letzter_stuhlgang")),
        ("letzte Miktion", s.get("letzte_miktion")),
        ("letztes Erbrechen", s.get("letztes_erbrechen")),
    ):
        if present(value):
            last_events.append(f"{label}: {clean(value)}")
    if last_events:
        paragraphs.append("Zu den letzten Ereignissen wurde dokumentiert: " + "; ".join(last_events) + ".")

    if o.get("schmerz_vorhanden") == "Ja":
        pain = []
        for label, value in (("Beginn", o.get("onset")), ("Auslöser/Linderung", o.get("provocation")), ("Qualität", o.get("quality")), ("Region", o.get("region")), ("Ausstrahlung", o.get("radiation")), ("Verlauf", o.get("zeitverlauf")), ("Dauer", o.get("dauer"))):
            if present(value):
                pain.append(f"{label}: {clean(value)}")
        if present(o.get("nrs")):
            pain.append(f"Schmerzintensität NRS {o.get('nrs')}/10")
        if pain:
            paragraphs.append("Die Schmerzanamnese ergab: " + "; ".join(pain) + ".")

    if e.get("icd_code") and e.get("diagnose"):
        paragraphs.append(f"Auf der ärztlichen Einweisung war ICD-10-GM {e.get('icd_code')} mit der Bezeichnung „{clean(e.get('diagnose'))}“ angegeben.")
    if amls.get("arbeitsdiagnose"):
        paragraphs.append(f"Als dokumentierte AMLS-Arbeitsdiagnose wurde „{clean(amls.get('arbeitsdiagnose'))}“ festgehalten.")

    for entry in m.get("timeline", []):
        if present(entry.get("massnahme")):
            sentence = f"Um {entry.get('zeit', '--:--')} Uhr erfolgte die Maßnahme „{clean(entry.get('massnahme'))}“"
            if present(entry.get("wirkung")):
                sentence += f"; als Wirkung wurde „{clean(entry.get('wirkung'))}“ dokumentiert"
            paragraphs.append(sentence + ".")
    for medication in m.get("medikation", []):
        if present(medication.get("name")):
            sentence = f"Um {medication.get('zeit', '--:--')} Uhr wurde {clean(medication.get('name'))}"
            if present(medication.get("dosis")):
                sentence += f" in einer Dosis von {clean(medication.get('dosis'))}"
            if present(medication.get("weg")):
                sentence += f" über den Applikationsweg {clean(medication.get('weg'))}"
            sentence += " verabreicht"
            if present(medication.get("wirkung")):
                sentence += f"; als Wirkung wurde „{clean(medication.get('wirkung'))}“ dokumentiert"
            paragraphs.append(sentence + ".")

    if present(v.get("kurzbericht")):
        paragraphs.append(f"Ergänzender Einsatzbericht: {clean(v.get('kurzbericht'))}.")

    return paragraphs


def generate_protocol():

    protocol = ""
    patient = st.session_state.get("patient", {})
    if not _has_content(patient):
        return ""

    # Hinweis: Keine personenbezogenen Metadaten werden ausgegeben (Datenschutz)

    v = patient.get("vitalwerte", {})
    x = patient.get("xabcde", {})
    s = patient.get("samplers", {})
    o = patient.get("opqrst", {})
    e = patient.get("einweisung", {})
    amls = patient.get("amls", {})
    m = patient.get("massnahmen", {})

    protocol += "RD-PROTOKOLL – DOKUMENTATIONSENTWURF\n"
    protocol += "=" * 50 + "\n"
    protocol += f"Erstellt am {datetime.now().strftime('%d.%m.%Y um %H:%M:%S')} Uhr\n"
    protocol += "Enthält ausschließlich dokumentierte Angaben; vor Verwendung vollständig prüfen.\n\n"

    narrative_paragraphs = build_protocol_narrative(patient)
    if narrative_paragraphs:
        protocol += "AUSFORMULIERTER EINSATZVERLAUF\n"
        protocol += "=" * 50 + "\n"
        protocol += "\n\n".join(narrative_paragraphs) + "\n\n"

    if e.get("icd_code") and e.get("diagnose"):
        protocol += "ÄRZTLICHE EINWEISUNG\n"
        protocol += "=" * 50 + "\n"
        protocol += f"ICD-10-GM {e.get('icd_code')}: {e.get('diagnose')}\n"
        if e.get("hinweis"):
            protocol += f"Einweisungshinweis: {e.get('hinweis')}\n"
        protocol += "\n"

    if amls.get("arbeitsdiagnose"):
        protocol += "AMLS-DIFFERENZIALDIAGNOSE\n"
        protocol += "=" * 50 + "\n"
        protocol += f"Arbeitsdiagnose: {amls.get('arbeitsdiagnose')}\n"
        if amls.get("excluded"):
            protocol += "Im Trichter zurückgestellt/ausgeschlossen: " + "; ".join(amls.get("excluded", [])) + "\n"
        protocol += "\n"

    # xABCDE - ausführlicher und strukturierter, mit integrierten Vitalwerten
    xabcde = ""
    blutung = x.get("blutung")
    if blutung and blutung != "Keine Angabe":
        xabcde += f"\nX — EXSANGUINATION (Blutung):\n  Status: {blutung}\n"
        if x.get("blutung_lokalisation"):
            xabcde += f"  Ort: {x.get('blutung_lokalisation')}\n"

    if x.get("atemweg") and x.get("atemweg") != "Keine Angabe":
        xabcde += f"\nA — ATEMWEG:\n  Status: {x.get('atemweg')}\n"
        if x.get("hws"):
            xabcde += f"  HWS-Stabilisierung: {x.get('hws')}\n"

    # B - ATMUNG mit SpO2 und Atemfrequenz
    b_section = ""
    af = v.get("af")
    spo2 = v.get("spo2")
    
    if x.get("atmung") and x.get("atmung") != "Keine Angabe":
        b_section = f"B — ATMUNG:\n  Status: {x.get('atmung')}\n"
        if x.get("atemgeraeusche"):
            b_section += f"  Atemgeräusche: {x.get('atemgeraeusche')}\n"
        if x.get("sauerstoff"):
            b_section += f"  Sauerstofftherapie: {x.get('sauerstoff')}\n"
    
    # Atemfrequenz (immer hinzufügen, wenn vorhanden)
    if af and af != 0:
        if not b_section:
            b_section = f"B — ATMUNG:\n"
        af_cat, af_val = categorize_af(af)
        b_section += f"  Atemfrequenz: {af} /min ({af_cat})\n"
    
    # SpO2 (immer hinzufügen, wenn vorhanden)
    if spo2 and spo2 != 0:
        if not b_section:
            b_section = f"B — ATMUNG:\n"
        s_cat, s_val = categorize_spo2(spo2)
        b_section += f"  Sauerstoffsättigung: {spo2} % ({s_cat})\n"
    
    if b_section:
        xabcde += "\n" + b_section

    # C - ZIRKULATION mit Blutdruck und Pulsfrequenz
    c_section = ""
    rr_sys = v.get("rr_sys")
    rr_dia = v.get("rr_dia")
    puls = v.get("puls")
    
    if x.get("haut") and x.get("haut") != "Keine Angabe":
        c_section = f"C — ZIRKULATION (Kreislauf):\n  Hautzeichen: {x.get('haut')}\n"
        if x.get("rekap"):
            c_section += f"  Kapillare Füllung: {x.get('rekap')}\n"
        if x.get("pulsqualitaet"):
            c_section += f"  Pulsqualität: {x.get('pulsqualitaet')}\n"
    
    # Blutdruck (immer hinzufügen, wenn vorhanden)
    if rr_sys and rr_dia:
        if not c_section:
            c_section = f"C — ZIRKULATION (Kreislauf):\n"
        rr_cat, rr_vals = categorize_rr(rr_sys, rr_dia)
        c_section += f"  Blutdruck: {rr_sys}/{rr_dia} mmHg ({rr_cat})\n"
    
    # Pulsfrequenz (immer hinzufügen, wenn vorhanden)
    if puls and puls != 0:
        if not c_section:
            c_section = f"C — ZIRKULATION (Kreislauf):\n"
        p_cat, p_val = categorize_puls(puls)
        c_section += f"  Pulsfrequenz: {puls} /min ({p_cat})\n"
    
    if c_section:
        xabcde += "\n" + c_section

    # D - DISABILITY mit GCS und Blutzucker
    d_section = ""
    gcs = v.get("gcs")
    bz = v.get("bz")
    
    if x.get("avpu") and x.get("avpu") != "Keine Angabe":
        d_section = f"D — DISABILITY (Neurologischer Status):\n  Bewusstsein (AVPU): {x.get('avpu')}\n"
        if x.get("pupillen"):
            d_section += f"  Pupillen: {x.get('pupillen')}\n"

    befast_values = [
        ("Balance", x.get("befast_balance")),
        ("Eyes", x.get("befast_eyes")),
        ("Face", x.get("befast_face")),
        ("Arms", x.get("befast_arms")),
        ("Speech", x.get("befast_speech")),
        ("Time", x.get("befast_time")),
    ]
    documented_befast = [(label, value) for label, value in befast_values if _is_valid_value(value)]
    if documented_befast:
        if not d_section:
            d_section = "D — DISABILITY (Neurologischer Status):\n"
        d_section += "  BE-FAST:\n"
        for label, value in documented_befast:
            d_section += f"    {label}: {value}\n"
    
    # GCS (immer hinzufügen, wenn vorhanden)
    if gcs:
        if not d_section:
            d_section = f"D — DISABILITY (Neurologischer Status):\n"
        try:
            g = int(gcs)
            if g == 15:
                g_cat = "Normal (vollständig orientiert)"
            elif g >= 13:
                g_cat = "Leicht eingeschränkt"
            elif g >= 9:
                g_cat = "Mäßig eingeschränkt"
            else:
                g_cat = "Schwer eingeschränkt / Intubationskriterium"
        except Exception:
            g_cat = "Unbekannt"
        d_section += f"  Glasgow Coma Scale: {gcs}/15 ({g_cat})\n"
    
    # Blutzucker (immer hinzufügen, wenn vorhanden)
    if bz and bz != 0:
        if not d_section:
            d_section = f"D — DISABILITY (Neurologischer Status):\n"
        bz_cat, bz_val = categorize_bz(bz)
        d_section += f"  Blutzucker: {bz} mg/dL ({bz_cat})\n"
    
    if d_section:
        xabcde += "\n" + d_section

    # E - EXPOSURE mit Temperatur
    e_section = ""
    temperatur = v.get("temperatur")
    
    if x.get("bodycheck") and x.get("bodycheck") != "Keine Angabe":
        e_section = f"E — EXPOSURE (Ganzkörperuntersuchung):\n  Status: {x.get('bodycheck')}\n"
        if x.get("bodycheck_text"):
            e_section += f"  Auffälligkeiten: {x.get('bodycheck_text')}\n"
        if x.get("unterkuehlung"):
            e_section += f"  Unterkühlung: {x.get('unterkuehlung')}\n"
        if x.get("verbrennung"):
            e_section += f"  Thermische Verletzungen: {x.get('verbrennung')}\n"
    
    # Körpertemperatur (immer hinzufügen, wenn vorhanden)
    if temperatur is not None:
        if not e_section:
            e_section = f"E — EXPOSURE (Ganzkörperuntersuchung):\n"
        t_cat, t_val = categorize_temperature(temperatur)
        e_section += f"  Körpertemperatur: {temperatur} °C ({t_cat})\n"
    
    # SAMPLERS und OPQRST zusätzlich unter E aufführen
    samplers_under_e = ""
    if s.get("symptome"):
        samplers_under_e += f"    S Symptome: {s.get('symptome')}\n"

    allergien = s.get("allergien")
    if allergien == "Keine bekannt":
        samplers_under_e += "    A Allergien: Keine bekannt\n"
    elif allergien == "Vorhanden":
        samplers_under_e += f"    A Allergien: {s.get('allergien_text','')}\n"

    medopt = s.get("medikamente_option")
    if medopt == "Siehe Medikamentenplan":
        samplers_under_e += "    M Medikamente: Siehe Medikamentenplan\n"
    elif medopt == "Medikamente eingeben":
        samplers_under_e += f"    M Medikamente: {s.get('medikamente','')}\n"

    if s.get("vorgeschichte"):
        samplers_under_e += f"    P Vorgeschichte: {s.get('vorgeschichte')}\n"

    letzte = s.get('letzte_mahlzeit')
    if letzte and letzte != "Keine Angabe":
        if letzte == 'Eigene Eingabe':
            samplers_under_e += f"    L Letzte Mahlzeit: {s.get('letzte_mahlzeit_text','')}\n"
        else:
            samplers_under_e += f"    L Letzte Mahlzeit: {letzte}\n"

    additional_last_events = [
        ("Letzte Medikamenteneinnahme", s.get("letzte_medikamenteneinnahme")),
        ("Letzter Stuhlgang", s.get("letzter_stuhlgang")),
        ("Letzte Miktion", s.get("letzte_miktion")),
        ("Letztes Erbrechen", s.get("letztes_erbrechen")),
    ]
    for label, value in additional_last_events:
        if _is_valid_value(value):
            samplers_under_e += f"    L {label}: {value}\n"

    if s.get('ereignis'):
        samplers_under_e += f"    E Ereignis: {s.get('ereignis')}\n"

    risks = []
    for k in ['raucher', 'alkohol', 'drogen', 'diabetes', 'hypertonie', 'antikoagulation']:
        if s.get(k):
            risks.append(k.upper())
    if s.get('risiken_sonstige'):
        risks.append(s.get('risiken_sonstige'))
    if risks:
        samplers_under_e += "    R Risikofaktoren: " + ", ".join(map(str, risks)) + "\n"

    schw = s.get('schwangerschaft')
    if schw and schw != 'Nicht relevant':
        samplers_under_e += f"    S Schwangerschaft: {schw}\n"

    opqrst_under_e = ""
    if o.get('onset'):
        opqrst_under_e += f"    O Onset: {o.get('onset')}"
        if o.get('onset_text'):
            opqrst_under_e += f" — {o.get('onset_text')}"
        opqrst_under_e += "\n"
    if o.get('provocation'):
        opqrst_under_e += f"    P Provocation: {o.get('provocation')}"
        if o.get('provocation_text'):
            opqrst_under_e += f" — {o.get('provocation_text')}"
        opqrst_under_e += "\n"
    if o.get('quality'):
        opqrst_under_e += f"    Q Quality: {o.get('quality')}"
        if o.get('quality_text'):
            opqrst_under_e += f" — {o.get('quality_text')}"
        opqrst_under_e += "\n"
    if o.get('region'):
        opqrst_under_e += f"    R Region: {o.get('region')}\n"
    if o.get('radiation'):
        opqrst_under_e += f"      Ausstrahlung: {o.get('radiation')}\n"
    if o.get('nrs'):
        try:
            n = int(o.get('nrs'))
            if n > 0:
                opqrst_under_e += f"    S Severity: {n}/10\n"
                if o.get('severity_desc'):
                    opqrst_under_e += f"      Auswirkung: {o.get('severity_desc')}\n"
        except Exception:
            pass
    if o.get('zeitverlauf'):
        opqrst_under_e += f"    T Time: {o.get('zeitverlauf')}\n"
        if o.get('dauer'):
            opqrst_under_e += f"      Dauer: {o.get('dauer')}\n"

    if samplers_under_e:
        if not e_section:
            e_section = "E — EXPOSURE (Ganzkörperuntersuchung):\n"
        e_section += "  SAMPLERS:\n" + samplers_under_e

    if opqrst_under_e:
        if not e_section:
            e_section = "E — EXPOSURE (Ganzkörperuntersuchung):\n"
        e_section += "  OPQRST:\n" + opqrst_under_e

    if e_section:
        xabcde += "\n" + e_section

    if xabcde:
        protocol += "xABCDE — STRUKTURIERTE UNTERSUCHUNG\n"
        protocol += "=" * 50 + "\n"
        protocol += xabcde + "\n"

    # Maßnahmen-Timeline
    timeline_entries = m.get("timeline", [])
    if timeline_entries:
        protocol += "MAßNAHMEN-TIMELINE\n"
        protocol += "=" * 50 + "\n"
        for entry in timeline_entries:
            zeit = entry.get("zeit", "--:--")
            massnahme = entry.get("massnahme", "Maßnahme")
            wirkung = entry.get("wirkung", "")
            line = f"{zeit} - {massnahme}"
            if wirkung:
                line += f" | Wirkung: {wirkung}"
            protocol += line + "\n"
        protocol += "\n"

    # Medikationsmodul
    meds = m.get("medikation", [])
    if meds:
        protocol += "MEDIKATION\n"
        protocol += "=" * 50 + "\n"
        for med in meds:
            zeit = med.get("zeit", "--:--")
            name = med.get("name", "Unbekannt")
            dosis = med.get("dosis", "k.A.")
            weg = med.get("weg", "k.A.")
            wirkung = med.get("wirkung", "")
            line = f"{zeit} - {name}, Dosis: {dosis}, Applikation: {weg}"
            if wirkung:
                line += f", Wirkung: {wirkung}"
            protocol += line + "\n"
        protocol += "\n"

    # Kurzbericht
    kurzbericht = v.get('kurzbericht', '').strip()
    if kurzbericht:
        protocol += "EINSATZ-KURZBERICHT\n"
        protocol += "=" * 50 + "\n"
        protocol += kurzbericht + "\n\n"

    return protocol
# --------------------------------------------------
# Grundeinstellungen
# --------------------------------------------------

st.set_page_config(
    page_title="RD-Protokoll Generator",
    page_icon="🚑",
    layout="wide"
)

# --- Custom styling (Dark Mode, centered navigation) -----------------
st.markdown(
        """
        <style>
    :root {
        --bg:#07111f;
        --bg-2:#0b1730;
        --panel:rgba(15,27,49,0.62);
        --panel-strong:rgba(16,28,52,0.84);
        --panel-soft:rgba(255,255,255,0.055);
        --muted:#9fb2ce;
        --accent:#5ea8ff;
        --accent-2:#ff7c88;
        --accent-3:#4be0bb;
        --accent-4:#ffb86a;
        --text:#eef5ff;
        --line:rgba(255,255,255,0.10);
        --shadow:0 30px 70px rgba(2,8,24,0.36);
    }
    @keyframes riseIn {
        from { opacity:0; transform:translateY(18px); }
        to { opacity:1; transform:translateY(0); }
    }
    @keyframes softPulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(94,168,255,0.16); }
        50% { box-shadow: 0 0 0 14px rgba(94,168,255,0); }
    }
    @keyframes glassSheen {
        0% { transform: translateX(-130%) rotate(10deg); }
        100% { transform: translateX(240%) rotate(10deg); }
    }
    @keyframes ambulanceFloat {
        0%, 100% { transform: translateY(0px) rotate(-2deg); }
        50% { transform: translateY(-8px) rotate(1deg); }
    }
    @keyframes blueFlash {
        0%, 100% { opacity:0.25; transform: scale(0.95); }
        50% { opacity:0.9; transform: scale(1.08); }
    }
    @keyframes redFlash {
        0%, 100% { opacity:0.18; transform: scale(0.92); }
        50% { opacity:0.72; transform: scale(1.04); }
    }
    html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stMainBlockContainer"], section.main {
        background:
            radial-gradient(circle at 10% -4%, rgba(78,143,255,0.26), transparent 28%),
            radial-gradient(circle at 88% 8%, rgba(255,108,139,0.18), transparent 26%),
            radial-gradient(circle at 50% 100%, rgba(75,224,187,0.10), transparent 28%),
            linear-gradient(140deg, var(--bg) 0%, var(--bg-2) 54%, #071220 100%) !important;
        color: var(--text);
        font-family: "Aptos", "Segoe UI Variable", "Segoe UI", sans-serif;
    }
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    section.main {
        color-scheme: dark;
    }
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"] {
        background: transparent !important;
    }
    [data-testid="stVerticalBlock"],
    [data-testid="stHorizontalBlock"] {
        background: transparent;
    }
    h1, h2, h3 { letter-spacing:-0.02em; }
    h3 {
        color:#b8dcff;
        margin-top:24px;
        margin-bottom:12px;
        border-bottom:1px solid rgba(141,199,255,0.14);
        padding-bottom:9px;
    }
    p, li, label { color: rgba(236,244,255,0.94); }
    .hero-card {
        position: relative;
        overflow: hidden;
        margin: 12px 0 20px;
        padding: 26px 28px 24px;
        border-radius: 34px;
        border: 1px solid rgba(255,255,255,0.14);
        background:
            radial-gradient(circle at 10% 14%, rgba(96,175,255,0.26), transparent 24%),
            radial-gradient(circle at 92% 10%, rgba(255,120,156,0.16), transparent 22%),
            linear-gradient(135deg, rgba(18,32,58,0.88) 0%, rgba(10,22,40,0.84) 100%);
        box-shadow: var(--shadow);
        backdrop-filter: blur(18px) saturate(150%);
        -webkit-backdrop-filter: blur(18px) saturate(150%);
        animation: riseIn 0.7s ease-out;
    }
    .hero-card::before {
        content:"";
        position:absolute;
        inset:-40% auto auto -10%;
        width:260px;
        height:260px;
        background: radial-gradient(circle, rgba(87,164,255,0.24), transparent 72%);
        pointer-events:none;
    }
    .hero-card::after {
        content:"";
        position:absolute;
        top:-40%;
        left:-16%;
        width:34%;
        height:180%;
        background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.09), rgba(255,255,255,0));
        transform: rotate(10deg);
        animation: glassSheen 10s linear infinite;
        pointer-events:none;
    }
    .hero-row { display:flex; justify-content:space-between; align-items:flex-start; gap:22px; flex-wrap:wrap; position:relative; z-index:1; }
    .hero-kicker { display:inline-flex; align-items:center; gap:10px; font-size:0.74rem; letter-spacing:0.18em; text-transform:uppercase; color:rgba(231,241,255,0.68); font-weight:900; }
    .hero-kicker-badge { width:10px; height:10px; border-radius:999px; background: linear-gradient(135deg, #61b6ff 0%, #ff7b8f 100%); box-shadow: 0 0 0 5px rgba(97,182,255,0.10); animation: softPulse 3.4s ease-in-out infinite; }
    .hero-title { margin-top:10px; font-size:2.28rem; line-height:0.98; font-weight:950; letter-spacing:-0.05em; color:#fbfdff; text-shadow: 0 10px 28px rgba(5,14,30,0.22); }
    .hero-meta { display:flex; gap:12px; flex-wrap:wrap; margin-top:18px; }
    .hero-chip {
        display:inline-flex;
        align-items:center;
        gap:8px;
        padding:10px 13px;
        border-radius:999px;
        background: rgba(255,255,255,0.06);
        border:1px solid rgba(255,255,255,0.10);
        color:#eef5ff;
        font-size:0.80rem;
        font-weight:850;
        box-shadow: 0 10px 22px rgba(2,8,24,0.16);
        transition: transform 0.22s ease, border-color 0.22s ease, background 0.22s ease;
    }
    .hero-chip:hover {
        transform: translateY(-2px);
        border-color: rgba(255,255,255,0.20);
        background: rgba(255,255,255,0.09);
    }
    .hero-chip span { opacity:0.72; font-weight:700; }
    .hero-cta { display:flex; align-items:flex-start; justify-content:flex-end; min-width:170px; }
    .hero-status {
        display:inline-flex;
        align-items:center;
        gap:8px;
        padding:11px 14px;
        border-radius:16px;
        background: linear-gradient(135deg, rgba(87,164,255,0.16), rgba(255,125,102,0.14));
        border:1px solid rgba(255,255,255,0.10);
        color:#f4f8ff;
        font-size:0.80rem;
        font-weight:850;
        box-shadow: 0 14px 26px rgba(2,8,24,0.20);
    }
    .hero-status-dot { width:8px; height:8px; border-radius:999px; background: #5cffb1; box-shadow: 0 0 0 5px rgba(92,255,177,0.10); }
    .workflow-shell {
        margin: 10px 0 16px;
        padding: 18px 18px 16px;
        border-radius: 26px;
        border: 1px solid rgba(255,255,255,0.10);
        background: linear-gradient(180deg, rgba(255,255,255,0.055), rgba(255,255,255,0.02));
        backdrop-filter: blur(16px) saturate(150%);
        -webkit-backdrop-filter: blur(16px) saturate(150%);
        box-shadow: 0 18px 40px rgba(2,8,24,0.22);
        animation: riseIn 0.85s ease-out;
    }
    .workflow-head { display:flex; justify-content:space-between; gap:14px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
    .workflow-kicker { font-size:0.76rem; text-transform:uppercase; letter-spacing:0.16em; color:rgba(238,245,255,0.58); font-weight:900; }
    .workflow-title { font-size:1.12rem; font-weight:900; color:#f5f9ff; }
    .workflow-count { padding:9px 13px; border-radius:999px; background:rgba(255,255,255,0.055); color:#dce9ff; font-weight:800; font-size:0.84rem; border:1px solid rgba(255,255,255,0.08); }
    .workflow-progress { height:10px; border-radius:999px; background:rgba(255,255,255,0.08); overflow:hidden; margin-bottom:12px; }
    .workflow-progress-bar { height:100%; border-radius:999px; background:linear-gradient(90deg, #5ea8ff 0%, #44ddbd 52%, #ff9c7c 100%); box-shadow: 0 0 18px rgba(94,168,255,0.22); }
    .rd-summary-card {
        margin: 14px 0 10px;
        padding: 14px 16px;
        border-radius: 18px;
        background: linear-gradient(180deg, rgba(255,255,255,0.055), rgba(255,255,255,0.025));
        border: 1px solid rgba(255,255,255,0.09);
        box-shadow: 0 14px 30px rgba(2,8,24,0.18);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        animation: riseIn 0.45s ease-out;
    }
    .rd-summary-head { font-size:0.74rem; text-transform:uppercase; letter-spacing:0.16em; color:rgba(235,244,255,0.58); font-weight:900; margin-bottom:10px; }
    .rd-summary-row { display:flex; flex-wrap:wrap; gap:8px; }
    .rd-summary-chip {
        display:inline-flex;
        align-items:center;
        padding:8px 10px;
        border-radius:999px;
        background: rgba(7,17,31,0.34);
        border:1px solid rgba(255,255,255,0.08);
        color:#eef5ff;
        font-size:0.82rem;
        line-height:1.2;
    }
    .rd-summary-empty .rd-summary-muted { color: rgba(234,243,255,0.62); font-size:0.88rem; }
    [data-testid="stButton"] > button {
        position: relative;
        overflow: hidden;
        width:100%;
        padding: 12px 18px;
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.12);
        background: linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.018));
        color: var(--text);
        font-weight: 850;
        margin:0;
        box-shadow: 0 14px 28px rgba(2,8,24,0.20);
        transition: transform 0.24s ease, border-color 0.24s ease, box-shadow 0.24s ease, background 0.24s ease;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        min-height: 52px;
        touch-action: manipulation;
    }
    [data-testid="stButton"] > button::before {
        content:"";
        position:absolute;
        inset:0;
        background: linear-gradient(120deg, rgba(255,255,255,0), rgba(255,255,255,0.11), rgba(255,255,255,0));
        transform: translateX(-150%);
        transition: transform 0.55s ease;
    }
    [data-testid="stButton"] > button:hover {
        border-color: rgba(255,255,255,0.24);
        transform: translateY(-3px);
        box-shadow: 0 18px 36px rgba(2,8,24,0.28);
        background: linear-gradient(180deg, rgba(255,255,255,0.065), rgba(255,255,255,0.028));
    }
    [data-testid="stButton"] > button:hover::before { transform: translateX(150%); }
    [data-testid="stButton"] > button:focus,
    [data-testid="stButton"] > button:focus-visible {
        outline:none;
        border-color: rgba(94,168,255,0.44);
        box-shadow: 0 0 0 4px rgba(94,168,255,0.16), 0 18px 36px rgba(2,8,24,0.26);
    }
    [data-testid="stButton"] > button[kind='primary'] {
        color:#fff;
        border: none;
        background: linear-gradient(135deg, rgba(95,137,255,0.98) 0%, rgba(255,94,114,0.96) 100%);
        box-shadow: 0 18px 32px rgba(112,102,255,0.24);
    }
    [data-testid="stButton"] > button[kind='primary']:hover {
        box-shadow: 0 24px 40px rgba(112,102,255,0.30);
        filter: saturate(1.08) brightness(1.03);
    }
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-testid="stTextArea"] textarea {
            background:rgba(8,20,38,0.72) !important;
            color:var(--text) !important;
            border:1px solid rgba(255,255,255,0.10) !important;
            border-radius:14px !important;
            font-size:0.95rem !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 10px 20px rgba(2,8,24,0.12) !important;
            min-height: 52px !important;
        }
        [data-testid="stTextInput"] input:focus,
        [data-testid="stNumberInput"] input:focus,
        [data-testid="stTextArea"] textarea:focus {
            border-color:var(--accent) !important;
            box-shadow: 0 0 0 3px rgba(75,140,255,0.16), 0 16px 28px rgba(2,8,24,0.16) !important;
        }
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            background:rgba(8,20,38,0.72) !important;
            color:var(--text) !important;
            border:1px solid rgba(255,255,255,0.10) !important;
            border-radius:14px !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 10px 20px rgba(2,8,24,0.12) !important;
            min-height: 52px !important;
        }
        [data-testid="stSelectbox"] div[data-baseweb="select"] input {
            background: transparent !important;
            box-shadow: none !important;
            border: none !important;
        }
        [role="option"] {
            min-height:52px !important;
            padding:12px 14px !important;
            font-size:0.98rem !important;
            display:flex !important;
            align-items:center !important;
            touch-action:manipulation;
        }
        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] span {
            font-weight: 800 !important;
            letter-spacing: 0.01em;
            color: #f4f8ff !important;
        }
        [data-testid="stSelectbox"] { margin: 10px 0; }
        [data-testid="stRadio"] > label {
            padding:10px 12px;
            border-radius:14px;
            cursor:pointer;
            transition: all 0.22s ease;
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.04);
        }
        [data-testid="stRadio"] > label:hover { background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.08); }
        [data-testid="stRadio"] div[role="radiogroup"] {
            display:grid;
            grid-template-columns:repeat(2, minmax(0, 1fr));
            gap:10px;
            margin-top:8px;
        }
        [data-testid="stRadio"] div[role="radiogroup"] > label {
            min-height:54px;
            margin:0 !important;
            padding:10px 12px !important;
            border-radius:14px;
            border:1px solid rgba(255,255,255,0.09);
            background:rgba(8,20,38,0.60);
            cursor:pointer;
            display:flex;
            align-items:center;
            touch-action:manipulation;
            transition:border-color .18s ease, background .18s ease, transform .18s ease;
        }
        [data-testid="stRadio"] div[role="radiogroup"] > label:hover {
            border-color:rgba(94,168,255,0.42);
            background:rgba(94,168,255,0.09);
        }
        [data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
            border-color:rgba(94,168,255,0.72);
            background:linear-gradient(135deg, rgba(75,140,255,0.24), rgba(92,222,177,0.12));
            box-shadow:0 0 0 2px rgba(75,140,255,0.10);
        }
        [data-testid="stRadio"] div[role="radiogroup"] p { font-size:0.96rem !important; font-weight:750 !important; }
        [data-testid="stSlider"] > div > div > div { border-radius:10px; }
        [data-testid="stCheckbox"] > label {
            cursor:pointer;
            min-height:54px;
            display:flex;
            align-items:center;
            padding:10px 12px;
            border-radius:14px;
            border:1px solid rgba(255,255,255,0.09);
            background:rgba(8,20,38,0.60);
            touch-action:manipulation;
        }
        [data-testid="stCheckbox"] > label:has(input:checked) {
            border-color:rgba(94,168,255,0.72);
            background:linear-gradient(135deg, rgba(75,140,255,0.24), rgba(92,222,177,0.12));
        }
        [data-testid="stNumberInput"] { margin: 10px 0; }
        [data-testid="stNumberInput"] button {
            min-width:48px;
            min-height:48px;
            touch-action:manipulation;
        }
        [data-testid="stTextArea"] { margin: 10px 0; }
        hr { border-color: rgba(255,255,255,0.06) !important; margin: 22px 0; }
        [data-testid="stAlert"] {
            border-radius: 18px;
            border: 1px solid rgba(255,255,255,0.10);
            background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02)) !important;
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            box-shadow: 0 18px 34px rgba(2,8,24,0.16);
        }
        [data-testid="stExpander"] {
            border-radius: 18px !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            background: linear-gradient(180deg, rgba(255,255,255,0.032), rgba(255,255,255,0.015)) !important;
            box-shadow: 0 14px 28px rgba(2,8,24,0.14);
            overflow: hidden;
        }
        [data-testid="stExpander"]:hover { border-color: rgba(255,255,255,0.14) !important; }
        [data-testid="stExpander"] summary { padding-top: 0.2rem; padding-bottom: 0.2rem; }
        [data-testid="stCodeBlock"], code { border-radius: 16px !important; }
        section[data-testid='stSidebar']{ display:none; }
        main .block-container { padding-top: 12px; padding-left: 80px; padding-right:80px; padding-bottom:120px; }
        @media (max-width: 900px) {
            main .block-container { padding-left: 18px; padding-right: 18px; }
            .hero-card { padding: 20px 18px 18px; border-radius: 24px; }
            .hero-title { font-size: 1.72rem; }
            .workflow-shell { padding: 14px 14px 12px; border-radius: 20px; }
            .hero-ambulance-wrap { opacity: 0.18 !important; right: 8px !important; bottom: 4px !important; transform: scale(0.75) !important; }
            [data-testid="stButton"] > button { min-height: 56px; font-size: 0.96rem; }
            [data-testid="stTextInput"] input,
            [data-testid="stNumberInput"] input,
            [data-testid="stSelectbox"] div[data-baseweb="select"] > div { min-height:56px !important; font-size:1rem !important; }
            [data-testid="stRadio"] div[role="radiogroup"] > label { min-height:58px; }
        }
    .st-key-tablet_bottom_nav {
            position: fixed;
            bottom: 0;
            left: 80px;
            right: 80px;
            z-index: 999;
            margin: 0;
            padding: 9px 12px;
            border: 1px solid rgba(255,255,255,0.09);
            border-bottom: none;
            border-radius: 18px 18px 0 0;
            background: rgba(7,17,31,0.97);
            box-shadow: 0 -10px 24px rgba(2,8,24,0.30);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
        }
        .st-key-tablet_bottom_nav .workflow-nav-status {
            min-height:44px;
            display:flex;
            align-items:center;
            justify-content:center;
            color:rgba(238,245,255,0.68);
            font-size:0.82rem;
            text-align:center;
        }
        .st-key-tablet_bottom_nav .workflow-nav-status.is-done { color:#86e7c2; }
        .workflow-compact-head {
            margin:8px 0 8px;
            padding:12px 15px;
            border-radius:18px;
            border:1px solid rgba(255,255,255,0.08);
            background:rgba(255,255,255,0.025);
        }
        .workflow-compact-row { display:flex; align-items:center; justify-content:space-between; gap:14px; }
        .workflow-compact-title { color:#f5f9ff; font-size:1rem; font-weight:850; }
        .workflow-compact-meta { color:rgba(238,245,255,0.58); font-size:0.78rem; white-space:nowrap; }
        .workflow-compact-track { height:4px; margin-top:9px; border-radius:999px; background:rgba(255,255,255,0.07); overflow:hidden; }
        .workflow-compact-fill { height:100%; border-radius:999px; background:#5ea8ff; }
        .st-key-workflow_overview [data-testid="stExpander"] { margin-bottom:14px; box-shadow:none !important; }
        .st-key-workflow_overview [data-testid="stButton"] > button {
            min-height:42px;
            padding:8px 10px;
            box-shadow:none;
            font-size:0.84rem;
        }
        @keyframes protocolGreenGlow {
            0%, 100% { box-shadow:0 0 0 1px rgba(74,222,128,.28), 0 0 12px rgba(34,197,94,.32); }
            50% { box-shadow:0 0 0 2px rgba(74,222,128,.52), 0 0 24px rgba(34,197,94,.62); }
        }
        .st-key-workflow_step_9 button {
            color:#fff !important;
            border-color:#69f0ae !important;
            background:linear-gradient(135deg, #087f5b 0%, #22c55e 100%) !important;
            animation:protocolGreenGlow 1.8s ease-in-out infinite !important;
        }
        .st-key-workflow_step_9 button:hover {
            background:linear-gradient(135deg, #0b9668 0%, #35d873 100%) !important;
        }
        /* Bewegungen sparsam einsetzen: Die Oberfläche soll im Einsatz ruhig bleiben. */
        .hero-card, .workflow-shell, .rd-summary-card { animation:none !important; }
        .hero-card::after, .hero-kicker-badge, .hero-ambulance-wrap,
        .hero-ambulance-light-blue, .hero-ambulance-light-red { animation:none !important; }
        @media (max-width: 900px) {
            .st-key-tablet_bottom_nav { left:8px; right:8px; padding:10px; }
            .workflow-compact-row { align-items:flex-start; }
            .workflow-compact-meta { white-space:normal; text-align:right; }
        }
        </style>
        """,
        unsafe_allow_html=True,
)

st.markdown(
    """
    <div style="
        position:relative;
        overflow:hidden;
        margin: 10px 0 22px;
        padding: 28px 30px 26px;
        border-radius: 30px;
        border: 1px solid rgba(255,255,255,0.14);
        background:
            radial-gradient(circle at 12% 16%, rgba(96,175,255,0.24), transparent 24%),
            radial-gradient(circle at 90% 8%, rgba(255,120,156,0.15), transparent 22%),
            linear-gradient(135deg, rgba(18,32,58,0.92) 0%, rgba(10,22,40,0.88) 100%);
        box-shadow: 0 28px 60px rgba(2,8,24,0.32);
    ">
        <div class="hero-ambulance-wrap" style="position:absolute; right:22px; bottom:10px; width:300px; height:150px; pointer-events:none; opacity:0.26; z-index:0; animation:ambulanceFloat 4.8s ease-in-out infinite;">
            <div class="hero-ambulance-light-blue" style="position:absolute; top:34px; left:86px; width:82px; height:82px; border-radius:999px; background:radial-gradient(circle, rgba(94,168,255,0.58) 0%, rgba(94,168,255,0.18) 34%, rgba(94,168,255,0) 72%); filter:blur(3px); animation:blueFlash 1.3s ease-in-out infinite;"></div>
            <div class="hero-ambulance-light-red" style="position:absolute; top:38px; left:138px; width:72px; height:72px; border-radius:999px; background:radial-gradient(circle, rgba(255,116,133,0.48) 0%, rgba(255,116,133,0.16) 34%, rgba(255,116,133,0) 72%); filter:blur(4px); animation:redFlash 1.3s ease-in-out infinite 0.18s;"></div>
            <div style="position:absolute; right:20px; bottom:12px; font-size:6rem; line-height:1; filter:drop-shadow(0 12px 26px rgba(5,10,20,0.28));">🚑</div>
        </div>
        <div style="display:flex; justify-content:space-between; gap:20px; align-items:flex-start; flex-wrap:wrap;">
            <div>
                <div style="display:inline-flex; align-items:center; gap:10px; font-size:0.76rem; letter-spacing:0.16em; text-transform:uppercase; color:rgba(231,241,255,0.72); font-weight:900;">
                    <span style="width:10px; height:10px; border-radius:999px; background:linear-gradient(135deg, #61b6ff 0%, #ff7b8f 100%); box-shadow:0 0 0 5px rgba(97,182,255,0.10);"></span>
                    RD-Protokoll Generator
                </div>
                <div style="margin-top:10px; font-size:2.35rem; line-height:0.98; font-weight:950; letter-spacing:-0.05em; color:#fbfdff;">
                    Schnell. Klar. Einsatzbereit.
                </div>
                <div style="margin-top:10px; color:rgba(231,241,255,0.70); font-size:0.98rem; font-weight:600;">
                    Dokumentationshilfe f\u00fcr den Rettungsdienst
                </div>
                <div style="display:flex; gap:12px; flex-wrap:wrap; margin-top:18px;">
                    <div style="padding:10px 13px; border-radius:999px; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.10); color:#eef5ff; font-size:0.8rem; font-weight:850;">17 SOPs <span style='opacity:0.72; font-weight:700;'>zentral steuerbar</span></div>
                    <div style="padding:10px 13px; border-radius:999px; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.10); color:#eef5ff; font-size:0.8rem; font-weight:850;">Workflow <span style='opacity:0.72; font-weight:700;'>schrittgef\u00fchrt</span></div>
                    <div style="padding:10px 13px; border-radius:999px; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.10); color:#eef5ff; font-size:0.8rem; font-weight:850;">Protokoll <span style='opacity:0.72; font-weight:700;'>einsatzbereit</span></div>
                </div>
            </div>
            <div style="display:inline-flex; align-items:center; gap:8px; padding:11px 14px; border-radius:16px; background:linear-gradient(135deg, rgba(87,164,255,0.16), rgba(255,125,102,0.14)); border:1px solid rgba(255,255,255,0.10); color:#f4f8ff; font-size:0.80rem; font-weight:850; box-shadow: 0 14px 26px rgba(2,8,24,0.18);">
                <span style="width:8px; height:8px; border-radius:999px; background:#5cffb1; box-shadow:0 0 0 5px rgba(92,255,177,0.10);"></span>
                Live-System
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Tablet-Browser öffnen für Zahlenfelder direkt die numerische Tastatur.
components.html(
    """
    <script>
    const configureTabletInputs = () => {
        const doc = window.parent.document;
        doc.querySelectorAll('[data-testid="stNumberInput"] input').forEach((input) => {
            input.setAttribute('inputmode', 'decimal');
            input.setAttribute('enterkeyhint', 'next');
        });
        doc.querySelectorAll('input[placeholder="14:32"], input[placeholder="14:35"]').forEach((input) => {
            input.setAttribute('inputmode', 'numeric');
        });
    };
    configureTabletInputs();
    new MutationObserver(configureTabletInputs).observe(window.parent.document.body, {
        childList: true,
        subtree: true
    });
    </script>
    """,
    height=0,
    width=0,
)

# --------------------------------------------------
# Patientenobjekt anlegen
# --------------------------------------------------

if "patient" not in st.session_state:

    st.session_state.patient = {

        "vitalwerte": {},

        "xabcde": {},

        "samplers": {},

        "opqrst": {},

        "einweisung": {},

        "amls": {"excluded": [], "custom_candidates": [], "arbeitsdiagnose": ""},

        "massnahmen": {
            "timeline": [],
            "medikation": []
        }

    }

patient = st.session_state.patient
patient.setdefault("vitalwerte", {})
patient.setdefault("xabcde", {})
patient.setdefault("samplers", {})
patient.setdefault("opqrst", {})
patient.setdefault("einweisung", {})
patient.setdefault("amls", {"excluded": [], "custom_candidates": [], "arbeitsdiagnose": ""})
patient["amls"].setdefault("excluded", [])
patient["amls"].setdefault("custom_candidates", [])
patient["amls"].setdefault("arbeitsdiagnose", "")
patient.setdefault("massnahmen", {"timeline": [], "medikation": []})
patient["massnahmen"].setdefault("timeline", [])
patient["massnahmen"].setdefault("medikation", [])

# --------------------------------------------------
# Admin-Konfiguration
# --------------------------------------------------

LOCAL_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()
SUPABASE_URL = "https://ottkgqhtmjvhhtnwphmc.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_87egwyr4tTwLh3tnZTDjkQ_eJh2eRZw"
SUPABASE_ADMIN_EMAIL = "admin@rd-protokoll-generator.local"
SOP_ADMIN_CONFIG_FILE = "sop_admin_config.json"
WORKFLOW_STEPS = [
    {"page": "❤️ Vitalwerte", "label": "Patient", "short_label": "Patient"},
    {"page": "🩺 xABCDE", "label": "Untersuchung", "short_label": "Untersuch."},
    {"page": "📋 SAMPLERS", "label": "Anamnese", "short_label": "Anamnese"},
    {"page": "🔥 OPQRST", "label": "Schmerzbild", "short_label": "Schmerz"},
    {"page": "⏱️ Maßnahmen", "label": "Maßnahmen", "short_label": "Maßn."},
    {"page": "🔎 Verdacht", "label": "Verdacht", "short_label": "Verdacht"},
    {"page": "💉 Med-Rechner", "label": "Rechner", "short_label": "Rechner"},
    {"page": "🔻 AMLS", "label": "AMLS-Trichter", "short_label": "AMLS"},
    {"page": "🗣️ Übergabe", "label": "Übergabe", "short_label": "Übergabe"},
    {"page": "📄 Protokoll", "label": "Protokoll", "short_label": "Protokoll"},
]
ADMIN_SOP_FIELDS = {
    "Anaphylaxie (SOPKB0105)": [
        {"key": "ana_adult_age_threshold", "label": "Altersschwelle Erwachsene (Jahre)", "default": 12.0, "min": 0.0, "max": 21.0, "step": 1.0},
        {"key": "ana_child_age_threshold", "label": "Altersschwelle Kind (Jahre)", "default": 6.0, "min": 0.0, "max": 18.0, "step": 1.0},
    ],
    "Asthma/COPD Bronchialobstruktion (SOPKB0207)": [
        {"key": "asthma_nebulizer_age_1", "label": "Altersgrenze Stufe 1 (Jahre)", "default": 4.0, "min": 0.0, "max": 18.0, "step": 1.0},
        {"key": "asthma_nebulizer_age_2", "label": "Altersgrenze Stufe 2 (Jahre)", "default": 6.0, "min": 0.0, "max": 21.0, "step": 1.0},
        {"key": "asthma_no_improvement_minutes", "label": "Re-Evaluationszeit keine Besserung (Min)", "default": 5.0, "min": 1.0, "max": 30.0, "step": 1.0},
    ],
    "Hypoglykämie": [
        {"key": "hypo_bz_threshold_mg", "label": "BZ-Schwelle (mg/dl)", "default": 60.0, "min": 20.0, "max": 200.0, "step": 1.0},
        {"key": "hypo_bz_threshold_mmol", "label": "BZ-Schwelle (mmol/l)", "default": 3.3, "min": 1.0, "max": 11.0, "step": 0.1},
    ],
    "Krampfanfall": [
        {"key": "seizure_iv_midazolam_mg_per_kg", "label": "Midazolam i.v. (mg/kgKG)", "default": 0.05, "min": 0.01, "max": 0.5, "step": 0.01},
    ],
    "Schlaganfall": [
        {"key": "stroke_rr_low_threshold", "label": "RR-Untergrenze Volumen (mmHg)", "default": 120.0, "min": 70.0, "max": 180.0, "step": 1.0},
        {"key": "stroke_rr_high_threshold", "label": "RR-Obergrenze Urapidil (mmHg)", "default": 220.0, "min": 160.0, "max": 280.0, "step": 1.0},
        {"key": "stroke_lysis_window_h", "label": "Lyse-Zeitfenster (h)", "default": 6.0, "min": 1.0, "max": 24.0, "step": 0.5},
        {"key": "stroke_thrombectomy_window_h", "label": "Thrombektomie-Zeitfenster (h)", "default": 8.0, "min": 1.0, "max": 36.0, "step": 0.5},
    ],
    "Kardiales Lungenödem": [
        {"key": "pulm_nitro_rr_threshold", "label": "RR-Schwelle für Nitro (mmHg)", "default": 120.0, "min": 80.0, "max": 200.0, "step": 1.0},
        {"key": "pulm_hypertensive_rr_threshold", "label": "RR-Schwelle hypertensiver Notfall (mmHg)", "default": 220.0, "min": 160.0, "max": 280.0, "step": 1.0},
    ],
    "Hypertensiver Notfall": [
        {"key": "htn_rr_threshold", "label": "RR-Schwelle hypertensiver Notfall (mmHg)", "default": 180.0, "min": 140.0, "max": 260.0, "step": 1.0},
    ],
    "Nichttraumatischer Brustschmerz: ACS": [
        {"key": "acs_morphin_nrs_threshold", "label": "NRS-Schwelle Morphin", "default": 4.0, "min": 0.0, "max": 10.0, "step": 1.0},
        {"key": "acs_af_alarm_threshold", "label": "AF-Alarmgrenze (/min)", "default": 10.0, "min": 4.0, "max": 30.0, "step": 1.0},
    ],
    "Abdominelle Schmerzen / Koliken": [
        {"key": "abd_initial_nrs_threshold", "label": "NRS-Schwelle Stufe 1", "default": 3.0, "min": 0.0, "max": 10.0, "step": 1.0},
        {"key": "abd_step2_nrs_threshold", "label": "NRS-Schwelle Stufe 2", "default": 6.0, "min": 0.0, "max": 10.0, "step": 1.0},
        {"key": "abd_step3_nrs_threshold", "label": "NRS-Schwelle Stufe 3", "default": 6.0, "min": 0.0, "max": 10.0, "step": 1.0},
        {"key": "abd_fentanyl_weight_threshold", "label": "Gewichtsschwelle Fentanyl (kg)", "default": 30.0, "min": 5.0, "max": 120.0, "step": 1.0},
    ],
    "Starke Schmerzen": [
        {"key": "pain_min_nrs_threshold", "label": "Start-Schwelle NRS", "default": 3.0, "min": 0.0, "max": 10.0, "step": 1.0},
        {"key": "pain_advanced_nrs_threshold", "label": "Schwelle erweiterte Maßnahmen", "default": 6.0, "min": 0.0, "max": 10.0, "step": 1.0},
        {"key": "pain_extreme_nrs_threshold", "label": "Schwelle unerträgliche Schmerzen", "default": 8.0, "min": 0.0, "max": 10.0, "step": 1.0},
        {"key": "pain_midazolam_age_threshold", "label": "Altersschwelle Midazolam reduziert (Jahre)", "default": 60.0, "min": 18.0, "max": 100.0, "step": 1.0},
        {"key": "pain_weight_high_threshold", "label": "Gewichtsschwelle >50 kg", "default": 50.0, "min": 20.0, "max": 150.0, "step": 1.0},
        {"key": "pain_weight_min_threshold", "label": "Gewichtsschwelle >30 kg", "default": 30.0, "min": 10.0, "max": 120.0, "step": 1.0},
    ],
    "Massive Übelkeit / Erbrechen": [
        {"key": "nausea_ondansetron_age_threshold", "label": "Altersschwelle Ondansetron (Jahre)", "default": 60.0, "min": 18.0, "max": 100.0, "step": 1.0},
    ],
    "Instabile Bradykardie": [
        {"key": "brady_hf_threshold", "label": "HF-Schwelle Bradykardie (/min)", "default": 60.0, "min": 30.0, "max": 100.0, "step": 1.0},
    ],
    "Instabile Tachykardie": [
        {"key": "tachy_hf_warning_threshold", "label": "HF-Hinweisschwelle Tachykardie (/min)", "default": 100.0, "min": 60.0, "max": 180.0, "step": 1.0},
    ],
    "Intoxikation: Benzodiazepine": [
        {"key": "benzo_flumazenil_initial_mg", "label": "Flumazenil initial (mg)", "default": 0.5, "min": 0.1, "max": 2.0, "step": 0.1},
    ],
    "Intoxikation: Opiate / Opioide": [
        {"key": "opioid_naloxon_initial_mg", "label": "Naloxon initial (mg)", "default": 0.4, "min": 0.1, "max": 2.0, "step": 0.1},
    ],
    "Lungenarterienembolie": [
        {"key": "lae_wells_threshold", "label": "Wells-Schwelle", "default": 5.0, "min": 0.0, "max": 12.0, "step": 0.5},
        {"key": "lae_spesi_threshold", "label": "sPESI-Schwelle", "default": 1.0, "min": 0.0, "max": 6.0, "step": 1.0},
    ],
    "Akuter Verschluss peripherer Arterien": [
        {"key": "pao_pain_threshold", "label": "NRS-Schwelle starke Schmerzen", "default": 3.0, "min": 0.0, "max": 10.0, "step": 1.0},
    ],
}


def check_admin_password(candidate_password):
    if LOCAL_ADMIN_PASSWORD:
        return candidate_password == LOCAL_ADMIN_PASSWORD

    if not candidate_password:
        return False

    auth_url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    payload = json.dumps({
        "email": SUPABASE_ADMIN_EMAIL,
        "password": candidate_password,
    }).encode("utf-8")

    request = urllib.request.Request(
        auth_url,
        data=payload,
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status == 200
    except urllib.error.HTTPError:
        return False
    except urllib.error.URLError as error:
        st.error(f"Supabase-Anmeldung nicht erreichbar: {error.reason}")
        return False


def _has_content(values):
    for value in values.values():
        if isinstance(value, dict) and _has_content(value):
            return True
        if isinstance(value, list) and value:
            return True
        if value not in [None, "", 0, "Keine Angabe", [], {}]:
            return True
    return False


def workflow_completion_state(patient_data):
    visited_pages = st.session_state.get("visited_pages", set())
    manual_done = st.session_state.get("workflow_manual_completion", {})

    return {
        "❤️ Vitalwerte": "❤️ Vitalwerte" in visited_pages or manual_done.get("❤️ Vitalwerte", False),
        "🩺 xABCDE": "🩺 xABCDE" in visited_pages or manual_done.get("🩺 xABCDE", False),
        "📋 SAMPLERS": "📋 SAMPLERS" in visited_pages or manual_done.get("📋 SAMPLERS", False),
        "🔥 OPQRST": "🔥 OPQRST" in visited_pages or manual_done.get("🔥 OPQRST", False),
        "⏱️ Maßnahmen": "⏱️ Maßnahmen" in visited_pages or manual_done.get("⏱️ Maßnahmen", False),
        "🔎 Verdacht": "🔎 Verdacht" in visited_pages or manual_done.get("🔎 Verdacht", False),
        "🔻 AMLS": bool(patient_data.get("amls", {}).get("arbeitsdiagnose")) or manual_done.get("🔻 AMLS", False),
        "🗣️ Übergabe": "🗣️ Übergabe" in visited_pages or manual_done.get("🗣️ Übergabe", False),
        "📄 Protokoll": "📄 Protokoll" in visited_pages or manual_done.get("📄 Protokoll", False),
    }


def workflow_step_index(page_name):
    for idx, step in enumerate(WORKFLOW_STEPS):
        if step["page"] == page_name:
            return idx
    return None


def workflow_missing_hint(page_name, patient_data):
    vital = patient_data.get("vitalwerte", {})
    xabcde = patient_data.get("xabcde", {})
    samplers = patient_data.get("samplers", {})
    opqrst = patient_data.get("opqrst", {})
    massnahmen = patient_data.get("massnahmen", {})

    hints = {
        "❤️ Vitalwerte": "Demographie oder erste Vitalwerte ergänzen.",
        "🩺 xABCDE": "Primärbefund in xABCDE dokumentieren.",
        "📋 SAMPLERS": "Ereignis, Allergien oder Vorgeschichte ergänzen.",
        "🔥 OPQRST": "Schmerzqualität, Region oder NRS erfassen.",
        "⏱️ Maßnahmen": "Mindestens eine Maßnahme oder Medikation dokumentieren.",
        "🔎 Verdacht": "Vorher Vitalwerte, xABCDE oder Anamnese ausfüllen.",
        "🔻 AMLS": "Differenzialdiagnosen prüfen und eine Arbeitsdiagnose festhalten.",
        "🗣️ Übergabe": "Vor Übergabe Maßnahmen und Kernbefunde vervollständigen.",
        "📄 Protokoll": "Protokoll generieren, damit der Schritt abgeschlossen ist.",
    }

    if page_name == "❤️ Vitalwerte" and _has_content(vital):
        return ""
    if page_name == "🩺 xABCDE" and _has_content(xabcde):
        return ""
    if page_name == "📋 SAMPLERS" and _has_content(samplers):
        return ""
    if page_name == "🔥 OPQRST" and _has_content(opqrst):
        return ""
    if page_name == "⏱️ Maßnahmen" and (massnahmen.get("timeline") or massnahmen.get("medikation")):
        return ""
    if page_name == "🔎 Verdacht" and (_has_content(vital) or _has_content(xabcde) or _has_content(samplers) or _has_content(opqrst)):
        return ""
    if page_name == "🔻 AMLS" and patient_data.get("amls", {}).get("arbeitsdiagnose"):
        return ""
    if page_name == "🗣️ Übergabe" and (massnahmen.get("timeline") or massnahmen.get("medikation") or _has_content(vital)):
        return ""
    if page_name == "📄 Protokoll" and st.session_state.get("protocol_generated", False):
        return ""
    return hints.get(page_name, "")


def _build_default_value_overrides():
    defaults = {}
    for fields in ADMIN_SOP_FIELDS.values():
        for field in fields:
            defaults[field["key"]] = field["default"]
    return defaults


DEFAULT_SOP_ADMIN_CONFIG = {
    "value_overrides": _build_default_value_overrides(),
}


def _deep_merge_dict(base_dict, update_dict):
    merged = deepcopy(base_dict)
    for key, value in update_dict.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_sop_admin_config():
    config = deepcopy(DEFAULT_SOP_ADMIN_CONFIG)
    if os.path.exists(SOP_ADMIN_CONFIG_FILE):
        try:
            with open(SOP_ADMIN_CONFIG_FILE, "r", encoding="utf-8") as file_obj:
                disk_config = json.load(file_obj)
            if isinstance(disk_config, dict):
                config = _deep_merge_dict(config, disk_config)
        except Exception:
            pass
    return config


def _save_sop_admin_config(config):
    with open(SOP_ADMIN_CONFIG_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(config, file_obj, ensure_ascii=False, indent=2)


if "admin_unlocked" not in st.session_state:
    st.session_state["admin_unlocked"] = False

if "sop_admin_config" not in st.session_state:
    st.session_state["sop_admin_config"] = _load_sop_admin_config()

if "workflow_manual_completion" not in st.session_state:
    st.session_state["workflow_manual_completion"] = {}

if "protocol_generated" not in st.session_state:
    st.session_state["protocol_generated"] = False

if "generated_protocol_text" not in st.session_state:
    st.session_state["generated_protocol_text"] = ""


def sop_value(key, default_value):
    return st.session_state.get("sop_admin_config", {}).get("value_overrides", {}).get(key, default_value)
# --------------------------------------------------
# Hilfsfunktionen
# --------------------------------------------------

def radio_field(section, key, label, options):
    value = st.radio(
        label,
        options,
        key=f"{section}_{key}"
    )
    patient[section][key] = value
    return value


def select_field(section, key, label, options):
    value = st.selectbox(
        label,
        options,
        key=f"{section}_{key}"
    )
    patient[section][key] = value
    return value


def text_field(section, key, label):
    value = st.text_input(
        label,
        key=f"{section}_{key}"
    )
    patient[section][key] = value
    return value


def textarea_field(section, key, label, height=120):
    value = st.text_area(
        label,
        height=height,
        key=f"{section}_{key}"
    )
    patient[section][key] = value
    return value


def checkbox_field(section, key, label):
    value = st.checkbox(
        label,
        key=f"{section}_{key}"
    )
    patient[section][key] = value
    return value


def sync_vitalwerte_from_session_state():
    v = patient["vitalwerte"]

    widget_keys = {
        "geschlecht": "geschlecht",
        "alter": "alter",
        "auffindesituation": "auffindesituation",
        "spo2_input": "spo2",
        "af_input": "af",
        "rr_sys_input": "rr_sys",
        "rr_dia_input": "rr_dia",
        "puls_input": "puls",
        "gcs_input": "gcs",
        "bz_input": "bz",
        "kurzbericht": "kurzbericht",
    }
    for widget_key, patient_key in widget_keys.items():
        if widget_key in st.session_state:
            v[patient_key] = st.session_state[widget_key]
        elif patient_key in v:
            st.session_state[widget_key] = v[patient_key]

    if "temperatur" in v and "temp_checkbox" not in st.session_state:
        st.session_state["temp_checkbox"] = _is_valid_value(v.get("temperatur"))
    if st.session_state.get("temp_checkbox"):
        if "temp_input" in st.session_state:
            v["temperatur"] = st.session_state["temp_input"]
        elif _is_valid_value(v.get("temperatur")):
            st.session_state["temp_input"] = v["temperatur"]
    else:
        v["temperatur"] = None


def sync_xabcde_from_session_state():
    x = patient["xabcde"]
    for key in [
        "atemweg",
        "hws",
        "atmung",
        "atemgeraeusche",
        "sauerstoff",
        "haut",
        "rekap",
        "pulsqualitaet",
        "avpu",
        "pupillen",
        "befast_balance",
        "befast_eyes",
        "befast_face",
        "befast_arms",
        "befast_speech",
        "befast_time",
        "bodycheck",
        "bodycheck_text",
        "unterkuehlung",
        "verbrennung",
    ]:
        if key in st.session_state:
            x[key] = st.session_state[key]
        elif key in x:
            st.session_state[key] = x[key]


def sync_samplers_from_session_state():
    s = patient["samplers"]
    for key in [
        "symptome",
        "allergien",
        "allergien_text",
        "medikamente_option",
        "medikamente",
        "vorgeschichte",
        "letzte_mahlzeit",
        "letzte_mahlzeit_text",
        "letzte_medikamenteneinnahme",
        "letzter_stuhlgang",
        "letzte_miktion",
        "letztes_erbrechen",
        "ereignis",
        "raucher",
        "alkohol",
        "drogen",
        "diabetes",
        "hypertonie",
        "antikoagulation",
        "risiken_sonstige",
        "schwangerschaft",
    ]:
        state_key = f"samplers_{key}"
        if state_key in st.session_state:
            s[key] = st.session_state[state_key]
        elif key in s:
            st.session_state[state_key] = s[key]


def sync_opqrst_from_session_state():
    o = patient["opqrst"]
    for key in [
        "schmerz_vorhanden",
        "onset",
        "onset_text",
        "provocation",
        "provocation_text",
        "quality",
        "quality_text",
        "region",
        "radiation",
        "nrs",
        "severity_desc",
        "zeitverlauf",
        "dauer",
    ]:
        state_key = f"opqrst_{key}"
        if state_key in st.session_state:
            o[key] = st.session_state[state_key]
        elif key in o:
            st.session_state[state_key] = o[key]


def _is_valid_value(value):
    return value not in [None, "", "Keine Angabe", 0]


def render_live_summary(title, lines):
    valid_lines = [line for line in lines if line]
    escaped_title = html.escape(title)
    if valid_lines:
        chip_markup = "".join(
            f"<span style='display:inline-flex; align-items:center; padding:8px 10px; border-radius:999px; background:rgba(7,17,31,0.34); border:1px solid rgba(255,255,255,0.08); color:#eef5ff; font-size:0.82rem; line-height:1.2;'>{html.escape(str(line))}</span>"
            for line in valid_lines[:5]
        )
        st.markdown(
            f"""
            <div style="margin:14px 0 10px; padding:14px 16px; border-radius:18px; background:linear-gradient(180deg, rgba(255,255,255,0.055), rgba(255,255,255,0.025)); border:1px solid rgba(255,255,255,0.09); box-shadow:0 14px 30px rgba(2,8,24,0.18);">
                <div style="font-size:0.74rem; text-transform:uppercase; letter-spacing:0.16em; color:rgba(235,244,255,0.58); font-weight:900; margin-bottom:10px;">{escaped_title}</div>
                <div style="display:flex; flex-wrap:wrap; gap:8px;">{chip_markup}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div style="margin:14px 0 10px; padding:14px 16px; border-radius:18px; background:linear-gradient(180deg, rgba(255,255,255,0.055), rgba(255,255,255,0.025)); border:1px solid rgba(255,255,255,0.09); box-shadow:0 14px 30px rgba(2,8,24,0.18);">
                <div style="font-size:0.74rem; text-transform:uppercase; letter-spacing:0.16em; color:rgba(235,244,255,0.58); font-weight:900; margin-bottom:10px;">{escaped_title}</div>
                <div style="color:rgba(234,243,255,0.62); font-size:0.88rem;">Noch keine relevanten Angaben</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_vital_alerts(vitalwerte):
    critical = []
    warnings = []

    def number(key):
        try:
            return float(vitalwerte.get(key))
        except (TypeError, ValueError):
            return None

    spo2 = number("spo2")
    if spo2 is not None and spo2 > 0:
        (critical if spo2 < 90 else warnings if spo2 < 95 else []).append(f"SpO₂ {spo2:g} %")

    af = number("af")
    if af is not None and af > 0:
        (critical if af < 10 or af > 30 else warnings if af > 20 else []).append(f"AF {af:g}/min")

    puls = number("puls")
    if puls is not None and puls > 0:
        (critical if puls < 50 or puls > 120 else warnings if puls > 100 else []).append(f"Puls {puls:g}/min")

    rr_sys = number("rr_sys")
    rr_dia = number("rr_dia")
    if rr_sys is not None and rr_sys > 0:
        rr_text = f"RR {rr_sys:g}/{rr_dia:g}" if rr_dia is not None else f"RR syst. {rr_sys:g}"
        (critical if rr_sys < 90 or rr_sys >= 180 else warnings if rr_sys >= 140 else []).append(rr_text)

    gcs = number("gcs")
    if gcs is not None:
        (critical if gcs <= 8 else warnings if gcs < 15 else []).append(f"GCS {gcs:g}")

    bz = number("bz")
    if bz is not None and bz > 0:
        (critical if bz < 60 or bz > 250 else warnings if bz < 70 or bz > 140 else []).append(f"BZ {bz:g} mg/dL")

    temperature = number("temperatur")
    if temperature is not None:
        (critical if temperature < 35 or temperature >= 40 else warnings if temperature < 36 or temperature >= 38 else []).append(f"Temp. {temperature:g} °C")

    if critical:
        st.error("🔴 Kritische Werte – sofort klinisch prüfen: " + " · ".join(critical))
    if warnings:
        st.warning("🟠 Auffällige Werte – Verlauf kontrollieren: " + " · ".join(warnings))


def collect_missing_documentation(patient_data):
    v = patient_data.get("vitalwerte", {})
    x = patient_data.get("xabcde", {})
    s = patient_data.get("samplers", {})
    o = patient_data.get("opqrst", {})
    fields = [
        ("Patient", "Geschlecht", v.get("geschlecht")),
        ("Patient", "Alter", v.get("alter")),
        ("Patient", "Auffindesituation", v.get("auffindesituation")),
        ("Vitalwerte", "SpO₂", v.get("spo2")),
        ("Vitalwerte", "Atemfrequenz", v.get("af")),
        ("Vitalwerte", "Blutdruck systolisch", v.get("rr_sys")),
        ("Vitalwerte", "Blutdruck diastolisch", v.get("rr_dia")),
        ("Vitalwerte", "Puls", v.get("puls")),
        ("Vitalwerte", "GCS", v.get("gcs")),
        ("Vitalwerte", "Blutzucker", v.get("bz")),
        ("xABCDE", "Atemweg", x.get("atemweg")),
        ("xABCDE", "Atmung", x.get("atmung")),
        ("xABCDE", "Haut/Kreislauf", x.get("haut")),
        ("xABCDE", "AVPU", x.get("avpu")),
        ("xABCDE", "Bodycheck", x.get("bodycheck")),
        ("SAMPLERS", "Symptome", s.get("symptome")),
        ("SAMPLERS", "Allergien", s.get("allergien")),
        ("SAMPLERS", "Medikamente", s.get("medikamente_option")),
        ("SAMPLERS", "Vorgeschichte", s.get("vorgeschichte")),
        ("SAMPLERS", "Ereignis", s.get("ereignis")),
    ]
    if o.get("schmerz_vorhanden") == "Ja":
        fields.extend([
            ("OPQRST", "Schmerzbeginn", o.get("onset")),
            ("OPQRST", "Schmerzqualität", o.get("quality")),
            ("OPQRST", "Schmerzregion", o.get("region")),
            ("OPQRST", "NRS", o.get("nrs")),
        ])
    return [
        {"section": section, "label": label}
        for section, label, value in fields
        if value in [None, "", 0, "Keine Angabe"]
    ]


def highlight_handover_text(text):
    highlighted = html.escape(text)
    patterns = [
        (r"\b(Apnoe|bewusstlos|Schock|Sepsis|Schlaganfall|ACS|Hypoxie|kritisch|verlegt)\b", "#ff667a", "rgba(255,70,92,.16)"),
        (r"\b(Dyspnoe|Tachypnoe|Bradypnoe|Tachykardie|Bradykardie|Hypotonie|Hypertonie|Blutung|Fieber|Intoxikation|auffällig|Schmerz)\w*\b", "#ffc857", "rgba(255,184,76,.15)"),
        (r"\b(SpO(?:2|₂)?|AF|Puls|RR|GCS|BZ)\s*[:]?\s*\d+(?:[.,]\d+)?(?:/\d+(?:[.,]\d+)?)?(?:\s*%|\s*/min)?", "#63c7ff", "rgba(74,174,255,.14)"),
        (r"\b(unauffällig|frei|stabil|wach|orientiert|isokor)\w*\b", "#5ce0a3", "rgba(57,211,142,.13)"),
    ]
    for pattern, color, background in patterns:
        highlighted = re.sub(
            pattern,
            lambda match: f'<span style="color:{color}; background:{background}; padding:1px 4px; border-radius:5px; font-weight:850;">{match.group(0)}</span>',
            highlighted,
            flags=re.IGNORECASE,
        )
    return highlighted.replace("\n", "<br>")


def render_colored_handover(title, text):
    st.markdown(
        f"""
        <div style="margin:10px 0 18px; padding:18px; border-radius:20px; background:rgba(8,20,38,.72); border:1px solid rgba(255,255,255,.10); box-shadow:0 14px 30px rgba(2,8,24,.18);">
            <div style="font-size:.76rem; text-transform:uppercase; letter-spacing:.14em; color:rgba(235,244,255,.58); font-weight:900; margin-bottom:12px;">{html.escape(title)}</div>
            <div style="font-family:ui-monospace, SFMono-Regular, Menlo, monospace; line-height:1.75; color:#eef5ff;">{highlight_handover_text(text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_handover_text(patient_data):
    v = patient_data.get("vitalwerte", {})
    x = patient_data.get("xabcde", {})
    s = patient_data.get("samplers", {})
    o = patient_data.get("opqrst", {})
    e = patient_data.get("einweisung", {})
    amls = patient_data.get("amls", {})
    m = patient_data.get("massnahmen", {})

    mist = []
    mechanism = s.get("ereignis") or v.get("auffindesituation") or "Kein klares Ereignis dokumentiert"
    injuries = x.get("bodycheck_text") if x.get("bodycheck") == "Auffällig" else "Keine relevanten Verletzungen dokumentiert"
    signs = []
    if _is_valid_value(v.get("spo2")):
        signs.append(f"SpO2 {v.get('spo2')}")
    if _is_valid_value(v.get("af")):
        signs.append(f"AF {v.get('af')}")
    if _is_valid_value(v.get("puls")):
        signs.append(f"Puls {v.get('puls')}")
    if _is_valid_value(v.get("rr_sys")) and _is_valid_value(v.get("rr_dia")):
        signs.append(f"RR {v.get('rr_sys')}/{v.get('rr_dia')}")
    treatment = []
    for event in m.get("timeline", []):
        if event.get("massnahme"):
            treatment.append(f"{event.get('zeit', '--:--')} {event.get('massnahme')}")
    mist.append(f"M: {mechanism}")
    mist.append(f"I: {injuries}")
    mist.append("S: " + (", ".join(signs) if signs else "Keine Vitalzeichen dokumentiert"))
    mist.append("T: " + ("; ".join(treatment[-4:]) if treatment else "Keine Maßnahmen dokumentiert"))

    isbar = []
    identity = "Patient"
    if _is_valid_value(v.get("geschlecht")):
        identity += f", {v.get('geschlecht')}"
    if _is_valid_value(v.get("alter")):
        identity += f", {v.get('alter')} Jahre"
    isbar.append(f"I: {identity}")
    isbar.append(f"S: {s.get('symptome') or 'Kein Leitsymptom dokumentiert'}")
    background = s.get("vorgeschichte") or "Keine relevante Vorgeschichte dokumentiert"
    if e.get("icd_code") and e.get("diagnose"):
        background += f"; Einweisung: ICD-10-GM {e.get('icd_code')} – {e.get('diagnose')}"
    isbar.append(f"B: {background}")
    assess = x.get("atmung") or x.get("atemweg") or x.get("avpu") or "Keine strukturierte Einschätzung dokumentiert"
    if amls.get("arbeitsdiagnose"):
        assess += f"; AMLS-Arbeitsdiagnose: {amls.get('arbeitsdiagnose')}"
    isbar.append(f"A: {assess}")
    rec = "Transport in geeignete Zielklinik und strukturierte Übergabe empfohlen"
    if o.get("nrs") and int(o.get("nrs", 0)) >= 7:
        rec = "Hohe Schmerzintensität, zeitnahe ärztliche Weiterbehandlung empfohlen"
    isbar.append(f"R: {rec}")

    return "\n".join(mist), "\n".join(isbar)


def build_suspicion_assessment(patient_data):
    v = patient_data.get("vitalwerte", {})
    x = patient_data.get("xabcde", {})
    s = patient_data.get("samplers", {})
    o = patient_data.get("opqrst", {})

    symptome = (s.get("symptome") or "").lower()
    region = (o.get("region") or "").lower()
    quality = (o.get("quality") or "").lower()
    ereignis = (s.get("ereignis") or "").lower()

    suspicions = []
    recommendations = []

    befast_normal_values = {None, "", "Keine Angabe", "Unauffällig", "Symmetrisch", "Kein Absinken"}
    if any(
        x.get(key) not in befast_normal_values
        for key in ("befast_balance", "befast_eyes", "befast_face", "befast_arms", "befast_speech")
    ):
        suspicions.append("Auffälliges BE-FAST-Screening / akutes neurologisches Defizit")
        recommendations.extend([
            "Symptombeginn bzw. Last-Seen-Well-Zeit sichern",
            "Zeitkritische Voranmeldung in einer geeigneten Stroke Unit erwägen",
            "Neurologischen Verlauf und Blutzucker wiederholt kontrollieren",
        ])

    if any(k in symptome for k in ["atemnot", "dyspnoe", "luftnot"]) or x.get("atmung") in ["Dyspnoe", "Tachypnoe", "Apnoe"] or (_is_valid_value(v.get("spo2")) and int(v.get("spo2")) < 90):
        suspicions.append("Respiratorische Insuffizienz / akute Dyspnoe")
        recommendations.extend([
            "Atemweg sichern und Atemarbeit engmaschig überwachen",
            "Sauerstofftherapie titriert fortführen",
            "Frühe Zielklinikmeldung bei persistierender Hypoxie"
        ])

    if any(k in symptome for k in ["brust", "thorax", "druck"]) or any(k in region for k in ["brust", "thorax"]) or "drückend" in quality:
        suspicions.append("Akutes Koronarsyndrom (ACS) als Differentialdiagnose")
        recommendations.extend([
            "12-Kanal-EKG und Verlaufskontrolle",
            "Schmerz- und Kreislaufmonitoring",
            "Zeitkritischen Transport erwägen"
        ])

    if x.get("avpu") in ["P", "U"] or (_is_valid_value(v.get("gcs")) and int(v.get("gcs")) <= 8):
        suspicions.append("Schwere neurologische Beeinträchtigung")
        recommendations.extend([
            "Atemwegsschutz priorisieren",
            "Neurologischen Verlauf wiederholt dokumentieren",
            "Zielklinik mit neurologischer Versorgung bevorzugen"
        ])

    if any(k in ereignis for k in ["sturz", "unfall", "trauma", "kollision"]) or (x.get("bodycheck") == "Auffällig"):
        suspicions.append("Traumatische Genese / relevante Verletzung möglich")
        recommendations.extend([
            "Vollständigen Bodycheck und Blutungskontrolle sichern",
            "Immobilisationsbedarf prüfen",
            "Traumazentrum-Indikation evaluieren"
        ])

    if _is_valid_value(v.get("bz")) and float(v.get("bz")) < 70:
        suspicions.append("Hypoglykämie")
        recommendations.extend([
            "Sofortige Glukosegabe gemäß SOP",
            "Blutzucker nach Intervention kontrollieren"
        ])
    elif _is_valid_value(v.get("bz")) and float(v.get("bz")) > 250:
        suspicions.append("Hyperglykäme Stoffwechsellage")
        recommendations.extend([
            "Hydratationsstatus und Vigilanz eng überwachen",
            "Zeitnahe klinische Abklärung veranlassen"
        ])

    if _is_valid_value(o.get("nrs")) and int(o.get("nrs")) >= 7:
        suspicions.append("Akutes Schmerzsyndrom")
        recommendations.extend([
            "Analgesiekonzept dokumentieren und Wirkung nachkontrollieren",
            "Schmerzverlauf (NRS) seriell erfassen"
        ])

    if not suspicions:
        suspicions.append("Aktuell keine klare Verdachtsdiagnose aus den verfügbaren Angaben ableitbar")
        recommendations.append("Datensatz vervollständigen (xABCDE, SAMPLERS, OPQRST) und Verlauf engmaschig re-evaluieren")

    # Duplikate entfernen, Reihenfolge behalten
    dedup_recs = list(dict.fromkeys(recommendations))
    dedup_susp = list(dict.fromkeys(suspicions))
    return dedup_susp, dedup_recs


def build_amls_candidates(patient_data):
    v = patient_data.get("vitalwerte", {})
    x = patient_data.get("xabcde", {})
    s = patient_data.get("samplers", {})
    o = patient_data.get("opqrst", {})
    referral = patient_data.get("einweisung", {})
    amls = patient_data.get("amls", {})

    text = " ".join(
        str(value or "")
        for value in (
            s.get("symptome"), s.get("ereignis"), s.get("vorgeschichte"),
            o.get("region"), o.get("quality"), o.get("onset_text"),
            v.get("kurzbericht"),
        )
    ).lower()
    candidates = []

    def add(name, category, rationale):
        if name and not any(item["name"] == name for item in candidates):
            candidates.append({"name": name, "category": category, "rationale": rationale})

    def mentions(*terms):
        return any(term in text for term in terms)

    def number(key):
        try:
            return float(v.get(key))
        except (TypeError, ValueError):
            return None

    af = number("af")
    spo2 = number("spo2")
    puls = number("puls")
    rr_sys = number("rr_sys")
    temperature = number("temperatur")
    gcs = number("gcs")

    if referral.get("diagnose"):
        add(
            f"Einweisungsdiagnose: {referral.get('diagnose')}",
            "Einweisung",
            f"Auf der Einweisung als ICD-10-GM {referral.get('icd_code', '–')} angegeben",
        )

    # Vitalwerte aus dem Reiter "Patient" öffnen den Trichter dynamisch.
    if af is not None and af > 20:
        add("Hyperventilation", "Respiratorisch", f"Tachypnoe mit AF {af:g}/min")
        add("Sepsis / schwere Infektion", "Infektiös", f"Tachypnoe mit AF {af:g}/min als mögliches systemisches Zeichen")
        add("Schock", "Kreislauf", f"Tachypnoe mit AF {af:g}/min als mögliches Kompensationszeichen")
        add("Lungenarterienembolie", "Kardiopulmonal", f"Tachypnoe mit AF {af:g}/min")
        add("Pneumonie", "Respiratorisch", f"Tachypnoe mit AF {af:g}/min")
        add("Metabolische Azidose", "Metabolisch", f"Tachypnoe mit AF {af:g}/min als mögliche Kompensation")
    elif af is not None and 0 < af < 10:
        add("Opiat-/Opioidintoxikation", "Toxikologisch", f"Bradypnoe mit AF {af:g}/min")
        add("Zentrale Atemdepression", "Neurologisch", f"Bradypnoe mit AF {af:g}/min")
        add("Respiratorische Erschöpfung", "Respiratorisch", f"Bradypnoe mit AF {af:g}/min")

    if spo2 is not None and 0 < spo2 < 95:
        add("Respiratorische Insuffizienz", "Respiratorisch", f"SpO₂ {spo2:g} %")
        add("Pneumonie", "Respiratorisch", f"SpO₂ {spo2:g} %")
        add("Lungenarterienembolie", "Kardiopulmonal", f"SpO₂ {spo2:g} %")
        add("Kardiales Lungenödem", "Kardiopulmonal", f"SpO₂ {spo2:g} %")

    if puls is not None and puls > 100:
        add("Schock", "Kreislauf", f"Tachykardie mit Puls {puls:g}/min")
        add("Sepsis / schwere Infektion", "Infektiös", f"Tachykardie mit Puls {puls:g}/min")
        add("Tachyarrhythmie", "Kardial", f"Puls {puls:g}/min")
        add("Schmerz-/Stressreaktion", "Sonstige", f"Puls {puls:g}/min")
    elif puls is not None and 0 < puls < 50:
        add("Bradyarrhythmie", "Kardial", f"Bradykardie mit Puls {puls:g}/min")
        add("Medikamentenwirkung / Intoxikation", "Toxikologisch", f"Puls {puls:g}/min")
        add("Intrakranielle Ursache", "Neurologisch", f"Puls {puls:g}/min")

    if rr_sys is not None and 0 < rr_sys < 90:
        add("Schock", "Kreislauf", f"Hypotonie mit RR systolisch {rr_sys:g} mmHg")
        add("Sepsis / schwere Infektion", "Infektiös", f"Hypotonie mit RR systolisch {rr_sys:g} mmHg")
        add("Blutung / Volumenmangel", "Kreislauf", f"Hypotonie mit RR systolisch {rr_sys:g} mmHg")
        add("Anaphylaxie", "Allergologisch", f"Hypotonie mit RR systolisch {rr_sys:g} mmHg")

    if temperature is not None and temperature >= 38:
        add("Sepsis / schwere Infektion", "Infektiös", f"Fieber mit {temperature:g} °C")
        add("Pneumonie", "Infektiös", f"Fieber mit {temperature:g} °C")
        add("Harnwegsinfekt / Urosepsis", "Infektiös", f"Fieber mit {temperature:g} °C")

    if gcs is not None and gcs < 15:
        add("Intrakranielle Ursache", "Neurologisch", f"GCS {gcs:g}")
        add("Intoxikation", "Toxikologisch", f"GCS {gcs:g}")
        add("Metabolische Entgleisung", "Metabolisch", f"GCS {gcs:g}")

    respiratory = mentions("atemnot", "dyspnoe", "luftnot", "husten") or x.get("atmung") in {"Dyspnoe", "Bradypnoe", "Tachypnoe", "Apnoe"}
    if respiratory:
        add("Asthma/COPD-Exazerbation", "Respiratorisch", "Dyspnoe bzw. auffällige Atmung dokumentiert")
        add("Pneumonie / respiratorischer Infekt", "Respiratorisch", "Atemwegsbeschwerden als mögliche infektiöse Ursache")
        add("Lungenarterienembolie", "Kardiopulmonal", "Akute Dyspnoe erfordert Ausschluss einer Embolie")
        add("Kardiales Lungenödem", "Kardiopulmonal", "Dyspnoe kann kardial bedingt sein")
        add("Pneumothorax", "Respiratorisch", "Akute respiratorische Beschwerden als mögliche Ursache")

    chest_pain = mentions("brust", "thorax", "retrosternal", "druck auf der brust") or any(
        term in str(o.get("region") or "").lower() for term in ("brust", "thorax")
    )
    if chest_pain:
        add("Akutes Koronarsyndrom", "Kardial", "Thoraxbeschwerden dokumentiert")
        add("Lungenarterienembolie", "Kardiopulmonal", "Thoraxschmerz gehört zum gefährlichen Differenzial")
        add("Aortensyndrom / Aortendissektion", "Vaskulär", "Zeitkritische Ursache bei akutem Thoraxschmerz")
        add("Pneumothorax", "Respiratorisch", "Thoraxschmerz kann pleuropulmonal bedingt sein")
        add("Muskuloskelettaler Thoraxschmerz", "Sonstige", "Nichtkardiale Ursache mitbedenken")

    befast_normal = {None, "", "Keine Angabe", "Unauffällig", "Symmetrisch", "Kein Absinken"}
    neuro_abnormal = any(
        x.get(key) not in befast_normal
        for key in ("befast_balance", "befast_eyes", "befast_face", "befast_arms", "befast_speech")
    ) or mentions("lähmung", "sprachstörung", "bewusstlos", "verwirrt", "krampf", "synkope")
    if neuro_abnormal:
        add("Schlaganfall / TIA", "Neurologisch", "Neurologische Auffälligkeit bzw. BE-FAST-Befund")
        add("Hypoglykämie", "Metabolisch", "Reversible neurologische Differenzialdiagnose")
        add("Krampfanfall / postiktaler Zustand", "Neurologisch", "Bewusstseins- oder neurologische Störung")
        add("Intoxikation", "Toxikologisch", "Bewusstseinsstörung kann toxisch bedingt sein")

    if mentions("bauch", "abdomen", "kolik", "flanke", "epigastr"):
        add("Akutes Abdomen", "Abdominell", "Abdominelle Beschwerden dokumentiert")
        add("Gastroenteritis", "Abdominell", "Gastrointestinale Ursache möglich")
        add("Gallenwegs-/Nierenkolik", "Abdominell", "Kolikartige oder flankige Beschwerden möglich")
        add("Aortenaneurysma / vaskuläres Ereignis", "Vaskulär", "Gefährliche vaskuläre Ursache ausschließen")
        add("Atypisches akutes Koronarsyndrom", "Kardial", "Oberbauchbeschwerden können kardial bedingt sein")

    if mentions("fieber", "schüttelfrost", "infekt"):
        add("Sepsis / schwere Infektion", "Infektiös", "Infektzeichen dokumentiert")
        add("Pneumonie", "Infektiös", "Häufiger respiratorischer Infektfokus")
        add("Harnwegsinfekt / Urosepsis", "Infektiös", "Möglicher Infektfokus")

    try:
        bz = float(v.get("bz"))
    except (TypeError, ValueError):
        bz = None
    if bz is not None and 0 < bz < 70:
        add("Hypoglykämie", "Metabolisch", f"BZ {bz:g} mg/dL")
    elif bz is not None and bz > 250:
        add("Hyperglykämische Stoffwechselentgleisung", "Metabolisch", f"BZ {bz:g} mg/dL")

    if x.get("avpu") in {"V", "P", "U"}:
        add("Intrakranielle Ursache", "Neurologisch", f"AVPU {x.get('avpu')} dokumentiert")
        add("Intoxikation", "Toxikologisch", "Bewusstseinsstörung unklarer Ursache")
        add("Metabolische Entgleisung", "Metabolisch", "Bewusstseinsstörung unklarer Ursache")

    if len(candidates) < 4:
        for name, category in (
            ("Kardiale Ursache / Rhythmusstörung", "Kardial"),
            ("Respiratorische Ursache", "Respiratorisch"),
            ("Neurologische Ursache", "Neurologisch"),
            ("Metabolische Entgleisung", "Metabolisch"),
            ("Infektion / Sepsis", "Infektiös"),
            ("Intoxikation", "Toxikologisch"),
        ):
            add(name, category, "Breiter AMLS-Sicherheitscheck bei noch unspezifischer Datenlage")

    for custom_name in amls.get("custom_candidates", []):
        add(custom_name, "Eigene Ergänzung", "Manuell zum Trichter hinzugefügt")

    return candidates


def amls_candidate_conflicts(candidate_name, patient_data):
    """Return documented findings that are atypical, without treating them as exclusions."""
    v = patient_data.get("vitalwerte", {})
    x = patient_data.get("xabcde", {})
    o = patient_data.get("opqrst", {})
    name = candidate_name.lower()
    conflicts = []

    def number(key):
        try:
            return float(v.get(key))
        except (TypeError, ValueError):
            return None

    spo2 = number("spo2")
    bz = number("bz")
    temperature = number("temperatur")
    puls = number("puls")
    af = number("af")
    rr_sys = number("rr_sys")
    gcs = number("gcs")

    if "hyperventilation" in name:
        if spo2 is not None and 0 < spo2 < 90:
            conflicts.append(f"SpO₂ {spo2:g} % spricht für relevante Oxygenierungsstörung")
        if rr_sys is not None and 0 < rr_sys < 90:
            conflicts.append(f"RR systolisch {rr_sys:g} mmHg mit Hypotonie")
        if gcs is not None and gcs < 15:
            conflicts.append(f"GCS {gcs:g} nicht unauffällig")

    if name == "schock" or "schock" in name:
        if rr_sys is not None and rr_sys >= 100:
            conflicts.append(f"RR systolisch {rr_sys:g} mmHg ohne Hypotonie")
        if puls is not None and 50 <= puls <= 100:
            conflicts.append(f"Puls {puls:g}/min ohne Tachykardie")
        if x.get("rekap") == "< 2 Sekunden":
            conflicts.append("Rekapillarisierungszeit < 2 Sekunden")
        if x.get("haut") == "Rosig / warm":
            conflicts.append("Haut rosig und warm")

    if "hypoglyk" in name and bz is not None and bz >= 70:
        conflicts.append(f"BZ {bz:g} mg/dL nicht hypoglykämisch")
    if ("hyperglyk" in name or "stoffwechselentgleisung" in name) and bz is not None and 70 <= bz <= 250:
        conflicts.append(f"BZ {bz:g} mg/dL ohne deutliche Entgleisung")

    if "pneumothorax" in name and x.get("atemgeraeusche") == "Beidseits vorhanden":
        conflicts.append("Atemgeräusche beidseits vorhanden")

    if any(term in name for term in ("asthma", "copd", "lungenödem", "respiratorische ursache")):
        if x.get("atmung") == "Unauffällig":
            conflicts.append("Atmung als unauffällig dokumentiert")
        if spo2 is not None and spo2 >= 95:
            conflicts.append(f"SpO₂ {spo2:g} % im Normbereich")

    if any(term in name for term in ("pneumonie", "infektion", "sepsis", "urosepsis", "gastroenteritis")):
        if temperature is not None and 36 <= temperature < 38:
            conflicts.append(f"Temperatur {temperature:g} °C ohne Fieber")
        if puls is not None and 50 <= puls <= 100:
            conflicts.append(f"Puls {puls:g}/min ohne Tachykardie")
        if rr_sys is not None and rr_sys >= 100:
            conflicts.append(f"RR systolisch {rr_sys:g} mmHg ohne Hypotonie")

    if any(term in name for term in ("schlaganfall", "tia", "neurologische ursache")):
        befast_keys = ("befast_balance", "befast_eyes", "befast_face", "befast_arms", "befast_speech")
        normal_values = {"Unauffällig", "Symmetrisch", "Kein Absinken"}
        documented = [x.get(key) for key in befast_keys if x.get(key) not in [None, "", "Keine Angabe"]]
        if len(documented) == len(befast_keys) and all(value in normal_values for value in documented):
            conflicts.append("BE-FAST vollständig unauffällig")

    if "akutes koronarsyndrom" in name or candidate_name == "Kardiale Ursache / Rhythmusstörung":
        region = str(o.get("region") or "").lower()
        if region and not any(term in region for term in ("brust", "thorax", "oberbauch", "epigastr")):
            conflicts.append(f"Schmerzregion {o.get('region')} atypisch")

    if "rhythmusstörung" in name and puls is not None and 50 <= puls <= 100:
        conflicts.append(f"Puls {puls:g}/min im Normbereich")
    if "tachyarrhythmie" in name and puls is not None and puls <= 100:
        conflicts.append(f"Puls {puls:g}/min ohne Tachykardie")
    if "bradyarrhythmie" in name and puls is not None and puls >= 50:
        conflicts.append(f"Puls {puls:g}/min nicht bradykard")

    if "lungenarterienembolie" in name and af is not None and af <= 20 and spo2 is not None and spo2 >= 95:
        conflicts.append(f"AF {af:g}/min und SpO₂ {spo2:g} % unauffällig")

    return conflicts
# --------------------------------------------------
# Navigation
# --------------------------------------------------

# Centered navigation in main area
if 'seite' not in st.session_state:
    st.session_state['seite'] = "❤️ Vitalwerte"

# Widget-Werte sichern, bevor ein Navigationsbutton die aktuelle Seite verlässt.
# Das ist besonders bei Text- und Zahlenfeldern wichtig, deren letzter Wert erst
# mit dem Klick auf den nächsten Reiter an Streamlit übertragen wird.
if st.session_state['seite'] == "❤️ Vitalwerte":
    sync_vitalwerte_from_session_state()
elif st.session_state['seite'] == "🩺 xABCDE":
    sync_xabcde_from_session_state()
elif st.session_state['seite'] == "📋 SAMPLERS":
    sync_samplers_from_session_state()

if 'xabcde_selected' not in st.session_state:
    st.session_state['xabcde_selected'] = "A"

if 'visited_pages' not in st.session_state:
    st.session_state['visited_pages'] = set()

st.session_state['visited_pages'].add(st.session_state['seite'])

topbar_left, topbar_right = st.columns([14, 2])
with topbar_left:
    new_case_col, _ = st.columns([2.4, 9.6])
    with new_case_col:
        if st.button("＋ Neuer Einsatz", key="new_case_btn", use_container_width=True, type="secondary"):
            st.session_state["confirm_new_case"] = True
with topbar_right:
    st.markdown("<div style='height: 0.1rem;'></div>", unsafe_allow_html=True)
    if st.button("Admin", key="top_admin_btn", use_container_width=True, type="secondary"):
        st.session_state["seite"] = "🛠️ Admin"
        st.rerun()

if st.session_state.get("confirm_new_case"):
    st.warning("Alle Eingaben des aktuellen Einsatzes werden gelöscht. Wirklich neu beginnen?")
    confirm_col, cancel_col, _ = st.columns([2, 2, 8])
    with confirm_col:
        if st.button("Ja, Einsatz leeren", key="confirm_new_case_btn", use_container_width=True, type="primary"):
            reset_patient_case()
            st.rerun()
    with cancel_col:
        if st.button("Abbrechen", key="cancel_new_case_btn", use_container_width=True):
            st.session_state["confirm_new_case"] = False
            st.rerun()

workflow_completion = workflow_completion_state(patient)
workflow_total = len(WORKFLOW_STEPS)
workflow_completed = sum(1 for step in WORKFLOW_STEPS if workflow_completion.get(step["page"]))
current_workflow_index = workflow_step_index(st.session_state["seite"])

if current_workflow_index is not None:
    st.markdown(
        f"""
        <div class="workflow-compact-head">
            <div class="workflow-compact-row">
                <div class="workflow-compact-title">{current_workflow_index + 1}. {WORKFLOW_STEPS[current_workflow_index]['label']}</div>
                <div class="workflow-compact-meta">{workflow_completed}/{workflow_total} erledigt</div>
            </div>
            <div class="workflow-compact-track"><div class="workflow-compact-fill" style="width:{(workflow_completed / workflow_total) * 100:.0f}%"></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if current_workflow_index != workflow_step_index("📄 Protokoll"):
        st.markdown(
            f"""
            <style>
            .st-key-workflow_step_{current_workflow_index} button {{
                color:#f5f9ff !important;
                border-color:rgba(94,168,255,.52) !important;
                background:rgba(94,168,255,.14) !important;
                box-shadow:0 0 0 1px rgba(94,168,255,.10), 0 0 18px rgba(94,168,255,.12) !important;
            }}
            .st-key-workflow_step_{current_workflow_index} button:hover {{
                background:rgba(94,168,255,.20) !important;
                border-color:rgba(94,168,255,.66) !important;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )

    with st.container(key="workflow_overview"):
        with st.expander("Alle Schritte anzeigen", expanded=False):
            for row_start in range(0, workflow_total, 5):
                workflow_cols = st.columns(min(5, workflow_total - row_start), gap="small")
                for column, idx in zip(workflow_cols, range(row_start, min(row_start + 5, workflow_total))):
                    step = WORKFLOW_STEPS[idx]
                    with column:
                        prefix = "✓" if workflow_completion.get(step["page"]) else ("•" if idx == current_workflow_index else "")
                        display_label = f"{prefix} {step.get('short_label', step['label'])}".strip()
                        button_type = "primary" if idx == current_workflow_index else "secondary"
                        if st.button(
                            display_label,
                            key=f"workflow_step_{idx}",
                            use_container_width=True,
                            type=button_type,
                        ):
                            st.session_state["seite"] = step["page"]
                            st.rerun()

seite = st.session_state['seite']

# --------------------------------------------------
# VITALWERTE
# --------------------------------------------------

if seite == "🛠️ Admin":

    st.header("🛠️ Adminbereich")
    st.caption("Passwortgeschützt: Alle SOP-Parameter zentral pflegen")

    if not st.session_state.get("admin_unlocked", False):
        admin_pw = st.text_input("Admin-Passwort", type="password", key="admin_password_input")
        if st.button("🔓 Admin freischalten", key="admin_unlock_btn", use_container_width=True, type="primary"):
            if check_admin_password(admin_pw):
                st.session_state["admin_unlocked"] = True
                st.success("Adminbereich freigeschaltet")
                st.rerun()
            else:
                st.error("Falsches Passwort")
    else:
        current_values = st.session_state["sop_admin_config"].get("value_overrides", {})

        st.info("Alle Felder wirken global auf die SOP-Logik. Änderungen erst nach Speichern aktiv.")

        edited_values = {}
        for sop_name, fields in ADMIN_SOP_FIELDS.items():
            with st.expander(sop_name, expanded=False):
                for field in fields:
                    value = st.number_input(
                        field["label"],
                        min_value=float(field["min"]),
                        max_value=float(field["max"]),
                        value=float(current_values.get(field["key"], field["default"])),
                        step=float(field["step"]),
                        key=f"admin_cfg_{field['key']}",
                    )
                    edited_values[field["key"]] = float(value)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Einstellungen speichern", use_container_width=True, type="primary"):
                new_overrides = dict(current_values)
                new_overrides.update(edited_values)
                st.session_state["sop_admin_config"] = {"value_overrides": new_overrides}
                _save_sop_admin_config(st.session_state["sop_admin_config"])
                st.success("Admin-Einstellungen gespeichert")

        with c2:
            if st.button("↺ Auf Defaults zurücksetzen", use_container_width=True):
                st.session_state["sop_admin_config"] = deepcopy(DEFAULT_SOP_ADMIN_CONFIG)
                _save_sop_admin_config(st.session_state["sop_admin_config"])
                st.success("Standardwerte wiederhergestellt")
                st.rerun()

        c3, c4 = st.columns(2)
        with c4:
            if st.button("🔒 Admin sperren", use_container_width=True):
                st.session_state["admin_unlocked"] = False
                st.rerun()

        st.subheader("Aktive Konfiguration")
        st.code(json.dumps(st.session_state.get("sop_admin_config", {}), indent=2, ensure_ascii=False), language="json")

elif seite == "❤️ Vitalwerte":

    st.header("❤️ Vitalwerte & Demographie")

    vitalwerte = patient["vitalwerte"]
    demographic_done = all(_is_valid_value(vitalwerte.get(key)) for key in ("geschlecht", "alter", "auffindesituation"))
    breathing_done = all(_is_valid_value(vitalwerte.get(key)) for key in ("spo2", "af"))
    circulation_done = all(_is_valid_value(vitalwerte.get(key)) for key in ("rr_sys", "rr_dia", "puls"))
    neuro_done = all(_is_valid_value(vitalwerte.get(key)) for key in ("gcs", "bz"))
    exposure_done = bool(st.session_state.get("temp_checkbox")) and _is_valid_value(vitalwerte.get("temperatur"))

    with st.expander(f"{'✓ ' if demographic_done else ''}Patientendemographie", expanded=not demographic_done):
        d1, d2, d3 = st.columns(3)
        with d1:
            vitalwerte["geschlecht"] = st.selectbox(
                "Geschlecht", ["", "männlich", "weiblich", "divers", "Unbekannt"], key="geschlecht"
            )
        with d2:
            vitalwerte["alter"] = st.number_input("Alter (Jahre)", 0, 130, 0, key="alter")
        with d3:
            vitalwerte["auffindesituation"] = st.selectbox(
                "Auffindesituation",
                ["", "sitzend vorgefunden", "liegend vorgefunden", "stehend vorgefunden", "am Boden", "auf Stuhl/Sofa", "in häuslicher Umgebung"],
                key="auffindesituation",
            )

    with st.expander(f"{'✓ ' if breathing_done else ''}B – Atmung & Oxygenation", expanded=not breathing_done):
        b1, b2 = st.columns(2)
        with b1:
            vitalwerte["spo2"] = st.number_input("SpO₂ (%)", 0, 100, 0, key="spo2_input")
            if _is_valid_value(vitalwerte["spo2"]):
                st.caption(f"Automatische Einordnung: {categorize_spo2(vitalwerte['spo2'])[0]}")
        with b2:
            vitalwerte["af"] = st.number_input("Atemfrequenz (/min)", 0, 80, 0, key="af_input")
            if _is_valid_value(vitalwerte["af"]):
                st.caption(f"Automatische Einordnung: {categorize_af(vitalwerte['af'])[0]}")

    with st.expander(f"{'✓ ' if circulation_done else ''}C – Zirkulation", expanded=not circulation_done):
        rr_sys_col, rr_dia_col, pulse_col = st.columns(3)
        with rr_sys_col:
            vitalwerte["rr_sys"] = st.number_input("RR systolisch (mmHg)", 0, 300, 0, key="rr_sys_input")
        with rr_dia_col:
            vitalwerte["rr_dia"] = st.number_input("RR diastolisch (mmHg)", 0, 200, 0, key="rr_dia_input")
        with pulse_col:
            vitalwerte["puls"] = st.number_input("Puls (/min)", 0, 250, 0, key="puls_input")
        rr_sys, rr_dia, pulse = vitalwerte.get("rr_sys"), vitalwerte.get("rr_dia"), vitalwerte.get("puls")
        categories = []
        if _is_valid_value(rr_sys) and _is_valid_value(rr_dia):
            categories.append(f"RR: {categorize_rr(rr_sys, rr_dia)[0]}")
        if _is_valid_value(pulse):
            categories.append(f"Puls: {categorize_puls(pulse)[0]}")
        if categories:
            st.caption("Automatische Einordnung: " + " · ".join(categories))

    with st.expander(f"{'✓ ' if neuro_done else ''}D – Neurologischer Status", expanded=not neuro_done):
        d1, d2 = st.columns(2)
        with d1:
            vitalwerte["gcs"] = st.number_input("Glasgow Coma Scale", 3, 15, 15, key="gcs_input")
        with d2:
            vitalwerte["bz"] = st.number_input("Blutzucker (mg/dL)", 0, 1000, 0, key="bz_input")
            if _is_valid_value(vitalwerte["bz"]):
                st.caption(f"Automatische Einordnung: {categorize_bz(vitalwerte['bz'])[0]}")

    with st.expander(f"{'✓ ' if exposure_done else ''}E – Temperatur", expanded=not exposure_done):
        temp_gemessen = st.checkbox("Temperatur gemessen", key="temp_checkbox")
        if temp_gemessen:
            vitalwerte["temperatur"] = st.number_input(
                "Temperatur (°C)", 30.0, 45.0, 36.5, 0.1, key="temp_input"
            )
            st.caption(f"Automatische Einordnung: {categorize_temperature(vitalwerte['temperatur'])[0]}")
        else:
            vitalwerte["temperatur"] = None

    with st.expander("Einsatz-Kurzbericht (optional)", expanded=not bool(vitalwerte.get("kurzbericht"))):
        vitalwerte["kurzbericht"] = st.text_area(
            "Beschreibung des Einsatzes",
            height=130,
            key="kurzbericht",
            placeholder="z. B. Sturz aus Höhe, Verkehrsunfall, Schmerzen seit zwei Stunden …",
        )

    render_live_summary(
        "Live-Zusammenfassung Vitalwerte",
        [
            f"Geschlecht: {patient['vitalwerte'].get('geschlecht')}" if _is_valid_value(patient['vitalwerte'].get('geschlecht')) else "",
            f"Alter: {patient['vitalwerte'].get('alter')}" if _is_valid_value(patient['vitalwerte'].get('alter')) else "",
            f"SpO2: {patient['vitalwerte'].get('spo2')}" if _is_valid_value(patient['vitalwerte'].get('spo2')) else "",
            f"Puls: {patient['vitalwerte'].get('puls')}" if _is_valid_value(patient['vitalwerte'].get('puls')) else "",
            f"GCS: {patient['vitalwerte'].get('gcs')}" if _is_valid_value(patient['vitalwerte'].get('gcs')) else "",
        ],
    )
    render_vital_alerts(patient["vitalwerte"])

# --------------------------------------------------
# xABCDE
# --------------------------------------------------

elif seite == "🩺 xABCDE":

    st.header("🩺 xABCDE")

    if "xabcde_selected" not in st.session_state:
        st.session_state["xabcde_selected"] = "A"

    x = patient.get("xabcde", {})

    section_complete = {
        "A": x.get("atemweg") not in [None, "", "Keine Angabe"] and x.get("hws") not in [None, "", "Keine Angabe"],
        "B": x.get("atmung") not in [None, "", "Keine Angabe"] and x.get("atemgeraeusche") not in [None, "", "Keine Angabe"],
        "C": x.get("haut") not in [None, "", "Keine Angabe"] and x.get("rekap") not in [None, "", "Keine Angabe"] and x.get("pulsqualitaet") not in [None, "", "Keine Angabe"],
        "D": x.get("avpu") not in [None, "", "Keine Angabe"] and x.get("pupillen") not in [None, "", "Keine Angabe"],
        "E": x.get("bodycheck") not in [None, "", "Keine Angabe"] and (
            x.get("bodycheck") != "Auffällig" or x.get("bodycheck_text") not in [None, ""]
        ),
    }

    incomplete_letters = [letter for letter, is_done in section_complete.items() if not is_done]
    selected = st.session_state["xabcde_selected"]

    col1, col2, col3, col4, col5 = st.columns(5, gap="large")
    buttons = ["A", "B", "C", "D", "E"]
    cols = [col1, col2, col3, col4, col5]
    for label, col in zip(buttons, cols):
        is_incomplete = label in incomplete_letters
        button_label = f"🔴 {label} !" if is_incomplete else label
        button_type = "primary" if label == selected else "secondary"
        with col:
            if st.button(button_label, key=f"xabcde_{label}", use_container_width=True, type=button_type):
                st.session_state["xabcde_selected"] = label
                st.rerun()

    selected = st.session_state["xabcde_selected"]

    st.info(f"Aktive Sektion: {selected} — offene Reiter sind mit 🔴 und ! markiert.")

    if selected == "A":
        st.subheader("A – Airway")
        airway_col, hws_col = st.columns(2, gap="large")
        with airway_col:
            patient["xabcde"]["atemweg"] = st.radio(
                "Atemweg",
                ["Keine Angabe", "Frei", "Gefährdet", "Verlegt"],
                key="atemweg"
            )
        with hws_col:
            patient["xabcde"]["hws"] = st.radio(
                "HWS",
                ["Keine Angabe", "Keine Immobilisation", "Stifneck", "Vakuummatratze"],
                key="hws"
            )

    elif selected == "B":
        st.subheader("B – Breathing")
        breathing_col, sounds_col = st.columns(2, gap="large")
        with breathing_col:
            patient["xabcde"]["atmung"] = st.radio(
                "Atmung",
                ["Keine Angabe", "Unauffällig", "Dyspnoe", "Bradypnoe", "Tachypnoe", "Apnoe"],
                key="atmung"
            )
        with sounds_col:
            patient["xabcde"]["atemgeraeusche"] = st.radio(
                "Atemgeräusche",
                ["Keine Angabe", "Beidseits vorhanden", "Links abgeschwächt", "Rechts abgeschwächt", "Keine"],
                key="atemgeraeusche"
            )
        oxygen_col, _ = st.columns(2, gap="large")
        with oxygen_col:
            patient["xabcde"]["sauerstoff"] = st.selectbox(
                "Sauerstoffgabe",
                ["Keine", "2 l/min", "4 l/min", "6 l/min", "10 l/min", "15 l/min"],
                key="sauerstoff"
            )

    elif selected == "C":
        st.subheader("C – Circulation")
        skin_col, recap_col = st.columns(2, gap="large")
        with skin_col:
            patient["xabcde"]["haut"] = st.radio(
                "Haut",
                ["Keine Angabe", "Rosig / warm", "Blass", "Kalt / schweißig", "Zyanotisch"],
                key="haut"
            )
        with recap_col:
            patient["xabcde"]["rekap"] = st.radio(
                "Rekapillarisierungszeit",
                ["Keine Angabe", "< 2 Sekunden", "> 2 Sekunden"],
                key="rekap"
            )
        pulse_col, _ = st.columns(2, gap="large")
        with pulse_col:
            patient["xabcde"]["pulsqualitaet"] = st.radio(
                "Pulsqualität",
                ["Keine Angabe", "Kräftig", "Schwach", "Fadenförmig"],
                key="pulsqualitaet"
            )

    elif selected == "D":
        st.subheader("D – Disability")
        avpu_col, pupils_col = st.columns(2, gap="large")
        with avpu_col:
            patient["xabcde"]["avpu"] = st.radio(
                "AVPU",
                ["Keine Angabe", "A", "V", "P", "U"],
                key="avpu"
            )
        with pupils_col:
            patient["xabcde"]["pupillen"] = st.radio(
                "Pupillen",
                ["Keine Angabe", "Isokor", "Anisokor", "Lichtstarr"],
                key="pupillen"
            )

        st.divider()
        st.subheader("🧠 BE-FAST Schlaganfall-Screening")
        st.caption("B Balance · E Eyes · F Face · A Arms · S Speech · T Time")
        befast_left, befast_right = st.columns(2)
        with befast_left:
            patient["xabcde"]["befast_balance"] = st.selectbox(
                "B – Balance",
                ["Keine Angabe", "Unauffällig", "Akute Gang-/Standunsicherheit", "Akuter Schwindel / Ataxie"],
                key="befast_balance",
            )
            patient["xabcde"]["befast_face"] = st.selectbox(
                "F – Face",
                ["Keine Angabe", "Symmetrisch", "Fazialisparese links", "Fazialisparese rechts"],
                key="befast_face",
            )
            patient["xabcde"]["befast_speech"] = st.selectbox(
                "S – Speech",
                ["Keine Angabe", "Unauffällig", "Dysarthrie", "Aphasie", "Sprachverständnis gestört"],
                key="befast_speech",
            )
        with befast_right:
            patient["xabcde"]["befast_eyes"] = st.selectbox(
                "E – Eyes",
                ["Keine Angabe", "Unauffällig", "Akute Sehstörung", "Doppelbilder", "Gesichtsfeldausfall"],
                key="befast_eyes",
            )
            patient["xabcde"]["befast_arms"] = st.selectbox(
                "A – Arms",
                ["Keine Angabe", "Kein Absinken", "Armabsinken links", "Armabsinken rechts", "Armabsinken beidseits"],
                key="befast_arms",
            )
            patient["xabcde"]["befast_time"] = st.text_input(
                "T – Time / Symptombeginn",
                placeholder="z. B. 14:20 Uhr oder zuletzt gesund um 12:00 Uhr",
                key="befast_time",
            )

        befast_normal_values = {"Unauffällig", "Symmetrisch", "Kein Absinken", "Keine Angabe", ""}
        befast_positive = [
            value
            for key, value in patient["xabcde"].items()
            if key in {"befast_balance", "befast_eyes", "befast_face", "befast_arms", "befast_speech"}
            and value not in befast_normal_values
        ]
        if befast_positive:
            st.error("🔴 BE-FAST auffällig: " + " · ".join(befast_positive))
        elif all(
            patient["xabcde"].get(key) not in [None, "", "Keine Angabe"]
            for key in ("befast_balance", "befast_eyes", "befast_face", "befast_arms", "befast_speech")
        ):
            st.success("🟢 BE-FAST ohne dokumentierte Auffälligkeit")

    elif selected == "E":
        st.subheader("E – Exposure")
        bodycheck_col, exposure_flags_col = st.columns(2, gap="large")
        with bodycheck_col:
            patient["xabcde"]["bodycheck"] = st.radio(
                "Bodycheck",
                ["Keine Angabe", "Unauffällig", "Auffällig"],
                key="bodycheck"
            )
        with exposure_flags_col:
            st.markdown("**Weitere Befunde**")
            patient["xabcde"]["unterkuehlung"] = st.checkbox(
                "Unterkühlung",
                key="unterkuehlung"
            )
            patient["xabcde"]["verbrennung"] = st.checkbox(
                "Verbrennung",
                key="verbrennung"
            )
        if patient["xabcde"]["bodycheck"] == "Auffällig":
            patient["xabcde"]["bodycheck_text"] = st.text_area(
                "Auffälligkeiten",
                height=120,
                key="bodycheck_text"
            )

    render_live_summary(
        "Live-Zusammenfassung xABCDE",
        [
            f"A: {patient['xabcde'].get('atemweg')}" if _is_valid_value(patient['xabcde'].get('atemweg')) else "",
            f"B: {patient['xabcde'].get('atmung')}" if _is_valid_value(patient['xabcde'].get('atmung')) else "",
            f"C: {patient['xabcde'].get('haut')}" if _is_valid_value(patient['xabcde'].get('haut')) else "",
            f"D: AVPU {patient['xabcde'].get('avpu')}" if _is_valid_value(patient['xabcde'].get('avpu')) else "",
            f"E: {patient['xabcde'].get('bodycheck')}" if _is_valid_value(patient['xabcde'].get('bodycheck')) else "",
        ],
    )
    # --------------------------------------------------
# SAMPLERS
# --------------------------------------------------

elif seite == "📋 SAMPLERS":

    st.header("📋 SAMPLERS")

    if "samplers_selected" not in st.session_state:
        st.session_state["samplers_selected"] = "S1"

    samplers_selected = st.session_state["samplers_selected"]
    st.markdown(
        f"""
        <style>
        .st-key-samplers_nav_{samplers_selected} button {{
            color:#f5f9ff !important;
            border-color:rgba(94,168,255,.52) !important;
            background:rgba(94,168,255,.14) !important;
            box-shadow:0 0 0 1px rgba(94,168,255,.10), 0 0 18px rgba(94,168,255,.12) !important;
        }}
        .st-key-samplers_nav_{samplers_selected} button:hover {{
            background:rgba(94,168,255,.20) !important;
            border-color:rgba(94,168,255,.66) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    s_col1, s_col2, s_col3, s_col4, s_col5, s_col6, s_col7, s_col8 = st.columns(8, gap="small")
    s_buttons = ["S1", "A", "M", "P", "L", "E", "R", "S2"]
    s_cols = [s_col1, s_col2, s_col3, s_col4, s_col5, s_col6, s_col7, s_col8]
    for label, col in zip(s_buttons, s_cols):
        with col:
            button_type = "primary" if label == samplers_selected else "secondary"
            if st.button(label, key=f"samplers_nav_{label}", use_container_width=True, type=button_type):
                st.session_state["samplers_selected"] = label
                st.rerun()

    if samplers_selected == "S1":
        st.subheader("S – Symptome")
        textarea_field("samplers", "symptome", "Beschwerden / Symptome")

    elif samplers_selected == "A":
        st.subheader("A – Allergien")
        allergien = radio_field(
            "samplers",
            "allergien",
            "Allergien",
            ["Keine Angabe", "Keine bekannt", "Vorhanden"]
        )
        if allergien == "Vorhanden":
            text_field("samplers", "allergien_text", "Welche Allergien?")

    elif samplers_selected == "M":
        st.subheader("M – Medikamente")
        medikamente = radio_field(
            "samplers",
            "medikamente_option",
            "Medikamente",
            ["Keine Angabe", "Siehe Medikamentenplan", "Medikamente eingeben"]
        )
        if medikamente == "Medikamente eingeben":
            textarea_field("samplers", "medikamente", "Bitte Medikamente eingeben")

    elif samplers_selected == "P":
        st.subheader("P – Patientenvorgeschichte")
        textarea_field("samplers", "vorgeschichte", "Vorerkrankungen")

    elif samplers_selected == "L":
        st.subheader("L – Letzte Nahrungsaufnahme")
        letzte_mahlzeit = radio_field(
            "samplers",
            "letzte_mahlzeit",
            "Letzte Mahlzeit",
            ["Keine Angabe", "< 2 Stunden", "2–6 Stunden", "> 6 Stunden", "Unbekannt", "Eigene Eingabe"]
        )
        if letzte_mahlzeit == "Eigene Eingabe":
            text_field("samplers", "letzte_mahlzeit_text", "Eigene Eingabe")

        st.divider()
        st.subheader("Weitere letzte Ereignisse")
        last_left, last_right = st.columns(2, gap="large")
        with last_left:
            text_field(
                "samplers",
                "letzte_medikamenteneinnahme",
                "Letzte Medikamenteneinnahme (wann / welches Medikament?)",
            )
            text_field(
                "samplers",
                "letzter_stuhlgang",
                "Letzter Stuhlgang (wann / auffällig?)",
            )
        with last_right:
            text_field(
                "samplers",
                "letzte_miktion",
                "Letzte Miktion / Wasserlassen (wann / auffällig?)",
            )
            text_field(
                "samplers",
                "letztes_erbrechen",
                "Letztes Erbrechen (wann / wie oft / Beschaffenheit?)",
            )

    elif samplers_selected == "E":
        st.subheader("E – Ereignis")
        textarea_field("samplers", "ereignis", "Ereignisbeschreibung", height=180)

    elif samplers_selected == "R":
        st.subheader("R – Risikofaktoren")
        col1, col2 = st.columns(2)
        with col1:
            checkbox_field("samplers", "raucher", "Raucher")
            checkbox_field("samplers", "alkohol", "Alkoholkonsum")
            checkbox_field("samplers", "drogen", "Drogen")
        with col2:
            checkbox_field("samplers", "diabetes", "Diabetes")
            checkbox_field("samplers", "hypertonie", "Hypertonie")
            checkbox_field("samplers", "antikoagulation", "Antikoagulation")
        text_field("samplers", "risiken_sonstige", "Weitere Risikofaktoren")

    elif samplers_selected == "S2":
        st.subheader("S – Schwangerschaft")
        radio_field(
            "samplers",
            "schwangerschaft",
            "Schwangerschaft",
            ["Nicht relevant", "Nein", "Ja", "Unbekannt"]
        )

    render_live_summary(
        "Live-Zusammenfassung SAMPLERS",
        [
            f"Symptome: {patient['samplers'].get('symptome')}" if _is_valid_value(patient['samplers'].get('symptome')) else "",
            f"Allergien: {patient['samplers'].get('allergien')}" if _is_valid_value(patient['samplers'].get('allergien')) else "",
            f"Vorgeschichte: {patient['samplers'].get('vorgeschichte')}" if _is_valid_value(patient['samplers'].get('vorgeschichte')) else "",
            f"Letzte Mahlzeit: {patient['samplers'].get('letzte_mahlzeit')}" if _is_valid_value(patient['samplers'].get('letzte_mahlzeit')) else "",
            f"Ereignis: {patient['samplers'].get('ereignis')}" if _is_valid_value(patient['samplers'].get('ereignis')) else "",
        ],
    )

# --------------------------------------------------
# OPQRST
# --------------------------------------------------

elif seite == "🔥 OPQRST":

    st.header("🔥 OPQRST – Schmerzassessment")

    if "opqrst_selected" not in st.session_state:
        st.session_state["opqrst_selected"] = "O"

    patient["opqrst"]["schmerz_vorhanden"] = st.radio(
        "Schmerzen vorhanden?",
        ["Nein", "Ja"],
        key="opqrst_schmerz",
        horizontal=True
    )

    if patient["opqrst"]["schmerz_vorhanden"] == "Ja":
        o_col1, o_col2, o_col3, o_col4, o_col5, o_col6 = st.columns(6, gap="small")
        o_buttons = ["O", "P", "Q", "R", "S", "T"]
        o_cols = [o_col1, o_col2, o_col3, o_col4, o_col5, o_col6]
        for label, col in zip(o_buttons, o_cols):
            with col:
                if st.button(label, key=f"opqrst_nav_{label}", use_container_width=True):
                    st.session_state["opqrst_selected"] = label
                    st.rerun()

        opqrst_selected = st.session_state["opqrst_selected"]
        st.info(f"Aktive OPQRST-Sektion: {opqrst_selected}")

        if opqrst_selected == "O":
            st.subheader("O – Onset (Beginn des Schmerzes)")
            patient["opqrst"]["onset"] = st.selectbox(
                "Beginn",
                ["", "Plötzlich", "Allmählich", "Progressiv verschlimmernd", "Wiederkehrend"],
                key="opqrst_onset"
            )
            patient["opqrst"]["onset_text"] = st.text_input(
                "Zusätzliche Information zu Beginn",
                key="opqrst_onset_text"
            )

        elif opqrst_selected == "P":
            st.subheader("P – Provocation/Palliation (Auslöser und Linderung)")
            patient["opqrst"]["provocation"] = st.selectbox(
                "Was verschlimmert oder lindert den Schmerz?",
                ["", "Bewegung verschlimmert", "Ruhe lindert", "Tiefe Atmung verschlimmert", "Druck lindert", "Wärme lindert", "Kälte lindert", "Nichts lindert"],
                key="opqrst_provocation"
            )
            patient["opqrst"]["provocation_text"] = st.text_input(
                "Genauere Beschreibung",
                key="opqrst_provocation_text"
            )

        elif opqrst_selected == "Q":
            st.subheader("Q – Quality (Charakteristik des Schmerzes)")
            patient["opqrst"]["quality"] = st.selectbox(
                "Wie beschreibt der Patient den Schmerz?",
                ["", "Stechend/Messerscharf", "Dumpf", "Drückend", "Reißend", "Brennend", "Ziehend", "Klopfend", "Rauschhaft"],
                key="opqrst_quality"
            )
            patient["opqrst"]["quality_text"] = st.text_input(
                "Patienteneigene Beschreibung",
                key="opqrst_quality_text"
            )

        elif opqrst_selected == "R":
            st.subheader("R – Region/Radiation (Ort und Ausbreitung)")
            patient["opqrst"]["region"] = st.text_input(
                "Wo tut es weh?",
                key="opqrst_region"
            )
            patient["opqrst"]["radiation"] = st.text_input(
                "Ausstrahlung (Breitet sich der Schmerz aus?)",
                key="opqrst_radiation"
            )

        elif opqrst_selected == "S":
            st.subheader("S – Severity (Stärke des Schmerzes)")
            patient["opqrst"]["nrs"] = st.slider(
                "Numerische Rating-Skala (NRS) 0-10",
                0, 10, 0,
                key="opqrst_nrs"
            )
            patient["opqrst"]["severity_desc"] = st.selectbox(
                "Auswirkung auf Aktivitäten",
                ["", "Kein Schmerz (0)", "Minimal (1-3)", "Mäßig (4-6)", "Schwer (7-8)", "Sehr schwer (9-10)"],
                key="opqrst_severity"
            )

        elif opqrst_selected == "T":
            st.subheader("T – Time (Zeitverlauf)")
            patient["opqrst"]["zeitverlauf"] = st.selectbox(
                "Zeitlicher Verlauf",
                ["", "Konstant", "Intermittierend", "Sich verschlimmernd", "Sich verbessernd", "Gleichbleibend"],
                key="opqrst_zeitverlauf"
            )
            patient["opqrst"]["dauer"] = st.text_input(
                "Wie lange besteht der Schmerz bereits?",
                placeholder="z.B. 2 Stunden, seit heute Morgen, ...",
                key="opqrst_dauer"
            )

    render_live_summary(
        "Live-Zusammenfassung OPQRST",
        [
            f"Onset: {patient['opqrst'].get('onset')}" if _is_valid_value(patient['opqrst'].get('onset')) else "",
            f"Provocation: {patient['opqrst'].get('provocation')}" if _is_valid_value(patient['opqrst'].get('provocation')) else "",
            f"Quality: {patient['opqrst'].get('quality')}" if _is_valid_value(patient['opqrst'].get('quality')) else "",
            f"Region: {patient['opqrst'].get('region')}" if _is_valid_value(patient['opqrst'].get('region')) else "",
            f"NRS: {patient['opqrst'].get('nrs')}" if _is_valid_value(patient['opqrst'].get('nrs')) else "",
        ],
    )

# --------------------------------------------------
# MASSNAHMEN
# --------------------------------------------------

elif seite == "⏱️ Maßnahmen":

    st.header("⏱️ Maßnahmen & Timeline")

    m = patient["massnahmen"]

    step_done_col, step_reset_col = st.columns(2)
    with step_done_col:
        if st.button("✓ Maßnahmen-Schritt abschließen", key="complete_measures_step", use_container_width=True):
            st.session_state["workflow_manual_completion"]["⏱️ Maßnahmen"] = True
            st.success("Maßnahmen als abgeschlossen markiert.")
    with step_reset_col:
        if st.button("↺ Abschluss zurücksetzen", key="reset_measures_step", use_container_width=True):
            st.session_state["workflow_manual_completion"]["⏱️ Maßnahmen"] = False
            st.info("Abschlussmarkierung für Maßnahmen entfernt.")

    st.subheader("🕒 Maßnahmen-Timeline")
    t1, t2, t3 = st.columns([1.25, 2, 2])
    with t1:
        timeline_time_input, timeline_now = st.columns([2, 1])
        with timeline_time_input:
            timeline_zeit = st.text_input("Uhrzeit", placeholder="14:32", key="timeline_zeit")
        with timeline_now:
            st.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
            st.button(
                "Jetzt",
                key="timeline_now_btn",
                use_container_width=True,
                on_click=set_current_time,
                args=("timeline_zeit",),
            )
    with t2:
        timeline_massnahme = st.text_input("Maßnahme", placeholder="z.B. O2 über Maske", key="timeline_massnahme")
    with t3:
        timeline_wirkung = st.text_input("Wirkung", placeholder="z.B. Dyspnoe rückläufig", key="timeline_wirkung")

    if st.button("Maßnahme zur Timeline hinzufügen", key="add_timeline", use_container_width=True):
        if _is_valid_value(timeline_massnahme):
            m["timeline"].append({
                "zeit": timeline_zeit if _is_valid_value(timeline_zeit) else datetime.now().strftime("%H:%M"),
                "massnahme": timeline_massnahme,
                "wirkung": timeline_wirkung,
            })
            st.success("Maßnahme hinzugefügt")
            st.rerun()
        else:
            st.warning("Bitte mindestens eine Maßnahme eingeben.")

    if m.get("timeline"):
        for idx, entry in enumerate(m["timeline"], start=1):
            st.write(f"{idx}. {entry.get('zeit','--:--')} - {entry.get('massnahme','')} | Wirkung: {entry.get('wirkung','-')}")

    st.divider()
    st.subheader("💊 Medikationsmodul")
    med1, med2, med3, med4, med5 = st.columns([2, 1, 1, 1.4, 2])
    with med1:
        med_name = st.text_input("Medikament", placeholder="z.B. Morphin", key="med_name")
    with med2:
        med_dosis = st.text_input("Dosis", placeholder="z.B. 2 mg", key="med_dosis")
    with med3:
        med_weg = st.selectbox("Applikation", ["i.v.", "i.m.", "p.o.", "intranasal", "inhalativ", "sonstiges"], key="med_weg")
    with med4:
        med_time_input, med_now = st.columns([2, 1])
        with med_time_input:
            med_zeit = st.text_input("Uhrzeit", placeholder="14:35", key="med_zeit")
        with med_now:
            st.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
            st.button(
                "Jetzt",
                key="med_now_btn",
                use_container_width=True,
                on_click=set_current_time,
                args=("med_zeit",),
            )
    with med5:
        med_wirkung = st.text_input("Wirkung", placeholder="z.B. Schmerzreduktion", key="med_wirkung")

    if st.button("Medikation hinzufügen", key="add_medikation", use_container_width=True):
        if _is_valid_value(med_name):
            m["medikation"].append({
                "name": med_name,
                "dosis": med_dosis,
                "weg": med_weg,
                "zeit": med_zeit if _is_valid_value(med_zeit) else datetime.now().strftime("%H:%M"),
                "wirkung": med_wirkung,
            })
            st.success("Medikation hinzugefügt")
            st.rerun()
        else:
            st.warning("Bitte ein Medikament eintragen.")

    if m.get("medikation"):
        for idx, med in enumerate(m["medikation"], start=1):
            st.write(f"{idx}. {med.get('zeit','--:--')} - {med.get('name','')} ({med.get('dosis','k.A.')}, {med.get('weg','k.A.')}) | Wirkung: {med.get('wirkung','-')}")

    render_live_summary(
        "Live-Zusammenfassung Maßnahmen",
        [
            f"Timeline-Einträge: {len(m.get('timeline', []))}",
            f"Medikationen: {len(m.get('medikation', []))}",
        ],
    )

# --------------------------------------------------
# VERDACHT
# --------------------------------------------------

elif seite == "🔎 Verdacht":

    st.header("🔎 Verdacht & Handlungshilfe")
    st.warning("Hinweis: Dies sind unterstützende Verdachtshinweise und keine ärztliche Diagnose.")

    st.subheader("🏥 ICD-10-GM auf der ärztlichen Einweisung")
    einweisung = patient["einweisung"]
    with st.form("icd_lookup_form", clear_on_submit=False):
        icd_input_col, icd_button_col = st.columns([4, 1])
        with icd_input_col:
            icd_input = st.text_input(
                "ICD-10-GM-Code",
                value=einweisung.get("icd_code", ""),
                placeholder="z. B. J45.0 oder I63.9",
                help="Untercodes können mit Punkt eingegeben werden.",
            )
        with icd_button_col:
            st.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
            lookup_submitted = st.form_submit_button("Übersetzen", use_container_width=True, type="primary")

    if lookup_submitted:
        with st.spinner("ICD-10-GM-Code wird nachgeschlagen …"):
            lookup_result = lookup_icd10_diagnosis(icd_input)
        if lookup_result.get("ok"):
            einweisung["icd_code"] = lookup_result["code"]
            einweisung["diagnose"] = lookup_result["diagnosis"]
            einweisung["source_url"] = lookup_result["source_url"]
        else:
            st.warning(lookup_result.get("error", "ICD-Code konnte nicht aufgelöst werden."))

    if einweisung.get("icd_code") and einweisung.get("diagnose"):
        st.success(f"**{einweisung['icd_code']}** — {einweisung['diagnose']}")
        st.caption("Bezeichnung aus der ICD-Code-Suche von gesund.bund.de; bitte mit der Einweisung abgleichen.")
        clear_icd_col, _ = st.columns([1, 4])
        with clear_icd_col:
            if st.button("ICD-Eintrag löschen", key="clear_icd_entry", use_container_width=True):
                patient["einweisung"] = {}
                st.rerun()

    st.divider()

    suspicions, recommendations = build_suspicion_assessment(patient)

    st.subheader("Mögliche Verdachtsdiagnosen")
    for idx, item in enumerate(suspicions, start=1):
        st.write(f"{idx}. {item}")

    st.subheader("Empfohlene nächste Hilfsmaßnahmen")
    for idx, rec in enumerate(recommendations, start=1):
        st.write(f"{idx}. {rec}")

    render_live_summary(
        "Live-Zusammenfassung Verdacht",
        [
            f"Verdachte: {len(suspicions)}",
            f"Empfehlungen: {len(recommendations)}",
            f"AVPU: {patient.get('xabcde', {}).get('avpu')}" if _is_valid_value(patient.get('xabcde', {}).get('avpu')) else "",
            f"SpO2: {patient.get('vitalwerte', {}).get('spo2')}" if _is_valid_value(patient.get('vitalwerte', {}).get('spo2')) else "",
        ],
    )

# --------------------------------------------------
# AMLS-TRICHTER
# --------------------------------------------------

elif seite == "🔻 AMLS":

    st.header("🔻 AMLS-Differenzialdiagnose-Trichter")
    st.warning(
        "Entscheidungsunterstützung, keine Diagnosestellung: Kandidaten aus dokumentierten Befunden ableiten, "
        "kritische Differenzialdiagnosen aktiv prüfen und Ausschlüsse klinisch begründen."
    )

    amls = patient["amls"]
    candidates = build_amls_candidates(patient)
    candidate_names = [item["name"] for item in candidates]
    amls["excluded"] = [name for name in amls.get("excluded", []) if name in candidate_names]
    excluded = set(amls["excluded"])
    remaining = [item for item in candidates if item["name"] not in excluded]
    conflicts_by_name = {
        item["name"]: [] if item["category"] == "Eigene Ergänzung" else amls_candidate_conflicts(item["name"], patient)
        for item in candidates
    }
    green_count = sum(1 for item in candidates if item["name"] not in excluded and not conflicts_by_name[item["name"]])
    yellow_count = sum(1 for item in candidates if item["name"] not in excluded and conflicts_by_name[item["name"]])

    total_count = max(len(candidates), 1)
    funnel_width = max(38, 100 - int((len(excluded) / total_count) * 62))
    st.markdown(
        f"""
        <div style="margin:12px 0 20px; text-align:center;">
            <div style="margin:auto; width:100%; padding:12px; border-radius:18px 18px 10px 10px; background:linear-gradient(135deg, rgba(94,168,255,.20), rgba(139,92,246,.18)); border:1px solid rgba(255,255,255,.12); font-weight:850;">Ausgangstrichter · {len(candidates)} Kandidaten · 🟢 {green_count} · 🟡 {yellow_count} · 🔴 {len(excluded)}</div>
            <div style="margin:7px auto; width:72%; height:10px; background:rgba(255,255,255,.08); clip-path:polygon(8% 0,92% 0,84% 100%,16% 100%);"></div>
            <div style="margin:auto; width:{funnel_width}%; min-width:260px; padding:14px; border-radius:12px 12px 22px 22px; background:linear-gradient(135deg, rgba(68,221,189,.18), rgba(94,168,255,.18)); border:1px solid rgba(92,255,177,.22); font-size:1.05rem; font-weight:900;">{len(remaining)} verbleibend</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    control_left, control_right = st.columns([1, 1])
    with control_left:
        with st.form("amls_custom_candidate_form", clear_on_submit=True):
            custom_candidate = st.text_input("Fehlende Differenzialdiagnose ergänzen", placeholder="Eigene Verdachtsdiagnose")
            add_custom = st.form_submit_button("Zum Trichter hinzufügen", use_container_width=True)
        if add_custom and custom_candidate.strip():
            cleaned_candidate = custom_candidate.strip()[:120]
            if cleaned_candidate not in amls["custom_candidates"]:
                amls["custom_candidates"].append(cleaned_candidate)
            st.rerun()
    with control_right:
        st.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
        if st.button("↺ Trichter vollständig zurücksetzen", key="amls_reset", use_container_width=True):
            amls["excluded"] = []
            amls["custom_candidates"] = []
            amls["arbeitsdiagnose"] = ""
            st.rerun()

    st.subheader("Kandidaten durch Antippen ausschließen")
    st.markdown(
        "🟢 **passend:** kein dokumentierter Widerspruch &nbsp;&nbsp; "
        "🟡 **prüfen:** mindestens ein Wert weicht vom typischen Muster ab &nbsp;&nbsp; "
        "🔴 **ausgeschlossen:** manuell angeklickt"
    )
    st.caption("Gelb ist kein Ausschluss. Rot markierte Kandidaten können durch erneutes Antippen zurückgeholt werden.")

    candidate_styles = []
    for idx, item in enumerate(candidates):
        if item["name"] in excluded:
            candidate_styles.append(
                f".st-key-amls_candidate_{idx} button {{background:linear-gradient(135deg,#991b1b,#ef4444) !important; border-color:#ff8a8a !important; color:white !important; opacity:1 !important;}}"
            )
        elif conflicts_by_name[item["name"]]:
            candidate_styles.append(
                f".st-key-amls_candidate_{idx} button {{background:linear-gradient(135deg,#a16207,#f4b942) !important; border-color:#ffd978 !important; color:#fffbea !important; opacity:1 !important;}}"
            )
        else:
            candidate_styles.append(
                f".st-key-amls_candidate_{idx} button {{background:linear-gradient(135deg,#087f5b,#22a06b) !important; border-color:#63e6be !important; color:white !important; opacity:1 !important;}}"
            )
    st.markdown("<style>" + "".join(candidate_styles) + "</style>", unsafe_allow_html=True)

    candidate_columns = st.columns(2, gap="large")
    for idx, item in enumerate(candidates):
        is_excluded = item["name"] in excluded
        conflicts = conflicts_by_name[item["name"]]
        with candidate_columns[idx % 2]:
            label = f"✕ {item['name']}" if is_excluded else item["name"]
            clicked = st.button(
                label,
                key=f"amls_candidate_{idx}",
                use_container_width=True,
                disabled=not is_excluded and len(remaining) <= 1,
            )
            st.caption(f"{item['category']} · {item['rationale']}")
            if conflicts and not is_excluded:
                st.caption("🟡 Abweichung: " + " · ".join(conflicts))
            if clicked:
                if is_excluded:
                    amls["excluded"].remove(item["name"])
                elif len(remaining) > 1:
                    amls["excluded"].append(item["name"])
                    if amls.get("arbeitsdiagnose") == item["name"]:
                        amls["arbeitsdiagnose"] = ""
                st.rerun()

    remaining = [item for item in candidates if item["name"] not in set(amls["excluded"])]
    if len(remaining) == 1:
        final_candidate = remaining[0]["name"]
        st.success(f"Letzter Kandidat im Trichter: **{final_candidate}**")
        if st.button(
            "Als dokumentierte Arbeitsdiagnose übernehmen",
            key="amls_confirm_working_diagnosis",
            use_container_width=True,
            type="primary",
        ):
            amls["arbeitsdiagnose"] = final_candidate
            st.session_state["workflow_manual_completion"]["🔻 AMLS"] = True
            st.rerun()

    if amls.get("arbeitsdiagnose"):
        st.info(f"Dokumentierte Arbeitsdiagnose: **{amls['arbeitsdiagnose']}**")
        if st.button("Arbeitsdiagnose zurücknehmen", key="amls_clear_working_diagnosis", use_container_width=True):
            amls["arbeitsdiagnose"] = ""
            st.session_state["workflow_manual_completion"]["🔻 AMLS"] = False
            st.rerun()

# --------------------------------------------------
# MEDIKAMENTENRECHNER
# --------------------------------------------------

elif seite == "💉 Med-Rechner":

    st.header("💉 Medikamentenrechner")
    st.caption("SOP-Rechner für mehrere Krankheitsbilder")
    st.warning("Sicherheits-Hinweis: Dieses Modul ist eine rechnerische SOP-Unterstützung. Es ersetzt keine klinische Entscheidung oder Freigabe durch Fachpersonal.")

    sop = st.selectbox(
        "SOP auswählen",
        [
            "Anaphylaxie (SOPKB0105)",
            "Asthma/COPD Bronchialobstruktion (SOPKB0207)",
            "Hypoglykämie",
            "Krampfanfall",
            "Schlaganfall",
            "Kardiales Lungenödem",
            "Hypertensiver Notfall",
            "Nichttraumatischer Brustschmerz: ACS",
            "Abdominelle Schmerzen / Koliken",
            "Massive Übelkeit / Erbrechen",
            "Starke Schmerzen",
            "Instabile Bradykardie",
            "Instabile Tachykardie",
            "Intoxikation: Benzodiazepine",
            "Intoxikation: Opiate / Opioide",
            "Lungenarterienembolie",
            "Akuter Verschluss peripherer Arterien",
        ],
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        alter = st.number_input("Alter (Jahre)", min_value=0, max_value=120, value=30, key="med_age")
    with c2:
        gewicht = st.number_input("Gewicht (kg)", min_value=1.0, max_value=250.0, value=70.0, step=0.1, key="med_weight")
    with c3:
        schwanger = st.selectbox("Schwangerschaft", ["Nein", "Ja", "Unbekannt"], key="med_pregnant")

    if sop == "Anaphylaxie (SOPKB0105)":
        st.subheader("Klinische Konstellation")
        k1, k2, k3 = st.columns(3)
        with k1:
            grad = st.selectbox("Anaphylaxiegrad", ["I", "II", "III", "IV"], key="ana_grade")
            abcd_problem = st.checkbox("A/B/C/D Problem (Grad II/III)", key="ana_abcd_problem")
        with k2:
            stridor = st.checkbox("Dysphonie / Uvulaschwellung / inspiratorischer Stridor", key="ana_stridor")
            bronch_obstr = st.checkbox("Dyspnoe / bronchiale Obstruktion", key="ana_bronch")
        with k3:
            schock = st.checkbox("Hypotonie / Schock / Bewusstlosigkeit", key="ana_shock")
            kreislaufstillstand = st.checkbox("Kreislaufstillstand", key="ana_cpr")

        ana_adult_age_threshold = float(sop_value("ana_adult_age_threshold", 12.0))
        ana_child_age_threshold = float(sop_value("ana_child_age_threshold", 6.0))

        if alter >= ana_adult_age_threshold:
            adrenalin_im_mg = 0.5
            clemastin_mg = 2.0
            prednisolon_mg = 250.0
            salbutamol_mg = 2.5
        elif alter >= ana_child_age_threshold:
            adrenalin_im_mg = 0.3
            clemastin_mg = round(0.03 * float(gewicht), 2)
            prednisolon_mg = round(2.0 * float(gewicht), 1)
            salbutamol_mg = 1.25
        else:
            adrenalin_im_mg = 0.15
            clemastin_mg = round(0.03 * float(gewicht), 2)
            prednisolon_mg = round(2.0 * float(gewicht), 1)
            salbutamol_mg = None

        volumen_ml = round(20.0 * float(gewicht), 0)

        st.subheader("Berechnete SOP-Dosierungen")
        d1, d2, d3 = st.columns(3)
        with d1:
            st.metric("Adrenalin i.m. (pur)", f"{adrenalin_im_mg} mg")
            st.caption("SOP: alle 5 Minuten wiederholbar bei fehlender Stabilisierung")
        with d2:
            st.metric("Clemastin i.v.", f"{clemastin_mg} mg")
            st.metric("Prednisolon i.v.", f"{prednisolon_mg} mg")
        with d3:
            st.metric("Volumenbolus Vollelektrolyt", f"{int(volumen_ml)} ml")
            if salbutamol_mg is not None:
                st.metric("Salbutamol verneb.", f"{salbutamol_mg} mg")
            else:
                st.metric("Salbutamol verneb.", "keine SOP-Angabe <4 Jahre")

        st.info("Adrenalin-Verneblung laut SOP bei Dysphonie/Uvulaschwellung/Stridor: 4 mg pur verneb.")

        handlung = []
        if kreislaufstillstand or grad == "IV":
            handlung.append("Grad IV / Kreislaufstillstand: Reanimationsalgorithmus (SOP CPR) priorisieren.")
        else:
            handlung.append("Basismaßnahmen: Auslöser entfernen, ABCDE, Monitoring, O2, i.v.-Zugang, Blutzucker, SAMPLER.")
            if abcd_problem or grad in ["II", "III"]:
                handlung.append(f"Unverzüglich Adrenalin i.m. {adrenalin_im_mg} mg (auch ohne vorliegenden i.v.-Zugang).")
            if stridor:
                handlung.append("Atemwegsproblem: Adrenalin 4 mg pur verneb + Clemastin i.v. + Prednisolon i.v.")
            if bronch_obstr:
                if salbutamol_mg is not None:
                    handlung.append(f"Bronchiale Obstruktion: Salbutamol {salbutamol_mg} mg verneb.")
                else:
                    handlung.append("Bronchiale Obstruktion: Salbutamol-Dosis für <4 Jahre nicht in dieser SOP angegeben.")
            if schock:
                handlung.append(f"Schockzeichen: Volumenbolus Vollelektrolyt {int(volumen_ml)} ml.")
            handlung.append("Bei fehlender Stabilisierung Adrenalin i.m. alle 5 Minuten wiederholen und Notarztindikation prüfen.")

        if schwanger == "Ja":
            handlung.append("Schwangerschaft: Risiko-Nutzen eng abwägen, frühzeitige notärztliche/klinische Einbindung.")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"Alter/Gewicht: {alter} J / {gewicht} kg",
                f"Adrenalin i.m.: {adrenalin_im_mg} mg",
                f"Prednisolon i.v.: {prednisolon_mg} mg",
                f"Volumen: {int(volumen_ml)} ml",
            ],
        )

    elif sop == "Asthma/COPD Bronchialobstruktion (SOPKB0207)":
        st.subheader("Klinische Konstellation")
        k1, k2, k3 = st.columns(3)
        with k1:
            sympt_tachy = st.selectbox("Symptomatische Tachykardie", ["Nein", "Ja"], key="asthma_sympt_tachy")
            copd_bekannt = st.selectbox("Bekannte COPD", ["Nein", "Ja"], key="asthma_copd_known")
        with k2:
            keine_besserung = st.selectbox("Keine Besserung nach 5 Min.", ["Nein", "Ja"], key="asthma_no_improve")
            cpap_relevant = st.selectbox("CPAP/NIV erwägen", ["Nein", "Ja"], key="asthma_cpap")
        with k3:
            spo2_aktuell = st.number_input("Aktuelle SpO2 (%)", min_value=50, max_value=100, value=92, key="asthma_spo2")

        meds = []
        handlung = []
        hinweise = []

        if sympt_tachy == "Ja":
            hinweise.append("Laut SOP: bei symptomatischer Tachykardie Notarztindikation prüfen / Notarztruf.")
        else:
            asthma_nebulizer_age_1 = float(sop_value("asthma_nebulizer_age_1", 4.0))
            asthma_nebulizer_age_2 = float(sop_value("asthma_nebulizer_age_2", 6.0))
            if alter < asthma_nebulizer_age_1:
                meds.append("Adrenalin 4 mg pur vernebelt")
            elif asthma_nebulizer_age_1 <= alter <= asthma_nebulizer_age_2:
                meds.append("Salbutamol 1,25 mg vernebelt")
            elif alter > asthma_nebulizer_age_2:
                meds.append("Salbutamol 2,5 mg vernebelt")
                meds.append("Ipratropiumbromid 500 mcg vernebelt")

        if alter > 12:
            meds.append("Prednisolon 100 mg i.v.")
        else:
            pred_mg = round(2.0 * float(gewicht), 1)
            meds.append(f"Prednisolon {pred_mg} mg i.v. (2 mg/kgKG)")
            meds.append("Alternative: Prednisolon 100 mg rektal")

        if copd_bekannt == "Ja":
            o2_ziel = "SpO2 88-92 %"
        else:
            o2_ziel = "SpO2 > 92 %"

        handlung.extend([
            "Basismaßnahmen: Beruhigen, Oberkörper hoch, Lippenbremse, vollständiges Monitoring",
            "Sauerstoffgabe 2-6 l/min (bei schwerer Dyspnoe initial höher), Zielbereich beachten",
            f"Medikation gemäß SOP verabreichen und Wirkung nach {int(sop_value('asthma_no_improvement_minutes', 5.0))} Minuten re-evaluieren",
        ])

        if cpap_relevant == "Ja" or alter > 12:
            handlung.append("CPAP / NIV erwägen (v. a. bei persistierender Ateminsuffizienz)")
        if keine_besserung == "Ja":
            handlung.append("Keine Besserung nach 5 Minuten: Notarztruf auslösen")

        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: SOP enthält keine gesonderte Dosisanpassung; frühe ärztliche Rücksprache einplanen.")

        if spo2_aktuell < 88:
            hinweise.append("Kritische Oxygenierung: Eskalation und engmaschige Kontrolle priorisieren.")

        st.subheader("Berechnete SOP-Dosierungen")
        for i, med in enumerate(meds, start=1):
            st.write(f"{i}. {med}")

        st.info(f"Sauerstoffziel laut SOP: {o2_ziel}")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        if hinweise:
            st.subheader("Zusätzliche Hinweise")
            for i, h in enumerate(hinweise, start=1):
                st.write(f"{i}. {h}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"Alter/Gewicht: {alter} J / {gewicht} kg",
                f"Symptomatische Tachykardie: {sympt_tachy}",
                f"O2-Ziel: {o2_ziel}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

    elif sop == "Hypoglykämie":
        st.subheader("Klinische Konstellation")
        h1, h2, h3 = st.columns(3)
        with h1:
            bz_mg = st.number_input("BZ (mg/dl)", min_value=10, max_value=1000, value=55, key="hypo_bz_mg")
        with h2:
            bewusstseinsstoerung = st.selectbox("Bewusstseinsstörung", ["Nein", "Ja"], key="hypo_conscious")
        with h3:
            keine_besserung_hypo = st.selectbox("Keine Besserung (5 Min.)", ["Nein", "Ja"], key="hypo_no_improve")

        bz_mmol = round(float(bz_mg) / 18.0, 1)
        hypo_bz_threshold_mg = float(sop_value("hypo_bz_threshold_mg", 60.0))
        hypo_bz_threshold_mmol = float(sop_value("hypo_bz_threshold_mmol", 3.3))
        kriterium_hypo = float(bz_mg) < hypo_bz_threshold_mg or bz_mmol < hypo_bz_threshold_mmol

        st.caption(f"Umgerechnet: {bz_mmol} mmol/l")

        handlung = [
            "Basismaßnahmen durchführen",
            "Notarztruf prüfen",
        ]
        meds = []
        hinweise = []

        if kriterium_hypo:
            if bewusstseinsstoerung == "Ja":
                meds.append("Glucose bis zu 16 g i.v.")
            else:
                meds.append("Glucose oral")
        else:
            hinweise.append(
                f"Schwellenwert für SOP-Hypoglykämie aktuell nicht erfüllt (BZ <{hypo_bz_threshold_mg:g} mg/dl oder <{hypo_bz_threshold_mmol:g} mmol/l)."
            )

        if keine_besserung_hypo == "Ja":
            handlung.append("Notarztruf auslösen")
            handlung.append("Kliniktransport priorisieren")
        else:
            handlung.append("Weiterbeobachtung und anschließend Klinik / Ende gemäß Gesamtlage")

        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: frühzeitige ärztliche Rücksprache einplanen.")

        st.subheader("Berechnete SOP-Medikation")
        if meds:
            for i, med in enumerate(meds, start=1):
                st.write(f"{i}. {med}")
        else:
            st.write("Keine unmittelbare Glucose-Gabe nach diesem SOP-Schwellenwert.")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        if hinweise:
            st.subheader("Zusätzliche Hinweise")
            for i, h in enumerate(hinweise, start=1):
                st.write(f"{i}. {h}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"BZ: {bz_mg} mg/dl ({bz_mmol} mmol/l)",
                f"Bewusstseinsstörung: {bewusstseinsstoerung}",
                f"Keine Besserung (5 Min.): {keine_besserung_hypo}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

    elif sop == "Krampfanfall":
        st.subheader("Klinische Konstellation")
        k1, k2, k3 = st.columns(3)
        with k1:
            andauernder_anfall_1 = st.selectbox("Andauernder Anfall", ["Nein", "Ja"], key="seizure_persistent_1")
        with k2:
            bewusstlos = st.selectbox("Bewusstlos", ["Nein", "Ja"], key="seizure_unconscious")
        with k3:
            iv_zugang = st.selectbox("i.v. Zugang vorhanden", ["Nein", "Ja"], key="seizure_iv_access")

        andauernder_anfall_2 = st.selectbox("Andauernder Anfall nach Intervention", ["Nein", "Ja"], key="seizure_persistent_2")

        seizure_iv_midazolam_mg_per_kg = float(sop_value("seizure_iv_midazolam_mg_per_kg", 0.05))
        iv_midazolam_mg = round(seizure_iv_midazolam_mg_per_kg * float(gewicht), 2)
        meds = []
        handlung = [
            "Basismaßnahmen durchführen",
            "Notarztruf prüfen",
        ]
        hinweise = []

        if andauernder_anfall_1 == "Nein":
            if bewusstlos == "Ja":
                handlung.append("Stabile Seitenlage")
            handlung.append("ABCDE-Re-Evaluation")
            handlung.append("Klinik / Ende gemäß Gesamtlage")
        else:
            if iv_zugang == "Ja":
                meds.append(f"Midazolam {iv_midazolam_mg} mg i.v. (0,05 mg/kgKG), langsam in mg-Schritten titrieren")
            else:
                if float(gewicht) <= 10:
                    meds.append("Midazolam nasal 2,5 mg (= 0,5 ml)")
                elif float(gewicht) < 20:
                    meds.append("Midazolam nasal 5 mg (= 1 ml)")
                else:
                    meds.append("Midazolam nasal 10 mg (= 2 ml)")
                hinweise.append("Intranasale Medikamentengabe gemäß SOP-Schema")

            if andauernder_anfall_2 == "Ja":
                handlung.append("Notarztruf auslösen")
                handlung.append("Kliniktransport priorisieren")
            else:
                handlung.append("ABCDE-Re-Evaluation")
                handlung.append("Klinik / Ende gemäß Gesamtlage")

        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: frühzeitige notärztliche/klinische Rücksprache einplanen.")

        st.subheader("Berechnete SOP-Medikation")
        if meds:
            for i, med in enumerate(meds, start=1):
                st.write(f"{i}. {med}")
        else:
            st.write("Keine sofortige Midazolam-Gabe gemäß Entscheidungsweg erforderlich.")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        if hinweise:
            st.subheader("Zusätzliche Hinweise")
            for i, h in enumerate(hinweise, start=1):
                st.write(f"{i}. {h}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"Alter/Gewicht: {alter} J / {gewicht} kg",
                f"Andauernder Anfall initial: {andauernder_anfall_1}",
                f"i.v. Zugang vorhanden: {iv_zugang}",
                f"Midazolam i.v.-Rechner: {iv_midazolam_mg} mg",
            ],
        )

    elif sop == "Schlaganfall":
        st.subheader("Klinische Konstellation")
        s1, s2, s3 = st.columns(3)
        with s1:
            rr_syst = st.number_input("RR syst. (mmHg)", min_value=50, max_value=300, value=170, key="stroke_rr_syst")
        with s2:
            symptombeginn_h = st.number_input("Stunden seit Symptombeginn", min_value=0.0, max_value=72.0, value=1.5, step=0.5, key="stroke_onset_h")
        with s3:
            befast_positiv = st.selectbox("BE-FAST positiv", ["Nein", "Ja"], key="stroke_befast")

        c1, c2, c3 = st.columns(3)
        with c1:
            cave_fieber = st.selectbox("CAVE Fieber", ["Nein", "Ja"], key="stroke_cave_fever")
        with c2:
            cave_exsikkose = st.selectbox("CAVE Exsikkose", ["Nein", "Ja"], key="stroke_cave_exsiccosis")
        with c3:
            cave_hypogly = st.selectbox("CAVE Hypoglykämie", ["Nein", "Ja"], key="stroke_cave_hypo")

        meds = []
        handlung = [
            "Basismaßnahmen durchführen",
            "Notarztruf prüfen",
        ]
        hinweise = []

        stroke_rr_low_threshold = float(sop_value("stroke_rr_low_threshold", 120.0))
        stroke_rr_high_threshold = float(sop_value("stroke_rr_high_threshold", 220.0))
        stroke_lysis_window_h = float(sop_value("stroke_lysis_window_h", 6.0))
        stroke_thrombectomy_window_h = float(sop_value("stroke_thrombectomy_window_h", 8.0))

        if rr_syst < stroke_rr_low_threshold:
            meds.append("Volumengabe 500 ml Vollelektrolytlösung i.v.")
            hinweise.append("Ziel: Normotension")
        elif rr_syst > stroke_rr_high_threshold:
            meds.append("Urapidil 5-15 mg langsam i.v., titrierend")
            hinweise.append(f"Ziel: systolischer RR < {stroke_rr_high_threshold:g} mmHg")
        else:
            hinweise.append(
                f"Bei RR syst. {stroke_rr_low_threshold:g}-{stroke_rr_high_threshold:g} mmHg keine primäre RR-Senkung gemäß SOP-Fluss."
            )

        handlung.append("Voranmeldung Neurologie / Stroke Unit")
        handlung.append("Kliniktransport priorisieren")

        if symptombeginn_h < stroke_lysis_window_h:
            hinweise.append(f"Zeitfenster: < {stroke_lysis_window_h:g} h, systemische Lyse möglich.")
        elif symptombeginn_h <= stroke_thrombectomy_window_h:
            hinweise.append(
                f"Zeitfenster: bis {stroke_thrombectomy_window_h:g} h und mehr, intraarterielle Thrombektomie möglich."
            )
        else:
            hinweise.append("Zeitfenster außerhalb klassischer Akutfenster, trotzdem Stroke-Unit-Voranmeldung.")

        if befast_positiv == "Ja":
            hinweise.append("BE-FAST passend: Balance/Eyes/Face/Arm/Speech/Time dokumentieren.")
        if cave_fieber == "Ja" or cave_exsikkose == "Ja" or cave_hypogly == "Ja":
            hinweise.append("CAVE-Konstellation vorhanden: Differenzialdiagnosen aktiv mitbeurteilen.")
        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: frühe neurologische/geburtshilfliche Rücksprache einplanen.")

        st.subheader("Berechnete SOP-Medikation")
        if meds:
            for i, med in enumerate(meds, start=1):
                st.write(f"{i}. {med}")
        else:
            st.write("Keine akute medikamentöse RR-Intervention gemäß SOP-Schwelle erforderlich.")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        st.subheader("Zusätzliche Hinweise")
        for i, h in enumerate(hinweise, start=1):
            st.write(f"{i}. {h}")

        st.info(
            "Stroke-Unit Kontakte (laut Vorlage): "
            "Borken 02861 97 707 77 | Wesel (ev.) 0281 106 5808 (tags) / 0281 106 5800 | "
            "Dülmen 02594 92 47750 | MST Enschede 0031 53 4873999 | Nordhorn 05921 84 2222 | "
            "UKM Münster 0251 83 55555"
        )

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"RR syst.: {rr_syst} mmHg",
                f"Seit Symptombeginn: {symptombeginn_h} h",
                f"BE-FAST positiv: {befast_positiv}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

    elif sop == "Kardiales Lungenödem":
        st.subheader("Klinische Konstellation")
        c1, c2, c3 = st.columns(3)
        with c1:
            rr_syst = st.number_input("RR syst. (mmHg)", min_value=50, max_value=300, value=160, key="pulm_rr_syst")
        with c2:
            keine_besserung_pulm = st.selectbox("Keine Besserung", ["Nein", "Ja"], key="pulm_no_improve")
        with c3:
            cpap_moeglich = st.selectbox("CPAP/NIV verfügbar", ["Nein", "Ja"], key="pulm_cpap_available")

        meds = []
        handlung = [
            "Basismaßnahmen durchführen",
            "Notarztruf prüfen",
            "CPAP-Therapie starten",
        ]
        hinweise = []

        if cpap_moeglich == "Ja":
            hinweise.append("CPAP / NIV anwenden (laut SOP frühzeitig vorgesehen).")
        else:
            hinweise.append("CPAP/NIV nicht verfügbar: Atemunterstützung bestmöglich mit O2 und Lagerung.")

        pulm_nitro_rr_threshold = float(sop_value("pulm_nitro_rr_threshold", 120.0))
        pulm_hypertensive_rr_threshold = float(sop_value("pulm_hypertensive_rr_threshold", 220.0))

        if rr_syst > pulm_nitro_rr_threshold:
            meds.append("Glyceroltrinitrat 0,4-0,8 mg s.l.")
        else:
            hinweise.append(f"Bei RR syst. <= {pulm_nitro_rr_threshold:g} mmHg kein Nitro gemäß SOP-Fluss.")

        meds.append("Furosemid 20 mg i.v. langsam, ggf. einmalige Repetition")

        if rr_syst >= pulm_hypertensive_rr_threshold:
            hinweise.append(f"Hypertensiver Notfall (RR syst. >= {pulm_hypertensive_rr_threshold:g} mmHg)")
            handlung.append("Notärztliche Eskalation unmittelbar priorisieren")
        else:
            hinweise.append(f"RR-Ziel im Verlauf: systolisch < {pulm_hypertensive_rr_threshold:g} mmHg")

        if keine_besserung_pulm == "Ja":
            handlung.append("Notarztruf auslösen")
        else:
            handlung.append("ABCDE-Re-Evaluation")

        handlung.append("Kliniktransport priorisieren")

        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: frühe notärztliche/klinische Rücksprache einplanen.")

        st.subheader("Berechnete SOP-Medikation")
        for i, med in enumerate(meds, start=1):
            st.write(f"{i}. {med}")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        st.subheader("Zusätzliche Hinweise")
        for i, h in enumerate(hinweise, start=1):
            st.write(f"{i}. {h}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"RR syst.: {rr_syst} mmHg",
                f"CPAP/NIV verfügbar: {cpap_moeglich}",
                f"Keine Besserung: {keine_besserung_pulm}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

    elif sop == "Hypertensiver Notfall":
        st.subheader("Klinische Konstellation")
        h1, h2, h3 = st.columns(3)
        with h1:
            rr_syst = st.number_input("RR syst. (mmHg)", min_value=50, max_value=300, value=190, key="htn_rr_syst")
        with h2:
            kein_lungenoedem = st.selectbox("Kein Lungenödem", ["Ja", "Nein"], key="htn_no_pulm_edema")
        with h3:
            keine_brustschmerzen = st.selectbox("Keine Brustschmerzen", ["Ja", "Nein"], key="htn_no_chest_pain")

        d1, d2, d3 = st.columns(3)
        with d1:
            befast_unauffaellig = st.selectbox("BE-FAST-Test unauffällig", ["Ja", "Nein"], key="htn_befast_normal")
        with d2:
            keine_besserung_htn = st.selectbox("Keine Besserung", ["Nein", "Ja"], key="htn_no_improve")
        with d3:
            organdysfunktion = st.multiselect(
                "Zusätzliche Organdysfunktion",
                [
                    "Kopfschmerzen",
                    "Druck im Kopf",
                    "Roter Kopf",
                    "Augenflimmern",
                    "Übelkeit",
                    "Ohrensausen",
                ],
                key="htn_organdysf",
            )

        meds = []
        handlung = [
            "Basismaßnahmen durchführen",
            "Notarztruf prüfen",
        ]
        hinweise = []

        htn_rr_threshold = float(sop_value("htn_rr_threshold", 180.0))
        if rr_syst <= htn_rr_threshold:
            hinweise.append(
                f"SOP-Hinweis: hypertensiver Notfall typischerweise bei RR syst. > {htn_rr_threshold:g} mmHg mit Organdysfunktion."
            )

        if len(organdysfunktion) == 0:
            hinweise.append("Keine zusätzliche Organdysfunktion markiert; Differenzialdiagnosen und Gesamtlage engmaschig prüfen.")

        if kein_lungenoedem == "Nein":
            handlung.append("Konstellation spricht für kardiales Lungenödem: entsprechenden SOP-Pfad priorisieren")
        elif keine_brustschmerzen == "Nein":
            handlung.append("Brustschmerz vorhanden: ACS-SOP priorisieren")
        elif befast_unauffaellig == "Nein":
            handlung.append("Neurologische Auffälligkeit: Schlaganfall-SOP priorisieren")
        else:
            meds.append("Urapidil 5-15 mg langsam i.v., titrierend")
            hinweise.append("Systolische RR-Senkung initial um maximal 20 % anstreben")

        if keine_besserung_htn == "Ja":
            handlung.append("Notarztruf auslösen")
        else:
            handlung.append("ABCDE-Re-Evaluation")

        handlung.append("Kliniktransport priorisieren")

        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: frühe notärztliche/klinische Rücksprache einplanen.")

        st.subheader("Berechnete SOP-Medikation")
        if meds:
            for i, med in enumerate(meds, start=1):
                st.write(f"{i}. {med}")
        else:
            st.write("Keine direkte Urapidil-Gabe in diesem Entscheidungszweig.")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        st.subheader("Zusätzliche Hinweise")
        for i, h in enumerate(hinweise, start=1):
            st.write(f"{i}. {h}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"RR syst.: {rr_syst} mmHg",
                f"Organdysfunktion markiert: {len(organdysfunktion)}",
                f"BE-FAST unauffällig: {befast_unauffaellig}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

    elif sop == "Nichttraumatischer Brustschmerz: ACS":
        st.subheader("Klinische Konstellation")
        a1, a2, a3 = st.columns(3)
        with a1:
            nrs_acs = st.number_input("NRS (0-10)", min_value=0, max_value=10, value=5, key="acs_nrs")
        with a2:
            af = st.number_input("AF / min", min_value=4, max_value=60, value=16, key="acs_rr")
        with a3:
            st_hebung_persist = st.selectbox("Persistierende ST-Hebung", ["Nein", "Ja"], key="acs_ste")

        b1, b2 = st.columns(2)
        with b1:
            neuer_schenkelblock = st.selectbox("Neuer Rechts-/Linksschenkelblock", ["Nein", "Ja"], key="acs_bundle_branch")
        with b2:
            keine_besserung_acs = st.selectbox("Keine Besserung", ["Nein", "Ja"], key="acs_no_improve")

        meds = [
            "ASS 250 mg i.v.",
            "Heparin 5000 I.E.",
        ]
        handlung = [
            "Basismaßnahmen durchführen",
            "Notarztruf prüfen",
        ]
        hinweise = [
            "Differenzialdiagnosen beachten: Spontanpneumothorax, Lungenembolie, akutes Aortenaneurysma",
            "BTM-Dokumentation bei Opioidgabe beachten",
        ]

        acs_morphin_nrs_threshold = float(sop_value("acs_morphin_nrs_threshold", 4.0))
        acs_af_alarm_threshold = float(sop_value("acs_af_alarm_threshold", 10.0))

        if nrs_acs > acs_morphin_nrs_threshold:
            meds.append("Morphin 3 mg i.v., einmalige Repetition nach 5 Minuten möglich")
            handlung.append(f"Nasenkapnografie, Alarmgrenze AF < {acs_af_alarm_threshold:g}/min")
            handlung.append("Voranmeldung Kardiologie und EKG-Übermittlung")
        else:
            handlung.append("ABCDE-Re-Evaluation")

        if af < acs_af_alarm_threshold:
            hinweise.append("Atemfrequenz unter Alarmgrenze: engmaschige Überwachung und Eskalation.")

        if st_hebung_persist == "Ja" or neuer_schenkelblock == "Ja":
            handlung.append("Sofortiger Transport in Kardiologie mit HKL-Option")
        else:
            handlung.append("Kliniktransport priorisieren")

        if keine_besserung_acs == "Ja":
            handlung.append("Notarztruf auslösen")

        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: frühe kardiologische/geburtshilfliche Rücksprache einplanen.")

        st.subheader("Berechnete SOP-Medikation")
        for i, med in enumerate(meds, start=1):
            st.write(f"{i}. {med}")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        st.subheader("Zusätzliche Hinweise")
        for i, h in enumerate(hinweise, start=1):
            st.write(f"{i}. {h}")

        st.info(
            "Kardiologie-Kontakte (laut Vorlage): "
            "Ahaus 02561 991013 | Bocholt 02871 201673 | Coesfeld 02541 8947500 | "
            "Gronau 02562 9150 | MST Enschede 0031 53 4873999 | Wesel (kath.) 0281 1040"
        )

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"NRS: {nrs_acs}",
                f"AF: {af}/min",
                f"ST-Hebung persistierend: {st_hebung_persist}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

    elif sop == "Abdominelle Schmerzen / Koliken":
        st.subheader("Klinische Konstellation")
        a1, a2, a3 = st.columns(3)
        with a1:
            nrs_abd_1 = st.number_input("NRS initial (0-10)", min_value=0, max_value=10, value=6, key="abd_nrs_1")
        with a2:
            nrs_abd_2 = st.number_input("NRS nach Paracetamol", min_value=0, max_value=10, value=6, key="abd_nrs_2")
        with a3:
            nrs_abd_3 = st.number_input("NRS nach Butylscopolamin", min_value=0, max_value=10, value=5, key="abd_nrs_3")

        meds = []
        handlung = [
            "Basismaßnahmen durchführen",
            "Notarztruf prüfen",
        ]
        hinweise = []

        abd_initial_nrs_threshold = float(sop_value("abd_initial_nrs_threshold", 3.0))
        abd_step2_nrs_threshold = float(sop_value("abd_step2_nrs_threshold", 6.0))
        abd_step3_nrs_threshold = float(sop_value("abd_step3_nrs_threshold", 6.0))
        abd_fentanyl_weight_threshold = float(sop_value("abd_fentanyl_weight_threshold", 30.0))

        if nrs_abd_1 >= abd_initial_nrs_threshold:
            if alter > 12:
                if float(gewicht) <= 50:
                    paracetamol_mg = round(15.0 * float(gewicht), 0)
                    meds.append(f"Paracetamol {int(paracetamol_mg)} mg i.v. (15 mg/kgKG)")
                else:
                    meds.append("Paracetamol 1 g i.v.")
            else:
                hinweise.append("Paracetamol-Stufe im SOP-Fluss explizit für Erw./Kind >12 Jahre angegeben.")
        else:
            handlung.append("ABCDE-Re-Evaluation")

        if nrs_abd_2 > abd_step2_nrs_threshold:
            butyl_mg = min(round(0.3 * float(gewicht), 1), 40.0)
            if alter > 12:
                meds.append(f"Butylscopolamin {butyl_mg} mg langsam i.v. (0,3 mg/kgKG, max. 40 mg)")
            else:
                hinweise.append("Butylscopolamin-Stufe im SOP-Fluss explizit für Erw./Kind >12 Jahre angegeben.")
        else:
            handlung.append("ABCDE-Re-Evaluation")

        if nrs_abd_3 > abd_step3_nrs_threshold:
            if float(gewicht) > abd_fentanyl_weight_threshold:
                meds.append("Fentanyl i.v.: 0,05 mg Einmalgaben alle 4 Minuten, Maximaldosis 2 µg/kgKG")
                hinweise.append("BTM-Dokumentation beachten")
            else:
                hinweise.append(f"Fentanyl-Stufe laut SOP erst ab >{abd_fentanyl_weight_threshold:g} kg.")
        else:
            handlung.append("ABCDE-Re-Evaluation")

        handlung.append("Kliniktransport")

        hinweise.append(
            "Hinweis aus SOP-Grafik: Von Butylscopolamin im Rahmen der Nierenkolik wird in der aktuellen S2k-Leitlinie in der Fachliteratur abgeraten."
        )

        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: frühe notärztliche/klinische Rücksprache einplanen.")

        st.subheader("Berechnete SOP-Medikation")
        if meds:
            for i, med in enumerate(meds, start=1):
                st.write(f"{i}. {med}")
        else:
            st.write("Keine stufenspezifische medikamentöse Empfehlung bei aktueller NRS-Konstellation.")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        st.subheader("Zusätzliche Hinweise")
        for i, h in enumerate(hinweise, start=1):
            st.write(f"{i}. {h}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"NRS initial: {nrs_abd_1}",
                f"NRS nach Paracetamol: {nrs_abd_2}",
                f"NRS nach Butylscopolamin: {nrs_abd_3}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

    elif sop == "Starke Schmerzen":
        st.subheader("Klinische Konstellation")
        p1, p2, p3 = st.columns(3)
        with p1:
            nrs = st.number_input("NRS (0-10)", min_value=0, max_value=10, value=6, key="pain_nrs")
        with p2:
            abdominelle_schmerzen = st.selectbox("Abdominelle Schmerzen", ["Nein", "Ja"], key="pain_abdominal")
        with p3:
            nichttraum_brustschmerz = st.selectbox("Nicht-traumatischer Brustschmerz", ["Nein", "Ja"], key="pain_nontrauma_chest")

        q1, q2, q3 = st.columns(3)
        with q1:
            trauma_andere_ursache = st.selectbox("Trauma oder andere Ursache", ["Nein", "Ja"], key="pain_trauma_other")
        with q2:
            keine_deutliche_besserung = st.selectbox("Keine deutliche Besserung", ["Nein", "Ja"], key="pain_no_clear_improve")
        with q3:
            erweiterte_massnahmen = st.selectbox("Erweiterte Basismaßnahmen", ["Nein", "Ja"], key="pain_extended_measures")

        meds = []
        handlung = [
            "Basismaßnahmen durchführen",
            "Notarztruf prüfen",
        ]
        hinweise = []

        pain_min_nrs_threshold = float(sop_value("pain_min_nrs_threshold", 3.0))
        pain_advanced_nrs_threshold = float(sop_value("pain_advanced_nrs_threshold", 6.0))
        pain_extreme_nrs_threshold = float(sop_value("pain_extreme_nrs_threshold", 8.0))
        pain_midazolam_age_threshold = float(sop_value("pain_midazolam_age_threshold", 60.0))
        pain_weight_high_threshold = float(sop_value("pain_weight_high_threshold", 50.0))
        pain_weight_min_threshold = float(sop_value("pain_weight_min_threshold", 30.0))

        if nrs < pain_min_nrs_threshold:
            hinweise.append(f"SOP-Hinweis: Flussbild für starke Schmerzen ab NRS >= {pain_min_nrs_threshold:g}.")

        if abdominelle_schmerzen == "Ja":
            handlung.append("Verdacht abdominelle Schmerzen / Koliken: entsprechenden SOP-Pfad priorisieren")
            handlung.append("Kliniktransport")
        elif nichttraum_brustschmerz == "Ja":
            handlung.append("Nicht-traumatischer Brustschmerz: ACS-SOP priorisieren")
            handlung.append("Kliniktransport")
        elif trauma_andere_ursache == "Ja":
            if alter >= 12:
                if float(gewicht) <= 50:
                    paracetamol_mg = round(15.0 * float(gewicht), 0)
                    meds.append(f"Paracetamol {int(paracetamol_mg)} mg i.v. (15 mg/kgKG)")
                else:
                    meds.append("Paracetamol 1 g i.v.")
            else:
                hinweise.append("Paracetamol-Dosierung im Flussbild vorrangig für Erw./Kind >12 Jahre angegeben.")

            if nrs >= pain_advanced_nrs_threshold or erweiterte_massnahmen == "Ja":
                handlung.append("Erweiterte Basismaßnahmen")
                if alter > pain_midazolam_age_threshold:
                    meds.append(f"Midazolam i.v.: 1 mg (Patient > {pain_midazolam_age_threshold:g} Jahre)")
                elif float(gewicht) > pain_weight_high_threshold:
                    meds.append(f"Midazolam i.v.: 2 mg (Erw./Kind > {pain_weight_high_threshold:g} kg)")
                elif float(gewicht) > pain_weight_min_threshold:
                    meds.append(f"Midazolam i.v.: 1 mg (Kind > {pain_weight_min_threshold:g} kg)")

                if float(gewicht) > pain_weight_min_threshold:
                    esketamin_mg = round(0.125 * float(gewicht), 2)
                    meds.append(f"Esketamin i.v.: {esketamin_mg} mg (0,125 mg/kgKG), max. einmalige Repetition")
                    meds.append("ODER Fentanyl i.v.: 0,05 mg Einmalgaben alle 4 Minuten, Maximaldosis 2 µg/kgKG")
                    hinweise.append("BTM-Dokumentation beachten")

                if keine_deutliche_besserung == "Ja":
                    handlung.append("Notarztruf auslösen")
                else:
                    handlung.append("Ruhigstellung, Schienung, Verband")
            else:
                handlung.append("Ruhigstellung, Schienung, Verband")

            handlung.append("Kliniktransport")
        else:
            handlung.append("Ursache unklar: klinische Re-Evaluation und geeigneten SOP-Pfad priorisieren")
            handlung.append("Kliniktransport")

        if nrs > pain_extreme_nrs_threshold:
            hinweise.append(
                f"Bei unerträglichen Schmerzen (NRS > {pain_extreme_nrs_threshold:g}) zuerst Midazolam/Esketamin/Fentanyl und anschließend Paracetamol erwägen."
            )

        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: frühe notärztliche/klinische Rücksprache einplanen.")

        st.subheader("Berechnete SOP-Medikation")
        if meds:
            for i, med in enumerate(meds, start=1):
                st.write(f"{i}. {med}")
        else:
            st.write("Keine spezifische medikamentöse Empfehlung in diesem Entscheidungszweig.")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        if hinweise:
            st.subheader("Zusätzliche Hinweise")
            for i, h in enumerate(hinweise, start=1):
                st.write(f"{i}. {h}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"NRS: {nrs}",
                f"Trauma/andere Ursache: {trauma_andere_ursache}",
                f"Keine deutliche Besserung: {keine_deutliche_besserung}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

    elif sop == "Massive Übelkeit / Erbrechen":
        st.subheader("Klinische Konstellation")
        m1, m2, m3 = st.columns(3)
        with m1:
            stillzeit = st.selectbox("Stillzeit", ["Nein", "Ja"], key="nausea_lactation")
        with m2:
            dehydration = st.selectbox("Dehydratation", ["Nein", "Ja"], key="nausea_dehydration")
        with m3:
            c2_intox = st.selectbox("C2-Intoxikation", ["Nein", "Ja"], key="nausea_c2_intox")

        n1, n2 = st.columns(2)
        with n1:
            neuro_defizit = st.selectbox("Neurologische Defizite", ["Nein", "Ja"], key="nausea_neuro_def")
        with n2:
            krampfleiden_bekannt = st.selectbox("Bekanntes Krampfleiden", ["Nein", "Ja"], key="nausea_known_seizure")

        meds = []
        handlung = [
            "Basismaßnahmen durchführen",
            "Notarztruf prüfen",
        ]
        hinweise = []

        if schwanger == "Ja" or stillzeit == "Ja":
            handlung.append("Keine Gabe von Antiemetika")
            handlung.append("ABCDE-Re-Evaluation")
            handlung.append("Kliniktransport")
        elif dehydration == "Ja" or c2_intox == "Ja":
            handlung.append("ABCDE-Re-Evaluation")
            handlung.append("Kliniktransport")
            hinweise.append("Bei Dehydratation oder C2-Intoxikation in diesem SOP-Zweig keine Antiemetika-Gabe.")
        else:
            nausea_ondansetron_age_threshold = float(sop_value("nausea_ondansetron_age_threshold", 60.0))
            if alter > nausea_ondansetron_age_threshold or neuro_defizit == "Ja" or krampfleiden_bekannt == "Ja":
                meds.append("Ondansetron 4 mg i.v., einmalige Repetition möglich")
            else:
                meds.append("Dimenhydrinat 31 mg i.v. und 31 mg als Zusatz in die Infusion")
            handlung.append("Kliniktransport")

        if schwanger == "Unbekannt":
            hinweise.append("Schwangerschaftsstatus unklar: vor Antiemetika-Gabe engmaschig abklären.")

        st.subheader("Berechnete SOP-Medikation")
        if meds:
            for i, med in enumerate(meds, start=1):
                st.write(f"{i}. {med}")
        else:
            st.write("Keine medikamentöse Antiemese in diesem Entscheidungszweig.")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        if hinweise:
            st.subheader("Zusätzliche Hinweise")
            for i, h in enumerate(hinweise, start=1):
                st.write(f"{i}. {h}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"Schwangerschaft/Stillzeit: {schwanger}/{stillzeit}",
                f"Dehydratation: {dehydration}",
                f"C2-Intoxikation: {c2_intox}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

    elif sop == "Instabile Bradykardie":
        st.subheader("Klinische Konstellation")
        b1, b2, b3 = st.columns(3)
        with b1:
            hf = st.number_input("Herzfrequenz (HF/min)", min_value=20, max_value=220, value=45, key="brady_hf")
        with b2:
            instabil = st.selectbox("Instabilitätszeichen vorhanden", ["Nein", "Ja"], key="brady_instability")
        with b3:
            asystolie_gefahr = st.selectbox("Asystolie-Gefahr", ["Nein", "Ja"], key="brady_asystole_risk")

        c1, c2 = st.columns(2)
        with c1:
            hf_ansteigend = st.selectbox("HF nach Ersttherapie ansteigend", ["Ja", "Nein"], key="brady_hr_rising")
        with c2:
            gcs_unter_10 = st.selectbox("GCS < 10", ["Nein", "Ja"], key="brady_gcs_lt10")

        meds = []
        handlung = [
            "Basismaßnahmen durchführen",
            "Notarztruf prüfen",
        ]
        hinweise = [
            "Instabilitätszeichen: Schock, Bewusstseinsstörung, Synkope, Myokardischämie, schwere Herzinsuffizienz",
            "Asystolie-Gefahr prüfen: kürzliche Asystolie, AV-Block II Typ 2 (Mobitz), AV-Block III und breiter QRS-Komplex, ventrikuläre Pausen > 3 Sek.",
        ]

        brady_hf_threshold = float(sop_value("brady_hf_threshold", 60.0))
        if hf >= brady_hf_threshold:
            hinweise.append(f"SOP-Hinweis: Flussbild für instabile Bradykardie bei HF < {brady_hf_threshold:g}/min.")

        if instabil == "Nein":
            handlung.append("ABCDE-Re-Evaluation")
            handlung.append("Kliniktransport")
        else:
            if asystolie_gefahr == "Nein":
                meds.append("Atropin 0,5 mg i.v., bis max. 3 mg")
            else:
                meds.append("Adrenalinperfusor: 1 mg Adrenalin in 500 ml Infusion, initial >1 Tropfen/Sek.")
                hinweise.append("Orientierung Perfusor: 1 Tropfen/Sek. = 60 Tropfen/Min. = ca. 3 ml/Min. = ca. 6 µg/Min.")

            if hf_ansteigend == "Ja":
                handlung.append("ABCDE-Re-Evaluation")
                handlung.append("Kliniktransport")
            else:
                handlung.append("Notarztruf auslösen")
                if gcs_unter_10 == "Ja":
                    handlung.append("Transthorakalen Schrittmacher vorbereiten/anwenden")
                else:
                    handlung.append("ABCDE-Re-Evaluation")
                handlung.append("Kliniktransport")

        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: frühe notärztliche/klinische Rücksprache einplanen.")

        st.subheader("Berechnete SOP-Medikation")
        if meds:
            for i, med in enumerate(meds, start=1):
                st.write(f"{i}. {med}")
        else:
            st.write("Keine medikamentöse Bradykardie-Therapie in diesem Entscheidungszweig.")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        st.subheader("Zusätzliche Hinweise")
        for i, h in enumerate(hinweise, start=1):
            st.write(f"{i}. {h}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"HF: {hf}/min",
                f"Instabilitätszeichen: {instabil}",
                f"Asystolie-Gefahr: {asystolie_gefahr}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

    elif sop == "Instabile Tachykardie":
        st.subheader("Klinische Konstellation")
        t1, t2, t3 = st.columns(3)
        with t1:
            hf_tachy = st.number_input("Herzfrequenz (HF/min)", min_value=20, max_value=300, value=160, key="tachy_hf")
        with t2:
            instabil_tachy = st.selectbox("Instabilitätszeichen vorhanden", ["Nein", "Ja"], key="tachy_instability")
        with t3:
            bewusstlos_tachy = st.selectbox("Bewusstlosigkeit", ["Nein", "Ja"], key="tachy_unconscious")

        meds = []
        handlung = [
            "Basismaßnahmen durchführen",
            "Reanimationsbereitschaft herstellen",
            "Notarztruf prüfen",
        ]
        hinweise = [
            "Instabilitätszeichen: Schock, Bewusstseinsstörung, Synkope, Myokardischämie, schwere Herzinsuffizienz",
        ]

        tachy_hf_warning_threshold = float(sop_value("tachy_hf_warning_threshold", 100.0))
        if hf_tachy < tachy_hf_warning_threshold:
            hinweise.append("SOP-Hinweis: Flussbild für instabile Tachykardie ist typischerweise bei deutlich erhöhter HF relevant.")

        if instabil_tachy == "Nein":
            handlung.append("ABCDE-Re-Evaluation")
            handlung.append("Klinik / Ende")
        else:
            if bewusstlos_tachy == "Ja":
                handlung.append("Notarztruf auslösen")
                meds.append("Erw.: Kardioversion")
                handlung.append("ABCDE-Re-Evaluation")
                handlung.append("Klinik / Ende")
            else:
                handlung.append("ABCDE-Re-Evaluation")
                handlung.append("Klinik / Ende")

        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: frühe notärztliche/klinische Rücksprache einplanen.")

        st.subheader("Berechnete SOP-Medikation")
        if meds:
            for i, med in enumerate(meds, start=1):
                st.write(f"{i}. {med}")
        else:
            st.write("Keine medikamentöse Empfehlung in diesem Entscheidungszweig.")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        st.subheader("Zusätzliche Hinweise")
        for i, h in enumerate(hinweise, start=1):
            st.write(f"{i}. {h}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"HF: {hf_tachy}/min",
                f"Instabilitätszeichen: {instabil_tachy}",
                f"Bewusstlosigkeit: {bewusstlos_tachy}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

    elif sop == "Intoxikation: Benzodiazepine":
        st.subheader("Klinische Konstellation")
        i1, i2, i3 = st.columns(3)
        with i1:
            somnolenz = st.selectbox("Somnolenz", ["Nein", "Ja"], key="benzo_somnolence")
        with i2:
            atemdepression = st.selectbox("Atemdepression", ["Nein", "Ja"], key="benzo_resp_depression")
        with i3:
            hypoxie = st.selectbox("Hypoxie", ["Nein", "Ja"], key="benzo_hypoxia")

        j1, j2 = st.columns(2)
        with j1:
            vital_bedroht = st.selectbox("Vital bedrohter Patient", ["Nein", "Ja"], key="benzo_vital_threat")
        with j2:
            keine_reaktion = st.selectbox("Keine ausreichende Reaktion", ["Nein", "Ja"], key="benzo_no_response")

        meds = []
        handlung = [
            "Basismaßnahmen durchführen",
            "Notarztruf prüfen",
        ]
        hinweise = [
            "Verdacht: Atemdepression, Somnolenz, Midazolam-Überdosierung bei Analgosedierung, Schlafmittelmissbrauch",
            "Ziel: ausreichende Spontanatmung",
            "Cave: Entzug mit Krampfanfall möglich",
        ]

        symptome_vorhanden = (somnolenz == "Ja") or (atemdepression == "Ja") or (hypoxie == "Ja")

        if not symptome_vorhanden:
            handlung.append("Weiteres Vorgehen nach Befund, engmaschiges Monitoring")
            handlung.append("Klinik / Ende")
        else:
            handlung.append("Kopf überstrecken, Esmarch-Handgriff, Guedel-/Wendel-Tubus, Seitenlage")

            if vital_bedroht == "Ja":
                benzo_flumazenil_initial_mg = float(sop_value("benzo_flumazenil_initial_mg", 0.5))
                meds.append(f"Flumazenil titriert, initial {benzo_flumazenil_initial_mg:g} mg i.v.")
                if keine_reaktion == "Ja":
                    handlung.append("Atemwegssicherung")
                else:
                    handlung.append("Weiteres Vorgehen nach Befund, engmaschiges Monitoring")
            else:
                handlung.append("Weiteres Vorgehen nach Befund, engmaschiges Monitoring")

            handlung.append("Klinik / Ende")

        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: frühe notärztliche/klinische Rücksprache einplanen.")

        st.subheader("Berechnete SOP-Medikation")
        if meds:
            for i, med in enumerate(meds, start=1):
                st.write(f"{i}. {med}")
        else:
            st.write("Keine medikamentöse Antidot-Therapie in diesem Entscheidungszweig.")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        st.subheader("Zusätzliche Hinweise")
        for i, h in enumerate(hinweise, start=1):
            st.write(f"{i}. {h}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"Somnolenz/Atemdepression/Hypoxie: {somnolenz}/{atemdepression}/{hypoxie}",
                f"Vital bedroht: {vital_bedroht}",
                f"Keine Reaktion: {keine_reaktion}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

    elif sop == "Intoxikation: Opiate / Opioide":
        st.subheader("Klinische Konstellation")
        o1, o2, o3 = st.columns(3)
        with o1:
            somnolenz = st.selectbox("Somnolenz", ["Nein", "Ja"], key="opioid_somnolence")
        with o2:
            atemdepression = st.selectbox("Atemdepression", ["Nein", "Ja"], key="opioid_resp_depression")
        with o3:
            hypoxie = st.selectbox("Hypoxie", ["Nein", "Ja"], key="opioid_hypoxia")

        p1, p2 = st.columns(2)
        with p1:
            vital_bedroht = st.selectbox("Vital bedrohter Patient", ["Nein", "Ja"], key="opioid_vital_threat")
        with p2:
            keine_reaktion = st.selectbox("Keine ausreichende Reaktion", ["Nein", "Ja"], key="opioid_no_response")

        meds = []
        handlung = [
            "Basismaßnahmen durchführen",
            "Notarztruf prüfen",
        ]
        hinweise = [
            "Verdacht: Atemdepression, Somnolenz, Einstichstellen, Opiatpflaster",
            "Ziel: ausreichende Spontanatmung",
            "CAVE: Entzug möglich",
        ]

        symptome_vorhanden = (somnolenz == "Ja") or (atemdepression == "Ja") or (hypoxie == "Ja")

        if not symptome_vorhanden:
            handlung.append("ABCDE-Re-Evaluation")
            handlung.append("Klinik / Ende")
        else:
            handlung.append("Kopf überstrecken, Esmarch-Handgriff, Guedel-/Wendel-Tubus, Seitenlage")

            if vital_bedroht == "Ja":
                opioid_naloxon_initial_mg = float(sop_value("opioid_naloxon_initial_mg", 0.4))
                meds.append(f"Naloxon titriert {opioid_naloxon_initial_mg:g} mg i.v. (auf 10 ml aufziehen)")
                if keine_reaktion == "Ja":
                    handlung.append("Notarztruf auslösen")
                else:
                    handlung.append("ABCDE-Re-Evaluation")
            else:
                handlung.append("ABCDE-Re-Evaluation")

            handlung.append("Klinik / Ende")

        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: frühe notärztliche/klinische Rücksprache einplanen.")

        st.subheader("Berechnete SOP-Medikation")
        if meds:
            for i, med in enumerate(meds, start=1):
                st.write(f"{i}. {med}")
        else:
            st.write("Keine medikamentöse Antidot-Therapie in diesem Entscheidungszweig.")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        st.subheader("Zusätzliche Hinweise")
        for i, h in enumerate(hinweise, start=1):
            st.write(f"{i}. {h}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"Somnolenz/Atemdepression/Hypoxie: {somnolenz}/{atemdepression}/{hypoxie}",
                f"Vital bedroht: {vital_bedroht}",
                f"Keine Reaktion: {keine_reaktion}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

    elif sop == "Lungenarterienembolie":
        st.subheader("Klinische Konstellation")

        w1, w2, w3 = st.columns(3)
        with w1:
            wells_thrombose_anamnese = st.selectbox(
                "Thrombose/LE in Anamnese", ["Nein", "Ja"], key="pe_wells_history"
            )
            wells_op_immobil = st.selectbox(
                "Frische OP oder Immobilisation", ["Nein", "Ja"], key="pe_wells_operation"
            )
            wells_tumor = st.selectbox("Tumorerkrankung", ["Nein", "Ja"], key="pe_wells_tumor")
        with w2:
            wells_haemoptyse = st.selectbox("Hämoptyse", ["Nein", "Ja"], key="pe_wells_hemoptysis")
            wells_puls_hoch = st.selectbox("Herzfrequenz > 100/min", ["Nein", "Ja"], key="pe_wells_hr")
            wells_dvt = st.selectbox("Zeichen einer tiefen Venenthrombose", ["Nein", "Ja"], key="pe_wells_dvt")
        with w3:
            wells_alternative_unwahrs = st.selectbox(
                "Alternative Diagnose unwahrscheinlicher", ["Nein", "Ja"], key="pe_wells_alt_diag"
            )

        s1, s2, s3 = st.columns(3)
        with s1:
            spesi_alter_80 = st.selectbox("Alter > 80 Jahre", ["Nein", "Ja"], key="pe_spesi_age")
            spesi_tumor = st.selectbox("Tumorerkrankung (sPESI)", ["Nein", "Ja"], key="pe_spesi_tumor")
        with s2:
            spesi_hf_100 = st.selectbox("Herzfrequenz >= 100/min", ["Nein", "Ja"], key="pe_spesi_hr")
            spesi_rr_100 = st.selectbox("RR syst. < 100 mmHg", ["Nein", "Ja"], key="pe_spesi_sbp")
        with s3:
            spesi_spo2_90 = st.selectbox("SpO2 < 90%", ["Nein", "Ja"], key="pe_spesi_spo2")
            spesi_chronic = st.selectbox(
                "Chron. Herzinsuff. und/oder Lungenerkrankung", ["Nein", "Ja"], key="pe_spesi_chronic"
            )

        wells_score = 0.0
        wells_score += 1.5 if wells_thrombose_anamnese == "Ja" else 0.0
        wells_score += 1.5 if wells_op_immobil == "Ja" else 0.0
        wells_score += 1.0 if wells_tumor == "Ja" else 0.0
        wells_score += 1.0 if wells_haemoptyse == "Ja" else 0.0
        wells_score += 1.5 if wells_puls_hoch == "Ja" else 0.0
        wells_score += 3.0 if wells_dvt == "Ja" else 0.0
        wells_score += 3.0 if wells_alternative_unwahrs == "Ja" else 0.0

        spesi_score = 0
        spesi_score += 1 if spesi_alter_80 == "Ja" else 0
        spesi_score += 1 if spesi_tumor == "Ja" else 0
        spesi_score += 1 if spesi_hf_100 == "Ja" else 0
        spesi_score += 1 if spesi_rr_100 == "Ja" else 0
        spesi_score += 1 if spesi_spo2_90 == "Ja" else 0
        spesi_score += 1 if spesi_chronic == "Ja" else 0

        meds = []
        handlung = [
            "Basismaßnahmen durchführen",
            "Notarztruf prüfen",
        ]
        hinweise = [
            f"Wells-Score berechnet: {wells_score:.1f} Punkte",
            f"sPESI-Score berechnet: {spesi_score} Punkte",
        ]

        wells_threshold = float(sop_value("lae_wells_threshold", 5.0))
        spesi_threshold = float(sop_value("lae_spesi_threshold", 1.0))

        if wells_score >= wells_threshold:
            if spesi_score >= spesi_threshold:
                meds.append("Heparin 5000 I.E. i.v.")
            else:
                hinweise.append(f"sPESI < {spesi_threshold:g}: in diesem SOP-Pfad keine Heparin-Gabe.")
        else:
            hinweise.append(f"Wells-Score < {wells_threshold:g}: in diesem SOP-Pfad keine Heparin-Gabe.")

        handlung.append("ABCDE-Re-Evaluation")
        handlung.append("Klinik / Ende")

        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: frühe notärztliche/klinische Rücksprache einplanen.")

        st.subheader("Berechnete SOP-Medikation")
        if meds:
            for i, med in enumerate(meds, start=1):
                st.write(f"{i}. {med}")
        else:
            st.write("Keine medikamentöse Empfehlung in diesem Entscheidungszweig.")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        st.subheader("Zusätzliche Hinweise")
        for i, h in enumerate(hinweise, start=1):
            st.write(f"{i}. {h}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"Wells-Score: {wells_score:.1f}",
                f"sPESI-Score: {spesi_score}",
                f"Heparin empfohlen: {'Ja' if len(meds) > 0 else 'Nein'}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

    else:
        st.subheader("Klinische Konstellation")

        a1, a2, a3 = st.columns(3)
        pao_pain_threshold = float(sop_value("pao_pain_threshold", 3.0))

        with a1:
            schmerzen_ge3 = st.selectbox(f"Schmerzen NRS >= {pao_pain_threshold:g}", ["Nein", "Ja"], key="pao_pain_ge3")
        with a2:
            instabilitaetszeichen = st.selectbox("Instabilitätszeichen (Schock/Prostration)", ["Nein", "Ja"], key="pao_instability")
        with a3:
            pulslosigkeit = st.selectbox("Pulselessness (Pulslosigkeit)", ["Nein", "Ja"], key="pao_pulseless")

        s1, s2, s3 = st.columns(3)
        with s1:
            pallor = st.selectbox("Pallor (Blässe)", ["Nein", "Ja"], key="pao_pallor")
        with s2:
            paresthesia = st.selectbox("Paresthesia", ["Nein", "Ja"], key="pao_paresthesia")
        with s3:
            paralysis = st.selectbox("Paralysis", ["Nein", "Ja"], key="pao_paralysis")

        risikofaktoren = st.multiselect(
            "Risikofaktoren",
            [
                "Vorhofflimmern",
                "kürzlicher Myokardinfarkt",
                "andere kardiale Morbiditäten",
                "Atherosklerose der Aorta",
                "prothetischer Aortenersatz",
                "Aorten-/Poplitealaneurysmen",
                "Zustand nach Revaskularisation",
                "arterielles Trauma (Unfall, iatrogen)",
                "Hyperkoagulabilität",
                "tiefe Venenthrombose bei persistierendem Foramen ovale",
            ],
            key="pao_risk_factors",
        )

        meds = ["Heparin 5.000 I.E. i.v."]
        handlung = [
            "Basismaßnahmen durchführen",
            "Notarztruf prüfen",
        ]
        hinweise = [
            "Leitsymptome der 6 P beachten: Pain, Pallor, Pulselessness, Paresthesia, Paralysis, Prostration",
        ]

        if schmerzen_ge3 == "Ja":
            handlung.append(f"Starke Schmerzen (NRS >= {pao_pain_threshold:g}): Analgesiepfad gemäß SOP Starke Schmerzen berücksichtigen")
        else:
            handlung.append("Keine starken Schmerzen (NRS < 3)")

        handlung.append("Heparin 5.000 I.E. i.v. verabreichen")
        handlung.append("Immobilisation und Tieflagerung der betroffenen Extremität")
        handlung.append("Klinik / Ende")

        if instabilitaetszeichen == "Ja":
            hinweise.append("Instabilitätszeichen vorhanden: notärztliche Eskalation priorisieren.")
        if pulslosigkeit == "Nein":
            hinweise.append("Pulslosigkeit nicht gesichert: Differenzialdiagnosen und Verlauf engmaschig prüfen.")
        if len(risikofaktoren) > 0:
            hinweise.append(f"Risikofaktoren markiert: {len(risikofaktoren)}")
        if schwanger == "Ja":
            hinweise.append("Schwangerschaft: frühe notärztliche/klinische Rücksprache einplanen.")

        st.subheader("Berechnete SOP-Medikation")
        for i, med in enumerate(meds, start=1):
            st.write(f"{i}. {med}")

        st.subheader("SOP-Handlungshilfe")
        for i, step in enumerate(handlung, start=1):
            st.write(f"{i}. {step}")

        st.subheader("Zusätzliche Hinweise")
        for i, h in enumerate(hinweise, start=1):
            st.write(f"{i}. {h}")

        render_live_summary(
            "Live-Zusammenfassung Medikamentenrechner",
            [
                f"SOP: {sop}",
                f"Schmerzen NRS >= 3: {schmerzen_ge3}",
                f"Pulslosigkeit: {pulslosigkeit}",
                f"Risikofaktoren: {len(risikofaktoren)}",
                f"Empfohlene Medikation: {len(meds)} Position(en)",
            ],
        )

# --------------------------------------------------
# UEBERGABE
# --------------------------------------------------

elif seite == "🗣️ Übergabe":

    st.header("🗣️ Übergabe (MIST / ISBAR)")

    mist_text, isbar_text = build_handover_text(patient)

    missing_for_handover = collect_missing_documentation(patient)
    if missing_for_handover:
        st.warning(
            f"{len(missing_for_handover)} Kernangaben fehlen noch. Die Übergabe wird trotzdem aus allen "
            "vorhandenen Daten erzeugt."
        )

    render_colored_handover("MIST – farbcodierte Übergabe", mist_text)
    render_colored_handover("ISBAR – farbcodierte Übergabe", isbar_text)

    with st.expander("Rohtext zum Kopieren anzeigen", expanded=False):
        st.markdown("**MIST**")
        st.code(mist_text, language=None)
        st.markdown("**ISBAR**")
        st.code(isbar_text, language=None)

    render_live_summary(
        "Live-Zusammenfassung Übergabe",
        [
            "MIST generiert",
            "ISBAR generiert",
            f"Maßnahmen: {len(patient.get('massnahmen', {}).get('timeline', []))}",
            f"Medikationen: {len(patient.get('massnahmen', {}).get('medikation', []))}",
        ],
    )

# --------------------------------------------------
# PROTOKOLL
# --------------------------------------------------

elif seite == "📄 Protokoll":

    st.header("📄 Fertiges Protokoll")

    missing_documentation = collect_missing_documentation(patient)
    if missing_documentation:
        st.warning(
            f"Noch {len(missing_documentation)} Angaben offen. Das Protokoll kann trotzdem erstellt werden; "
            "fehlende Werte werden einfach nicht ausgegeben."
        )
        grouped_missing = {}
        for item in missing_documentation:
            grouped_missing.setdefault(item["section"], []).append(item["label"])
        with st.expander("Offene Angaben anzeigen", expanded=True):
            for section, labels in grouped_missing.items():
                st.markdown(f"**{section}:** " + " · ".join(labels))
    else:
        st.success("Alle vorgesehenen Kernangaben sind dokumentiert.")

    protocol_done_col, protocol_reset_col = st.columns(2)
    with protocol_done_col:
        if st.button("✓ Protokoll-Schritt abschließen", key="complete_protocol_step", use_container_width=True):
            st.session_state["workflow_manual_completion"]["📄 Protokoll"] = True
            st.success("Protokoll-Schritt als abgeschlossen markiert.")
    with protocol_reset_col:
        if st.button("↺ Abschluss zurücksetzen", key="reset_protocol_step", use_container_width=True):
            st.session_state["workflow_manual_completion"]["📄 Protokoll"] = False
            st.session_state["protocol_generated"] = False
            st.info("Abschlussmarkierung für Protokoll entfernt.")

    st.write(
        "Nach Klick auf **Protokoll generieren** wird automatisch "
        "ein RD-Protokoll aus den eingegebenen Daten erstellt."
    )

    st.divider()

    if st.button(
        "🚑 Protokoll generieren",
        use_container_width=True,
        type="primary"
    ):

        protocol = generate_protocol()

        if protocol.strip() == "":

            st.warning("Es wurden noch keine Daten eingegeben.")

        else:

            st.session_state["protocol_generated"] = True
            st.session_state["workflow_manual_completion"]["📄 Protokoll"] = True
            st.session_state["generated_protocol_text"] = protocol

            st.success("Protokoll erstellt.")

    if st.session_state.get("generated_protocol_text"):
        st.text_area(
            "RD-Protokoll",
            st.session_state["generated_protocol_text"],
            height=600
        )

        st.download_button(
            "💾 Protokoll als TXT herunterladen",
            st.session_state["generated_protocol_text"],
            file_name="RD_Protokoll.txt",
            mime="text/plain"
        )

        escaped_protocol = json.dumps(st.session_state["generated_protocol_text"])
        components.html(
            f"""
            <div style=\"margin-top:10px;\">
                <button id=\"copy-protocol-btn\" style=\"
                    width:100%;
                    padding:12px 16px;
                    border-radius:10px;
                    border:none;
                    background:linear-gradient(135deg, #4e72ff 0%, #5ac8ff 100%);
                    color:#fff;
                    font-weight:700;
                    cursor:pointer;
                \">📋 Protokoll kopieren</button>
                <div id=\"copy-status\" style=\"margin-top:8px; color:#b7d7ff; font-size:0.92rem;\"></div>
            </div>
            <script>
            const text = {escaped_protocol};
            const btn = document.getElementById('copy-protocol-btn');
            const status = document.getElementById('copy-status');
            btn.addEventListener('click', async () => {{
                try {{
                    await navigator.clipboard.writeText(text);
                    status.textContent = 'Protokoll wurde in die Zwischenablage kopiert.';
                }} catch (err) {{
                    status.textContent = 'Kopieren fehlgeschlagen. Bitte manuell markieren und kopieren.';
                }}
            }});
            </script>
            """,
            height=95,
        )

if seite != "🛠️ Admin" and current_workflow_index is not None:
    with st.container(key="tablet_bottom_nav"):
        nav_prev_col, nav_info_col, nav_next_col = st.columns([1.2, 2.6, 1.2])
        previous_step = WORKFLOW_STEPS[current_workflow_index - 1] if current_workflow_index > 0 else None
        next_step = WORKFLOW_STEPS[current_workflow_index + 1] if current_workflow_index < workflow_total - 1 else None

        with nav_prev_col:
            if previous_step:
                if st.button(f"← {previous_step['label']}", key="workflow_prev_btn", use_container_width=True):
                    st.session_state["seite"] = previous_step["page"]
                    st.rerun()

        with nav_info_col:
            current_done = workflow_completion.get(seite, False)
            missing_before_protocol = collect_missing_documentation(patient) if next_step and next_step["page"] == "📄 Protokoll" else []
            if missing_before_protocol:
                nav_status = f"{len(missing_before_protocol)} Angaben offen · Weiter trotzdem möglich"
                nav_status_class = ""
            elif current_done:
                nav_status = "✓ Schritt vollständig"
                nav_status_class = "is-done"
            else:
                nav_status = workflow_missing_hint(seite, patient) or "Schritt prüfen und fortfahren"
                nav_status_class = ""
            st.markdown(
                f'<div class="workflow-nav-status {nav_status_class}">{html.escape(nav_status)}</div>',
                unsafe_allow_html=True,
            )

        with nav_next_col:
            if next_step:
                if st.button(f"{next_step['label']} →", key="workflow_next_btn", use_container_width=True, type="primary"):
                    if next_step["page"] == "📄 Protokoll":
                        automatic_protocol = generate_protocol()
                        if automatic_protocol.strip():
                            st.session_state["generated_protocol_text"] = automatic_protocol
                            st.session_state["protocol_generated"] = True
                            st.session_state["workflow_manual_completion"]["📄 Protokoll"] = True
                    st.session_state["seite"] = next_step["page"]
                    st.rerun()
