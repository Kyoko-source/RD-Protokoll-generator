# Backend-Refactor-Plan

Ziel: `backend/main.py` bleibt als App-Factory/Einstiegspunkt klein. Fachlogik wandert in schmale Router und Services, damit Auth, Datenschutz, Protokollerstellung und Admin-Funktionen einzeln testbar bleiben.

## Zielstruktur

- `backend/app.py`: FastAPI-App, Middleware, Startup, Frontend-Serving.
- `backend/auth.py`: Login, Reauth, Passwortwechsel, aktuelle Session.
- `backend/admin.py`: Mitarbeitende, Ankuendigungen, Feedback, Admin-Ansichten.
- `backend/cases.py`: Entwuerfe, abgeschlossene Einsaetze, PDF-Export.
- `backend/privacy.py`: Datenschutzstatus, Aufbewahrung, Loeschlaeufe.
- `backend/protocols.py`: Protokolltext, Qualitaetspruefung, Verdachtsdiagnosen, Medikamente.
- `backend/interfaces_api.py`: Import/Export-Endpunkte fuer Leitstelle, Corpuls, NANA und FHIR.
- `backend/schemas.py`: Pydantic-Modelle ohne mutable Defaults.
- `backend/services/`: pure Fachfunktionen, die ohne FastAPI getestet werden koennen.

## Reihenfolge

1. Pydantic-Modelle nach `schemas.py` verschieben.
2. Auth-Endpunkte nach `auth.py` auslagern; Storage-Session-Funktionen bleiben in `storage.py`.
3. Protokoll-/Qualitaetslogik in `services/protocols.py` trennen.
4. Cases/PDF in `cases.py` verschieben.
5. Admin/Privacy/Interfaces in einzelne Router verschieben.
6. `main.py` auf App-Erstellung, Router-Registrierung und statisches Frontend reduzieren.

## Leitplanken

- Nach jedem Schritt `python -m unittest discover` und `python -m py_compile backend/main.py storage.py` ausfuehren.
- API-Pfade und Response-Felder stabil halten, damit das React-Frontend nicht gleichzeitig umgebaut werden muss.
- Erst nach dem Split groessere fachliche Aenderungen vornehmen.
