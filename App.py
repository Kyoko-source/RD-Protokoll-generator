import streamlit as st
import streamlit.components.v1 as components
from io import BytesIO
from fpdf import FPDF
from datetime import datetime
import json


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


def generate_protocol():

    protocol = ""
    patient = st.session_state.get("patient", {})

    # Hinweis: Keine personenbezogenen Metadaten werden ausgegeben (Datenschutz)

    v = patient.get("vitalwerte", {})
    x = patient.get("xabcde", {})
    s = patient.get("samplers", {})
    o = patient.get("opqrst", {})
    m = patient.get("massnahmen", {})

    # Narrative Einleitung (anonym, nur nicht-identifizierende Informationen)
    try:
        intro = "PATIENTENSITUATION:\n"
        intro += "─" * 50 + "\n"
        
        sex = v.get('geschlecht')
        age = v.get('alter')
        found = v.get('auffindesituation')
        avpu = x.get('avpu')
        ereignis = s.get('ereignis')
        
        intro_desc = "Patient"
        
        if sex:
            intro_desc += f" ({sex})"
        if age and int(age) > 0:
            intro_desc += f", {int(age)} Jahre alt"
        
        if found:
            intro_desc += f"\nAuffindesituation: {found}"

        # Bewusstseinszustand aus AVPU
        if avpu and avpu != "Keine Angabe":
            intro_desc += "\nBewusstseinszustand: "
            if avpu == 'A':
                intro_desc += "Wach, vollständig ansprechbar und orientiert"
            elif avpu == 'V':
                intro_desc += "Verbal ansprechbar"
            elif avpu == 'P':
                intro_desc += "Nur auf Schmerzreize ansprechbar"
            elif avpu == 'U':
                intro_desc += "Nicht ansprechbar (bewusstlos)"

        if ereignis:
            intro_desc += f"\n\nEinsatzmeldung: {ereignis}"

        intro += intro_desc + "\n\n"
        protocol += intro
    except Exception:
        pass

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
        b_section += f"  Atemfrequenz: {af_cat}\n"
    
    # SpO2 (immer hinzufügen, wenn vorhanden)
    if spo2 and spo2 != 0:
        if not b_section:
            b_section = f"B — ATMUNG:\n"
        s_cat, s_val = categorize_spo2(spo2)
        b_section += f"  Sauerstoffsättigung: {s_cat}\n"
    
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
        c_section += f"  Blutdruck: {rr_cat}\n"
    
    # Pulsfrequenz (immer hinzufügen, wenn vorhanden)
    if puls and puls != 0:
        if not c_section:
            c_section = f"C — ZIRKULATION (Kreislauf):\n"
        p_cat, p_val = categorize_puls(puls)
        c_section += f"  Pulsfrequenz: {p_cat}\n"
    
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
        d_section += f"  Glasgow Coma Scale: {g_cat}\n"
    
    # Blutzucker (immer hinzufügen, wenn vorhanden)
    if bz and bz != 0:
        if not d_section:
            d_section = f"D — DISABILITY (Neurologischer Status):\n"
        bz_cat, bz_val = categorize_bz(bz)
        d_section += f"  Blutzucker: {bz_cat}\n"
    
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
        e_section += f"  Körpertemperatur: {t_cat}\n"
    
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

    # Klinischer Verlauf als Fließtext
    try:
        narrative = []
        if s.get("symptome"):
            narrative.append(f"Leitsymptomatisch zeigte sich {s.get('symptome')}. ")
        if x.get("atemweg") and x.get("atemweg") != "Keine Angabe":
            narrative.append(f"Der Atemweg war {x.get('atemweg').lower()}. ")
        if x.get("atmung") and x.get("atmung") != "Keine Angabe":
            narrative.append(f"Die Atmung wurde als {x.get('atmung').lower()} eingeschätzt. ")
        if x.get("haut") and x.get("haut") != "Keine Angabe":
            narrative.append(f"Kreislaufbezogen zeigte sich die Haut {x.get('haut').lower()}. ")
        if x.get("avpu") and x.get("avpu") != "Keine Angabe":
            narrative.append(f"Neurologisch ergab sich ein AVPU-Status {x.get('avpu')}. ")
        if o.get("nrs") and int(o.get("nrs", 0)) > 0:
            narrative.append(f"Die Schmerzintensität wurde mit NRS {o.get('nrs')}/10 angegeben. ")
        if narrative:
            protocol += "KLINISCHER VERLAUF (NARRATIV)\n"
            protocol += "=" * 50 + "\n"
            protocol += "".join(narrative).strip() + "\n\n"
    except Exception:
        pass

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

