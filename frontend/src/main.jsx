import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  AlertTriangle,
  Building2,
  Cable,
  CheckCircle2,
  Download,
  FileText,
  HeartPulse,
  Lock,
  LogOut,
  Printer,
  RotateCcw,
  ShieldCheck,
  Stethoscope,
  Trash2,
  UserPlus,
  Wrench
} from 'lucide-react';
import './styles.css';

function resolveApiBase() {
  const configured = import.meta.env.VITE_API_BASE;
  if (configured !== undefined) return configured;
  if (window.location.port === '8000') return '';
  const host = window.location.hostname || '127.0.0.1';
  return `${window.location.protocol}//${host}:8000`;
}

const API_BASE = resolveApiBase();
const SESSION_TIMEOUT_MS = 20 * 60 * 1000;

function localDraftKey(employeeId) {
  return `nana_local_draft_${employeeId || 'unknown'}`;
}

function loadLocalDraft(employeeId) {
  try {
    const raw = localStorage.getItem(localDraftKey(employeeId));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveLocalDraft(employeeId, patient) {
  if (!employeeId || !patient) return null;
  const draft = {
    patient,
    updatedAt: new Date().toISOString(),
    source: 'browser'
  };
  localStorage.setItem(localDraftKey(employeeId), JSON.stringify(draft));
  return draft;
}

function clearLocalDraft(employeeId) {
  if (employeeId) {
    localStorage.removeItem(localDraftKey(employeeId));
  }
}

function hasValue(value) {
  return ![undefined, null, '', 'Keine Angabe'].includes(value) && !(Array.isArray(value) && value.length === 0);
}

const vitalStatusOptions = {
  spo2_status: ['Keine Angabe', 'Normal', 'Leicht erniedrigt', 'Kritisch erniedrigt', 'Nicht messbar'],
  af_status: ['Keine Angabe', 'Bradypnoe', 'Normal', 'Tachypnoe', 'Schwere Tachypnoe', 'Apnoe'],
  rr_status: ['Keine Angabe', 'Hypotonie', 'Normal', 'Leicht erhöht', 'Hypertonie', 'Hypertensive Krise', 'Nicht messbar'],
  puls_status: ['Keine Angabe', 'Bradykardie', 'Normal', 'Tachykardie', 'Starke Tachykardie', 'Nicht tastbar'],
  gcs_status: ['Keine Angabe', 'Normal', 'Leicht eingeschränkt', 'Mittelgradig eingeschränkt', 'Schwer eingeschränkt'],
  bz_status: ['Keine Angabe', 'Hypoglykämie', 'Normal', 'Hyperglykämie', 'Nicht messbar'],
  temperatur_status: ['Keine Angabe', 'Unterkühlung', 'Normal', 'Erhöht / subfebril', 'Fieber', 'Hohes Fieber', 'Nicht gemessen']
};

function addProtocolBlock(title, rows) {
  const documented = rows.filter(([, value]) => hasValue(value));
  if (documented.length === 0) return '';
  const lines = [`${title}`, '=================================================='];
  documented.forEach(([label, value]) => lines.push(`${label}: ${value}`));
  return `${lines.join('\n')}\n\n`;
}

function renderListBlock(title, items, formatter) {
  const lines = (Array.isArray(items) ? items : []).map(formatter).filter(hasValue);
  if (lines.length === 0) return '';
  return `${title}\n==================================================\n${lines.map((line) => `- ${line}`).join('\n')}\n\n`;
}

function generateLocalProtocolText(patient) {
  const vital = patient.vitalwerte || {};
  const x = patient.xabcde || {};
  const s = patient.samplers || {};
  const o = patient.opqrst || {};
  const amls = patient.amls || {};
  const measures = patient.massnahmen || {};
  const handover = patient.uebergabe || {};
  let text = 'NANA RETTUNGSDIENST-PROTOKOLL\n';
  text += '==================================================\n';
  text += `Lokal erzeugt am ${new Date().toLocaleString('de-DE')}\n`;
  text += 'Dokumentationsentwurf: vor Weitergabe fachlich pruefen.\n\n';
  text += addProtocolBlock('VITALWERTE & DEMOGRAPHIE', [
    ['Alter', vital.alter],
    ['Geschlecht', vital.geschlecht],
    ['RR', hasValue(vital.rr_sys) || hasValue(vital.rr_dia) ? `${vital.rr_sys || ''}/${vital.rr_dia || ''} mmHg` : ''],
    ['RR Einordnung', vital.rr_status],
    ['Puls', vital.puls],
    ['Puls Einordnung', vital.puls_status],
    ['SpO2', vital.spo2],
    ['SpO2 Einordnung', vital.spo2_status],
    ['Atemfrequenz', vital.af],
    ['Atemfrequenz Einordnung', vital.af_status],
    ['BZ', vital.bz],
    ['BZ Einordnung', vital.bz_status],
    ['Temperatur', vital.temperatur],
    ['Temperatur Einordnung', vital.temperatur_status],
    ['GCS', vital.gcs],
    ['GCS Einordnung', vital.gcs_status],
    ['Kurzbericht', vital.kurzbericht],
  ]);
  text += addProtocolBlock('xABCDE', [
    ['X Blutung', x.blutung],
    ['A Atemweg', x.atemweg],
    ['B Atmung', x.atmung],
    ['C Hautzeichen', x.haut],
    ['D AVPU', x.avpu],
    ['E Bodycheck', x.bodycheck],
    ['Auffaelligkeiten', x.bodycheck_text],
    ['BE-FAST Balance', x.befast_balance],
    ['BE-FAST Eyes', x.befast_eyes],
    ['BE-FAST Face', x.befast_face],
    ['BE-FAST Arms', x.befast_arms],
    ['BE-FAST Speech', x.befast_speech],
    ['BE-FAST Time', x.befast_time],
  ]);
  text += addProtocolBlock('SAMPLERS', [
    ['Symptome', s.symptome],
    ['Allergien', s.allergien],
    ['Medikamente', s.medikamente],
    ['Vorgeschichte', s.vorgeschichte],
    ['Letzte Aufnahme', s.letzte_aufnahme],
    ['Ereignis', s.ereignis],
    ['Risikofaktoren', s.risikofaktoren],
    ['Sonstiges', s.sonstiges],
  ]);
  text += addProtocolBlock('OPQRST', [
    ['Onset', o.onset],
    ['Provocation/Palliation', o.provocation],
    ['Quality', o.quality],
    ['Region/Radiation', o.region],
    ['Severity/NRS', o.severity],
    ['Time/Verlauf', o.time],
  ]);
  text += addProtocolBlock('AMLS / VERDACHTSDIAGNOSTIK', [
    ['Leitsymptom', amls.leitsymptom],
    ['Arbeitsdiagnose', amls.arbeitsdiagnose],
    ['Notizen/Begruendung', amls.notizen],
  ]);
  text += renderListBlock('Differenzialdiagnosen / Kandidaten', amls.custom_candidates, (item) => {
    const candidate = typeof item === 'string' ? { diagnose: item } : item || {};
    return [candidate.diagnose || candidate.name, candidate.hinweis || candidate.rationale].filter(hasValue).join(': ');
  });
  text += renderListBlock('AMLS-Ausschluesse / zurueckgestellt', amls.excluded, (item) => {
    const excluded = typeof item === 'string' ? { diagnose: item } : item || {};
    return [excluded.diagnose || excluded.name, excluded.begruendung || excluded.rationale].filter(hasValue).join(': ');
  });
  text += renderListBlock('MASSNAHMEN', measures.timeline, (item) => `${item.zeit || ''} - ${item.massnahme || ''}`.trim());
  text += renderListBlock('MEDIKATION', measures.medikation, (item) => `${item.zeit || ''} - ${item.medikament || ''} ${item.dosis || ''} ${item.weg || ''}`.trim());
  text += addProtocolBlock('UEBERGABE', [
    ['Ziel', handover.ziel],
    ['Text', handover.text],
  ]);
  return text.trim();
}

function api(path, options = {}, token = '') {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers ?? {})
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return fetch(`${API_BASE}${path}`, { ...options, headers })
    .then(async (response) => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (response.status === 404 && data.detail === 'Not Found') {
          throw new Error(`API-Endpunkt nicht gefunden: ${API_BASE || window.location.origin}${path}. Bitte NANA neu starten, damit Backend und App dieselbe Version nutzen.`);
        }
        throw new Error(data.detail || 'Anfrage fehlgeschlagen');
      }
      return data;
    })
    .catch((err) => {
      if (err instanceof TypeError) {
        throw new Error('Backend nicht erreichbar. Lokale Entwürfe bleiben im Browser erhalten.');
      }
      throw err;
    });
}

async function fileRequest(path, options = {}, token = '') {
  const headers = { ...(options.headers ?? {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (response.status === 404 && data.detail === 'Not Found') {
      throw new Error(`API-Endpunkt nicht gefunden: ${API_BASE || window.location.origin}${path}. Bitte NANA neu starten.`);
    }
    throw new Error(data.detail || 'Datei konnte nicht erstellt werden');
  }
  const disposition = response.headers.get('Content-Disposition') || '';
  const filenameMatch = disposition.match(/filename="([^"]+)"/);
  return {
    blob: await response.blob(),
    filename: filenameMatch?.[1] || 'nana-protokoll.pdf'
  };
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function printBlob(blob) {
  const url = URL.createObjectURL(blob);
  const printWindow = window.open(url, '_blank', 'noopener,noreferrer');
  if (printWindow) {
    printWindow.addEventListener('load', () => printWindow.print(), { once: true });
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function SystemStatus({ online, backendOnline, lastSync }) {
  const state = !online ? 'offline' : backendOnline ? 'online' : 'limited';
  const label = !online ? 'Offline' : backendOnline ? 'Backend verbunden' : 'Backend nicht erreichbar';
  return (
    <div className={`system-status system-${state}`}>
      <span>{label}</span>
      <small>{lastSync ? `Letzter Sync: ${lastSync}` : 'Noch kein Sync in dieser Sitzung'}</small>
    </div>
  );
}

const tileIcons = {
  protocol: FileText,
  hospital: Building2,
  icd10: Stethoscope,
  devices: Wrench,
  interfaces: Cable,
  admin: ShieldCheck
};

function Login({ onLogin }) {
  const [employees, setEmployees] = useState([]);
  const [employeeId, setEmployeeId] = useState('');
  const [password, setPassword] = useState('');
  const [adminName, setAdminName] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [pendingChange, setPendingChange] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api('/api/auth/employees')
      .then((data) => {
        setEmployees(data.employees || []);
        setEmployeeId(data.employees?.[0]?.id || '');
      })
      .catch((err) => setError(err.message));
  }, []);

  async function submitLogin(event) {
    event.preventDefault();
    setError('');
    try {
      const result = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ employee_id: employeeId, password })
      });
      if (result.status === 'password_change_required') {
        setPendingChange(result);
        return;
      }
      onLogin(result);
    } catch (err) {
      setError(err.message);
    }
  }

  async function submitFirstAdmin(event) {
    event.preventDefault();
    setError('');
    try {
      const result = await api('/api/auth/setup-first-admin', {
        method: 'POST',
        body: JSON.stringify({ name: adminName, password: adminPassword })
      });
      onLogin(result);
    } catch (err) {
      setError(err.message);
    }
  }

  async function submitPasswordChange(event) {
    event.preventDefault();
    setError('');
    try {
      const result = await api('/api/auth/set-password', {
        method: 'POST',
        body: JSON.stringify({ token: pendingChange.token, new_password: newPassword })
      });
      onLogin(result);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="login-shell">
      <section className="brand-panel">
        <div className="brand-mark">
          <span>NANA</span>
        </div>
        <p>Notfall-Aufzeichnungs- und Nachbearbeitungs-Assistent</p>
      </section>

      <section className="login-panel">
        <div className="panel-title">
          <Lock size={22} />
          <h1>{pendingChange ? 'Passwort setzen' : 'Mitarbeiter-Login'}</h1>
        </div>

        {pendingChange ? (
          <form onSubmit={submitPasswordChange}>
            <label>
              Neues Passwort
              <input
                type="password"
                value={newPassword}
                minLength={8}
                onChange={(event) => setNewPassword(event.target.value)}
                autoFocus
              />
            </label>
            <button type="submit">Passwort speichern</button>
          </form>
        ) : employees.length === 0 ? (
          <form onSubmit={submitFirstAdmin}>
            <label>
              Ersten Admin anlegen
              <input
                type="text"
                value={adminName}
                onChange={(event) => setAdminName(event.target.value)}
                placeholder="Name"
                autoFocus
              />
            </label>
            <label>
              Admin-Passwort
              <input
                type="password"
                value={adminPassword}
                minLength={8}
                onChange={(event) => setAdminPassword(event.target.value)}
              />
            </label>
            <button type="submit">Admin erstellen</button>
          </form>
        ) : (
          <form onSubmit={submitLogin}>
            <label>
              Mitarbeiter
              <select value={employeeId} onChange={(event) => setEmployeeId(event.target.value)}>
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.name} · {employee.role === 'admin' ? 'Admin' : 'Mitarbeiter'}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Passwort
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <button type="submit">Einloggen</button>
          </form>
        )}

        {error && <div className="error-box">{error}</div>}
      </section>
    </main>
  );
}

