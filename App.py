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
    
    if e_section:
        xabcde += "\n" + e_section

    if xabcde:
        protocol += "xABCDE — STRUKTURIERTE UNTERSUCHUNG\n"
        protocol += "=" * 50 + "\n"
        protocol += xabcde + "\n"

    # SAMPLERS
    samplers = ""
    if s.get("symptome"):
        samplers += f"SYMPTOME: {s.get('symptome')}\n"

    allergien = s.get("allergien")
    if allergien == "Keine bekannt":
        samplers += "ALLERGIEN: Keine bekannt\n"
    elif allergien == "Vorhanden":
        samplers += f"ALLERGIEN: {s.get('allergien_text','')}\n"

    medopt = s.get("medikamente_option")
    if medopt == "Siehe Medikamentenplan":
        samplers += "MEDIKAMENTE: Siehe Medikamentenplan\n"
    elif medopt == "Medikamente eingeben":
        samplers += f"MEDIKAMENTE: {s.get('medikamente','')}\n"

    if s.get("vorgeschichte"):
        samplers += f"VORGESCHICHTE: {s.get('vorgeschichte')}\n"

    letzte = s.get('letzte_mahlzeit')
    if letzte and letzte != "Keine Angabe":
        if letzte == 'Eigene Eingabe':
            samplers += f"LETZTE MAHLZEIT: {s.get('letzte_mahlzeit_text','')}\n"
        else:
            samplers += f"LETZTE MAHLZEIT: {letzte}\n"

    if s.get('ereignis'):
        samplers += f"EREIGNIS: {s.get('ereignis')}\n"

    # Risiken
    risks = []
    for k in ['raucher','alkohol','drogen','diabetes','hypertonie','antikoagulation']:
        if s.get(k):
            risks.append(k.upper())
    if s.get('risiken_sonstige'):
        risks.append(s.get('risiken_sonstige'))
    if risks:
        samplers += "RISIKOFAKTOREN: " + ", ".join(map(str, risks)) + "\n"

    schw = s.get('schwangerschaft')
    if schw and schw != 'Nicht relevant':
        samplers += f"SCHWANGERSCHAFT: {schw}\n"

    if samplers:
        protocol += "PATIENTENGESCHICHTE (SAMPLERS)\n"
        protocol += "=" * 50 + "\n"
        protocol += samplers + "\n"

    # OPQRST - Schmerzassessment ausführlich
    if o.get('schmerz_vorhanden') == 'Ja' or o.get('nrs'):
        opqrst = ""
        if o.get('onset'):
            opqrst += f"\nONSET (Beginn): {o.get('onset')}"
            if o.get('onset_text'):
                opqrst += f" — {o.get('onset_text')}"
            opqrst += "\n"
        if o.get('provocation'):
            opqrst += f"PROVOCATION (Auslöser/Linderung): {o.get('provocation')}"
            if o.get('provocation_text'):
                opqrst += f" — {o.get('provocation_text')}"
            opqrst += "\n"
        if o.get('quality'):
            opqrst += f"QUALITY (Charakteristik): {o.get('quality')}"
            if o.get('quality_text'):
                opqrst += f" — {o.get('quality_text')}"
            opqrst += "\n"
        if o.get('region'):
            opqrst += f"REGION (Lokalisation): {o.get('region')}\n"
        if o.get('radiation'):
            opqrst += f"  Ausstrahlung: {o.get('radiation')}\n"
        if o.get('nrs'):
            try:
                n = int(o.get('nrs'))
                if n > 0:
                    opqrst += f"SEVERITY (Stärke): {n}/10 (Numerische Ratingskala)\n"
                    if o.get('severity_desc'):
                        opqrst += f"  Auswirkung: {o.get('severity_desc')}\n"
            except Exception:
                pass
        if o.get('zeitverlauf'):
            opqrst += f"TIME (Zeitverlauf): {o.get('zeitverlauf')}\n"
            if o.get('dauer'):
                opqrst += f"  Dauer: {o.get('dauer')}\n"
        if opqrst:
            protocol += "SCHMERZASSESSMENT (OPQRST)\n"
            protocol += "=" * 50 + "\n"
            protocol += opqrst + "\n"

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
        :root { --bg:#071026; --card:#0f1724; --muted:#9aa4b2; --accent:#1e73ff; --accent-2:#ff6b6b; --text:#e6eef8 }
        html, body, [class*="css"]  { background: linear-gradient(180deg,var(--bg) 0%, #051123 100%) !important; color:var(--text) }
        .header { background: linear-gradient(90deg,var(--accent) 0%, #0950b0 100%); color: white; padding: 14px 22px; border-radius:10px }
        .card { background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)); padding: 18px; border-radius: 12px; box-shadow: 0 10px 30px rgba(2,6,23,0.6); color:var(--text); margin-top:18px }
        /* Tight nav button styling */
        [data-testid="column"]:nth-child(n+2):nth-child(-n+6) { padding: 0 -4px; }
        [data-testid="column"]:nth-child(n+2):nth-child(-n+6) > [data-testid="stButton"] > button { width: 100%; padding: 14px 20px; border-radius: 22px; border: 1px solid rgba(255,255,255,0.06); background: rgba(255,255,255,0.03); color: var(--text); font-weight: 700; margin: 0; box-shadow: 0 6px 20px rgba(2,6,23,0.6); transition: all 0.15s ease; }
        [data-testid="column"]:nth-child(n+2):nth-child(-n+6) > [data-testid="stButton"] > button:hover { background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.12); transform: translateY(-2px); }
        /* Active nav button - apply gradient when it contains certain keywords */
        [data-testid="column"]:nth-child(n+2):nth-child(-n+6) > [data-testid="stButton"] > button:focus { outline: none; }
        </style>
        <script>
        // Color active nav button
        setTimeout(function() {
            const navButtons = document.querySelectorAll('[data-testid="column"]:nth-child(n+2):nth-child(-n+6) button');
            navButtons.forEach((btn, idx) => {
                const text = btn.textContent.trim();
                if (text === '❤️ Vitalwerte' || text === '🩺 xABCDE' || text === '📋 SAMPLERS' || text === '🔥 OPQRST' || text === '📄 Protokoll') {
                    // Check if button was recently clicked by checking if it's focused
                    btn.addEventListener('click', function() {
                        navButtons.forEach(b => b.style.background = 'rgba(255,255,255,0.03)');
                        btn.style.background = 'linear-gradient(90deg, #1e73ff 0%, #ff6b6b 100%)';
                        btn.style.color = '#fff';
                        btn.style.border = 'none';
                        btn.style.boxShadow = '0 8px 25px rgba(12,50,120,0.4)';
                    });
                }
            });
        }, 100);
        </script>
        <style>
        /* Inputs */
        input, textarea { background:#081029; color:var(--text) !important; border:1px solid rgba(255,255,255,0.04); border-radius:8px; padding:10px !important; font-size:0.95rem }
        input:focus, textarea:focus { border-color:#1e73ff !important; box-shadow: 0 0 8px rgba(30,115,255,0.3) !important }
        select { background:#081029; color:var(--text) !important; border:1px solid rgba(255,255,255,0.04); border-radius:8px; padding:10px !important }
        /* Selectbox styling */
        [data-testid="stSelectbox"] { margin: 12px 0 }
        /* Radio button styling */
        [data-testid="stRadio"] > label { padding:8px; border-radius:8px; cursor:pointer; transition: all 0.2s ease }
        [data-testid="stRadio"] > label:hover { background: rgba(255,255,255,0.02) }
        /* Slider styling */
        [data-testid="stSlider"] > div > div > div { border-radius:8px }
        /* Checkbox styling */
        [data-testid="stCheckbox"] > label { cursor:pointer; transition: all 0.2s ease }
        /* Number input */
        [data-testid="stNumberInput"] { margin: 12px 0 }
        /* Text area */
        [data-testid="stTextArea"] { margin: 12px 0 }
        /* Subheader styling */
        h3 { color:#1e73ff; margin-top:20px; margin-bottom:12px; border-bottom:1px solid rgba(30,115,255,0.3); padding-bottom:8px }
        /* Divider */
        hr { border-color: rgba(255,255,255,0.05) !important; margin: 24px 0 }
        /* Hide sidebar completely */
        section[data-testid='stSidebar']{ display:none; }
        /* Main content padding */
        main .block-container { padding-top: 12px; padding-left: 80px; padding-right:80px }
        </style>
        <div class='header'>
            <div style='display:flex; align-items:center; gap:14px'>
                <div style='font-size:20px; font-weight:800'>🚑 RD-Protokoll Generator</div>
                <div style='opacity:0.9; color:var(--muted); margin-left:8px'>— Hochwertige, ausfüllbare Einsatzdokumentation (anonym)</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
)

# --------------------------------------------------
# Patientenobjekt anlegen
# --------------------------------------------------

if "patient" not in st.session_state:

    st.session_state.patient = {

        "vitalwerte": {},

        "xabcde": {},

        "samplers": {},

        "opqrst": {}

    }

patient = st.session_state.patient
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
# --------------------------------------------------
# Navigation
# --------------------------------------------------

# Centered navigation in main area
if 'seite' not in st.session_state:
    st.session_state['seite'] = "❤️ Vitalwerte"

nav_options = [
    "❤️ Vitalwerte",
    "🩺 xABCDE",
    "📋 SAMPLERS",
    "🔥 OPQRST",
    "📄 Protokoll"
]

# Navigation mit inline HTML + Session-State handling
nav_container = st.container()
with nav_container:
    # HTML-basierte visuelle Navigation
    cols_nav = st.columns([1] + [1]*5 + [1])
    
    for i, opt in enumerate(nav_options):
        is_active = (st.session_state['seite'] == opt)
        col = cols_nav[i+1]
        
        if col.button(opt, key=f"nav_{i}", use_container_width=True):
            st.session_state['seite'] = opt
            st.rerun()

seite = st.session_state['seite']

# --------------------------------------------------
# VITALWERTE
# --------------------------------------------------

if seite == "❤️ Vitalwerte":

    st.header("❤️ Vitalwerte & Demographie")
    
    # --- Blutdruck ---
    st.subheader("Blutdruck (RR)")
    col_rr1, col_rr2 = st.columns(2)
    
    with col_rr1:
        rr_option = st.radio(
            "Wie möchtest du den Blutdruck eingeben?",
            ["Zahlen eingeben", "Auswählen"],
            key="rr_option",
            horizontal=True
        )
    
    if rr_option == "Zahlen eingeben":
        col_sys, col_dia = st.columns(2)
        with col_sys:
            patient["vitalwerte"]["rr_sys"] = st.number_input("RR systolisch", 0, 300, 0)
        with col_dia:
            patient["vitalwerte"]["rr_dia"] = st.number_input("RR diastolisch", 0, 200, 0)
    else:
        rr_cat = st.selectbox(
            "Blutdruck-Kategorie",
            ["", "Hypotonie (<90/60)", "Normal (90-140/60-90)", "Erhöht (140-160/90-100)", "Hypertonie (>160/100)"],
            key="rr_category"
        )
        if rr_cat == "Hypotonie (<90/60)":
            patient["vitalwerte"]["rr_sys"], patient["vitalwerte"]["rr_dia"] = 85, 55
        elif rr_cat == "Normal (90-140/60-90)":
            patient["vitalwerte"]["rr_sys"], patient["vitalwerte"]["rr_dia"] = 120, 80
        elif rr_cat == "Erhöht (140-160/90-100)":
            patient["vitalwerte"]["rr_sys"], patient["vitalwerte"]["rr_dia"] = 150, 95
        elif rr_cat == "Hypertonie (>160/100)":
            patient["vitalwerte"]["rr_sys"], patient["vitalwerte"]["rr_dia"] = 170, 105
    
    st.divider()
    
    # --- Puls, SpO2, BZ ---
    st.subheader("Weitere Vitalwerte")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        patient["vitalwerte"]["puls"] = st.number_input("Pulsfrequenz (/min)", 0, 250, 0)
    
    with c2:
        patient["vitalwerte"]["spo2"] = st.number_input("SpO₂ (%)", 0, 100, 0)
    
    with c3:
        patient["vitalwerte"]["bz"] = st.number_input("Blutzucker (mg/dL)", 0, 1000, 0)
    
    st.divider()
    
    # --- Atemfrequenz ---
    st.subheader("Atemfrequenz (AF)")
    af_option = st.radio(
        "Wie möchtest du die Atemfrequenz eingeben?",
        ["Zahlen eingeben", "Auswählen"],
        key="af_option",
        horizontal=True
    )
    
    if af_option == "Zahlen eingeben":
        patient["vitalwerte"]["af"] = st.number_input("AF (/min)", 0, 60, 0)
    else:
        af_cat = st.selectbox(
            "Atemfrequenz-Kategorie",
            ["", "Bradypnoe (<10)", "Normal (10-20)", "Tachypnoe (20-30)", "Schwere Tachypnoe (>30)"],
            key="af_category"
        )
        if af_cat == "Bradypnoe (<10)":
            patient["vitalwerte"]["af"] = 8
        elif af_cat == "Normal (10-20)":
            patient["vitalwerte"]["af"] = 15
        elif af_cat == "Tachypnoe (20-30)":
            patient["vitalwerte"]["af"] = 25
        elif af_cat == "Schwere Tachypnoe (>30)":
            patient["vitalwerte"]["af"] = 35
    
    st.divider()
    
    # --- Temperatur ---
    st.subheader("Körpertemperatur")
    temp_gemessen = st.checkbox("Temperatur gemessen", key="temp_checkbox")
    
    if temp_gemessen:
        temp_option = st.radio(
            "Wie möchtest du die Temperatur eingeben?",
            ["Zahlen eingeben", "Auswählen"],
            key="temp_option",
            horizontal=True
        )
        
        if temp_option == "Zahlen eingeben":
            patient["vitalwerte"]["temperatur"] = st.number_input(
                "Temperatur (°C)",
                min_value=30.0,
                max_value=45.0,
                value=36.5,
                step=0.1
            )
        else:
            temp_cat = st.selectbox(
                "Temperatur-Kategorie",
                ["", "Unterkühlung (<36°C)", "Normal (36-37.5°C)", "Erhöht (37.5-38°C)", "Fieber (>38°C)"],
                key="temp_category"
            )
            if temp_cat == "Unterkühlung (<36°C)":
                patient["vitalwerte"]["temperatur"] = 35.5
            elif temp_cat == "Normal (36-37.5°C)":
                patient["vitalwerte"]["temperatur"] = 37.0
            elif temp_cat == "Erhöht (37.5-38°C)":
                patient["vitalwerte"]["temperatur"] = 37.7
            elif temp_cat == "Fieber (>38°C)":
                patient["vitalwerte"]["temperatur"] = 38.5
    
    st.divider()
    
    # --- GCS ---
    st.subheader("Neurologischer Status")
    patient["vitalwerte"]["gcs"] = st.number_input("Glasgow Coma Scale (GCS)", 3, 15, 15)
    
    st.divider()
    
    # --- Demographie ---
    st.subheader("Patientendemographie")
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
    
    # --- Kurzbericht ---
    st.subheader("📝 Einsatz-Kurzbericht")
    patient["vitalwerte"]["kurzbericht"] = st.text_area(
        "Beschreibung des Einsatzes (optional)",
        height=150,
        key="kurzbericht",
        placeholder="z.B. Sturz aus Höhe, Verkehrsunfall, Schmerzen seit 2 Stunden, ..."
    )

# --------------------------------------------------
# xABCDE
# --------------------------------------------------

elif seite == "🩺 xABCDE":

    st.header("🩺 xABCDE")

    # ---------------- x ----------------

    st.subheader("x – Exsanguination")

    patient["xabcde"]["blutung"] = st.radio(
        "Kritische Blutung",
        [
            "Keine Angabe",
            "Keine kritische Blutung",
            "Kritische Blutung vorhanden"
        ],
        key="x_blutung"
    )

    if patient["xabcde"]["blutung"] == "Kritische Blutung vorhanden":

        patient["xabcde"]["blutung_lokalisation"] = st.text_input(
            "Lokalisation",
            key="x_blutung_lokalisation"
        )

    st.divider()

    # ---------------- A ----------------

    st.subheader("A – Airway")

    patient["xabcde"]["atemweg"] = st.radio(
        "Atemweg",
        [
            "Keine Angabe",
            "Frei",
            "Gefährdet",
            "Verlegt"
        ],
        key="atemweg"
    )

    patient["xabcde"]["hws"] = st.radio(
        "HWS",
        [
            "Keine Angabe",
            "Keine Immobilisation",
            "Stifneck",
            "Vakuummatratze"
        ],
        key="hws"
    )

    st.divider()

    # ---------------- B ----------------

    st.subheader("B – Breathing")

    patient["xabcde"]["atmung"] = st.radio(
        "Atmung",
        [
            "Keine Angabe",
            "Unauffällig",
            "Dyspnoe",
            "Bradypnoe",
            "Tachypnoe",
            "Apnoe"
        ],
        key="atmung"
    )

    patient["xabcde"]["atemgeraeusche"] = st.radio(
        "Atemgeräusche",
        [
            "Keine Angabe",
            "Beidseits vorhanden",
            "Links abgeschwächt",
            "Rechts abgeschwächt",
            "Keine"
        ],
        key="atemgeraeusche"
    )

    patient["xabcde"]["sauerstoff"] = st.selectbox(
        "Sauerstoffgabe",
        [
            "Keine",
            "2 l/min",
            "4 l/min",
            "6 l/min",
            "10 l/min",
            "15 l/min"
        ],
        key="sauerstoff"
    )

    st.divider()

    # ---------------- C ----------------

    st.subheader("C – Circulation")

    patient["xabcde"]["haut"] = st.radio(
        "Haut",
        [
            "Keine Angabe",
            "Rosig / warm",
            "Blass",
            "Kalt / schweißig",
            "Zyanotisch"
        ],
        key="haut"
    )

    patient["xabcde"]["rekap"] = st.radio(
        "Rekapillarisierungszeit",
        [
            "Keine Angabe",
            "< 2 Sekunden",
            "> 2 Sekunden"
        ],
        key="rekap"
    )

    patient["xabcde"]["pulsqualitaet"] = st.radio(
        "Pulsqualität",
        [
            "Keine Angabe",
            "Kräftig",
            "Schwach",
            "Fadenförmig"
        ],
        key="pulsqualitaet"
    )

    st.divider()

    # ---------------- D ----------------

    st.subheader("D – Disability")

    patient["xabcde"]["avpu"] = st.radio(
        "AVPU",
        [
            "Keine Angabe",
            "A",
            "V",
            "P",
            "U"
        ],
        key="avpu"
    )

    patient["xabcde"]["pupillen"] = st.radio(
        "Pupillen",
        [
            "Keine Angabe",
            "Isokor",
            "Anisokor",
            "Lichtstarr"
        ],
        key="pupillen"
    )

    st.divider()

    # ---------------- E ----------------

    st.subheader("E – Exposure")

    patient["xabcde"]["bodycheck"] = st.radio(
        "Bodycheck",
        [
            "Keine Angabe",
            "Unauffällig",
            "Auffällig"
        ],
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
    # --------------------------------------------------
# SAMPLERS
# --------------------------------------------------

elif seite == "📋 SAMPLERS":

    st.header("📋 SAMPLERS")

    # -------------------------
    # S Symptome
    # -------------------------

    st.subheader("S – Symptome")

    textarea_field(
        "samplers",
        "symptome",
        "Beschwerden / Symptome"
    )

    st.divider()

    # -------------------------
    # A Allergien
    # -------------------------

    st.subheader("A – Allergien")

    allergien = radio_field(

        "samplers",

        "allergien",

        "Allergien",

        [

            "Keine Angabe",

            "Keine bekannt",

            "Vorhanden"

        ]

    )

    if allergien == "Vorhanden":

        text_field(

            "samplers",

            "allergien_text",

            "Welche Allergien?"

        )

    st.divider()

    # -------------------------
    # M Medikamente
    # -------------------------

    st.subheader("M – Medikamente")

    medikamente = radio_field(

        "samplers",

        "medikamente_option",

        "Medikamente",

        [

            "Keine Angabe",

            "Siehe Medikamentenplan",

            "Medikamente eingeben"

        ]

    )

    if medikamente == "Medikamente eingeben":

        textarea_field(

            "samplers",

            "medikamente",

            "Bitte Medikamente eingeben"

        )

    st.divider()

    # -------------------------
    # P Vorgeschichte
    # -------------------------

    st.subheader("P – Patientenvorgeschichte")

    textarea_field(

        "samplers",

        "vorgeschichte",

        "Vorerkrankungen"

    )

    st.divider()

    # -------------------------
    # L Letzte Mahlzeit
    # -------------------------

    st.subheader("L – Letzte Nahrungsaufnahme")

    letzte_mahlzeit = radio_field(

        "samplers",

        "letzte_mahlzeit",

        "Letzte Mahlzeit",

        [

            "Keine Angabe",

            "< 2 Stunden",

            "2–6 Stunden",

            "> 6 Stunden",

            "Unbekannt",

            "Eigene Eingabe"

        ]

    )

    if letzte_mahlzeit == "Eigene Eingabe":

        text_field(

            "samplers",

            "letzte_mahlzeit_text",

            "Eigene Eingabe"

        )

    st.divider()

    # -------------------------
    # E Ereignis
    # -------------------------

    st.subheader("E – Ereignis")

    textarea_field(

        "samplers",

        "ereignis",

        "Ereignisbeschreibung",

        height=180

    )

    st.divider()

    # -------------------------
    # R Risikofaktoren
    # -------------------------

    st.subheader("R – Risikofaktoren")

    col1, col2 = st.columns(2)

    with col1:

        checkbox_field("samplers","raucher","Raucher")
        checkbox_field("samplers","alkohol","Alkoholkonsum")
        checkbox_field("samplers","drogen","Drogen")

    with col2:

        checkbox_field("samplers","diabetes","Diabetes")
        checkbox_field("samplers","hypertonie","Hypertonie")
        checkbox_field("samplers","antikoagulation","Antikoagulation")

    text_field(

        "samplers",

        "risiken_sonstige",

        "Weitere Risikofaktoren"

    )

    st.divider()

    # -------------------------
    # S Schwangerschaft
    # -------------------------

    st.subheader("S – Schwangerschaft")

    radio_field(

        "samplers",

        "schwangerschaft",

        "Schwangerschaft",

        [

            "Nicht relevant",

            "Nein",

            "Ja",

            "Unbekannt"

        ]

    )

# --------------------------------------------------
# OPQRST
# --------------------------------------------------

elif seite == "🔥 OPQRST":

    st.header("🔥 OPQRST – Schmerzassessment")
    
    st.write("Detaillierte Schmerzerfassung für Schmerzpatienten")
    
    # Schmerz vorhanden?
    patient["opqrst"]["schmerz_vorhanden"] = st.radio(
        "Schmerzen vorhanden?",
        ["Nein", "Ja"],
        key="opqrst_schmerz",
        horizontal=True
    )
    
    if patient["opqrst"]["schmerz_vorhanden"] == "Ja":
        
        st.divider()
        
        # O - Onset
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
        
        st.divider()
        
        # P - Provocation/Palliation
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
        
        st.divider()
        
        # Q - Quality
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
        
        st.divider()
        
        # R - Region/Radiation
        st.subheader("R – Region/Radiation (Ort und Ausbreitung)")
        patient["opqrst"]["region"] = st.text_input(
            "Wo tut es weh?",
            key="opqrst_region"
        )
        patient["opqrst"]["radiation"] = st.text_input(
            "Ausstrahlung (Breitet sich der Schmerz aus?)",
            key="opqrst_radiation"
        )
        
        st.divider()
        
        # S - Severity
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
        
        st.divider()
        
        # T - Time
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
