import json
import time
import streamlit as st
import openai
from openai import OpenAI

st.set_page_config(page_title="RD-Protokoll", layout="wide")
st.title("RD-Protokoll Generator (online)")
st.caption("⚠️ Keine Identdaten eingeben. Nur Werte/Befunde/Anamnese ohne Personenbezug.")

api_key = st.secrets.get("OPENAI_API_KEY", "")
client = OpenAI(api_key=api_key)


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


def create_response_with_retry(payload, max_retries=4):
    """
    Führt den OpenAI-Request mit einfachem Exponential Backoff aus.
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            return client.responses.create(**payload)

        except openai.RateLimitError as e:
            last_error = e
            if attempt == max_retries - 1:
                raise
            wait_time = min(2 ** attempt, 8)
            time.sleep(wait_time)

        except openai.APIConnectionError as e:
            last_error = e
            if attempt == max_retries - 1:
                raise
            wait_time = min(2 ** attempt, 8)
            time.sleep(wait_time)

        except openai.APITimeoutError as e:
            last_error = e
            if attempt == max_retries - 1:
                raise
            wait_time = min(2 ** attempt, 8)
            time.sleep(wait_time)

    if last_error:
        raise last_error


st.subheader("Vitalwerte (optional)")
c1, c2, c3, c4 = st.columns(4)

with c1:
    rr_sys = st.number_input("RR syst.", min_value=0, max_value=300, value=0, step=1)
    rr_dia = st.number_input("RR diast.", min_value=0, max_value=200, value=0, step=1)

with c2:
    puls = st.number_input("Puls", min_value=0, max_value=300, value=0, step=1)
    spo2 = st.number_input("SpO₂", min_value=0, max_value=100, value=0, step=1)

with c3:
    af = st.number_input("AF", min_value=0, max_value=80, value=0, step=1)
    temp_x10 = st.number_input("Temp x10 (z.B. 367=36.7)", min_value=0, max_value=450, value=0, step=1)

with c4:
    bz = st.number_input("BZ", min_value=0, max_value=1000, value=0, step=1)
    gcs = st.number_input("GCS", min_value=0, max_value=15, value=0, step=1)

vitals = {}
if rr_sys:
    vitals["RR_sys"] = int(rr_sys)
if rr_dia:
    vitals["RR_dia"] = int(rr_dia)
if puls:
    vitals["Puls"] = int(puls)
if spo2:
    vitals["SpO2"] = int(spo2)
if af:
    vitals["AF"] = int(af)
if temp_x10:
    vitals["Temp_C"] = round(temp_x10 / 10.0, 1)
if bz:
    vitals["BZ"] = int(bz)
if gcs:
    vitals["GCS"] = int(gcs)

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
    x_zusatz = st.text_input("xABCDE Zusatz (optional)", "", max_chars=300)

with b:
    st.subheader("SAMPLERS")
    s_symptome = st.text_input("S – Symptome (kurz)", "", max_chars=300)
    a_allergien = st.selectbox("A – Allergien", ["—", "keine bekannt", "vorhanden (siehe Zusatz)"])
    m_medis = st.selectbox("M – Medikamente", ["—", "keine", "regelmäßig (siehe Zusatz)"])
    p_vorg = st.selectbox("P – Vorgeschichte", ["—", "keine bekannt", "vorhanden (siehe Zusatz)"])
    e_ereignis = st.text_area(
        "E – Ereignis (kurz)",
        height=90,
        max_chars=1000,
        placeholder="Keine Namen, Adressen, Geburtsdaten oder Telefonnummern eingeben.",
    )
    samplers_zusatz = st.text_area(
        "SAMPLERS Zusatz (optional)",
        height=80,
        max_chars=1000,
        placeholder="Keine Identdaten eingeben.",
    )

with c:
    st.subheader("OPQRST")
    schmerz = st.selectbox("Schmerz vorhanden?", ["—", "nein", "ja"])
    o_onset = st.selectbox("O – Beginn", ["—", "plötzlich", "schleichend", "unbekannt"])
    q_quality = st.selectbox(
        "Q – Qualität",
        ["—", "drückend", "stechend", "brennend", "kolikartig", "dumpf", "unbekannt"],
    )
    s_nrs = st.selectbox("S – Stärke (NRS)", ["—"] + [str(i) for i in range(0, 11)])
    opqrst_zusatz = st.text_area("OPQRST Zusatz (optional)", height=80, max_chars=1000)

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
- Überschriften nur dann, wenn in diesem Abschnitt Daten vorhanden sind:
  1) Vitalwerte/Monitoring
  2) xABCDE
  3) SAMPLERS
  4) OPQRST
- Innerhalb der Abschnitte: kurze, sachliche Zeilen im RD-Stil.
- Keine Floskeln, keine Einleitung, kein Fazit.
- Keine Markdown-Sonderzeichen außer einfachen Überschriften als Klartext.
"""

st.divider()

if st.button("📝 Generieren", type="primary", use_container_width=True):
    if not api_key:
        st.error("OPENAI_API_KEY fehlt. In Streamlit Cloud unter App → Settings → Secrets eintragen.")
        st.stop()

    if not data:
        st.warning("Keine Werte ausgewählt oder eingegeben.")
        st.stop()

    user_prompt = "Daten (JSON):\n" + json.dumps(data, ensure_ascii=False, indent=2)

    payload = {
        "model": "gpt-4.1-mini",
        "input": [
            {"role": "system", "content": system_instructions.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
        "max_output_tokens": 900,
    }

    try:
        with st.spinner("Generiere Protokoll…"):
            resp = create_response_with_retry(payload)

        out_text = getattr(resp, "output_text", "") or ""

        if not out_text.strip():
            st.warning("Das Modell hat keine verwertbare Ausgabe geliefert.")
            st.stop()

        out_text = out_text.strip()

        st.subheader("Fertiges Protokoll")
        st.text_area("Ausgabe", out_text, height=420)

        st.download_button(
            "⬇️ Download als .txt",
            data=out_text.encode("utf-8"),
            file_name="rd_protokoll.txt",
            mime="text/plain",
            use_container_width=True,
        )

    except openai.RateLimitError:
        st.error(
            "OpenAI-Limit erreicht (zu viele Anfragen oder kein verfügbares Kontingent). "
            "Bitte kurz warten und erneut versuchen."
        )

    except openai.AuthenticationError:
        st.error("Authentifizierung fehlgeschlagen. Bitte OPENAI_API_KEY in den Streamlit-Secrets prüfen.")

    except openai.BadRequestError as e:
        st.error(f"Ungültige Anfrage an die API: {e}")

    except openai.APIConnectionError:
        st.error("Netzwerkfehler zur OpenAI-API. Bitte später erneut versuchen.")

    except openai.APITimeoutError:
        st.error("Zeitüberschreitung bei der Anfrage. Bitte erneut versuchen.")

    except openai.APIStatusError as e:
        st.error(f"OpenAI-API-Statusfehler: HTTP {e.status_code}")

    except Exception as e:
        st.error(f"Unerwarteter Fehler: {e}")

with st.expander("Debug: gesendete Daten"):
    st.code(json.dumps(data, ensure_ascii=False, indent=2), language="json")