function Dashboard({ session, onLogout, connectivity, onSync }) {
  const [dashboard, setDashboard] = useState(null);
  const [cases, setCases] = useState([]);
  const [view, setView] = useState('home');
  const [error, setError] = useState('');
  const [statusText, setStatusText] = useState('');

  useEffect(() => {
    api('/api/dashboard', {}, session.token)
      .then(setDashboard)
      .catch((err) => setError(err.message));
    api('/api/cases', {}, session.token)
      .then((data) => setCases(data.cases || []))
      .catch(() => setCases([]));
  }, [session.token]);

  const employee = dashboard?.employee || session.employee;
  const tiles = dashboard?.tiles || [];
  const activeCases = useMemo(() => cases.filter((item) => item.status !== 'deleted'), [cases]);

  async function logout() {
    await api('/api/auth/logout', { method: 'POST' }, session.token).catch(() => {});
    onLogout();
  }

  async function downloadCasePdf(caseId) {
    setError('');
    setStatusText('');
    try {
      const file = await fileRequest(`/api/cases/${caseId}/pdf`, {}, session.token);
      downloadBlob(file.blob, file.filename);
      setStatusText('PDF wurde erstellt.');
    } catch (err) {
      setError(err.message);
    }
  }

  async function printCasePdf(caseId) {
    setError('');
    setStatusText('');
    try {
      const file = await fileRequest(`/api/cases/${caseId}/pdf`, {}, session.token);
      await api('/api/protocol/print-audit', {
        method: 'POST',
        body: JSON.stringify({ case_id: caseId, source: 'archive' })
      }, session.token).catch(() => {});
      printBlob(file.blob);
      setStatusText('Druckfenster wurde geöffnet.');
    } catch (err) {
      setError(err.message);
    }
  }

  if (view === 'protocol') {
    return <ProtocolView session={session} employee={employee} onBack={() => setView('home')} onLogout={logout} connectivity={connectivity} onSync={onSync} />;
  }

  if (view === 'hospital') {
    return <HospitalView session={session} employee={employee} onBack={() => setView('home')} onOpenProtocol={() => setView('protocol')} onLogout={logout} />;
  }

  if (view === 'icd10') {
    return <Icd10View session={session} employee={employee} onBack={() => setView('home')} onOpenProtocol={() => setView('protocol')} onLogout={logout} />;
  }

  if (view === 'devices') {
    return <DevicesView session={session} employee={employee} onBack={() => setView('home')} onLogout={logout} />;
  }

  if (view === 'interfaces') {
    return (
      <InterfacesView
        session={session}
        employee={employee}
        onBack={() => setView('home')}
        onOpenProtocol={() => setView('protocol')}
        onLogout={logout}
      />
    );
  }

  if (view === 'admin') {
    return <AdminView session={session} employee={employee} onBack={() => setView('home')} onLogout={logout} />;
  }

  return (
    <main className="app-shell">
      <SystemStatus {...connectivity} />
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">Notfall-Aufzeichnungs- und Nachbearbeitungs-Assistent</div>
        </div>
        <div className="user-area">
          <span>{employee?.name}</span>
          <button className="icon-button" onClick={logout} aria-label="Abmelden">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      {error && <div className="error-box">{error}</div>}
      {statusText && <div className="success-box">{statusText}</div>}

      <section className="status-band">
        <div>
          <ShieldCheck size={20} />
          <span>{employee?.role === 'admin' ? 'Admin-Profil' : 'Mitarbeiter-Profil'}</span>
        </div>
        <div>
          <Activity size={20} />
          <span>{activeCases.length} archivierte Einsätze sichtbar</span>
        </div>
        <div>
          <HeartPulse size={20} />
          <span>Streamlit-Prototyp bleibt parallel verfügbar</span>
        </div>
      </section>

      <section className="tile-grid">
        {tiles.map((tile) => {
          const Icon = tileIcons[tile.id] || FileText;
          return (
            <button
              className={`tile tile-${tile.id}`}
              key={tile.id}
              onClick={() => {
                if (tile.id === 'protocol') setView('protocol');
                if (tile.id === 'hospital') setView('hospital');
                if (tile.id === 'icd10') setView('icd10');
                if (tile.id === 'devices') setView('devices');
                if (tile.id === 'interfaces') setView('interfaces');
                if (tile.id === 'admin') setView('admin');
              }}
            >
              <Icon size={32} />
              <span>{tile.label}</span>
              <small>{tile.subtitle}</small>
            </button>
          );
        })}
      </section>

      <section className="work-panel">
        <div className="section-head">
          <h2>Archiv</h2>
          <span>{activeCases.length} Fälle</span>
        </div>
        <div className="case-list">
          {activeCases.length === 0 ? (
            <p className="muted">Noch keine abgeschlossenen Einsätze sichtbar.</p>
          ) : (
            activeCases.slice(0, 6).map((item) => (
              <article className="case-row archive-row" key={item.id}>
                <div>
                  <strong>{item.summary}</strong>
                  <span>{item.completed_at}</span>
                </div>
                <span className={`status-pill status-${item.status}`}>{item.status}</span>
                <button type="button" onClick={() => downloadCasePdf(item.id)}>
                  <Download size={16} /> PDF
                </button>
                <button type="button" onClick={() => printCasePdf(item.id)}>
                  <Printer size={16} /> Drucken
                </button>
              </article>
            ))
          )}
        </div>
      </section>
    </main>
  );
}

