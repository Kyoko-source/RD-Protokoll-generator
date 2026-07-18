# NANA Production Readiness

Diese Checkliste ersetzt keine rechtliche Datenschutzpruefung, beschreibt aber die technischen Mindestpunkte fuer einen produktiven Betrieb.

## Pflicht vor Echtbetrieb

- `NANA_ENV=production` setzen.
- `NANA_DATA_KEY` ausserhalb der Datenbank sicher speichern und separat sichern.
- `NANA_ALLOWED_ORIGINS` auf die echte HTTPS-Domain setzen.
- `NANA_ALLOWED_HOSTS` auf echte Domain plus interne Healthcheck-Hosts setzen, z. B. `nana.example.de,localhost,127.0.0.1,nana`.
- `NANA_ENABLE_BEARER_AUTH=0` setzen; produktiv nur HttpOnly-Cookie-Sessions verwenden.
- Auth laeuft ueber HttpOnly-Cookies mit CSRF-Schutz.
- Neue Passwoerter muessen mindestens 14 Zeichen, Gross-/Kleinbuchstaben, Zahl und Sonderzeichen enthalten.
- `NANA_MAX_REQUEST_BODY_BYTES` passend klein halten; Standard ist 2 MiB.
- Einsatz-Zusammenfassungen, Patientendaten und Protokolltexte muessen verschluesselt in SQLite liegen.
- Audit-Details duerfen nur technische Allowlist-Felder enthalten, keine Patientendaten oder Freitexte.
- `deploy/backup.env` mit `BACKUP_PASSPHRASE` und `NANA_REQUIRE_ENCRYPTED_BACKUPS=1` anlegen.
- `nana-backup.timer` aktivieren und mindestens einen verschluesselten Backup-Testlauf pruefen.
- Restore mit `deploy/scripts/restore_nana.sh /opt/NANA/backups/<backup>.sqlite.gz.enc` in einer Testumgebung pruefen.
- Adminbereich: Aufbewahrungsfrist fuer Einsatzdaten und Sicherheitslogs festlegen.
- Adminbereich: externe Kartenlinks nur nach Datenschutzbewertung aktivieren.
- Caddy mit HTTPS, HSTS, CSP, Referrer-Policy, Permissions-Policy, X-Robots-Tag und no-store fuer Patientendaten betreiben.
- Zugriff auf Server, GitHub, SSH-Keys und Backups auf benoetigte Personen begrenzen.

## Regelbetrieb

- Backup-Status taeglich ueber `systemctl status nana-backup.timer` und `journalctl -u nana-backup.service` pruefen.
- Security-/Login-Logs nach festgelegter Frist im Adminbereich loeschen.
- Abgelaufene Einsatzdaten nach Aufbewahrungsfrist loeschen oder anonymisieren.
- Updates nur nach erfolgreichem `scripts/verify_nana.ps1` und `npm.cmd run build` im Ordner `frontend` deployen.
- Nach jedem Deployment `/api/health` pruefen: Datenbank ok, Frontend vorhanden, Verschluesselung aktiv, externer Datenschluessel im Produktionsbetrieb.
- Nach jedem Deployment `/api/health` pruefen: `security.bearer_auth_enabled=false` und `security.trusted_hosts_configured=true`.
- Nach jedem Deployment Login, Entwurf speichern, Einsatz abschliessen und PDF-Export kurz durchtesten.
- Restore-Probe regelmaessig dokumentieren.

## Datenschutz und Recht

- Verantwortlicher/Auftragsverarbeiter festlegen.
- AVV, TOMs, Datenschutzhinweise und Loeschkonzept freigeben lassen.
- DSFA fuer Gesundheitsdaten und mobilen Einsatzkontext durchfuehren.
- Kartenanbieter und Leitstellen-Schnittstelle vertraglich und technisch bewerten.
- Meldeprozess fuer Datenschutzvorfaelle dokumentieren.