st.title("🚑 RD-Protokoll Generator")
st.caption("Dokumentationshilfe für den Rettungsdienst")

# --- Custom styling (Dark Mode, centered navigation) -----------------
st.markdown(
        """
        <style>
    :root { --bg:#070f1f; --panel:#0f1b31; --panel-2:#1a2c4a; --muted:#9aa9c2; --accent:#57a4ff; --accent-2:#ff7d66; --accent-3:#35d8a6; --text:#eef5ff; --line:rgba(255,255,255,0.09); }
    html, body, [class*="css"] { background: radial-gradient(circle at 18% 0%, rgba(87,164,255,0.22), transparent 34%), radial-gradient(circle at 92% 12%, rgba(255,125,102,0.18), transparent 34%), linear-gradient(135deg, var(--bg) 0%, #081327 100%) !important; color: var(--text); }
    .header { position: relative; overflow:hidden; background: linear-gradient(125deg, rgba(68,132,240,0.95) 0%, rgba(98,126,217,0.92) 34%, rgba(209,117,137,0.9) 100%); color: white; padding: 22px 26px; border-radius: 20px; box-shadow: 0 18px 44px rgba(3,10,26,0.42); border: 1px solid rgba(255,255,255,0.2); }
    .header::before { content:""; position:absolute; inset:-20% auto auto -10%; width:220px; height:220px; background: radial-gradient(circle, rgba(255,255,255,0.25), transparent 70%); pointer-events:none; }
    .header-title { font-size:1.6rem; font-weight:900; letter-spacing:0.01em; }
    .header-sub { opacity:0.92; color:rgba(255,255,255,0.92); font-size:1.01rem; font-weight:600; }
        [data-testid="column"]:nth-child(n+2):nth-child(-n+10) { padding: 0 2px; }
    [data-testid="column"]:nth-child(n+2):nth-child(-n+10) > [data-testid="stButton"] > button { width:100%; padding: 13px 18px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.13); background: linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.015)); color: var(--text); font-weight: 800; margin:0; box-shadow: 0 12px 24px rgba(2,8,24,0.28); transition: all 0.22s ease; }
    [data-testid="column"]:nth-child(n+2):nth-child(-n+10) > [data-testid="stButton"] > button:hover { border-color: rgba(255,255,255,0.28); transform: translateY(-2px); }
        [data-testid="column"]:nth-child(n+2):nth-child(-n+10) > [data-testid="stButton"] > button:focus { outline:none; }
    [data-testid="column"]:nth-child(n+2):nth-child(-n+10) > [data-testid="stButton"] > button[kind='primary'] { color:#fff; border:none; box-shadow: 0 15px 30px rgba(64,124,255,0.3); }
        input, textarea, select { background:#0c1628 !important; color:var(--text) !important; border:1px solid rgba(255,255,255,0.08) !important; border-radius:12px !important; padding:10px 12px !important; font-size:0.95rem !important; }
        input:focus, textarea:focus, select:focus { border-color:var(--accent) !important; box-shadow: 0 0 0 3px rgba(75,140,255,0.18) !important; }
        [data-testid="stSelectbox"] { margin: 10px 0; }
        [data-testid="stRadio"] > label { padding:8px 10px; border-radius:10px; cursor:pointer; transition: all 0.2s ease; }
        [data-testid="stRadio"] > label:hover { background: rgba(255,255,255,0.03); }
        [data-testid="stSlider"] > div > div > div { border-radius:10px; }
        [data-testid="stCheckbox"] > label { cursor:pointer; }
        [data-testid="stNumberInput"] { margin: 10px 0; }
        [data-testid="stTextArea"] { margin: 10px 0; }
        h3 { color:#8dc7ff; margin-top:20px; margin-bottom:10px; border-bottom:1px solid rgba(141,199,255,0.2); padding-bottom:8px; }
        hr { border-color: rgba(255,255,255,0.06) !important; margin: 22px 0; }
        section[data-testid='stSidebar']{ display:none; }
        main .block-container { padding-top: 12px; padding-left: 80px; padding-right:80px }
        </style>
        """,
        unsafe_allow_html=True,
)

