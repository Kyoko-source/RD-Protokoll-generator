# NANA Server-Setup

Diese Anleitung beschreibt den naechsten praktischen Schritt: NANA auf einem eigenen Ubuntu-Server mit Docker und HTTPS bereitstellen.

## Voraussetzungen

- Eigene Domain oder Subdomain, zum Beispiel `nana.example.de`
- DNS-A-Record zeigt auf die Server-IP
- Ubuntu-Server mit SSH-Zugriff
- Ports `80` und `443` sind beim Anbieter freigegeben
- AV-Vertrag und EU-Serverstandort klaeren, bevor echte Patientendaten genutzt werden

## 1. Server vorbereiten

Auf dem Server:

```bash
sudo bash deploy/scripts/bootstrap_ubuntu.sh
```

Das installiert Docker, Docker Compose, Git und setzt die Firewall auf SSH, HTTP und HTTPS.

## 2. Produktionskonfiguration erstellen

Lokal oder auf dem Server im Repo:

```powershell
powershell ./deploy/scripts/render_production_config.ps1 -Domain nana.example.de -Email admin@example.de
```

Dabei entstehen:

- `deploy/env.production`
- `deploy/caddy/Caddyfile`

Beide Dateien sind absichtlich durch `.gitignore` geschuetzt.

## 3. Starten

Auf dem Server im Repo:

```bash
bash deploy/scripts/deploy_server.sh
```

Danach sollte NANA ueber die Domain erreichbar sein:

```text
https://nana.example.de
```

## 4. Backup testen

```powershell
powershell ./deploy/scripts/backup_nana.ps1
```

Wichtig: Das Datenbank-Backup ist ohne den passenden `NANA_DATA_KEY` nicht sinnvoll wiederherstellbar. Den Schluessel separat sichern.

## 5. Update

Auf dem Server:

```bash
git pull
bash deploy/scripts/deploy_server.sh
```

## Datenschutz vor Produktivbetrieb

Dieses Setup ist eine technische Basis. Vor echten Patientendaten muessen mindestens Hostingvertrag/AVV, Berechtigungskonzept, Backup-Konzept, Wiederherstellungstest und organisatorische Datenschutzfreigabe geklaert sein.
