# NANA

Notfall-Aufzeichnungs- und Nachbearbeitungs-Assistent.

## Aktueller Stand

- `App.py`: funktionierender Streamlit-Prototyp
- `backend/`: neues FastAPI-Backend fuer die kuenftige App
- `frontend/`: neues React/Vite-Frontend als PWA-Grundlage

Die neue App-Struktur wird parallel aufgebaut, damit der Prototyp weiter nutzbar bleibt.

## Lokal starten

PC:

```powershell
powershell.exe -ExecutionPolicy Bypass -File scripts\start_nana_app.ps1
```

Danach im Browser:

```text
http://127.0.0.1:5173
```

Handy im gleichen WLAN:

```powershell
.\NANA Handy starten.cmd
```

## Von ueberall erreichbar machen

Die Grundlage fuer einen sicheren Serverbetrieb liegt in:

- `Dockerfile`
- `docker-compose.production.example.yml`
- `deploy/docker-compose.https.example.yml`
- `deploy/caddy/Caddyfile.example`
- `deploy/env.production.example`
- `docs/deployment.md`

Fuer echte Nutzung mit Patientendaten nur mit HTTPS, EU-Hosting, externem `NANA_DATA_KEY`, Backups und AV-Vertrag betreiben.