st.markdown("""<div class='header'><div style='display:flex; align-items:center; gap:14px; flex-wrap:wrap;'><div class='header-title'>🚑 RD-Protokoll Generator</div><div class='header-sub'>Schnell. Klar. Einsatzbereit.</div></div></div>""", unsafe_allow_html=True)

# --------------------------------------------------
# Patientenobjekt anlegen
# --------------------------------------------------

if "patient" not in st.session_state:

    st.session_state.patient = {

        "vitalwerte": {},

        "xabcde": {},

        "samplers": {},

        "opqrst": {},

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
patient.setdefault("massnahmen", {"timeline": [], "medikation": []})
patient["massnahmen"].setdefault("timeline", [])
patient["massnahmen"].setdefault("medikation", [])
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


def _is_valid_value(value):
    return value not in [None, "", "Keine Angabe", 0]


def render_live_summary(title, lines):
    valid_lines = [line for line in lines if line]
    if valid_lines:
        st.caption(f"{title}: " + " | ".join(valid_lines[:5]))
    else:
        st.caption(f"{title}: Noch keine relevanten Angaben")


def build_handover_text(patient_data):
    v = patient_data.get("vitalwerte", {})
    x = patient_data.get("xabcde", {})
    s = patient_data.get("samplers", {})
    o = patient_data.get("opqrst", {})
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
    isbar.append(f"B: {s.get('vorgeschichte') or 'Keine relevante Vorgeschichte dokumentiert'}")
    assess = x.get("atmung") or x.get("atemweg") or x.get("avpu") or "Keine strukturierte Einschätzung dokumentiert"
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
# --------------------------------------------------
# Navigation
# --------------------------------------------------

# Centered navigation in main area
if 'seite' not in st.session_state:
    st.session_state['seite'] = "❤️ Vitalwerte"

if 'xabcde_selected' not in st.session_state:
    st.session_state['xabcde_selected'] = "A"

nav_options = [
    "❤️ Vitalwerte",
    "🩺 xABCDE",
    "📋 SAMPLERS",
    "🔥 OPQRST",
    "⏱️ Maßnahmen",
    "🔎 Verdacht",
    "💉 Medikamentenrechner",
    "🗣️ Übergabe",
    "📄 Protokoll"
]

# Navigation mit Streamlit-Buttons und Session-State
nav_container = st.container()
with nav_container:
    cols_nav = st.columns([1] + [1]*9 + [1])
    for i, opt in enumerate(nav_options):
        with cols_nav[i+1]:
            nav_type = "primary" if st.session_state['seite'] == opt else "secondary"
            if st.button(opt, key=f"nav_{i}", use_container_width=True, type=nav_type):
                st.session_state['seite'] = opt
                st.rerun()

seite = st.session_state['seite']

active_nav_palette = {
    "❤️ Vitalwerte": ("#ff5b86", "#ff9a5a"),
    "🩺 xABCDE": ("#4b8cff", "#35d8a6"),
    "📋 SAMPLERS": ("#5f89ff", "#7a67f8"),
    "🔥 OPQRST": ("#ff8a4d", "#ff4f7b"),
    "⏱️ Maßnahmen": ("#2ac4df", "#3de99a"),
    "🔎 Verdacht": ("#f3b33d", "#ff6f4a"),
    "💉 Medikamentenrechner": ("#22b8cf", "#4c6fff"),
    "🗣️ Übergabe": ("#7d6bff", "#5bbdff"),
    "📄 Protokoll": ("#4e72ff", "#5ac8ff"),
}
start_color, end_color = active_nav_palette.get(seite, ("#4b8cff", "#ff7a7a"))
st.markdown(
    f"""
    <style>
    [data-testid="column"]:nth-child(n+2):nth-child(-n+10) > [data-testid="stButton"] > button[kind='primary'] {{
        background: linear-gradient(135deg, {start_color} 0%, {end_color} 100%);
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------
# VITALWERTE
# --------------------------------------------------

if seite == "❤️ Vitalwerte":

    st.header("❤️ Vitalwerte & Demographie")
    
    # --- GANZ OBEN: Demographie ---
    st.subheader("👤 Patientendemographie")
    d1, d2, d3 = st.columns(3)
    
    with d1:
        patient["vitalwerte"]["geschlecht"] = st.selectbox(
            "Geschlecht",
            ["", "männlich", "weiblich", "divers", "Unbekannt"],
            key="geschlecht"
        )
    
    with d2:
        patient["vitalwerte"]["alter"] = st.number_input(
            "Alter (Jahre)",
            min_value=0,
            max_value=130,
            value=0,
            key="alter"
        )
    
    with d3:
        patient["vitalwerte"]["auffindesituation"] = st.selectbox(
            "Auffindesituation",
            ["", "sitzend vorgefunden", "liegend vorgefunden", "stehend vorgefunden", "am Boden", "auf Stuhl/Sofa", "in häuslicher Umgebung"],
            key="auffindesituation"
        )
    
    st.divider()
    
    # --- B: ATMUNG & OXYGENATION ---
    st.subheader("B – ATMUNG & OXYGENATION")
    
    b1, b2 = st.columns(2)
    
    with b1:
        spo2_cat = st.selectbox(
            "SpO₂-Wert",
            ["", "Normal (≥95%)", "Leicht ↓ (90-94%)", "Kritisch ↓ (<90%)", "Selber schreiben"],
            key="spo2_category"
        )
        if spo2_cat == "Selber schreiben":
            patient["vitalwerte"]["spo2"] = st.number_input("SpO₂ (%)", 0, 100, 0, key="spo2_input")
        elif spo2_cat == "Normal (≥95%)":
            patient["vitalwerte"]["spo2"] = 97
        elif spo2_cat == "Leicht ↓ (90-94%)":
            patient["vitalwerte"]["spo2"] = 92
        elif spo2_cat == "Kritisch ↓ (<90%)":
            patient["vitalwerte"]["spo2"] = 85
    
    with b2:
        af_cat = st.selectbox(
            "AF-Wert",
            ["", "Bradypnoe (<10)", "Normal (10-20)", "Tachypnoe (20-30)", "Schwer (>30)", "Selber schreiben"],
            key="af_category"
        )
        if af_cat == "Selber schreiben":
            patient["vitalwerte"]["af"] = st.number_input("AF (/min)", 0, 60, 0, key="af_input")
        elif af_cat == "Bradypnoe (<10)":
            patient["vitalwerte"]["af"] = 8
        elif af_cat == "Normal (10-20)":
            patient["vitalwerte"]["af"] = 15
        elif af_cat == "Tachypnoe (20-30)":
            patient["vitalwerte"]["af"] = 25
        elif af_cat == "Schwer (>30)":
            patient["vitalwerte"]["af"] = 35
    
    st.divider()
    
    # --- C: ZIRKULATION ---
    st.subheader("C – ZIRKULATION")
    
    c1, c2 = st.columns(2)
    
    with c1:
        rr_cat = st.selectbox(
            "RR-Wert",
            ["", "Hypotonie (<90/60)", "Normal (90-140/60-90)", "Erhöht (140-160/90-100)", "Hypertonie (>160/100)", "Selber schreiben"],
            key="rr_category"
        )

        if rr_cat == "Selber schreiben":
            col_sys, col_dia = st.columns(2)
            with col_sys:
                patient["vitalwerte"]["rr_sys"] = st.number_input("sys", 0, 300, 0, key="rr_sys_input")
            with col_dia:
                patient["vitalwerte"]["rr_dia"] = st.number_input("dia", 0, 200, 0, key="rr_dia_input")
        elif rr_cat == "Hypotonie (<90/60)":
            patient["vitalwerte"]["rr_sys"], patient["vitalwerte"]["rr_dia"] = 85, 55
        elif rr_cat == "Normal (90-140/60-90)":
            patient["vitalwerte"]["rr_sys"], patient["vitalwerte"]["rr_dia"] = 120, 80
        elif rr_cat == "Erhöht (140-160/90-100)":
            patient["vitalwerte"]["rr_sys"], patient["vitalwerte"]["rr_dia"] = 150, 95
        elif rr_cat == "Hypertonie (>160/100)":
            patient["vitalwerte"]["rr_sys"], patient["vitalwerte"]["rr_dia"] = 170, 105
    
    with c2:
        patient["vitalwerte"]["puls"] = st.number_input("Pulsfrequenz (/min)", 0, 250, 0, key="puls_input")
    
    st.divider()
    
    # --- D: DISABILITY (Neurologischer Status) ---
    st.subheader("D – DISABILITY (Neurologischer Status)")
    
    d1, d2 = st.columns(2)
    
    with d1:
        patient["vitalwerte"]["gcs"] = st.number_input("Glasgow Coma Scale", 3, 15, 15, key="gcs_input")
    
    with d2:
        patient["vitalwerte"]["bz"] = st.number_input("Blutzucker (mg/dL)", 0, 1000, 0, key="bz_input")
    
    st.divider()
    
    # --- E: EXPOSURE (Temperatur) ---
    st.subheader("E – EXPOSURE (Ganzkörperuntersuchung)")
    
    temp_gemessen = st.checkbox("Temperatur gemessen", key="temp_checkbox")
    
    if temp_gemessen:
        temp_cat = st.selectbox(
            "Temp-Wert",
            ["", "Unterkühlung (<36°C)", "Normal (36-37.5°C)", "Erhöht (37.5-38°C)", "Fieber (>38°C)", "Selber schreiben"],
            key="temp_category"
        )
        if temp_cat == "Selber schreiben":
            patient["vitalwerte"]["temperatur"] = st.number_input(
                "Temp (°C)",
                min_value=30.0,
                max_value=45.0,
                value=36.5,
                step=0.1,
                key="temp_input"
            )
        elif temp_cat == "Unterkühlung (<36°C)":
            patient["vitalwerte"]["temperatur"] = 35.5
        elif temp_cat == "Normal (36-37.5°C)":
            patient["vitalwerte"]["temperatur"] = 37.0
        elif temp_cat == "Erhöht (37.5-38°C)":
            patient["vitalwerte"]["temperatur"] = 37.7
        elif temp_cat == "Fieber (>38°C)":
            patient["vitalwerte"]["temperatur"] = 38.5
    
    st.divider()
    
    # --- Kurzbericht ---
    st.subheader("📝 Einsatz-Kurzbericht")
    patient["vitalwerte"]["kurzbericht"] = st.text_area(
        "Beschreibung des Einsatzes (optional)",
        height=150,
        key="kurzbericht",
        placeholder="z.B. Sturz aus Höhe, Verkehrsunfall, Schmerzen seit 2 Stunden, ..."
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
        patient["xabcde"]["atemweg"] = st.radio(
            "Atemweg",
            ["Keine Angabe", "Frei", "Gefährdet", "Verlegt"],
            key="atemweg"
        )
        patient["xabcde"]["hws"] = st.radio(
            "HWS",
            ["Keine Angabe", "Keine Immobilisation", "Stifneck", "Vakuummatratze"],
            key="hws"
        )

    elif selected == "B":
        st.subheader("B – Breathing")
        patient["xabcde"]["atmung"] = st.radio(
            "Atmung",
            ["Keine Angabe", "Unauffällig", "Dyspnoe", "Bradypnoe", "Tachypnoe", "Apnoe"],
            key="atmung"
        )
        patient["xabcde"]["atemgeraeusche"] = st.radio(
            "Atemgeräusche",
            ["Keine Angabe", "Beidseits vorhanden", "Links abgeschwächt", "Rechts abgeschwächt", "Keine"],
            key="atemgeraeusche"
        )
        patient["xabcde"]["sauerstoff"] = st.selectbox(
            "Sauerstoffgabe",
            ["Keine", "2 l/min", "4 l/min", "6 l/min", "10 l/min", "15 l/min"],
            key="sauerstoff"
        )

    elif selected == "C":
        st.subheader("C – Circulation")
        patient["xabcde"]["haut"] = st.radio(
            "Haut",
            ["Keine Angabe", "Rosig / warm", "Blass", "Kalt / schweißig", "Zyanotisch"],
            key="haut"
        )
        patient["xabcde"]["rekap"] = st.radio(
            "Rekapillarisierungszeit",
            ["Keine Angabe", "< 2 Sekunden", "> 2 Sekunden"],
            key="rekap"
        )
        patient["xabcde"]["pulsqualitaet"] = st.radio(
            "Pulsqualität",
            ["Keine Angabe", "Kräftig", "Schwach", "Fadenförmig"],
            key="pulsqualitaet"
        )

    elif selected == "D":
        st.subheader("D – Disability")
        patient["xabcde"]["avpu"] = st.radio(
            "AVPU",
            ["Keine Angabe", "A", "V", "P", "U"],
            key="avpu"
        )
        patient["xabcde"]["pupillen"] = st.radio(
            "Pupillen",
            ["Keine Angabe", "Isokor", "Anisokor", "Lichtstarr"],
            key="pupillen"
        )

    elif selected == "E":
        st.subheader("E – Exposure")
        patient["xabcde"]["bodycheck"] = st.radio(
            "Bodycheck",
            ["Keine Angabe", "Unauffällig", "Auffällig"],
            key="bodycheck"
        )
        if patient["xabcde"]["bodycheck"] == "Auffällig":
            patient["xabcde"]["bodycheck_text"] = st.text_area(
                "Auffälligkeiten",
                height=120,
                key="bodycheck_text"
            )
        patient["xabcde"]["unterkuehlung"] = st.checkbox(
            "Unterkühlung",
            key="unterkuehlung"
        )
        patient["xabcde"]["verbrennung"] = st.checkbox(
            "Verbrennung",
            key="verbrennung"
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

    s_col1, s_col2, s_col3, s_col4, s_col5, s_col6, s_col7, s_col8 = st.columns(8, gap="small")
    s_buttons = ["S1", "A", "M", "P", "L", "E", "R", "S2"]
    s_cols = [s_col1, s_col2, s_col3, s_col4, s_col5, s_col6, s_col7, s_col8]
    for label, col in zip(s_buttons, s_cols):
        with col:
            if st.button(label, key=f"samplers_nav_{label}", use_container_width=True):
                st.session_state["samplers_selected"] = label
                st.rerun()

    samplers_selected = st.session_state["samplers_selected"]
    st.info(f"Aktive SAMPLERS-Sektion: {samplers_selected}")

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

    st.subheader("🕒 Maßnahmen-Timeline")
    t1, t2, t3 = st.columns([1, 2, 2])
    with t1:
        timeline_zeit = st.text_input("Uhrzeit", placeholder="14:32", key="timeline_zeit")
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
    med1, med2, med3, med4, med5 = st.columns([2, 1, 1, 1, 2])
    with med1:
        med_name = st.text_input("Medikament", placeholder="z.B. Morphin", key="med_name")
    with med2:
        med_dosis = st.text_input("Dosis", placeholder="z.B. 2 mg", key="med_dosis")
    with med3:
        med_weg = st.selectbox("Applikation", ["i.v.", "i.m.", "p.o.", "intranasal", "inhalativ", "sonstiges"], key="med_weg")
    with med4:
        med_zeit = st.text_input("Uhrzeit", placeholder="14:35", key="med_zeit")
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
# MEDIKAMENTENRECHNER
# --------------------------------------------------

elif seite == "💉 Medikamentenrechner":

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

        if alter >= 12:
            adrenalin_im_mg = 0.5
            clemastin_mg = 2.0
            prednisolon_mg = 250.0
            salbutamol_mg = 2.5
        elif alter >= 6:
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
            if alter < 4:
                meds.append("Adrenalin 4 mg pur vernebelt")
            elif 4 <= alter <= 6:
                meds.append("Salbutamol 1,25 mg vernebelt")
            elif alter > 6:
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
            "Medikation gemäß SOP verabreichen und Wirkung nach 5 Minuten re-evaluieren",
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
        kriterium_hypo = float(bz_mg) < 60 or bz_mmol < 3.3

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
            hinweise.append("Schwellenwert für SOP-Hypoglykämie aktuell nicht erfüllt (BZ <60 mg/dl oder <3,3 mmol/l).")

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

        iv_midazolam_mg = round(0.05 * float(gewicht), 2)
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

        if rr_syst < 120:
            meds.append("Volumengabe 500 ml Vollelektrolytlösung i.v.")
            hinweise.append("Ziel: Normotension")
        elif rr_syst > 220:
            meds.append("Urapidil 5-15 mg langsam i.v., titrierend")
            hinweise.append("Ziel: systolischer RR < 220 mmHg")
        else:
            hinweise.append("Bei RR syst. 120-220 mmHg keine primäre RR-Senkung gemäß SOP-Fluss.")

        handlung.append("Voranmeldung Neurologie / Stroke Unit")
        handlung.append("Kliniktransport priorisieren")

        if symptombeginn_h < 6:
            hinweise.append("Zeitfenster: < 6 h, systemische Lyse möglich.")
        elif symptombeginn_h <= 8:
            hinweise.append("Zeitfenster: bis 8 h und mehr, intraarterielle Thrombektomie möglich.")
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

        if rr_syst > 120:
            meds.append("Glyceroltrinitrat 0,4-0,8 mg s.l.")
        else:
            hinweise.append("Bei RR syst. <= 120 mmHg kein Nitro gemäß SOP-Fluss.")

        meds.append("Furosemid 20 mg i.v. langsam, ggf. einmalige Repetition")

        if rr_syst >= 220:
            hinweise.append("Hypertensiver Notfall (RR syst. >= 220 mmHg)")
            handlung.append("Notärztliche Eskalation unmittelbar priorisieren")
        else:
            hinweise.append("RR-Ziel im Verlauf: systolisch < 220 mmHg")

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

        if rr_syst <= 180:
            hinweise.append("SOP-Hinweis: hypertensiver Notfall typischerweise bei RR syst. > 180 mmHg mit Organdysfunktion.")

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

        if nrs_acs > 4:
            meds.append("Morphin 3 mg i.v., einmalige Repetition nach 5 Minuten möglich")
            handlung.append("Nasenkapnografie, Alarmgrenze AF < 10/min")
            handlung.append("Voranmeldung Kardiologie und EKG-Übermittlung")
        else:
            handlung.append("ABCDE-Re-Evaluation")

        if af < 10:
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

        if nrs_abd_1 >= 3:
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

        if nrs_abd_2 > 6:
            butyl_mg = min(round(0.3 * float(gewicht), 1), 40.0)
            if alter > 12:
                meds.append(f"Butylscopolamin {butyl_mg} mg langsam i.v. (0,3 mg/kgKG, max. 40 mg)")
            else:
                hinweise.append("Butylscopolamin-Stufe im SOP-Fluss explizit für Erw./Kind >12 Jahre angegeben.")
        else:
            handlung.append("ABCDE-Re-Evaluation")

        if nrs_abd_3 > 6:
            if float(gewicht) > 30:
                meds.append("Fentanyl i.v.: 0,05 mg Einmalgaben alle 4 Minuten, Maximaldosis 2 µg/kgKG")
                hinweise.append("BTM-Dokumentation beachten")
            else:
                hinweise.append("Fentanyl-Stufe laut SOP erst ab >30 kg.")
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

        if nrs < 3:
            hinweise.append("SOP-Hinweis: Flussbild für starke Schmerzen ab NRS >= 3.")

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

            if nrs >= 6 or erweiterte_massnahmen == "Ja":
                handlung.append("Erweiterte Basismaßnahmen")
                if alter > 60:
                    meds.append("Midazolam i.v.: 1 mg (Patient > 60 Jahre)")
                elif float(gewicht) > 50:
                    meds.append("Midazolam i.v.: 2 mg (Erw./Kind > 50 kg)")
                elif float(gewicht) > 30:
                    meds.append("Midazolam i.v.: 1 mg (Kind > 30 kg)")

                if float(gewicht) > 30:
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

        if nrs > 8:
            hinweise.append("Bei unerträglichen Schmerzen (NRS > 8) zuerst Midazolam/Esketamin/Fentanyl und anschließend Paracetamol erwägen.")

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
            if alter > 60 or neuro_defizit == "Ja" or krampfleiden_bekannt == "Ja":
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

        if hf >= 60:
            hinweise.append("SOP-Hinweis: Flussbild für instabile Bradykardie bei HF < 60/min.")

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

    else:
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

        if hf_tachy < 100:
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

# --------------------------------------------------
# UEBERGABE
# --------------------------------------------------

elif seite == "🗣️ Übergabe":

    st.header("🗣️ Übergabe (MIST / ISBAR)")

    mist_text, isbar_text = build_handover_text(patient)

    st.subheader("MIST")
    st.text_area("Übergabe MIST", mist_text, height=180, key="handover_mist")

    st.subheader("ISBAR")
    st.text_area("Übergabe ISBAR", isbar_text, height=220, key="handover_isbar")

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

            st.success("Protokoll erstellt.")

            st.text_area(

                "RD-Protokoll",

                protocol,

                height=600

            )

            st.download_button(

                "💾 Protokoll als TXT herunterladen",

                protocol,

                file_name="RD_Protokoll.txt",

                mime="text/plain"

            )

            escaped_protocol = json.dumps(protocol)
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
