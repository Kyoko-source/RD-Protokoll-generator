import streamlit as st

st.set_page_config(
    page_title="RD-Protokoll Generator",
    page_icon="🚑",
    layout="wide"
)

st.title("🚑 RD-Protokoll Generator")
st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "❤️ Vitalwerte",
    "🩺 xABCDE",
    "📋 SAMPLERS",
    "🔥 OPQRST",
    "📄 Protokoll"
])

# -----------------------------
# VITALWERTE
# -----------------------------

with tab1:

    st.header("Vitalwerte")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        rr_sys = st.number_input(
            "RR systolisch",
            0,
            300,
            0
        )

        rr_dia = st.number_input(
            "RR diastolisch",
            0,
            200,
            0
        )

    with c2:

        puls = st.number_input(
            "Puls",
            0,
            250,
            0
        )

        spo2 = st.number_input(
            "SpO₂",
            0,
            100,
            0
        )

    with c3:

        af = st.number_input(
            "Atemfrequenz",
            0,
            60,
            0
        )

        bz = st.number_input(
            "Blutzucker",
            0,
            1000,
            0
        )

    with c4:

        temperatur = st.number_input(
            "Temperatur",
            30.0,
            45.0,
            0.0,
            step=0.1
        )

        gcs = st.number_input(
            "GCS",
            3,
            15,
            15
        )

    st.markdown("---")

    c5, c6 = st.columns(2)

    with c5:

        ekg = st.radio(
            "EKG",
            [
                "Keine Angabe",
                "Sinusrhythmus",
                "Vorhofflimmern",
                "Tachykardie",
                "Bradykardie",
                "Sonstiges"
            ]
        )

    with c6:

        bzkontrolle = st.radio(
            "BZ gemessen",
            [
                "Nein",
                "Ja"
            ]
        )

# -----------------------------
# PLATZHALTER
# -----------------------------

# -----------------------------
# xABCDE
# -----------------------------

with tab2:

    st.header("🩺 xABCDE")

    # x
    st.subheader("x - Exsanguination")

    x_blutung = st.radio(
        "Kritische Blutung",
        [
            "Keine Angabe",
            "Keine kritische Blutung",
            "Kritische Blutung vorhanden"
        ]
    )

    if x_blutung == "Kritische Blutung vorhanden":
        blutung_lokalisation = st.text_input(
            "Lokalisation der Blutung"
        )

    st.divider()

    # A
    st.subheader("A - Airway")

    airway = st.radio(
        "Atemweg",
        [
            "Keine Angabe",
            "Frei",
            "Gefährdet",
            "Verlegt"
        ]
    )

    if airway != "Keine Angabe":

        hws = st.radio(
            "HWS Immobilisation",
            [
                "Keine Angabe",
                "Nicht erforderlich",
                "Angelegt"
            ]
        )

    st.divider()

    # B
    st.subheader("B - Breathing")

    atmung = st.radio(
        "Atmung",
        [
            "Keine Angabe",
            "Unauffällig",
            "Dyspnoe",
            "Tachypnoe",
            "Bradypnoe",
            "Apnoe"
        ]
    )

    atemgeraeusche = st.radio(
        "Atemgeräusche",
        [
            "Keine Angabe",
            "Beidseits vorhanden",
            "Abgeschwächt",
            "Seitendifferenz",
            "Keine"
        ]
    )

    sauerstoff = st.radio(
        "Sauerstoffgabe",
        [
            "Keine",
            "2 l/min",
            "4 l/min",
            "6 l/min",
            "10 l/min",
            "15 l/min"
        ]
    )

    st.divider()

    # C
    st.subheader("C - Circulation")

    haut = st.radio(
        "Haut",
        [
            "Keine Angabe",
            "Rosig / warm",
            "Blass",
            "Kalt / schweißig",
            "Zyanotisch"
        ]
    )

    rekap = st.radio(
        "Rekapillarisierungszeit",
        [
            "Keine Angabe",
            "< 2 Sekunden",
            "> 2 Sekunden"
        ]
    )

    pulsqualitaet = st.radio(
        "Pulsqualität",
        [
            "Keine Angabe",
            "Kräftig",
            "Schwach",
            "Fadenförmig"
        ]
    )

    st.divider()

    # D
    st.subheader("D - Disability")

    avpu = st.radio(
        "AVPU",
        [
            "Keine Angabe",
            "A",
            "V",
            "P",
            "U"
        ]
    )

    pupillen = st.radio(
        "Pupillen",
        [
            "Keine Angabe",
            "Isokor und lichtreagibel",
            "Anisokor",
            "Lichtstarr"
        ]
    )

    bz_d = st.number_input(
        "BZ (optional)",
        0,
        1000,
        0
    )

    st.divider()

    # E
    st.subheader("E - Exposure")

    bodycheck = st.radio(
        "Bodycheck",
        [
            "Keine Angabe",
            "Ohne Auffälligkeiten",
            "Auffälligkeiten vorhanden"
        ]
    )

    if bodycheck == "Auffälligkeiten vorhanden":

        bodycheck_text = st.text_area(
            "Welche Auffälligkeiten?"
        )

    unterkuehlung = st.checkbox(
        "Unterkühlung"
    )

    verbrennung = st.checkbox(
        "Verbrennung"
    )
    
