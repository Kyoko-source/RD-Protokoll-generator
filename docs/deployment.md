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

## HTTPS mit Caddy

`deploy/caddy/Caddyfile.example` auf dem Server kopieren und `nana.example.de` durch die echte Domain ersetzen.
Caddy leitet dann HTTPS-Anfragen an `127.0.0.1:8000` weiter.

Wenn `deploy/docker-compose.https.example.yml` genutzt wird, spricht Caddy intern direkt mit `nana:8000`.

## Backup und Restore

Backup:

```powershell
powershell ./deploy/scripts/backup_nana.ps1
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
