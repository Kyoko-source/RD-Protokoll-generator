# NANA Backend

FastAPI-Grundgeruest fuer die spaetere NANA-App.

## Start

```powershell
uvicorn backend.main:app --reload --port 8000
```

Das Backend nutzt aktuell dieselbe SQLite-Datenbank wie der Streamlit-Prototyp.
Patientendaten werden nicht an externe Systeme uebertragen.