function InterfacesView({ session, employee, onBack, onOpenProtocol, onLogout }) {
  const [cases, setCases] = useState([]);
  const [source, setSource] = useState('dispatch');
  const [payload, setPayload] = useState('');
  const [importResult, setImportResult] = useState(null);
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api('/api/cases', {}, session.token)
      .then((data) => setCases(data.cases || []))
      .catch((err) => setError(err.message));
  }, [session.token]);

  async function importPayload() {
    setError('');
    setStatusText('');
    setImportResult(null);
    try {
      const result = await api('/api/admin/interfaces/import', {
        method: 'POST',
        body: JSON.stringify({ source, payload })
      }, session.token);
      setImportResult(result);
      setStatusText(`Import übernommen: ${Object.keys(result.imported || {}).length} Felder.`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function exportDraft(format) {
    setError('');
    setStatusText('');
    try {
      const file = await fileRequest(`/api/admin/interfaces/export/draft/${format}`, {}, session.token);
      downloadBlob(file.blob, file.filename);
      setStatusText(`Entwurf als ${format.toUpperCase()} exportiert.`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function exportCase(caseId, format) {
    setError('');
    setStatusText('');
    try {
      const file = await fileRequest(`/api/admin/interfaces/export/cases/${caseId}/${format}`, {}, session.token);
      downloadBlob(file.blob, file.filename);
      setStatusText(`Einsatz als ${format.toUpperCase()} exportiert.`);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="app-shell">
      <SystemStatus {...connectivity} />
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">Schnittstellen · Import und Export</div>
        </div>
        <div className="user-area">
          <span>{employee?.name}</span>
          <button className="icon-button" onClick={onLogout} aria-label="Abmelden">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      <section className="protocol-toolbar">
        <button type="button" onClick={onBack}>Zurück zum Hauptmenü</button>
        <button type="button" onClick={onOpenProtocol}>Zum Protokoll</button>
      </section>

      {error && <div className="error-box">{error}</div>}
      {statusText && <div className="success-box">{statusText}</div>}

      <section className="interface-grid">
        <article className="work-panel">
          <div className="section-head">
            <h2>Import</h2>
            <span>Admin-only</span>
          </div>
          <div className="interface-import">
            <label>
              Quelle
              <select value={source} onChange={(event) => setSource(event.target.value)}>
                <option value="dispatch">Leitstelle JSON/CSV/Text</option>
                <option value="corpuls">Corpuls/Monitor JSON</option>
              </select>
            </label>
            <label>
              Importdaten
              <textarea
                value={payload}
                onChange={(event) => setPayload(event.target.value)}
                placeholder={'einsatznummer: 12345\nstichwort: Brustschmerz\nadresse: Musterstrasse 1\nort: Borken'}
                rows={12}
              />
            </label>
            <button type="button" onClick={importPayload}>Import ins Protokoll übernehmen</button>
          </div>
          {importResult && (
            <div className="import-result">
              {Object.entries(importResult.imported || {}).map(([key, value]) => (
                <div key={key}>
                  <strong>{key}</strong>
                  <span>{String(value)}</span>
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="work-panel">
          <div className="section-head">
            <h2>Entwurf exportieren</h2>
            <span>NANA / FHIR</span>
          </div>
          <div className="export-actions">
            <button type="button" onClick={() => exportDraft('nana')}>
              <Download size={16} /> NANA JSON
            </button>
            <button type="button" onClick={() => exportDraft('fhir')}>
              <Download size={16} /> FHIR Bundle
            </button>
          </div>
          <div className="privacy-list">
            <div>
              <strong>Leitstellen-Import</strong>
              <span>JSON, CSV oder Text mit Feldnamen wird in Einsatzdaten übernommen.</span>
            </div>
            <div>
              <strong>Corpuls-Vorbereitung</strong>
              <span>JSON-Vitaldaten werden in den Vitalwerte-Abschnitt übernommen.</span>
            </div>
            <div>
              <strong>Audit</strong>
              <span>Jeder Import und Export wird im Audit-Log gespeichert.</span>
            </div>
          </div>
        </article>
      </section>

      <section className="work-panel">
        <div className="section-head">
          <h2>Archiv exportieren</h2>
          <span>{cases.length} Einsätze</span>
        </div>
        <div className="case-list">
          {cases.length === 0 ? (
            <p className="muted">Keine exportierbaren Einsätze vorhanden.</p>
          ) : cases.slice(0, 12).map((item) => (
            <article className="case-row interface-case-row" key={item.id}>
              <div>
                <strong>{item.summary}</strong>
                <span>{item.completed_at} · {item.employee_name || 'anonym'}</span>
              </div>
              <span className={`status-pill status-${item.status}`}>{item.status}</span>
              <button type="button" onClick={() => exportCase(item.id, 'nana')}>
                <Download size={16} /> NANA
              </button>
              <button type="button" onClick={() => exportCase(item.id, 'fhir')}>
                <Download size={16} /> FHIR
              </button>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

function HospitalView({ session, employee, onBack, onOpenProtocol, onLogout }) {
  const [town, setTown] = useState('Borken');
  const [category, setCategory] = useState('Allgemeine Notaufnahme');
  const [data, setData] = useState({ towns: [], categories: [], hospitals: [] });
  const [patient, setPatient] = useState(emptyPatient);
  const [newHospital, setNewHospital] = useState({ name: '', country: 'DE', address: '', town: '', phone: '', categories: [] });
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');

  async function loadHospitals(nextTown = town, nextCategory = category) {
    setError('');
    try {
      const [hospitalData, draftData] = await Promise.all([
        api(`/api/hospitals?town=${encodeURIComponent(nextTown)}&category=${encodeURIComponent(nextCategory)}`, {}, session.token),
        api('/api/draft', {}, session.token)
      ]);
      setData(hospitalData);
      setPatient({ ...emptyPatient, ...(draftData.patient || {}) });
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadHospitals();
  }, [session.token]);

  async function selectHospital(hospital) {
    setError('');
    setStatusText('');
    const nextPatient = {
      ...patient,
      transport: {
        ...(patient.transport || {}),
        hospital_id: hospital.id,
        hospital_name: hospital.name,
        hospital_country: hospital.country,
        hospital_address: hospital.address,
        distance_km: hospital.distance_km,
        category,
        town
      },
      uebergabe: {
        ...(patient.uebergabe || {}),
        ziel: hospital.name
      }
    };
    try {
      await api('/api/draft', {
        method: 'PUT',
        body: JSON.stringify({ patient: nextPatient })
      }, session.token);
      setPatient(nextPatient);
      setStatusText(`${hospital.name} wurde ins Protokoll übernommen.`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function saveHospital(event) {
    event.preventDefault();
    setError('');
    setStatusText('');
    try {
      await api('/api/admin/hospitals', {
        method: 'POST',
        body: JSON.stringify(newHospital)
      }, session.token);
      setNewHospital({ name: '', country: 'DE', address: '', town: '', phone: '', categories: [] });
      setStatusText('Klinik wurde gespeichert.');
      await loadHospitals();
    } catch (err) {
      setError(err.message);
    }
  }

  function toggleNewHospitalCategory(item) {
    setNewHospital((current) => {
      const categories = current.categories.includes(item)
        ? current.categories.filter((entry) => entry !== item)
        : [...current.categories, item];
      return { ...current, categories };
    });
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">Krankenhaus Finder · Zielklinik wählen</div>
        </div>
        <div className="user-area">
          <span>{employee?.name}</span>
          <button className="icon-button" onClick={onLogout} aria-label="Abmelden"><LogOut size={18} /></button>
        </div>
      </header>

      <section className="protocol-toolbar">
        <button type="button" onClick={onBack}>Zurück zum Hauptmenü</button>
        <button type="button" onClick={onOpenProtocol}>Zum Protokoll</button>
      </section>

      {error && <div className="error-box">{error}</div>}
      {statusText && <div className="success-box">{statusText}</div>}

      <section className="finder-controls">
        <label>
          Standort
          <select value={town} onChange={(event) => { setTown(event.target.value); loadHospitals(event.target.value, category); }}>
            {(data.towns || []).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>
          Leitsymptom / Fachrichtung
          <select value={category} onChange={(event) => { setCategory(event.target.value); loadHospitals(town, event.target.value); }}>
            {(data.categories || []).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
      </section>

      <section className="hospital-grid">
        {(data.hospitals || []).map((hospital) => (
          <article className="hospital-card" key={hospital.id}>
            <div className="hospital-meta">
              <span>{hospital.country}</span>
              <span>{hospital.distance_km ?? '-'} km</span>
              <span>{hospital.estimated_minutes ?? '-'} min</span>
            </div>
            <h2>{hospital.name}</h2>
            <p>{hospital.address}</p>
            {hospital.phone && <p>{hospital.phone}</p>}
            <div className="tag-list">
              {(hospital.categories || []).slice(0, 5).map((item) => <span key={item}>{item}</span>)}
            </div>
            <button type="button" onClick={() => selectHospital(hospital)}>Als Ziel übernehmen</button>
          </article>
        ))}
      </section>

      {employee?.role === 'admin' && (
        <section className="work-panel">
          <div className="section-head">
            <h2>Klinik pflegen</h2>
            <span>Admin</span>
          </div>
          <form className="hospital-admin-form" onSubmit={saveHospital}>
            <input value={newHospital.name} onChange={(event) => setNewHospital({ ...newHospital, name: event.target.value })} placeholder="Klinikname" />
            <input value={newHospital.address} onChange={(event) => setNewHospital({ ...newHospital, address: event.target.value })} placeholder="Adresse" />
            <input value={newHospital.phone} onChange={(event) => setNewHospital({ ...newHospital, phone: event.target.value })} placeholder="Telefon" />
            <select value={newHospital.country} onChange={(event) => setNewHospital({ ...newHospital, country: event.target.value })}>
              <option value="DE">DE</option>
              <option value="NL">NL</option>
            </select>
            <div className="check-grid">
              {(data.categories || []).map((item) => (
                <label key={item}>
                  <input type="checkbox" checked={newHospital.categories.includes(item)} onChange={() => toggleNewHospitalCategory(item)} />
                  {item}
                </label>
              ))}
            </div>
            <button type="submit">Klinik speichern</button>
          </form>
        </section>
      )}
    </main>
  );
}

function Icd10View({ session, employee, onBack, onOpenProtocol, onLogout }) {
  const [code, setCode] = useState('');
  const [result, setResult] = useState(null);
  const [patient, setPatient] = useState(emptyPatient);
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api('/api/draft', {}, session.token)
      .then((data) => setPatient({ ...emptyPatient, ...(data.patient || {}) }))
      .catch((err) => setError(err.message));
  }, [session.token]);

  async function lookup() {
    setError('');
    setStatusText('');
    try {
      const data = await api('/api/icd10/lookup', {
        method: 'POST',
        body: JSON.stringify({ code })
      }, session.token);
      setResult(data);
    } catch (err) {
      setError(err.message);
    }
  }

  async function applyIcd() {
    if (!result) return;
    const nextPatient = {
      ...patient,
      einweisung: {
        ...(patient.einweisung || {}),
        icd_code: result.code,
        diagnose: result.diagnosis
      }
    };
    try {
      await api('/api/draft', {
        method: 'PUT',
        body: JSON.stringify({ patient: nextPatient })
      }, session.token);
      setPatient(nextPatient);
      setStatusText('ICD10 wurde ins Protokoll übernommen.');
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">ICD10 Code · Dekodierer</div>
        </div>
        <div className="user-area">
          <span>{employee?.name}</span>
          <button className="icon-button" onClick={onLogout} aria-label="Abmelden"><LogOut size={18} /></button>
        </div>
      </header>
      <section className="protocol-toolbar">
        <button type="button" onClick={onBack}>Zurück zum Hauptmenü</button>
        <button type="button" onClick={onOpenProtocol}>Zum Protokoll</button>
      </section>
      {error && <div className="error-box">{error}</div>}
      {statusText && <div className="success-box">{statusText}</div>}
      <section className="work-panel icd-panel">
        <div className="section-head">
          <h2>ICD10 suchen</h2>
          <span>lokaler Grundkatalog</span>
        </div>
        <div className="icd-search">
          <input value={code} onChange={(event) => setCode(event.target.value)} placeholder="z.B. I21.9, I63, R55" />
          <button type="button" onClick={lookup}>Dekodieren</button>
        </div>
        {result && (
          <div className="icd-result">
            <strong>{result.code}</strong>
            <span>{result.diagnosis}</span>
            <small>{result.found ? `Treffer über ${result.matched_code}` : 'Bitte fachlich prüfen und ggf. manuell ergänzen.'}</small>
            <button type="button" onClick={applyIcd}>Ins Protokoll übernehmen</button>
          </div>
        )}
      </section>
    </main>
  );
}

function DevicesView({ session, employee, onBack, onLogout }) {
  const [devices, setDevices] = useState([]);
  const [selectedName, setSelectedName] = useState('');
  const [selectedTopic, setSelectedTopic] = useState('');
  const [stepIndex, setStepIndex] = useState(0);
  const [error, setError] = useState('');

  useEffect(() => {
    api('/api/devices', {}, session.token)
      .then((data) => {
        const nextDevices = data.devices || [];
        setDevices(nextDevices);
        setSelectedName(nextDevices[0]?.name || '');
        setSelectedTopic(Object.keys(nextDevices[0]?.topics || {})[0] || '');
      })
      .catch((err) => setError(err.message));
  }, [session.token]);

  const selectedDevice = devices.find((item) => item.name === selectedName) || {};
  const topicNames = Object.keys(selectedDevice.topics || {});
  const steps = selectedDevice.topics?.[selectedTopic] || [];
  const currentStep = steps[Math.min(stepIndex, Math.max(steps.length - 1, 0))] || '';

  function selectDevice(name) {
    const device = devices.find((item) => item.name === name) || {};
    const firstTopic = Object.keys(device.topics || {})[0] || '';
    setSelectedName(name);
    setSelectedTopic(firstTopic);
    setStepIndex(0);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">Geräte · Kurzreferenzen</div>
        </div>
        <div className="user-area">
          <span>{employee?.name}</span>
          <button className="icon-button" onClick={onLogout} aria-label="Abmelden"><LogOut size={18} /></button>
        </div>
      </header>
      <section className="protocol-toolbar">
        <button type="button" onClick={onBack}>Zurück zum Hauptmenü</button>
      </section>
      {error && <div className="error-box">{error}</div>}
      <section className="device-layout">
        <aside className="work-panel device-list">
          {devices.map((device) => (
            <button type="button" className={device.name === selectedName ? 'active' : ''} key={device.name} onClick={() => selectDevice(device.name)}>
              <span>{device.icon}</span>
              <strong>{device.name}</strong>
            </button>
          ))}
        </aside>
        <section className="work-panel device-detail">
          <div className="section-head">
            <h2>{selectedDevice.icon} {selectedDevice.name}</h2>
            <span>{selectedDevice.source_label}</span>
          </div>
          <p className="muted">{selectedDevice.model_note}</p>
          <select value={selectedTopic} onChange={(event) => { setSelectedTopic(event.target.value); setStepIndex(0); }}>
            {topicNames.map((topic) => <option key={topic} value={topic}>{topic}</option>)}
          </select>
          <div className="device-step">
            <span>Schritt {steps.length ? stepIndex + 1 : 0} / {steps.length}</span>
            <p>{currentStep}</p>
          </div>
          <div className="device-step-actions">
            <button type="button" onClick={() => setStepIndex(Math.max(0, stepIndex - 1))} disabled={stepIndex === 0}>Zurück</button>
            <button type="button" onClick={() => setStepIndex(Math.min(steps.length - 1, stepIndex + 1))} disabled={stepIndex >= steps.length - 1}>Weiter</button>
          </div>
        </section>
      </section>
    </main>
  );
}

function AdminView({ session, employee, onBack, onLogout }) {
  const [employees, setEmployees] = useState([]);
  const [auditEvents, setAuditEvents] = useState([]);
  const [privacy, setPrivacy] = useState(null);
  const [qualityRules, setQualityRules] = useState([]);
  const [cases, setCases] = useState([]);
  const [newName, setNewName] = useState('');
  const [newRole, setNewRole] = useState('employee');
  const [retentionDays, setRetentionDays] = useState(3650);
  const [temporaryPassword, setTemporaryPassword] = useState('');
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');
  const exportEvents = auditEvents.filter((event) => event.action.includes('pdf') || event.action.includes('print'));

  async function loadAdminData() {
    setError('');
    try {
      const [employeeData, auditData, privacyData, caseData] = await Promise.all([
        api('/api/admin/employees', {}, session.token),
        api('/api/admin/audit', {}, session.token),
        api('/api/admin/privacy', {}, session.token),
        api('/api/cases', {}, session.token)
      ]);
      const qualityData = await api('/api/admin/quality-rules', {}, session.token).catch(() => ({ rules: [] }));
      setEmployees(employeeData.employees || []);
      setAuditEvents(auditData.events || []);
      setPrivacy(privacyData);
      setQualityRules(qualityData.rules || []);
      setRetentionDays(privacyData.retention_days || 3650);
      setCases(caseData.cases || []);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadAdminData();
  }, [session.token]);

  async function createEmployee(event) {
    event.preventDefault();
    setError('');
    setStatusText('');
    setTemporaryPassword('');
    try {
      const result = await api('/api/admin/employees', {
        method: 'POST',
        body: JSON.stringify({ name: newName, role: newRole })
      }, session.token);
      setTemporaryPassword(`${result.employee.name}: ${result.temporary_password}`);
      setStatusText('Mitarbeiterprofil wurde angelegt.');
      setNewName('');
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function updateEmployee(item, changes) {
    setError('');
    setStatusText('');
    setTemporaryPassword('');
    try {
      const result = await api(`/api/admin/employees/${item.id}`, {
        method: 'PUT',
        body: JSON.stringify(changes)
      }, session.token);
      if (result.temporary_password) {
        setTemporaryPassword(`${result.employee.name}: ${result.temporary_password}`);
      }
      setStatusText('Mitarbeiterprofil wurde aktualisiert.');
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function saveRetention() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/admin/privacy', {
        method: 'PUT',
        body: JSON.stringify({ retention_days: Number(retentionDays) })
      }, session.token);
      setStatusText(`Aufbewahrung gesetzt: ${result.retention_days} Tage.`);
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function anonymizeCase(caseId) {
    setError('');
    setStatusText('');
    try {
      await api(`/api/admin/cases/${caseId}/anonymize`, { method: 'POST' }, session.token);
      setStatusText('Einsatz wurde anonymisiert.');
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteCase(caseId) {
    setError('');
    setStatusText('');
    try {
      await api(`/api/admin/cases/${caseId}`, { method: 'DELETE' }, session.token);
      setStatusText('Einsatz wurde gelöscht.');
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">Admin · Datenschutz & Benutzerverwaltung</div>
        </div>
        <div className="user-area">
          <span>{employee?.name}</span>
          <button className="icon-button" onClick={onLogout} aria-label="Abmelden">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      <section className="protocol-toolbar">
        <button type="button" onClick={onBack}>Zurück zum Hauptmenü</button>
        <button type="button" onClick={loadAdminData}>Aktualisieren</button>
      </section>

      {error && <div className="error-box">{error}</div>}
      {statusText && <div className="success-box">{statusText}</div>}
      {temporaryPassword && (
        <div className="secret-box">
          <strong>Einmalpasswort nur jetzt anzeigen:</strong>
          <code>{temporaryPassword}</code>
        </div>
      )}

      <section className="admin-grid">
        <article className="work-panel">
          <div className="section-head">
            <h2>Mitarbeiter</h2>
            <span>{employees.length} Profile</span>
          </div>
          <form className="inline-form" onSubmit={createEmployee}>
            <input value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="Name" />
            <select value={newRole} onChange={(event) => setNewRole(event.target.value)}>
              <option value="employee">Mitarbeiter</option>
              <option value="admin">Admin</option>
            </select>
            <button type="submit"><UserPlus size={17} /> Anlegen</button>
          </form>
          <div className="admin-list">
            {employees.map((item) => (
              <div className="admin-row" key={item.id}>
                <div>
                  <strong>{item.name}</strong>
                  <span>{item.role === 'admin' ? 'Admin' : 'Mitarbeiter'} · {item.active ? 'aktiv' : 'gesperrt'}</span>
                </div>
                <select value={item.role} onChange={(event) => updateEmployee(item, { role: event.target.value })}>
                  <option value="employee">Mitarbeiter</option>
                  <option value="admin">Admin</option>
                </select>
                <button type="button" onClick={() => updateEmployee(item, { active: !item.active })}>
                  {item.active ? 'Sperren' : 'Aktivieren'}
                </button>
                <button type="button" onClick={() => updateEmployee(item, { reset_password: true })}>
                  <RotateCcw size={16} /> OTP
                </button>
              </div>
            ))}
          </div>
        </article>

        <article className="work-panel">
          <div className="section-head">
            <h2>Datenschutz</h2>
            <span>{privacy?.encryption?.enabled ? 'Verschlüsselung aktiv' : 'Prüfen'}</span>
          </div>
          <div className="privacy-list">
            <div>
              <strong>Speicher-Schutz</strong>
              <span>{privacy?.encryption?.provider || 'wird geladen'}</span>
            </div>
            <div>
              <strong>Schlüsselquelle</strong>
              <span>{privacy?.encryption?.key_source || '-'}</span>
            </div>
            <div>
              <strong>Sitzungssperre</strong>
              <span>{privacy?.session_minutes || 30} Minuten Backend · 20 Minuten Oberfläche</span>
            </div>
            <div>
              <strong>Audit-Log</strong>
              <span>{privacy?.audit_events || 0} letzte Ereignisse abrufbar</span>
            </div>
          </div>
          <div className="inline-form">
            <input value={retentionDays} onChange={(event) => setRetentionDays(event.target.value)} inputMode="numeric" />
            <button type="button" onClick={saveRetention}>Aufbewahrung speichern</button>
          </div>
          <p className="muted">{privacy?.encryption?.production_hint}</p>
        </article>
      </section>

      <section className="work-panel">
        <div className="section-head">
          <h2>Fall-Datenschutz</h2>
          <span>{cases.length} Einsätze</span>
        </div>
        <div className="case-list">
          {cases.length === 0 ? (
            <p className="muted">Keine Fälle vorhanden.</p>
          ) : cases.slice(0, 12).map((item) => (
            <article className="case-row case-row-actions" key={item.id}>
              <div>
                <strong>{item.summary}</strong>
                <span>{item.completed_at} · {item.employee_name || 'anonym'}</span>
              </div>
              <span className={`status-pill status-${item.status}`}>{item.status}</span>
              <button type="button" onClick={() => anonymizeCase(item.id)}>Anonymisieren</button>
              <button type="button" className="danger-button" onClick={() => deleteCase(item.id)}>
                <Trash2 size={16} /> Löschen
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="work-panel">
        <div className="section-head">
          <h2>QS-Regeln</h2>
          <span>{qualityRules.length} aktiv</span>
        </div>
        <div className="rules-grid">
          {qualityRules.map((rule) => (
            <div className={`rule-card rule-${rule.severity}`} key={rule.id}>
              <strong>{rule.label}</strong>
              <span>{rule.section} · {rule.severity}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="work-panel">
        <div className="section-head">
          <h2>Audit-Log</h2>
          <span>letzte Ereignisse</span>
        </div>
        <div className="audit-list">
          {auditEvents.slice(0, 10).map((event, index) => (
            <div className="audit-row" key={`${event.timestamp}-${index}`}>
              <strong>{event.action}</strong>
              <span>{event.timestamp} · {event.employee_name || 'System'} · {event.entity_type || '-'}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="work-panel">
        <div className="section-head">
          <h2>Exporthistorie</h2>
          <span>{exportEvents.length} Ereignisse</span>
        </div>
        <div className="audit-list">
          {exportEvents.length === 0 ? (
            <p className="muted">Noch keine PDF- oder Druckereignisse im Audit-Log.</p>
          ) : exportEvents.slice(0, 12).map((event, index) => (
            <div className="audit-row" key={`export-${event.timestamp}-${index}`}>
              <strong>{event.action}</strong>
              <span>{event.timestamp} · {event.employee_name || 'System'} · {event.entity_id || event.entity_type || '-'}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

const emptyPatient = {
  vitalwerte: {},
  xabcde: {},
  samplers: {},
  opqrst: {},
  einweisung: {},
  amls: { excluded: [], custom_candidates: [], arbeitsdiagnose: '', leitsymptom: '', notizen: '' },
  massnahmen: { timeline: [], medikation: [] },
  transport: {},
  einsatz: {},
  uebergabe: {}
};

function ProtocolView({ session, employee, onBack, onLogout, connectivity, onSync }) {
  const [patient, setPatient] = useState(emptyPatient);
  const [protocolSection, setProtocolSection] = useState('vitalwerte');
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');
  const [generatedProtocol, setGeneratedProtocol] = useState('');
  const [qualityResult, setQualityResult] = useState(null);
  const [forceFinish, setForceFinish] = useState(false);
  const [localDraft, setLocalDraft] = useState(() => loadLocalDraft(employee?.id));
  const [draftReady, setDraftReady] = useState(false);
  const [suspicionResult, setSuspicionResult] = useState(null);
  const [amlsSuggestions, setAmlsSuggestions] = useState([]);
  const [calculator, setCalculator] = useState({ sop: 'Anaphylaxie (SOPKB0105)', age: '30', weight: '70', pregnant: 'Nein', bz: '55', rr_sys: '160', nrs: '7' });
  const [calculatorResult, setCalculatorResult] = useState(null);
  const vitalwerte = patient.vitalwerte || {};
  const xabcde = patient.xabcde || {};
  const samplers = patient.samplers || {};
  const opqrst = patient.opqrst || {};
  const massnahmen = patient.massnahmen || { timeline: [], medikation: [] };
  const amls = patient.amls || {};
  const uebergabe = patient.uebergabe || {};
  const amlsCandidates = Array.isArray(amls.custom_candidates) ? amls.custom_candidates : [];
  const amlsExcluded = Array.isArray(amls.excluded) ? amls.excluded : [];
  const amlsExcludedNames = new Set(amlsExcluded.map((item) => (
    typeof item === 'string' ? item : item?.diagnose || item?.name || ''
  )).filter(Boolean));
  const amlsVisibleCandidates = amlsSuggestions.length > 0 ? amlsSuggestions : amlsCandidates.map((item) => {
    const candidate = typeof item === 'string' ? { diagnose: item } : item || {};
    return {
      name: candidate.diagnose || candidate.name || '',
      category: 'Eigene Ergänzung',
      rationale: candidate.hinweis || candidate.rationale || 'Manuell ergänzt',
      conflicts: [],
      status: amlsExcludedNames.has(candidate.diagnose || candidate.name || '') ? 'excluded' : 'matching',
    };
  }).filter((item) => item.name);
  const amlsRemainingCandidates = amlsVisibleCandidates.filter((item) => !amlsExcludedNames.has(item.name));
  const amlsMatchingCount = amlsVisibleCandidates.filter((item) => !amlsExcludedNames.has(item.name) && !(item.conflicts || []).length).length;
  const amlsCheckCount = amlsVisibleCandidates.filter((item) => !amlsExcludedNames.has(item.name) && (item.conflicts || []).length).length;

  useEffect(() => {
    api('/api/draft', {}, session.token)
      .then((data) => {
        setPatient({ ...emptyPatient, ...(data.patient || {}) });
        setDraftReady(true);
        const syncTime = data.updated_at || new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
        onSync?.(syncTime);
      })
      .catch((err) => {
        const fallback = loadLocalDraft(employee?.id);
        if (fallback?.patient) {
          setPatient({ ...emptyPatient, ...fallback.patient });
          setLocalDraft(fallback);
          setStatusText('Backend nicht erreichbar. Lokaler Entwurf wurde geladen.');
        } else {
          setError(err.message);
        }
        setDraftReady(true);
      });
  }, [session.token, employee?.id]);

  useEffect(() => {
    if (!draftReady) return;
    const saved = saveLocalDraft(employee?.id, patient);
    if (saved) {
      setLocalDraft(saved);
    }
  }, [patient, draftReady, employee?.id]);

  useEffect(() => {
    if (protocolSection === 'amls' && amlsSuggestions.length === 0) {
      loadAmlsSuggestions();
    }
  }, [protocolSection]);

  function restoreLocalDraft() {
    const draft = loadLocalDraft(employee?.id);
    if (draft?.patient) {
      setPatient({ ...emptyPatient, ...draft.patient });
      setLocalDraft(draft);
      setStatusText(`Lokaler Entwurf wiederhergestellt: ${new Date(draft.updatedAt).toLocaleString('de-DE')}`);
    }
  }

  function discardLocalDraft() {
    clearLocalDraft(employee?.id);
    setLocalDraft(null);
    setStatusText('Lokaler Entwurf wurde verworfen.');
  }

  function updateVital(key, value) {
    setPatient((current) => ({
      ...current,
      vitalwerte: {
        ...(current.vitalwerte || {}),
        [key]: value
      }
    }));
  }

  function updateXabcde(key, value) {
    setPatient((current) => ({
      ...current,
      xabcde: {
        ...(current.xabcde || {}),
        [key]: value
      }
    }));
  }

  function updateSamplers(key, value) {
    setPatient((current) => ({
      ...current,
      samplers: {
        ...(current.samplers || {}),
        [key]: value
      }
    }));
  }

  function updateOpqrst(key, value) {
    setPatient((current) => ({
      ...current,
      opqrst: {
        ...(current.opqrst || {}),
        [key]: value
      }
    }));
  }

  function updateAmls(key, value) {
    setPatient((current) => ({
      ...current,
      amls: {
        ...(current.amls || {}),
        [key]: value
      }
    }));
  }

  function addAmlsCandidate() {
    setPatient((current) => ({
      ...current,
      amls: {
        ...(current.amls || {}),
        excluded: Array.isArray((current.amls || {}).excluded) ? (current.amls || {}).excluded : [],
        custom_candidates: [
          ...(Array.isArray((current.amls || {}).custom_candidates) ? (current.amls || {}).custom_candidates : []),
          { diagnose: '', hinweis: '' }
        ]
      }
    }));
  }

  function updateAmlsCandidate(index, key, value) {
    setPatient((current) => {
      const candidates = [...(Array.isArray((current.amls || {}).custom_candidates) ? (current.amls || {}).custom_candidates : [])];
      const existing = candidates[index];
      candidates[index] = typeof existing === 'string' ? { diagnose: existing, [key]: value } : { ...(existing || {}), [key]: value };
      return { ...current, amls: { ...(current.amls || {}), custom_candidates: candidates } };
    });
  }

  function removeAmlsCandidate(index) {
    setPatient((current) => {
      const candidates = [...(Array.isArray((current.amls || {}).custom_candidates) ? (current.amls || {}).custom_candidates : [])];
      candidates.splice(index, 1);
      return { ...current, amls: { ...(current.amls || {}), custom_candidates: candidates } };
    });
  }

  function addAmlsExcluded() {
    setPatient((current) => ({
      ...current,
      amls: {
        ...(current.amls || {}),
        custom_candidates: Array.isArray((current.amls || {}).custom_candidates) ? (current.amls || {}).custom_candidates : [],
        excluded: [
          ...(Array.isArray((current.amls || {}).excluded) ? (current.amls || {}).excluded : []),
          { diagnose: '', begruendung: '' }
        ]
      }
    }));
  }

  function updateAmlsExcluded(index, key, value) {
    setPatient((current) => {
      const excluded = [...(Array.isArray((current.amls || {}).excluded) ? (current.amls || {}).excluded : [])];
      const existing = excluded[index];
      excluded[index] = typeof existing === 'string' ? { diagnose: existing, [key]: value } : { ...(existing || {}), [key]: value };
      return { ...current, amls: { ...(current.amls || {}), excluded } };
    });
  }

  function removeAmlsExcluded(index) {
    setPatient((current) => {
      const excluded = [...(Array.isArray((current.amls || {}).excluded) ? (current.amls || {}).excluded : [])];
      excluded.splice(index, 1);
      return { ...current, amls: { ...(current.amls || {}), excluded } };
    });
  }

  function resetAmlsFunnel() {
    setPatient((current) => ({
      ...current,
      amls: { ...(current.amls || {}), excluded: [], custom_candidates: [], arbeitsdiagnose: '', leitsymptom: '', notizen: '' }
    }));
  }

  function updateUebergabe(key, value) {
    setPatient((current) => ({
      ...current,
      uebergabe: {
        ...(current.uebergabe || {}),
        [key]: value
      }
    }));
  }

  function addMeasure() {
    setPatient((current) => ({
      ...current,
      massnahmen: {
        ...(current.massnahmen || {}),
        timeline: [...((current.massnahmen || {}).timeline || []), { zeit: '', massnahme: '' }],
        medikation: ((current.massnahmen || {}).medikation || [])
      }
    }));
  }

  function updateMeasure(index, key, value) {
    setPatient((current) => {
      const timeline = [...(((current.massnahmen || {}).timeline) || [])];
      timeline[index] = { ...(timeline[index] || {}), [key]: value };
      return {
        ...current,
        massnahmen: {
          ...(current.massnahmen || {}),
          timeline,
          medikation: ((current.massnahmen || {}).medikation || [])
        }
      };
    });
  }

  function removeMeasure(index) {
    setPatient((current) => {
      const timeline = [...(((current.massnahmen || {}).timeline) || [])];
      timeline.splice(index, 1);
      return { ...current, massnahmen: { ...(current.massnahmen || {}), timeline } };
    });
  }

  function addMedication() {
    setPatient((current) => ({
      ...current,
      massnahmen: {
        ...(current.massnahmen || {}),
        timeline: ((current.massnahmen || {}).timeline || []),
        medikation: [...((current.massnahmen || {}).medikation || []), { zeit: '', medikament: '', dosis: '', weg: '' }]
      }
    }));
  }

  function updateMedication(index, key, value) {
    setPatient((current) => {
      const medikation = [...(((current.massnahmen || {}).medikation) || [])];
      medikation[index] = { ...(medikation[index] || {}), [key]: value };
      return {
        ...current,
        massnahmen: {
          ...(current.massnahmen || {}),
          timeline: ((current.massnahmen || {}).timeline || []),
          medikation
        }
      };
    });
  }

  function removeMedication(index) {
    setPatient((current) => {
      const medikation = [...(((current.massnahmen || {}).medikation) || [])];
      medikation.splice(index, 1);
      return { ...current, massnahmen: { ...(current.massnahmen || {}), medikation } };
    });
  }

  async function runSuspicionAssessment() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/protocol/suspicion', {
        method: 'POST',
        body: JSON.stringify({ patient })
      }, session.token);
      setSuspicionResult(result);
      setStatusText('Verdacht wurde aus den dokumentierten Daten aktualisiert.');
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadAmlsSuggestions() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/protocol/amls-candidates', {
        method: 'POST',
        body: JSON.stringify({ patient })
      }, session.token);
      setAmlsSuggestions(result.candidates || []);
      setStatusText('AMLS-Kandidaten wurden aus den Befunden abgeleitet.');
    } catch (err) {
      setError(err.message);
    }
  }

  function applyAmlsSuggestion(item) {
    const name = item?.name || '';
    if (!name) return;
    setPatient((current) => {
      const currentAmls = current.amls || {};
      const candidates = Array.isArray(currentAmls.custom_candidates) ? currentAmls.custom_candidates : [];
      const exists = candidates.some((entry) => (typeof entry === 'string' ? entry : entry?.diagnose || entry?.name) === name);
      return {
        ...current,
        amls: {
          ...currentAmls,
          custom_candidates: exists ? candidates : [...candidates, { diagnose: name, hinweis: item.rationale || item.category || '' }]
        }
      };
    });
    setStatusText(`${name} wurde in den AMLS-Trichter übernommen.`);
  }

  function toggleAmlsExclusion(item) {
    const name = item?.name || '';
    if (!name) return;
    const isExcluded = amlsExcludedNames.has(name);
    if (!isExcluded && amlsRemainingCandidates.length <= 1) {
      setStatusText('Der letzte Kandidat bleibt im Trichter. Du kannst ihn als Arbeitsdiagnose übernehmen.');
      return;
    }
    setPatient((current) => {
      const currentAmls = current.amls || {};
      const excluded = Array.isArray(currentAmls.excluded) ? currentAmls.excluded : [];
      const nextExcluded = isExcluded
        ? excluded.filter((entry) => (typeof entry === 'string' ? entry : entry?.diagnose || entry?.name || '') !== name)
        : [...excluded, name];
      return {
        ...current,
        amls: {
          ...currentAmls,
          excluded: nextExcluded,
          arbeitsdiagnose: currentAmls.arbeitsdiagnose === name && !isExcluded ? '' : currentAmls.arbeitsdiagnose
        }
      };
    });
    setStatusText(isExcluded ? `${name} wurde zurück in den Trichter geholt.` : `${name} wurde im AMLS-Trichter zurückgestellt.`);
  }

  function adoptAmlsDiagnosis(name) {
    if (!name) return;
    updateAmls('arbeitsdiagnose', name);
    setStatusText(`${name} wurde als Arbeitsdiagnose übernommen.`);
  }

  async function calculateMedication() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/protocol/medication-calculator', {
        method: 'POST',
        body: JSON.stringify({
          sop: calculator.sop,
          age: Number(calculator.age || vitalwerte.alter || 30),
          weight: Number(calculator.weight || 70),
          pregnant: calculator.pregnant,
          inputs: {
            bz: Number(calculator.bz || 55),
            rr_sys: Number(calculator.rr_sys || vitalwerte.rr_sys || 160),
            nrs: Number(calculator.nrs || opqrst.severity || 7)
          }
        })
      }, session.token);
      setCalculatorResult(result);
      setStatusText('SOP-Rechner wurde aktualisiert.');
    } catch (err) {
      setError(err.message);
    }
  }

  function addCalculatedMedication(text) {
    setPatient((current) => ({
      ...current,
      massnahmen: {
        ...(current.massnahmen || {}),
        timeline: ((current.massnahmen || {}).timeline || []),
        medikation: [...(((current.massnahmen || {}).medikation) || []), { zeit: '', medikament: text, dosis: '', weg: 'laut SOP-Rechner' }]
      }
    }));
    setStatusText('Medikation wurde in das Protokoll übernommen.');
  }

  async function saveDraft() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/draft', {
        method: 'PUT',
        body: JSON.stringify({ patient })
      }, session.token);
      setStatusText(`Entwurf gespeichert: ${result.updated_at}`);
      onSync?.(result.updated_at);
      const saved = saveLocalDraft(employee?.id, patient);
      setLocalDraft(saved);
    } catch (err) {
      const saved = saveLocalDraft(employee?.id, patient);
      setLocalDraft(saved);
      setError(`${err.message} Lokale Sicherung wurde aktualisiert.`);
    }
  }

  async function generateProtocol() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/protocol/preview', {
        method: 'POST',
        body: JSON.stringify({ patient })
      }, session.token);
      setGeneratedProtocol(result.protocol_text || '');
      setProtocolSection('protokoll');
      setStatusText('Protokoll wurde erzeugt.');
    } catch (err) {
      const fallback = generateLocalProtocolText(patient);
      if (fallback) {
        setGeneratedProtocol(fallback);
        setProtocolSection('protokoll');
        setStatusText('Protokoll wurde lokal erzeugt. Backend bitte neu starten, damit PDF/Archiv wieder die aktuelle API nutzen.');
        setError(err.message);
      } else {
        setError(err.message);
      }
    }
  }

  async function checkQuality() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/protocol/quality', {
        method: 'POST',
        body: JSON.stringify({ patient })
      }, session.token);
      setQualityResult(result);
      setForceFinish(false);
      setProtocolSection('protokoll');
      setStatusText(`QS geprüft: ${result.score} Punkte.`);
      return result;
    } catch (err) {
      setError(err.message);
      return null;
    }
  }

  async function finishCase() {
    setError('');
    setStatusText('');
    try {
      const quality = qualityResult || await checkQuality();
      if (quality && (quality.warning_count > 0 || quality.critical_count > 0) && !forceFinish) {
        setProtocolSection('protokoll');
        setStatusText('Bitte Warnungen prüfen. Danach kann der Einsatz bewusst mit Warnungen beendet werden.');
        setForceFinish(true);
        return;
      }
      const result = await api('/api/cases/finish', {
        method: 'POST',
        body: JSON.stringify({ patient, force_finish: forceFinish })
      }, session.token);
      setGeneratedProtocol(result.protocol_text || '');
      setQualityResult(result.quality || qualityResult);
      setPatient(emptyPatient);
      clearLocalDraft(employee?.id);
      setLocalDraft(null);
      setProtocolSection('protokoll');
      setForceFinish(false);
      const warningText = result.quality?.warning_count || result.quality?.critical_count ? ' mit QS-Warnungen' : '';
      setStatusText(`Einsatz${warningText} beendet und archiviert: ${result.case_id}`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function exportDraftPdf() {
    setError('');
    setStatusText('');
    try {
      const file = await fileRequest('/api/protocol/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient })
      }, session.token);
      downloadBlob(file.blob, file.filename);
      setStatusText('PDF wurde erstellt.');
    } catch (err) {
      setError(err.message);
    }
  }

  async function printDraftPdf() {
    setError('');
    setStatusText('');
    try {
      const file = await fileRequest('/api/protocol/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient })
      }, session.token);
      await api('/api/protocol/print-audit', {
        method: 'POST',
        body: JSON.stringify({ source: 'draft' })
      }, session.token).catch(() => {});
      printBlob(file.blob);
      setStatusText('Druckfenster wurde geöffnet.');
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">Protokoll · Vitalwerte & Demographie</div>
        </div>
        <div className="user-area">
          <span>{employee?.name}</span>
          <button className="icon-button" onClick={onLogout} aria-label="Abmelden">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      <section className="protocol-toolbar">
        <button type="button" onClick={onBack}>Zurück zum Hauptmenü</button>
        <button type="button" onClick={checkQuality}><CheckCircle2 size={16} /> QS prüfen</button>
        <button type="button" onClick={generateProtocol}>Protokoll generieren</button>
        <button type="button" onClick={exportDraftPdf}><Download size={16} /> PDF</button>
        <button type="button" onClick={printDraftPdf}><Printer size={16} /> Drucken</button>
        <button type="button" onClick={saveDraft}>Entwurf speichern</button>
        <button type="button" onClick={finishCase}>{forceFinish ? 'Mit Warnungen beenden' : 'Einsatz beenden'}</button>
      </section>

      {error && <div className="error-box">{error}</div>}
      {statusText && <div className="success-box">{statusText}</div>}
      {localDraft && (
        <section className="offline-draft-box">
          <div>
            <strong>Lokale Sicherung vorhanden</strong>
            <span>{new Date(localDraft.updatedAt).toLocaleString('de-DE')}</span>
          </div>
          <button type="button" onClick={restoreLocalDraft}>Lokalen Entwurf wiederherstellen</button>
          <button type="button" onClick={discardLocalDraft}>Lokalen Entwurf verwerfen</button>
        </section>
      )}

      <section className="protocol-tabs">
        <button
          type="button"
          className={protocolSection === 'vitalwerte' ? 'active' : ''}
          onClick={() => setProtocolSection('vitalwerte')}
        >
          Vitalwerte
        </button>
        <button
          type="button"
          className={protocolSection === 'xabcde' ? 'active' : ''}
          onClick={() => setProtocolSection('xabcde')}
        >
          xABCDE
        </button>
        <button
          type="button"
          className={protocolSection === 'samplers' ? 'active' : ''}
          onClick={() => setProtocolSection('samplers')}
        >
          SAMPLERS
        </button>
        <button
          type="button"
          className={protocolSection === 'opqrst' ? 'active' : ''}
          onClick={() => setProtocolSection('opqrst')}
        >
          OPQRST
        </button>
        <button
          type="button"
          className={protocolSection === 'verdacht' ? 'active' : ''}
          onClick={() => setProtocolSection('verdacht')}
        >
          Verdacht
        </button>
        <button
          type="button"
          className={protocolSection === 'amls' ? 'active' : ''}
          onClick={() => setProtocolSection('amls')}
        >
          AMLS
        </button>
        <button
          type="button"
          className={protocolSection === 'rechner' ? 'active' : ''}
          onClick={() => setProtocolSection('rechner')}
        >
          Rechner
        </button>
        <button
          type="button"
          className={protocolSection === 'massnahmen' ? 'active' : ''}
          onClick={() => setProtocolSection('massnahmen')}
        >
          Maßnahmen
        </button>
        <button
          type="button"
          className={protocolSection === 'abschluss' ? 'active' : ''}
          onClick={() => setProtocolSection('abschluss')}
        >
          Abschluss
        </button>
        <button
          type="button"
          className={protocolSection === 'protokoll' ? 'active' : ''}
          onClick={() => setProtocolSection('protokoll')}
        >
          Protokoll
        </button>
      </section>

      {protocolSection === 'vitalwerte' && <section className="work-panel">
        <div className="section-head">
          <h2>Vitalwerte & Demographie</h2>
          <span>Entwurf pro Mitarbeiter</span>
        </div>

        <div className="form-grid">
          <label>
            Alter
            <input value={vitalwerte.alter || ''} onChange={(event) => updateVital('alter', event.target.value)} inputMode="numeric" />
          </label>
          <label>
            Geschlecht
            <select value={vitalwerte.geschlecht || ''} onChange={(event) => updateVital('geschlecht', event.target.value)}>
              <option value="">Keine Angabe</option>
              <option value="männlich">männlich</option>
              <option value="weiblich">weiblich</option>
              <option value="divers">divers</option>
            </select>
          </label>
          <label>
            RR systolisch
            <input value={vitalwerte.rr_sys || ''} onChange={(event) => updateVital('rr_sys', event.target.value)} inputMode="numeric" />
          </label>
          <label>
            RR diastolisch
            <input value={vitalwerte.rr_dia || ''} onChange={(event) => updateVital('rr_dia', event.target.value)} inputMode="numeric" />
          </label>
          <label>
            RR Einordnung
            <select value={vitalwerte.rr_status || 'Keine Angabe'} onChange={(event) => updateVital('rr_status', event.target.value)}>
              {vitalStatusOptions.rr_status.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label>
            Puls
            <input value={vitalwerte.puls || ''} onChange={(event) => updateVital('puls', event.target.value)} inputMode="numeric" />
          </label>
          <label>
            Puls Einordnung
            <select value={vitalwerte.puls_status || 'Keine Angabe'} onChange={(event) => updateVital('puls_status', event.target.value)}>
              {vitalStatusOptions.puls_status.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label>
            SpO2
            <input value={vitalwerte.spo2 || ''} onChange={(event) => updateVital('spo2', event.target.value)} inputMode="numeric" />
          </label>
          <label>
            SpO2 Einordnung
            <select value={vitalwerte.spo2_status || 'Keine Angabe'} onChange={(event) => updateVital('spo2_status', event.target.value)}>
              {vitalStatusOptions.spo2_status.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label>
            Atemfrequenz
            <input value={vitalwerte.af || ''} onChange={(event) => updateVital('af', event.target.value)} inputMode="numeric" />
          </label>
          <label>
            Atemfrequenz Einordnung
            <select value={vitalwerte.af_status || 'Keine Angabe'} onChange={(event) => updateVital('af_status', event.target.value)}>
              {vitalStatusOptions.af_status.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label>
            BZ
            <input value={vitalwerte.bz || ''} onChange={(event) => updateVital('bz', event.target.value)} inputMode="numeric" />
          </label>
          <label>
            BZ Einordnung
            <select value={vitalwerte.bz_status || 'Keine Angabe'} onChange={(event) => updateVital('bz_status', event.target.value)}>
              {vitalStatusOptions.bz_status.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label>
            Temperatur
            <input value={vitalwerte.temperatur || ''} onChange={(event) => updateVital('temperatur', event.target.value)} inputMode="decimal" />
          </label>
          <label>
            Temperatur Einordnung
            <select value={vitalwerte.temperatur_status || 'Keine Angabe'} onChange={(event) => updateVital('temperatur_status', event.target.value)}>
              {vitalStatusOptions.temperatur_status.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label>
            GCS
            <input value={vitalwerte.gcs || ''} onChange={(event) => updateVital('gcs', event.target.value)} inputMode="numeric" />
          </label>
          <label>
            GCS Einordnung
            <select value={vitalwerte.gcs_status || 'Keine Angabe'} onChange={(event) => updateVital('gcs_status', event.target.value)}>
              {vitalStatusOptions.gcs_status.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
        </div>

        <label className="wide-field">
          Kurzbericht
          <textarea value={vitalwerte.kurzbericht || ''} onChange={(event) => updateVital('kurzbericht', event.target.value)} rows={5} />
        </label>
      </section>}

      {protocolSection === 'xabcde' && <section className="work-panel">
        <div className="section-head">
          <h2>xABCDE Erstbeurteilung</h2>
          <span>strukturiert nach Priorität</span>
        </div>

        <div className="assessment-grid">
          <fieldset>
            <legend>X · Blutung</legend>
            <label>
              Blutung
              <select value={xabcde.blutung || ''} onChange={(event) => updateXabcde('blutung', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Keine starke Blutung">Keine starke Blutung</option>
                <option value="Starke Blutung kontrolliert">Starke Blutung kontrolliert</option>
                <option value="Starke Blutung unkontrolliert">Starke Blutung unkontrolliert</option>
              </select>
            </label>
            <label>
              Lokalisation
              <input value={xabcde.blutung_lokalisation || ''} onChange={(event) => updateXabcde('blutung_lokalisation', event.target.value)} />
            </label>
          </fieldset>

          <fieldset>
            <legend>A · Atemweg</legend>
            <label>
              Atemweg
              <select value={xabcde.atemweg || ''} onChange={(event) => updateXabcde('atemweg', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Frei">Frei</option>
                <option value="Gefährdet">Gefährdet</option>
                <option value="Verlegt">Verlegt</option>
              </select>
            </label>
            <label>
              HWS / Stabilisierung
              <select value={xabcde.hws || ''} onChange={(event) => updateXabcde('hws', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Keine Immobilisation">Keine Immobilisation</option>
                <option value="Stifneck">Stifneck</option>
                <option value="Vakuummatratze">Vakuummatratze</option>
              </select>
            </label>
          </fieldset>

          <fieldset>
            <legend>B · Atmung</legend>
            <label>
              Atmung
              <select value={xabcde.atmung || ''} onChange={(event) => updateXabcde('atmung', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Unauffällig">Unauffällig</option>
                <option value="Dyspnoe">Dyspnoe</option>
                <option value="Bradypnoe">Bradypnoe</option>
                <option value="Tachypnoe">Tachypnoe</option>
                <option value="Apnoe">Apnoe</option>
              </select>
            </label>
            <label>
              Atemgeräusche
              <select value={xabcde.atemgeraeusche || ''} onChange={(event) => updateXabcde('atemgeraeusche', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Beidseits vorhanden">Beidseits vorhanden</option>
                <option value="Links abgeschwächt">Links abgeschwächt</option>
                <option value="Rechts abgeschwächt">Rechts abgeschwächt</option>
                <option value="Keine">Keine</option>
              </select>
            </label>
            <label>
              Sauerstofftherapie
              <select value={xabcde.sauerstoff || ''} onChange={(event) => updateXabcde('sauerstoff', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Keine">Keine</option>
                <option value="2 l/min">2 l/min</option>
                <option value="4 l/min">4 l/min</option>
                <option value="6 l/min">6 l/min</option>
                <option value="10 l/min">10 l/min</option>
                <option value="15 l/min">15 l/min</option>
              </select>
            </label>
          </fieldset>

          <fieldset>
            <legend>C · Kreislauf</legend>
            <label>
              Hautzeichen
              <select value={xabcde.haut || ''} onChange={(event) => updateXabcde('haut', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Rosig / warm">Rosig / warm</option>
                <option value="Blass">Blass</option>
                <option value="Kalt / schweißig">Kalt / schweißig</option>
                <option value="Zyanotisch">Zyanotisch</option>
              </select>
            </label>
            <label>
              Rekapillarisierungszeit
              <select value={xabcde.rekap || ''} onChange={(event) => updateXabcde('rekap', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="< 2 Sekunden">&lt; 2 Sekunden</option>
                <option value="> 2 Sekunden">&gt; 2 Sekunden</option>
              </select>
            </label>
            <label>
              Pulsqualität
              <select value={xabcde.pulsqualitaet || ''} onChange={(event) => updateXabcde('pulsqualitaet', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Kräftig">Kräftig</option>
                <option value="Schwach">Schwach</option>
                <option value="Fadenförmig">Fadenförmig</option>
              </select>
            </label>
          </fieldset>

          <fieldset>
            <legend>D · Neurologie</legend>
            <label>
              AVPU
              <select value={xabcde.avpu || ''} onChange={(event) => updateXabcde('avpu', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="A">A</option>
                <option value="V">V</option>
                <option value="P">P</option>
                <option value="U">U</option>
              </select>
            </label>
            <label>
              Pupillen
              <select value={xabcde.pupillen || ''} onChange={(event) => updateXabcde('pupillen', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Isokor">Isokor</option>
                <option value="Anisokor">Anisokor</option>
                <option value="Lichtstarr">Lichtstarr</option>
              </select>
            </label>
            <label>
              BE-FAST Balance
              <select value={xabcde.befast_balance || ''} onChange={(event) => updateXabcde('befast_balance', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Unauffällig">Unauffällig</option>
                <option value="Akute Gang-/Standunsicherheit">Akute Gang-/Standunsicherheit</option>
                <option value="Akuter Schwindel / Ataxie">Akuter Schwindel / Ataxie</option>
              </select>
            </label>
            <label>
              BE-FAST Face
              <select value={xabcde.befast_face || ''} onChange={(event) => updateXabcde('befast_face', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Symmetrisch">Symmetrisch</option>
                <option value="Fazialisparese links">Fazialisparese links</option>
                <option value="Fazialisparese rechts">Fazialisparese rechts</option>
              </select>
            </label>
            <label>
              BE-FAST Speech
              <select value={xabcde.befast_speech || ''} onChange={(event) => updateXabcde('befast_speech', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Unauffällig">Unauffällig</option>
                <option value="Dysarthrie">Dysarthrie</option>
                <option value="Aphasie">Aphasie</option>
                <option value="Sprachverständnis gestört">Sprachverständnis gestört</option>
              </select>
            </label>
            <label>
              BE-FAST Eyes
              <select value={xabcde.befast_eyes || ''} onChange={(event) => updateXabcde('befast_eyes', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Unauffällig">Unauffällig</option>
                <option value="Akute Sehstörung">Akute Sehstörung</option>
                <option value="Doppelbilder">Doppelbilder</option>
                <option value="Gesichtsfeldausfall">Gesichtsfeldausfall</option>
              </select>
            </label>
            <label>
              BE-FAST Arms
              <select value={xabcde.befast_arms || ''} onChange={(event) => updateXabcde('befast_arms', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Kein Absinken">Kein Absinken</option>
                <option value="Armabsinken links">Armabsinken links</option>
                <option value="Armabsinken rechts">Armabsinken rechts</option>
                <option value="Armabsinken beidseits">Armabsinken beidseits</option>
              </select>
            </label>
            <label>
              BE-FAST Time / Symptombeginn
              <input value={xabcde.befast_time || ''} onChange={(event) => updateXabcde('befast_time', event.target.value)} />
            </label>
          </fieldset>

          <fieldset>
            <legend>E · Exposure</legend>
            <label>
              Bodycheck
              <select value={xabcde.bodycheck || ''} onChange={(event) => updateXabcde('bodycheck', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Unauffällig">Unauffällig</option>
                <option value="Auffällig">Auffällig</option>
                <option value="Nicht vollständig möglich">Nicht vollständig möglich</option>
              </select>
            </label>
            <label>
              Auffälligkeiten
              <textarea value={xabcde.bodycheck_text || ''} onChange={(event) => updateXabcde('bodycheck_text', event.target.value)} rows={4} />
            </label>
          </fieldset>
        </div>
      </section>}

      {protocolSection === 'samplers' && <section className="work-panel">
        <div className="section-head">
          <h2>SAMPLERS Anamnese</h2>
          <span>strukturierte Patientenbefragung</span>
        </div>

        <div className="assessment-grid">
          <fieldset>
            <legend>S · Symptome</legend>
            <label>
              Leitsymptome
              <textarea value={samplers.symptome || ''} onChange={(event) => updateSamplers('symptome', event.target.value)} rows={4} />
            </label>
          </fieldset>

          <fieldset>
            <legend>A · Allergien</legend>
            <label>
              Allergien / Unverträglichkeiten
              <textarea value={samplers.allergien || ''} onChange={(event) => updateSamplers('allergien', event.target.value)} rows={4} />
            </label>
          </fieldset>

          <fieldset>
            <legend>M · Medikamente</legend>
            <label>
              Dauermedikation / Bedarfsmedikation
              <textarea value={samplers.medikamente || ''} onChange={(event) => updateSamplers('medikamente', event.target.value)} rows={4} />
            </label>
          </fieldset>

          <fieldset>
            <legend>P · Patientenvorgeschichte</legend>
            <label>
              Vorerkrankungen / relevante Vorgeschichte
              <textarea value={samplers.vorgeschichte || ''} onChange={(event) => updateSamplers('vorgeschichte', event.target.value)} rows={4} />
            </label>
          </fieldset>

          <fieldset>
            <legend>L · Letzte orale Aufnahme</legend>
            <label>
              Essen / Trinken / Zeitpunkt
              <input value={samplers.letzte_aufnahme || ''} onChange={(event) => updateSamplers('letzte_aufnahme', event.target.value)} />
            </label>
          </fieldset>

          <fieldset>
            <legend>E · Ereignis</legend>
            <label>
              Ereignis / Auslöser / Verlauf
              <textarea value={samplers.ereignis || ''} onChange={(event) => updateSamplers('ereignis', event.target.value)} rows={4} />
            </label>
          </fieldset>

          <fieldset>
            <legend>R · Risikofaktoren</legend>
            <label>
              Risikofaktoren
              <textarea value={samplers.risikofaktoren || ''} onChange={(event) => updateSamplers('risikofaktoren', event.target.value)} rows={4} />
            </label>
          </fieldset>

          <fieldset>
            <legend>S · Sonstiges</legend>
            <label>
              Schwangerschaft / Sonstiges
              <textarea value={samplers.sonstiges || ''} onChange={(event) => updateSamplers('sonstiges', event.target.value)} rows={4} />
            </label>
          </fieldset>
        </div>
      </section>}

      {protocolSection === 'opqrst' && <section className="work-panel">
        <div className="section-head">
          <h2>OPQRST</h2>
          <span>Schmerz und Leitsymptom</span>
        </div>
        <div className="assessment-grid">
          <fieldset>
            <legend>O · Onset</legend>
            <label>Beginn<input value={opqrst.onset || ''} onChange={(event) => updateOpqrst('onset', event.target.value)} /></label>
          </fieldset>
          <fieldset>
            <legend>P · Provocation/Palliation</legend>
            <label>Besser / schlechter<textarea value={opqrst.provocation || ''} onChange={(event) => updateOpqrst('provocation', event.target.value)} rows={4} /></label>
          </fieldset>
          <fieldset>
            <legend>Q · Quality</legend>
            <label>Qualität<input value={opqrst.quality || ''} onChange={(event) => updateOpqrst('quality', event.target.value)} /></label>
          </fieldset>
          <fieldset>
            <legend>R · Region/Radiation</legend>
            <label>Ort / Ausstrahlung<textarea value={opqrst.region || ''} onChange={(event) => updateOpqrst('region', event.target.value)} rows={4} /></label>
          </fieldset>
          <fieldset>
            <legend>S · Severity</legend>
            <label>NRS / Stärke<input value={opqrst.severity || ''} onChange={(event) => updateOpqrst('severity', event.target.value)} inputMode="numeric" /></label>
          </fieldset>
          <fieldset>
            <legend>T · Time</legend>
            <label>Verlauf<textarea value={opqrst.time || ''} onChange={(event) => updateOpqrst('time', event.target.value)} rows={4} /></label>
          </fieldset>
        </div>
      </section>}

      {protocolSection === 'verdacht' && <section className="work-panel">
        <div className="section-head">
          <h2>Verdacht & Handlungshilfe</h2>
          <span>aus Vitalwerten, xABCDE, SAMPLERS und OPQRST</span>
        </div>
        <div className="protocol-toolbar compact-toolbar">
          <button type="button" onClick={runSuspicionAssessment}>Verdacht aktualisieren</button>
          <button type="button" onClick={() => setProtocolSection('amls')}>Weiter zu AMLS</button>
        </div>
        {suspicionResult ? (
          <div className="support-grid">
            <article>
              <h3>Mögliche Verdachtsdiagnosen</h3>
              {(suspicionResult.suspicions || []).map((item, index) => (
                <div className="support-row" key={`suspicion-${index}`}>
                  <strong>{index + 1}</strong>
                  <span>{item}</span>
                </div>
              ))}
            </article>
            <article>
              <h3>Empfohlene nächste Schritte</h3>
              {(suspicionResult.recommendations || []).map((item, index) => (
                <div className="support-row" key={`recommendation-${index}`}>
                  <strong>{index + 1}</strong>
                  <span>{item}</span>
                </div>
              ))}
            </article>
          </div>
        ) : (
          <p className="muted">Noch keine Auswertung gestartet.</p>
        )}
      </section>}

      {protocolSection === 'amls' && <section className="work-panel">
        <div className="section-head">
          <h2>AMLS-Trichter</h2>
          <span>Differenzialdiagnosen prüfen und begründen</span>
        </div>

        <div className="amls-summary">
          <div>
            <strong>{amlsVisibleCandidates.length}</strong>
            <span>Kandidaten</span>
          </div>
          <div>
            <strong>{amlsExcluded.length}</strong>
            <span>zurückgestellt</span>
          </div>
          <div>
            <strong>{amlsRemainingCandidates.length}</strong>
            <span>verbleibend</span>
          </div>
        </div>
        <div className="amls-funnel">
          <div>Ausgangstrichter · {amlsVisibleCandidates.length} Kandidaten · passend {amlsMatchingCount} · prüfen {amlsCheckCount} · zurückgestellt {amlsExcluded.length}</div>
          <span />
          <strong>{amlsRemainingCandidates.length} verbleibend</strong>
        </div>

        <div className="assessment-grid">
          <fieldset>
            <legend>Verdacht</legend>
            <label>
              Leitsymptom / Hauptproblem
              <input value={amls.leitsymptom || ''} onChange={(event) => updateAmls('leitsymptom', event.target.value)} />
            </label>
            <label>
              Arbeitsdiagnose
              <input value={amls.arbeitsdiagnose || ''} onChange={(event) => updateAmls('arbeitsdiagnose', event.target.value)} />
            </label>
          </fieldset>
          <fieldset>
            <legend>Begründung</legend>
            <label>
              Klinische Notiz / Entscheidungsgrundlage
              <textarea value={amls.notizen || ''} onChange={(event) => updateAmls('notizen', event.target.value)} rows={6} />
            </label>
          </fieldset>
        </div>

        <div className="list-head">
          <h3>Differenzialdiagnosen</h3>
          <div className="list-actions">
            <button type="button" onClick={loadAmlsSuggestions}>Trichter aktualisieren</button>
            <button type="button" onClick={addAmlsCandidate}>Kandidat hinzufügen</button>
          </div>
        </div>
        <div className="candidate-grid amls-candidate-grid">
          {amlsVisibleCandidates.map((item) => {
            const isExcluded = amlsExcludedNames.has(item.name);
            const conflicts = item.conflicts || [];
            const statusClass = isExcluded ? 'excluded' : conflicts.length ? 'check' : 'matching';
            return (
              <button
                type="button"
                className={`amls-candidate-card amls-${statusClass}`}
                key={`${item.category}-${item.name}`}
                onClick={() => toggleAmlsExclusion(item)}
              >
                <strong>{isExcluded ? `Zurückgestellt: ${item.name}` : item.name}</strong>
                <span>{item.category} · {item.rationale}</span>
                {conflicts.length > 0 && !isExcluded && <small>Prüfen: {conflicts.join(' · ')}</small>}
              </button>
            );
          })}
          {amlsVisibleCandidates.length === 0 && <p className="muted">Noch keine Kandidaten. Trichter aktualisieren oder eigene Diagnosen ergänzen.</p>}
        </div>
        {amlsRemainingCandidates.length === 1 && (
          <div className="amls-final">
            <strong>Letzter Kandidat im Trichter: {amlsRemainingCandidates[0].name}</strong>
            <button type="button" onClick={() => adoptAmlsDiagnosis(amlsRemainingCandidates[0].name)}>
              Als Arbeitsdiagnose übernehmen
            </button>
          </div>
        )}
        <div className="dynamic-list">
          {amlsCandidates.map((item, index) => {
            const candidate = typeof item === 'string' ? { diagnose: item, hinweis: '' } : item || {};
            return (
              <div className="dynamic-row amls-row" key={`amls-candidate-${index}`}>
                <input
                  placeholder="Diagnose / Verdacht"
                  value={candidate.diagnose || candidate.name || ''}
                  onChange={(event) => updateAmlsCandidate(index, 'diagnose', event.target.value)}
                />
                <input
                  placeholder="Hinweis, Befund oder warum möglich"
                  value={candidate.hinweis || candidate.rationale || ''}
                  onChange={(event) => updateAmlsCandidate(index, 'hinweis', event.target.value)}
                />
                <button type="button" onClick={() => removeAmlsCandidate(index)}>Entfernen</button>
              </div>
            );
          })}
          {amlsCandidates.length === 0 && <p className="muted">Noch keine Differenzialdiagnosen ergänzt.</p>}
        </div>

        <div className="list-head">
          <h3>Ausschlüsse / zurückgestellt</h3>
          <button type="button" onClick={addAmlsExcluded}>Ausschluss hinzufügen</button>
        </div>
        <div className="dynamic-list">
          {amlsExcluded.map((item, index) => {
            const excluded = typeof item === 'string' ? { diagnose: item, begruendung: '' } : item || {};
            return (
              <div className="dynamic-row amls-row" key={`amls-excluded-${index}`}>
                <input
                  placeholder="Diagnose"
                  value={excluded.diagnose || excluded.name || ''}
                  onChange={(event) => updateAmlsExcluded(index, 'diagnose', event.target.value)}
                />
                <input
                  placeholder="Begründung"
                  value={excluded.begruendung || excluded.rationale || ''}
                  onChange={(event) => updateAmlsExcluded(index, 'begruendung', event.target.value)}
                />
                <button type="button" onClick={() => removeAmlsExcluded(index)}>Entfernen</button>
              </div>
            );
          })}
          {amlsExcluded.length === 0 && <p className="muted">Noch keine Ausschlüsse dokumentiert.</p>}
        </div>

        <div className="protocol-toolbar amls-actions">
          <button type="button" onClick={resetAmlsFunnel}><RotateCcw size={16} /> AMLS zurücksetzen</button>
          <button type="button" onClick={generateProtocol}>Protokoll mit AMLS generieren</button>
        </div>
      </section>}

      {protocolSection === 'rechner' && <section className="work-panel">
        <div className="section-head">
          <h2>Medikamentenrechner</h2>
          <span>SOP-Unterstützung aus dem Streamlit-Prototyp</span>
        </div>
        <div className="form-grid">
          <label>
            SOP
            <select value={calculator.sop} onChange={(event) => setCalculator({ ...calculator, sop: event.target.value })}>
              {[
                'Anaphylaxie (SOPKB0105)',
                'Asthma/COPD Bronchialobstruktion (SOPKB0207)',
                'Hypoglykämie',
                'Krampfanfall',
                'Schlaganfall',
                'Kardiales Lungenödem',
                'Starke Schmerzen',
                'Hypertensiver Notfall',
                'Nichttraumatischer Brustschmerz: ACS',
                'Abdominelle Schmerzen / Koliken',
                'Lungenarterienembolie'
              ].map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label>
            Alter
            <input value={calculator.age} onChange={(event) => setCalculator({ ...calculator, age: event.target.value })} inputMode="numeric" />
          </label>
          <label>
            Gewicht kg
            <input value={calculator.weight} onChange={(event) => setCalculator({ ...calculator, weight: event.target.value })} inputMode="decimal" />
          </label>
          <label>
            Schwangerschaft
            <select value={calculator.pregnant} onChange={(event) => setCalculator({ ...calculator, pregnant: event.target.value })}>
              <option value="Nein">Nein</option>
              <option value="Ja">Ja</option>
              <option value="Unbekannt">Unbekannt</option>
            </select>
          </label>
          <label>
            BZ mg/dl
            <input value={calculator.bz} onChange={(event) => setCalculator({ ...calculator, bz: event.target.value })} inputMode="numeric" />
          </label>
          <label>
            RR syst.
            <input value={calculator.rr_sys} onChange={(event) => setCalculator({ ...calculator, rr_sys: event.target.value })} inputMode="numeric" />
          </label>
          <label>
            NRS
            <input value={calculator.nrs} onChange={(event) => setCalculator({ ...calculator, nrs: event.target.value })} inputMode="numeric" />
          </label>
        </div>
        <div className="protocol-toolbar compact-toolbar">
          <button type="button" onClick={calculateMedication}>SOP berechnen</button>
        </div>
        {calculatorResult && (
          <div className="support-grid">
            <article>
              <h3>Berechnete Medikation</h3>
              {(calculatorResult.medications || []).length === 0 && <p className="muted">Keine konkrete Medikation in diesem Entscheidungszweig.</p>}
              {(calculatorResult.medications || []).map((item, index) => (
                <div className="support-row support-row-action" key={`calc-med-${index}`}>
                  <strong>{index + 1}</strong>
                  <span>{item}</span>
                  <button type="button" onClick={() => addCalculatedMedication(item)}>Übernehmen</button>
                </div>
              ))}
            </article>
            <article>
              <h3>Handlungshilfe</h3>
              {(calculatorResult.actions || []).map((item, index) => (
                <div className="support-row" key={`calc-action-${index}`}>
                  <strong>{index + 1}</strong>
                  <span>{item}</span>
                </div>
              ))}
              {(calculatorResult.notes || []).map((item, index) => (
                <div className="support-note" key={`calc-note-${index}`}>{item}</div>
              ))}
            </article>
          </div>
        )}
      </section>}

      {protocolSection === 'massnahmen' && <section className="work-panel">
        <div className="section-head">
          <h2>Maßnahmen & Medikation</h2>
          <span>chronologisch dokumentieren</span>
        </div>

        <div className="list-head">
          <h3>Maßnahmen</h3>
          <button type="button" onClick={addMeasure}>Maßnahme hinzufügen</button>
        </div>
        <div className="dynamic-list">
          {(massnahmen.timeline || []).map((item, index) => (
            <div className="dynamic-row" key={`measure-${index}`}>
              <input placeholder="Zeit" value={item.zeit || ''} onChange={(event) => updateMeasure(index, 'zeit', event.target.value)} />
              <input placeholder="Maßnahme" value={item.massnahme || ''} onChange={(event) => updateMeasure(index, 'massnahme', event.target.value)} />
              <button type="button" onClick={() => removeMeasure(index)}>Entfernen</button>
            </div>
          ))}
          {(massnahmen.timeline || []).length === 0 && <p className="muted">Noch keine Maßnahmen dokumentiert.</p>}
        </div>

        <div className="list-head">
          <h3>Medikation</h3>
          <button type="button" onClick={addMedication}>Medikation hinzufügen</button>
        </div>
        <div className="dynamic-list">
          {(massnahmen.medikation || []).map((item, index) => (
            <div className="dynamic-row medication-row" key={`medication-${index}`}>
              <input placeholder="Zeit" value={item.zeit || ''} onChange={(event) => updateMedication(index, 'zeit', event.target.value)} />
              <input placeholder="Medikament" value={item.medikament || ''} onChange={(event) => updateMedication(index, 'medikament', event.target.value)} />
              <input placeholder="Dosis" value={item.dosis || ''} onChange={(event) => updateMedication(index, 'dosis', event.target.value)} />
              <input placeholder="Weg" value={item.weg || ''} onChange={(event) => updateMedication(index, 'weg', event.target.value)} />
              <button type="button" onClick={() => removeMedication(index)}>Entfernen</button>
            </div>
          ))}
          {(massnahmen.medikation || []).length === 0 && <p className="muted">Noch keine Medikation dokumentiert.</p>}
        </div>
      </section>}

      {protocolSection === 'abschluss' && <section className="work-panel">
        <div className="section-head">
          <h2>Verdacht & Übergabe</h2>
          <span>Arbeitsdiagnose und Zielübergabe</span>
        </div>
        <div className="assessment-grid">
          <fieldset>
            <legend>Verdacht</legend>
            <label>
              Arbeitsdiagnose
              <input value={amls.arbeitsdiagnose || ''} onChange={(event) => updateAmls('arbeitsdiagnose', event.target.value)} />
            </label>
          </fieldset>
          <fieldset>
            <legend>Übergabe</legend>
            <label>
              Ziel / Empfänger
              <input value={uebergabe.ziel || ''} onChange={(event) => updateUebergabe('ziel', event.target.value)} />
            </label>
            <label>
              Übergabetext
              <textarea value={uebergabe.text || ''} onChange={(event) => updateUebergabe('text', event.target.value)} rows={6} />
            </label>
          </fieldset>
        </div>
      </section>}

      {protocolSection === 'protokoll' && <section className="work-panel">
        <div className="section-head">
          <h2>Protokoll</h2>
          <span>Vorschau und Abschluss</span>
        </div>
        {qualityResult && (
          <div className={`quality-box quality-${qualityResult.level}`}>
            <div className="quality-score">
              <strong>{qualityResult.score}</strong>
              <span>QS-Punkte</span>
            </div>
            <div className="quality-summary">
              <span>{qualityResult.ok_count} erfüllt</span>
              <span>{qualityResult.warning_count} Warnungen</span>
              <span>{qualityResult.critical_count} kritisch</span>
            </div>
            <div className="quality-list">
              {(qualityResult.items || []).filter((item) => item.status !== 'ok').map((item) => (
                <div className={`quality-item quality-item-${item.status}`} key={item.id}>
                  <AlertTriangle size={16} />
                  <div>
                    <strong>{item.label}</strong>
                    <span>{item.message}</span>
                  </div>
                </div>
              ))}
              {(qualityResult.items || []).filter((item) => item.status !== 'ok').length === 0 && (
                <div className="quality-item quality-item-ok">
                  <CheckCircle2 size={16} />
                  <div>
                    <strong>Keine Warnungen</strong>
                    <span>Die aktiven QS-Regeln sind erfüllt.</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
        <textarea
          className="protocol-preview"
          value={generatedProtocol}
          onChange={(event) => setGeneratedProtocol(event.target.value)}
          placeholder="Noch keine Vorschau erzeugt."
          rows={18}
        />
      </section>}
    </main>
  );
}

function App() {
  const [session, setSession] = useState(() => {
    const raw = localStorage.getItem('nana_session');
    return raw ? JSON.parse(raw) : null;
  });
  const [online, setOnline] = useState(() => navigator.onLine);
  const [backendOnline, setBackendOnline] = useState(true);
  const [lastSync, setLastSync] = useState('');

  function handleLogin(result) {
    const nextSession = { token: result.token, employee: result.employee, lastActivity: Date.now() };
    localStorage.setItem('nana_session', JSON.stringify(nextSession));
    setSession(nextSession);
  }

  function handleLogout() {
    localStorage.removeItem('nana_session');
    setSession(null);
  }

  useEffect(() => {
    if (!session) return undefined;

    function markActivity() {
      const raw = localStorage.getItem('nana_session');
      const current = raw ? JSON.parse(raw) : session;
      const nextSession = { ...current, lastActivity: Date.now() };
      localStorage.setItem('nana_session', JSON.stringify(nextSession));
    }

    function checkTimeout() {
      const raw = localStorage.getItem('nana_session');
      const current = raw ? JSON.parse(raw) : null;
      if (!current?.lastActivity || Date.now() - current.lastActivity > SESSION_TIMEOUT_MS) {
        api('/api/auth/logout', { method: 'POST' }, current?.token || '').catch(() => {});
        handleLogout();
      }
    }

    const events = ['click', 'keydown', 'pointermove', 'touchstart'];
    events.forEach((eventName) => window.addEventListener(eventName, markActivity));
    const interval = window.setInterval(checkTimeout, 30000);
    return () => {
      events.forEach((eventName) => window.removeEventListener(eventName, markActivity));
      window.clearInterval(interval);
    };
  }, [session]);

  useEffect(() => {
    function updateOnline() {
      setOnline(navigator.onLine);
    }

    async function checkBackend() {
      try {
        await api('/api/health');
        setBackendOnline(true);
      } catch {
        setBackendOnline(false);
      }
    }

    window.addEventListener('online', updateOnline);
    window.addEventListener('offline', updateOnline);
    checkBackend();
    const interval = window.setInterval(checkBackend, 30000);
    return () => {
      window.removeEventListener('online', updateOnline);
      window.removeEventListener('offline', updateOnline);
      window.clearInterval(interval);
    };
  }, []);

  const connectivity = { online, backendOnline, lastSync };

  return session
    ? <Dashboard session={session} onLogout={handleLogout} connectivity={connectivity} onSync={setLastSync} />
    : <Login onLogin={handleLogin} />;
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}

createRoot(document.getElementById('root')).render(<App />);
