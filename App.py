import streamlit as st
def add_line(text, value):
    """
    Fügt nur Zeilen hinzu, wenn ein Wert vorhanden ist.
    """
    if value not in ["", "Keine Angabe", 0, None]:
        return text + value + "\n"
    return text


def generate_protocol():

    protocol = ""

    # --------------------------------------------------
    # Vitalwerte
    # --------------------------------------------------

    vital = ""

    if rr_sys and rr_dia:
        vital += f"RR {rr_sys}/{rr_dia} mmHg\n"

    if puls:
        vital += f"Puls {puls}/min\n"

    if spo2:
        vital += f"SpO₂ {spo2}%\n"

    if af:
        vital += f"AF {af}/min\n"

    if bz:
        vital += f"BZ {bz} mg/dl\n"

    if temperatur:
        vital += f"Temperatur {temperatur:.1f} °C\n"

    if gcs:
        vital += f"GCS {gcs}\n"

    if vital != "":
        protocol += "VITALWERTE\n"
        protocol += "-------------------------\n"
        protocol += vital + "\n"

    # --------------------------------------------------
    # xABCDE
    # --------------------------------------------------

    xabcde = ""

    if x_blutung != "Keine Angabe":
        xabcde += f"x: {x_blutung}\n"

    if airway != "Keine Angabe":
        xabcde += f"A: Atemweg {airway}\n"

    if atmung != "Keine Angabe":
        xabcde += f"B: Atmung {atmung}\n"

    if haut != "Keine Angabe":
        xabcde += f"C: Haut {haut}\n"

    if avpu != "Keine Angabe":
        xabcde += f"D: AVPU {avpu}\n"

    if bodycheck != "Keine Angabe":
        xabcde += f"E: {bodycheck}\n"

    if xabcde != "":
        protocol += "xABCDE\n"
        protocol += "-------------------------\n"
        protocol += xabcde + "\n"

    # --------------------------------------------------
    # SAMPLERS
    # --------------------------------------------------

    samplers = ""

    if symptome != "":
        samplers += f"S: {symptome}\n"

    if allergien == "Keine bekannt":
        samplers += "A: Keine Allergien bekannt\n"

    if allergien == "Vorhanden":
        samplers += f"A: {allergie_text}\n"

    if medikamente_option == "Siehe Medikamentenplan":
        samplers += "M: Siehe Medikamentenplan\n"

    if medikamente_option == "Medikamente eingeben":
        samplers += f"M: {medikamente}\n"

    if vorgeschichte != "":
        samplers += f"P: {vorgeschichte}\n"

    if letzte_mahlzeit != "":
        samplers += f"L: {letzte_mahlzeit}\n"

    if ereignis != "":
        samplers += f"E: {ereignis}\n"

    if samplers != "":
        protocol += "SAMPLERS\n"
        protocol += "-------------------------\n"
        protocol += samplers + "\n"

    # --------------------------------------------------
    # OPQRST
    # --------------------------------------------------

    if schmerz_vorhanden == "Ja":

        opqrst = ""

        if onset != "Keine Angabe":
            opqrst += f"O: {onset}\n"

        if provocation != "":
            opqrst += f"P: {provocation}\n"

        if quality != "Keine Angabe":
            opqrst += f"Q: {quality}\n"

        if region != "":
            opqrst += f"R: {region}\n"

        if nrs > 0:
            opqrst += f"S: NRS {nrs}/10\n"

        if zeitverlauf != "":
            opqrst += f"T: {zeitverlauf}\n"

        if opqrst != "":
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

with tab5:

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
