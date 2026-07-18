# NANA Backend

FastAPI-Backend fuer die NANA-App.

## Start

```powershell
uvicorn backend.main:app --reload --port 8000
```

Das Backend nutzt SQLite als lokale Datenbank.
Patientendaten werden nicht an externe Systeme uebertragen.
