# NANA Production Readiness

Diese Checkliste ersetzt keine rechtliche Datenschutzpruefung, beschreibt aber die technischen Mindestpunkte fuer einen produktiven Betrieb.

## Pflicht vor Echtbetrieb

- `NANA_ENV=production` setzen.
- `NANA_DATA_KEY` ausserhalb der Datenbank sicher speichern und separat sichern.
- `deploy/backup.env` mit `BACKUP_PASSPHRASE` und `NANA_REQUIRE_ENCRYPTED_BACKUPS=1` anlegen.
- `nana-backup.timer` aktivieren und mindestens einen verschluesselten Backup-Testlauf pruefen.
- Restore mit `deploy/scripts/restore_nana.sh /opt/NANA/backups/<backup>.sqlite.gz.enc` in einer Testumgebung pruefen.
- Adminbereich: Aufbewahrungsfrist fuer Einsatzdaten und Sicherheitslogs festlegen.
- Adminbereich: externe Kartenlinks nur nach Datenschutzbewertung aktivieren.
- Caddy mit HTTPS, HSTS, CSP, Referrer-Policy und Permissions-Policy betreiben.
- Zugriff auf Server, GitHub, SSH-Keys und Backups auf benoetigte Personen begrenzen.

## Regelbetrieb

- Backup-Status taeglich ueber `systemctl status nana-backup.timer` und `journalctl -u nana-backup.service` pruefen.
- Security-/Login-Logs nach festgelegter Frist im Adminbereich loeschen.
- Abgelaufene Einsatzdaten nach Aufbewahrungsfrist loeschen oder anonymisieren.
- Updates nur nach erfolgreichem `python -m py_compile` und `npm run build` deployen.
- Restore-Probe regelmaessig dokumentieren.

## Datenschutz und Recht

- Verantwortlicher/Auftragsverarbeiter festlegen.
- AVV, TOMs, Datenschutzhinweise und Loeschkonzept freigeben lassen.
- DSFA fuer Gesundheitsdaten und mobilen Einsatzkontext durchfuehren.
- Kartenanbieter und Leitstellen-Schnittstelle vertraglich und technisch bewerten.
- Meldeprozess fuer Datenschutzvorfaelle dokumentieren.
