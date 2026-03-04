import json
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="RD-Protokoll", layout="wide")
st.title("RD-Protokoll Generator (online)")
st.caption("⚠️ Keine Identdaten eingeben. Nur Werte/Befunde/Anamnese ohne Personenbezug.")

# OpenAI Client – Key kommt aus Streamlit Secrets (Cloud)
client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", ""))

def prune(obj):
    """Entfernt leere Werte rekursiv: None, '', '—', leere Dicts/Listen."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            pv = prune(v)
            if pv in (None, "", "—", {}, []):
                continue
            out[k] = pv
        return out if out else None
    if isinstance(obj, list):
        out = []
        for v in obj:
            pv = prune(v)
            if pv in (None, "", "—", {}, []):
                continue
            out.append(pv)
        return out if out else None
    if isinstance(obj, str):
        s = obj.strip()
        return None if s in ("", "—") else s
    return obj

st.subheader("Vitalwerte (optional)")
c1, c2, c3, c4 = st.columns(4)
with c1:
    rr_sys = st.number_input("RR syst.", 0, 300, 0, 1)
    rr_dia = st.number_input("RR diast.", 0, 200, 0, 1)
with c2:
    puls = st.number_input("Puls", 0, 300, 0, 1)
    spo2 = st.number_input("SpO₂", 0, 100, 0, 1)
with c3:
    af = st.number_input("AF", 0, 80, 0, 1)
    temp_x10 = st.number_input("Temp x10 (z.B. 367=36.7)", 0, 450, 0, 1)
with c4:
    bz = st.number_input("BZ", 0, 1000, 0, 1)
    gcs = st.number_input("GCS", 0, 15, 0, 1)

vitals = {}
if rr_sys: vitals["RR_sys"] = int(rr_sys)
if rr_dia: vitals["RR_dia"] = int(rr_dia)
if puls: vitals["Puls"] = int(puls)
if spo2: vitals["SpO2"] = int(spo2)
if af: vitals["AF"] = int(af)
if temp_x10: vitals["Temp_C"] = round(temp_x10 / 10.0, 1)
if bz: vitals["BZ"] = int(bz)
if gcs: vitals["GCS"] = int(gcs)

st.divider()
a, b, c = st.columns(3)

with a:
    st.subheader("xABCDE")
    x_blutung = st.selectbox("x – Starke Blutung?", ["—", "nein", "ja"])
    a_airway = st.selectbox("A – Atemweg", ["—", "frei", "gefährdet", "verlegt"])
    b_atmung = st.selectbox("B – Atmung", ["—", "unauffällig", "Dyspnoe", "Tachypnoe", "Bradypnoe"])
    c_haut = st.selectbox("C – Haut", ["—", "rosig/warm", "blass", "kalt/schweißig", "zyanotisch"])
    d_avpu = st.selectbox("D – AVPU", ["—", "A", "V", "P", "U"])
    e_umgebung = st.selectbox("E – Umgebung", ["—", "unauffällig", "Unterkühlung", "Hitzeexposition"])
    x_zusatz = st.text_input("xABCDE Zusatz (optional)", "")

with b:
    st.subheader("SAMPLERS")
    s_symptome = st.text_input("S – Symptome (kurz)", "")
    a_allergien = st.selectbox("A – Allergien", ["—", "keine bekannt", "vorhanden (siehe Zusatz)"])
    m_medis = st.selectbox("M – Medikamente", ["—", "keine", "regelmäßig (siehe Zusatz)"])
    p_vorg = st.selectbox("P – Vorgeschichte", ["—", "keine bekannt", "vorhanden (siehe Zusatz)"])
    e_ereignis = st.text_area("E – Ereignis (kurz)", height=90)
    samplers_zusatz = st.text_area("SAMPLERS Zusatz (optional)", height=80)

with c:
    st.subheader("OPQRST")
    schmerz = st.selectbox("Schmerz vorhanden?", ["—", "nein", "ja"])
    o_onset = st.selectbox("O – Beginn", ["—", "plötzlich", "schleichend", "unbekannt"])
    q_quality = st.selectbox("Q – Qualität", ["—", "drückend", "stechend", "brennend", "kolikartig", "dumpf", "unbekannt"])
    s_nrs = st.selectbox("S – Stärke (NRS)", ["—"] + [str(i) for i in range(0, 11)])
    opqrst_zusatz = st.text_area("OPQRST Zusatz (optional)", height=80)

raw = {
    "vitalwerte": vitals if vitals else None,
    "xABCDE": {
        "x_blutung": x_blutung,
        "A_atemweg": a_airway,
        "B_atmung": b_atmung,
        "C_haut": c_haut,
        "D_avpu": d_avpu,
        "E_umgebung": e_umgebung,
        "zusatz": x_zusatz,
    },
    "SAMPLERS": {
        "S_symptome": s_symptome,
        "A_allergien": a_allergien,
        "M_medikamente": m_medis,
        "P_vorgeschichte": p_vorg,
        "E_ereignis": e_ereignis,
        "zusatz": samplers_zusatz,
    },
    "OPQRST": {
        "schmerz": schmerz,
        "O_beginn": o_onset,
        "Q_qualitaet": q_quality,
        "S_nrs": s_nrs,
        "zusatz": opqrst_zusatz,
    },
}
data = prune(raw) or {}

system_instructions = """
Du bist eine Dokumentationshilfe für den deutschen Rettungsdienst.

Harte Regeln:
- Verwende ausschließlich die gelieferten Daten. Ergänze nichts, interpretiere nicht.
- Keine Identdaten anfordern oder hinzufügen.
- Nicht gelieferte Punkte dürfen NICHT erwähnt werden (auch nicht als 'nicht erhoben').

Ausgabe:
- Überschriften (nur wenn Daten vorhanden):
  1) Vitalwerte/Monitoring
  2) xABCDE
  3) SAMPLERS
  4) OPQRST
- Innerhalb: kurze, sachliche Zeilen im RD-Stil.
"""

st.divider()
if st.button("📝 Generieren", type="primary", use_container_width=True):
    if not st.secrets.get("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY fehlt. In Streamlit Cloud unter App → Settings → Secrets eintragen.")
        st.stop()

    if not data:
        st.warning("Keine Werte ausgewählt/eingegeben.")
        st.stop()

    user_prompt = "Daten (JSON):\n" + json.dumps(data, ensure_ascii=False, indent=2)

    with st.spinner("Generiere Protokoll…"):
        resp = client.responses.create(
            model="gpt-4.1-mini",
            temperature=0.1,
            max_output_tokens=900,
            input=[
                {"role": "system", "content": system_instructions.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
        )

    out_text = resp.output_text
    st.subheader("Fertiges Protokoll")
    st.text_area("Ausgabe", out_text, height=420)

    st.download_button(
        "⬇️ Download als .txt",
        data=out_text.encode("utf-8"),
        file_name="rd_protokoll.txt",
        mime="text/plain",
        use_container_width=True,
    )

with st.expander("Debug: gesendete Daten"):
    st.code(json.dumps(data, ensure_ascii=False, indent=2), language="json")
