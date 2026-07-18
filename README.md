# NANA

Notfall-Aufzeichnungs- und Nachbearbeitungs-Assistent.

## Aktueller Stand

- `backend/`: FastAPI-Backend fuer API, Auth, Datenschutz, Protokolle und Serverbetrieb
- `frontend/`: React/Vite-Frontend als PWA

Die fruehere Streamlit-Version wurde entfernt. NANA laeuft jetzt ueber Backend und Frontend.

## Lokal starten

PC:

```powershell
powershell.exe -ExecutionPolicy Bypass -File scripts\start_nana_app.ps1
```

Vor Deployments pruefen:

```powershell
powershell.exe -ExecutionPolicy Bypass -File scripts\verify_nana.ps1
cd frontend
npm.cmd run build
cd ..
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
- `docs/server_setup.md`

Fuer echte Nutzung mit Patientendaten nur mit HTTPS, EU-Hosting, externem `NANA_DATA_KEY`, Backups und AV-Vertrag betreiben.
