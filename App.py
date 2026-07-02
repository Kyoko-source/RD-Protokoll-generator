import streamlit as st
from io import BytesIO
from fpdf import FPDF
from datetime import datetime


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
        [data-testid="column"]:nth-child(n+2):nth-child(-n+8) { padding: 0 2px; }
    [data-testid="column"]:nth-child(n+2):nth-child(-n+8) > [data-testid="stButton"] > button { width:100%; padding: 13px 18px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.13); background: linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.015)); color: var(--text); font-weight: 800; margin:0; box-shadow: 0 12px 24px rgba(2,8,24,0.28); transition: all 0.22s ease; }
    [data-testid="column"]:nth-child(n+2):nth-child(-n+8) > [data-testid="stButton"] > button:hover { border-color: rgba(255,255,255,0.28); transform: translateY(-2px); }
        [data-testid="column"]:nth-child(n+2):nth-child(-n+8) > [data-testid="stButton"] > button:focus { outline:none; }
    [data-testid="column"]:nth-child(n+2):nth-child(-n+8) > [data-testid="stButton"] > button[kind='primary'] { color:#fff; border:none; box-shadow: 0 15px 30px rgba(64,124,255,0.3); }
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
    "🗣️ Übergabe",
    "📄 Protokoll"
]

# Navigation mit Streamlit-Buttons und Session-State
nav_container = st.container()
with nav_container:
    cols_nav = st.columns([1] + [1]*7 + [1])
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
    "🗣️ Übergabe": ("#7d6bff", "#5bbdff"),
    "📄 Protokoll": ("#4e72ff", "#5ac8ff"),
}
start_color, end_color = active_nav_palette.get(seite, ("#4b8cff", "#ff7a7a"))
st.markdown(
    f"""
    <style>
    [data-testid="column"]:nth-child(n+2):nth-child(-n+8) > [data-testid="stButton"] > button[kind='primary'] {{
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

            # PDF generieren
            try:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)
                # Title
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 8, "RD-Protokoll", ln=1, align='C')
                pdf.ln(2)
                pdf.cell(0, 6, f"Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=1)
                pdf.ln(4)
                pdf.set_font("Arial", size=12)
                for line in protocol.splitlines():
                    pdf.multi_cell(0, 6, line)
                # Footer
                pdf.set_y(-20)
                pdf.set_font("Arial", size=8)
                pdf.cell(0, 6, "Generiert mit RD-Protokoll Generator", align='C')
                pdf_bytes = pdf.output(dest="S").encode('latin-1')
                pdf_buffer = BytesIO(pdf_bytes)

                st.download_button(
                    "💾 Protokoll als PDF herunterladen",
                    data=pdf_buffer,
                    file_name="RD_Protokoll.pdf",
                    mime="application/pdf"
                )
            except Exception:
                st.info("PDF-Export nicht verfügbar (abhängige Bibliothek fehlt).")
