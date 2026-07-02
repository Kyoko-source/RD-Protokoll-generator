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

    # Vitalwerte (mit qualitativen Beschreibungen)
    vital = ""
    rr_sys = v.get("rr_sys") or None
    rr_dia = v.get("rr_dia") or None
    if rr_sys and rr_dia:
        rr_cat, rr_vals = categorize_rr(rr_sys, rr_dia)
        if isinstance(rr_vals, tuple):
            vital += f"RR: {rr_cat} ({rr_vals[0]}/{rr_vals[1]} mmHg)\n"
        else:
            vital += f"RR: {rr_cat}\n"

    puls = v.get("puls") or None
    if puls is not None and puls != 0:
        p_cat, p_val = categorize_puls(puls)
        if p_val is not None:
            vital += f"Puls: {p_cat} ({p_val}/min)\n"
        else:
            vital += f"Puls: {p_cat}\n"

    spo2 = v.get("spo2") or None
    if spo2 is not None and spo2 != 0:
        s_cat, s_val = categorize_spo2(spo2)
        if s_val is not None:
            vital += f"SpO₂: {s_cat} ({s_val} %)\n"
        else:
            vital += f"SpO₂: {s_cat}\n"

    af = v.get("af") or None
    if af is not None and af != 0:
        af_cat, af_val = categorize_af(af)
        if af_val is not None:
            vital += f"AF: {af_cat} ({af_val}/min)\n"
        else:
            vital += f"AF: {af_cat}\n"

    bz = v.get("bz") or None
    if bz is not None and bz != 0:
        bz_cat, bz_val = categorize_bz(bz)
        if bz_val is not None:
            vital += f"BZ: {bz_cat} ({bz_val} mg/dl)\n"
        else:
            vital += f"BZ: {bz_cat}\n"

    temperatur = v.get("temperatur")
    if temperatur is not None:
        t_cat, t_val = categorize_temperature(temperatur)
        if t_val is not None:
            vital += f"Temperatur: {t_cat} ({t_val:.1f} °C)\n"
        else:
            vital += f"Temperatur: {t_cat}\n"

    gcs = v.get("gcs")
    if gcs:
        # GCS: numeric but mit kurzer Interpretation
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
        vital += f"GCS: {g_cat} ({gcs})\n"

    if vital:
        protocol += "VITALWERTE\n"
        protocol += "=========================\n"
        protocol += vital + "\n"

    # xABCDE
    xabcde = ""
    blutung = x.get("blutung")
    if blutung and blutung != "Keine Angabe":
        xabcde += f"x: {blutung}\n"
        if x.get("blutung_lokalisation"):
            xabcde += f"  Lokalisation: {x.get('blutung_lokalisation')}\n"

    if x.get("atemweg") and x.get("atemweg") != "Keine Angabe":
        xabcde += f"A: Atemweg {x.get('atemweg')}\n"

    if x.get("atmung") and x.get("atmung") != "Keine Angabe":
        xabcde += f"B: Atmung {x.get('atmung')}\n"

    if x.get("haut") and x.get("haut") != "Keine Angabe":
        xabcde += f"C: Haut {x.get('haut')}\n"

    if x.get("avpu") and x.get("avpu") != "Keine Angabe":
        xabcde += f"D: AVPU {x.get('avpu')}\n"

    if x.get("bodycheck") and x.get("bodycheck") != "Keine Angabe":
        xabcde += f"E: {x.get('bodycheck')}\n"
        if x.get("bodycheck_text"):
            xabcde += f"  Auffälligkeiten: {x.get('bodycheck_text')}\n"

    if xabcde:
        protocol += "xABCDE\n"
        protocol += "-------------------------\n"
        protocol += xabcde + "\n"

    # SAMPLERS
    samplers = ""
    if s.get("symptome"):
        samplers += f"S: {s.get('symptome')}\n"

    allergien = s.get("allergien")
    if allergien == "Keine bekannt":
        samplers += "A: Keine Allergien bekannt\n"
    elif allergien == "Vorhanden":
        samplers += f"A: {s.get('allergien_text','')}.\n"

    medopt = s.get("medikamente_option")
    if medopt == "Siehe Medikamentenplan":
        samplers += "M: Siehe Medikamentenplan\n"
    elif medopt == "Medikamente eingeben":
        samplers += f"M: {s.get('medikamente','')}\n"

    if s.get("vorgeschichte"):
        samplers += f"P: {s.get('vorgeschichte')}\n"

    letzte = s.get('letzte_mahlzeit')
    if letzte and letzte != "Keine Angabe":
        if letzte == 'Eigene Eingabe':
            samplers += f"L: {s.get('letzte_mahlzeit_text','')}\n"
        else:
            samplers += f"L: {letzte}\n"

    if s.get('ereignis'):
        samplers += f"E: {s.get('ereignis')}\n"

    # Risiken
    risks = []
    for k in ['raucher','alkohol','drogen','diabetes','hypertonie','antikoagulation']:
        if s.get(k):
            risks.append(k)
    if s.get('risiken_sonstige'):
        risks.append(s.get('risiken_sonstige'))
    if risks:
        samplers += "R: " + ", ".join(map(str,risks)) + "\n"

    schw = s.get('schwangerschaft')
    if schw and schw != 'Nicht relevant':
        samplers += f"S (Schwangerschaft): {schw}\n"

    if samplers:
        protocol += "SAMPLERS\n"
        protocol += "-------------------------\n"
        protocol += samplers + "\n"

    # OPQRST
    if o.get('schmerz_vorhanden') == 'Ja' or o.get('nrs'):
        opqrst = ""
        if o.get('onset'):
            opqrst += f"O: {o.get('onset')}\n"
        if o.get('provocation'):
            opqrst += f"P: {o.get('provocation')}\n"
        if o.get('quality'):
            opqrst += f"Q: {o.get('quality')}\n"
        if o.get('region'):
            opqrst += f"R: {o.get('region')}\n"
        if o.get('nrs'):
            try:
                n = int(o.get('nrs'))
                if n > 0:
                    opqrst += f"S: NRS {n}/10\n"
            except Exception:
                pass
        if o.get('zeitverlauf'):
            opqrst += f"T: {o.get('zeitverlauf')}\n"
        if opqrst:
            protocol += "OPQRST\n"
            protocol += "-------------------------\n"
            protocol += opqrst + "\n"

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

