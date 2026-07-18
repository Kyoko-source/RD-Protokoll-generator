# NANA Deployment

Diese Dateien sind der Startpunkt fuer den Betrieb ueber eine eigene HTTPS-Domain.

## Zielbild

- NANA laeuft als ein Backend-Container.
- Das React/PWA-Frontend wird im Container gebaut und vom FastAPI-Backend ausgeliefert.
- Ein Reverse Proxy wie Caddy oder Nginx stellt HTTPS bereit.
- Die SQLite-Datenbank liegt in einem persistenten Volume.
- `NANA_DATA_KEY` liegt nur als Server-Secret vor und nie in Git.

Eine konkrete Server-Schrittfolge liegt in `docs/server_setup.md`.

## Produktionsvariablen

Pflicht:

```env
NANA_ENV=production
NANA_DB_PATH=/data/nana.db
NANA_DATA_KEY=<langer-zufaelliger-schluessel>
NANA_ALLOWED_ORIGINS=https://nana.example.de
NANA_ALLOWED_HOSTS=nana.example.de,localhost,127.0.0.1,nana
NANA_MAX_REQUEST_BODY_BYTES=2097152
NANA_ENABLE_BEARER_AUTH=0
```

Auf dem Server:

1. `deploy/env.production.example` nach `deploy/env.production` kopieren.
2. `nana.example.de` durch die echte Domain ersetzen.
3. `NANA_DATA_KEY` durch einen echten geheimen Wert ersetzen.
4. `deploy/caddy/Caddyfile.example` nach `deploy/caddy/Caddyfile` kopieren.
5. Domain und E-Mail-Adresse in der Caddyfile ersetzen.

Alternativ erstellt dieses Skript beide Dateien:

```powershell
powershell ./deploy/scripts/render_production_config.ps1 -Domain nana.example.de -Email admin@example.de
```

`NANA_DATA_KEY` erzeugen:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Container bauen und starten

Vor jedem Deployment lokal Backend, Datenbank und API pruefen:

```powershell
powershell.exe -ExecutionPolicy Bypass -File scripts\verify_nana.ps1
```

Frontend-Production-Build direkt im Frontend-Ordner pruefen:

```powershell
cd frontend
npm.cmd run build
cd ..
```

Wenn Docker lokal verfuegbar ist, zusaetzlich den Image-Build pruefen:

```powershell
powershell.exe -ExecutionPolicy Bypass -File scripts\verify_nana.ps1 -Docker
```

Nur NANA hinter externem Reverse Proxy:

```powershell
docker compose -f docker-compose.production.example.yml up --build -d
```

NANA plus Caddy/HTTPS auf demselben Server:

```powershell
docker compose -f deploy/docker-compose.https.example.yml up --build -d
```

Oder mit Pruefung der benoetigten Dateien:

```bash
bash deploy/scripts/deploy_server.sh
```

Danach laeuft NANA lokal auf dem Server unter:

```text
http://127.0.0.1:8000
```

Nach vorne ins Internet sollte nur der HTTPS-Reverse-Proxy zeigen.

## Server-Check nach Deployment

Nach jedem Server-Deployment pruefen:

```bash
docker compose -f deploy/docker-compose.https.example.yml ps
curl -fsS http://127.0.0.1:8000/api/health
```

Die Health-Antwort sollte mindestens zeigen:

- `status: ok`
- `database.ok: true`
- `frontend_ready: true`
- `encryption.enabled: true`
- `encryption.key_source: environment` im Produktionsbetrieb

Danach im Browser pruefen:

- Login funktioniert.
- Adminbereich laedt.
- Entwurf speichern funktioniert.
- Einsatz abschliessen funktioniert.
- PDF-Export funktioniert.
- Datenschutzseite zeigt den externen Datenschluessel als aktiv.

## HTTPS mit Caddy

`deploy/caddy/Caddyfile.example` auf dem Server kopieren und `nana.example.de` durch die echte Domain ersetzen.
Caddy leitet dann HTTPS-Anfragen an `127.0.0.1:8000` weiter.

Wenn `deploy/docker-compose.https.example.yml` genutzt wird, spricht Caddy intern direkt mit `nana:8000`.

## Backup und Restore

Backup:

```powershell
$env:BACKUP_PASSPHRASE="<lange-zufaellige-backup-passphrase>"
powershell ./deploy/scripts/backup_nana.ps1
```

Unverschluesselte lokale Entwicklungsbackups sind nur mit expliziter Bestaetigung moeglich:

```powershell
powershell ./deploy/scripts/backup_nana.ps1 -AllowPlaintextDevelopmentBackup
```

Restore:

```powershell
powershell ./deploy/scripts/restore_nana.ps1 -BackupFile ./backups/nana-db-YYYYMMDD-HHMMSS.sqlite
```

Wichtig: Das Backup ist nur mit dem passenden `NANA_DATA_KEY` voll nutzbar. Key und Datenbank getrennt, aber beide sicher aufbewahren.

## Datenschutz-Check vor echtem Patientendatenbetrieb

Vor produktiver Nutzung mit Patientendaten:

- EU-Serverstandort verwenden.
- AV-Vertrag mit Hosting-Anbieter abschliessen.
- Backups verschluesseln und Wiederherstellung testen.
- `NANA_DATA_KEY` separat vom Datenbank-Backup sichern.
- Admin-Zugang mit starkem Passwort und Rollenrechten verwenden.
- Zugriff nur ueber HTTPS erlauben.
- Audit-Log und Aufbewahrungsfristen regelmaessig pruefen.

Das ersetzt keine Rechtsberatung, ist aber die technische Mindestbasis fuer den naechsten Schritt.
