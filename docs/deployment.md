# NANA Deployment

Diese Dateien sind der Startpunkt fuer den Betrieb ueber eine eigene HTTPS-Domain.

## Zielbild

- NANA laeuft als ein Backend-Container.
- Das React/PWA-Frontend wird im Container gebaut und vom FastAPI-Backend ausgeliefert.
- Ein Reverse Proxy wie Caddy oder Nginx stellt HTTPS bereit.
- Die SQLite-Datenbank liegt in einem persistenten Volume.
- `NANA_DATA_KEY` liegt nur als Server-Secret vor und nie in Git.

## Produktionsvariablen

Pflicht:

```env
NANA_ENV=production
NANA_DB_PATH=/data/nana.db
NANA_DATA_KEY=<langer-zufaelliger-schluessel>
NANA_ALLOWED_ORIGINS=https://nana.example.de
```

`NANA_DATA_KEY` erzeugen:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Container bauen und starten

```powershell
docker compose -f docker-compose.production.example.yml up --build -d
```

Danach laeuft NANA lokal auf dem Server unter:

```text
http://127.0.0.1:8000
```

Nach vorne ins Internet sollte nur der HTTPS-Reverse-Proxy zeigen.

## HTTPS mit Caddy

`deploy/caddy/Caddyfile.example` auf dem Server kopieren und `nana.example.de` durch die echte Domain ersetzen.
Caddy leitet dann HTTPS-Anfragen an `127.0.0.1:8000` weiter.

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