# --- Custom styling -------------------------------------------------
st.markdown(
        """
        <style>
        .stApp { background: linear-gradient(180deg, #f7fbff 0%, #ffffff 100%); }
        .header { background:#003366; color: white; padding: 12px 20px; border-radius:8px }
        .card { background: #ffffff; padding: 12px; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
        .big-title { font-size:28px; font-weight:700; color:#003366 }
        </style>
        <div class='header'>
            <div style='display:flex; align-items:center; gap:12px'>
                <div style='font-size:22px'>🚑 RD-Protokoll Generator</div>
                <div style='opacity:0.85'>— Hochwertige, ausfüllbare Einsatzdokumentation</div>
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

seite = st.sidebar.radio(

    "Navigation",

    [

        "❤️ Vitalwerte",

        "🩺 xABCDE",

        "📋 SAMPLERS",

        "🔥 OPQRST",

        "📄 Protokoll"

    ]

)

# --------------------------------------------------
# VITALWERTE
# --------------------------------------------------

if seite == "❤️ Vitalwerte":

    st.header("❤️ Vitalwerte")

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        patient["vitalwerte"]["rr_sys"] = st.number_input(
            "RR systolisch",
            0,
            300,
            0
        )

        patient["vitalwerte"]["rr_dia"] = st.number_input(
            "RR diastolisch",
            0,
            200,
            0
        )

    with c2:

        patient["vitalwerte"]["puls"] = st.number_input(
            "Puls",
            0,
            250,
            0
        )

        patient["vitalwerte"]["spo2"] = st.number_input(
            "SpO₂",
            0,
            100,
            0
        )

    with c3:

        patient["vitalwerte"]["af"] = st.number_input(
            "Atemfrequenz",
            0,
            60,
            0
        )

        patient["vitalwerte"]["bz"] = st.number_input(
            "Blutzucker",
            0,
            1000,
            0
        )

    with c4:

        temp_gemessen = st.checkbox("Temperatur gemessen")

        if temp_gemessen:

            patient["vitalwerte"]["temperatur"] = st.number_input(

                "Temperatur",

                min_value=30.0,

                max_value=45.0,

                value=36.5,

                step=0.1

            )

        patient["vitalwerte"]["gcs"] = st.number_input(
            "GCS",
            3,
            15,
            15
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
# -----------------------------
# PROTOKOLL
# -----------------------------

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