# -----------------------------
# SAMPLERS
# -----------------------------

with tab3:

    st.header("📋 SAMPLERS")

    # S
    st.subheader("S - Symptome")

    symptome = st.text_area(
        "Beschwerden / Symptome",
        height=100,
        placeholder="z.B. Thoraxschmerzen, Atemnot..."
    )

    st.divider()

    # A
    st.subheader("A - Allergien")

    allergien = st.radio(
        "Allergien",
        [
            "Keine Angabe",
            "Keine bekannt",
            "Vorhanden"
        ]
    )

    allergie_text = ""

    if allergien == "Vorhanden":
        allergie_text = st.text_input(
            "Welche Allergien?"
        )

    st.divider()

    # M
    st.subheader("M - Medikamente")

    medikamente_option = st.radio(
        "Medikamente",
        [
            "Keine Angabe",
            "Siehe Medikamentenplan",
            "Medikamente eingeben"
        ]
    )

    medikamente = ""

    if medikamente_option == "Medikamente eingeben":
        medikamente = st.text_area(
            "Medikamente",
            height=120,
            placeholder="z.B.\nRamipril\nMetformin\nASS 100"
        )

    st.divider()

    # P
    st.subheader("P - Patientenvorgeschichte")

    vorgeschichte = st.text_area(
        "Vorerkrankungen",
        height=100,
        placeholder="z.B. Hypertonie, Diabetes..."
    )

    st.divider()

    # L
    st.subheader("L - Letzte Mahlzeit")

    letzte_mahlzeit = st.text_input(
        "Letzte Nahrungsaufnahme"
    )

    st.divider()

    # E
    st.subheader("E - Ereignis")

    ereignis = st.text_area(
        "Ereignisbeschreibung",
        height=150
    )

    st.divider()

    # R
    st.subheader("R - Risikofaktoren")

    raucher = st.checkbox("Raucher")

    alkohol = st.checkbox("Alkoholkonsum")

    drogen = st.checkbox("Drogenkonsum")

    sonstige_risiken = st.text_input(
        "Weitere Risikofaktoren"
    )

    st.divider()

    # S
    st.subheader("S - Schwangerschaft")

    schwangerschaft = st.radio(
        "Schwangerschaft",
        [
            "Keine Angabe",
            "Nein",
            "Ja",
            "Nicht relevant"
        ]
    )
    # -----------------------------
# OPQRST
# -----------------------------

with tab4:

    st.header("🔥 OPQRST")

    schmerz_vorhanden = st.radio(
        "Hat der Patient Schmerzen?",
        [
            "Nein",
            "Ja"
        ]
    )

    if schmerz_vorhanden == "Ja":

        st.divider()

        st.subheader("O - Onset")

        onset = st.selectbox(
            "Beginn",
            [
                "Keine Angabe",
                "Plötzlich",
                "Schleichend",
                "Nach Belastung",
                "In Ruhe",
                "Unbekannt"
            ]
        )

        st.divider()

        st.subheader("P - Provocation / Palliation")

        provocation = st.text_input(
            "Was verschlechtert oder verbessert den Schmerz?"
        )

        st.divider()

        st.subheader("Q - Quality")

        quality = st.selectbox(
            "Schmerzqualität",
            [
                "Keine Angabe",
                "Stechend",
                "Drückend",
                "Dumpf",
                "Brennend",
                "Kolikartig",
                "Reißend",
                "Pochend"
            ]
        )

        st.divider()

        st.subheader("R - Region / Radiation")

        region = st.text_input(
            "Lokalisation"
        )

        ausstrahlung = st.text_input(
            "Ausstrahlung"
        )

        st.divider()

        st.subheader("S - Severity")

        nrs = st.slider(
            "Schmerzskala (NRS)",
            0,
            10,
            0
        )

        st.divider()

        st.subheader("T - Time")

        zeitverlauf = st.text_area(
            "Zeitlicher Verlauf",
            height=120
        )

        begleiterscheinungen = st.text_area(
            "Begleiterscheinungen",
            height=100
        )
