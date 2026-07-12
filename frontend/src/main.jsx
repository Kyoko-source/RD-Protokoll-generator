import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  Building2,
  Cable,
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

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';
const SESSION_TIMEOUT_MS = 20 * 60 * 1000;

function api(path, options = {}, token = '') {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers ?? {})
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return fetch(`${API_BASE}${path}`, { ...options, headers }).then(async (response) => {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || 'Anfrage fehlgeschlagen');
    }
    return data;
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

function Dashboard({ session, onLogout }) {
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
    return <ProtocolView session={session} employee={employee} onBack={() => setView('home')} onLogout={logout} />;
  }

  if (view === 'admin') {
    return <AdminView session={session} employee={employee} onBack={() => setView('home')} onLogout={logout} />;
  }

  return (
    <main className="app-shell">
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

function AdminView({ session, employee, onBack, onLogout }) {
  const [employees, setEmployees] = useState([]);
  const [auditEvents, setAuditEvents] = useState([]);
  const [privacy, setPrivacy] = useState(null);
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
      setEmployees(employeeData.employees || []);
      setAuditEvents(auditData.events || []);
      setPrivacy(privacyData);
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
  amls: { excluded: [], custom_candidates: [], arbeitsdiagnose: '' },
  massnahmen: { timeline: [], medikation: [] },
  transport: {},
  einsatz: {},
  uebergabe: {}
};

function ProtocolView({ session, employee, onBack, onLogout }) {
  const [patient, setPatient] = useState(emptyPatient);
  const [protocolSection, setProtocolSection] = useState('vitalwerte');
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');
  const [generatedProtocol, setGeneratedProtocol] = useState('');
  const vitalwerte = patient.vitalwerte || {};
  const xabcde = patient.xabcde || {};
  const samplers = patient.samplers || {};
  const opqrst = patient.opqrst || {};
  const massnahmen = patient.massnahmen || { timeline: [], medikation: [] };
  const amls = patient.amls || {};
  const uebergabe = patient.uebergabe || {};

  useEffect(() => {
    api('/api/draft', {}, session.token)
      .then((data) => setPatient({ ...emptyPatient, ...(data.patient || {}) }))
      .catch((err) => setError(err.message));
  }, [session.token]);

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

  async function saveDraft() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/draft', {
        method: 'PUT',
        body: JSON.stringify({ patient })
      }, session.token);
      setStatusText(`Entwurf gespeichert: ${result.updated_at}`);
    } catch (err) {
      setError(err.message);
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
      setError(err.message);
    }
  }

  async function finishCase() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/cases/finish', {
        method: 'POST',
        body: JSON.stringify({ patient })
      }, session.token);
      setGeneratedProtocol(result.protocol_text || '');
      setPatient(emptyPatient);
      setProtocolSection('protokoll');
      setStatusText(`Einsatz beendet und archiviert: ${result.case_id}`);
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
        <button type="button" onClick={generateProtocol}>Protokoll generieren</button>
        <button type="button" onClick={exportDraftPdf}><Download size={16} /> PDF</button>
        <button type="button" onClick={printDraftPdf}><Printer size={16} /> Drucken</button>
        <button type="button" onClick={saveDraft}>Entwurf speichern</button>
        <button type="button" onClick={finishCase}>Einsatz beenden</button>
      </section>

      {error && <div className="error-box">{error}</div>}
      {statusText && <div className="success-box">{statusText}</div>}

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
            Puls
            <input value={vitalwerte.puls || ''} onChange={(event) => updateVital('puls', event.target.value)} inputMode="numeric" />
          </label>
          <label>
            SpO2
            <input value={vitalwerte.spo2 || ''} onChange={(event) => updateVital('spo2', event.target.value)} inputMode="numeric" />
          </label>
          <label>
            Atemfrequenz
            <input value={vitalwerte.af || ''} onChange={(event) => updateVital('af', event.target.value)} inputMode="numeric" />
          </label>
          <label>
            BZ
            <input value={vitalwerte.bz || ''} onChange={(event) => updateVital('bz', event.target.value)} inputMode="numeric" />
          </label>
          <label>
            Temperatur
            <input value={vitalwerte.temperatur || ''} onChange={(event) => updateVital('temperatur', event.target.value)} inputMode="decimal" />
          </label>
          <label>
            GCS
            <input value={vitalwerte.gcs || ''} onChange={(event) => updateVital('gcs', event.target.value)} inputMode="numeric" />
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
                <option value="frei">frei</option>
                <option value="gefährdet">gefährdet</option>
                <option value="verlegt">verlegt</option>
              </select>
            </label>
            <label>
              HWS / Stabilisierung
              <input value={xabcde.hws || ''} onChange={(event) => updateXabcde('hws', event.target.value)} />
            </label>
          </fieldset>

          <fieldset>
            <legend>B · Atmung</legend>
            <label>
              Atmung
              <select value={xabcde.atmung || ''} onChange={(event) => updateXabcde('atmung', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="unauffällig">unauffällig</option>
                <option value="erschwert">erschwert</option>
                <option value="insuffizient">insuffizient</option>
                <option value="Apnoe">Apnoe</option>
              </select>
            </label>
            <label>
              Atemgeräusche
              <input value={xabcde.atemgeraeusche || ''} onChange={(event) => updateXabcde('atemgeraeusche', event.target.value)} />
            </label>
            <label>
              Sauerstofftherapie
              <input value={xabcde.sauerstoff || ''} onChange={(event) => updateXabcde('sauerstoff', event.target.value)} />
            </label>
          </fieldset>

          <fieldset>
            <legend>C · Kreislauf</legend>
            <label>
              Hautzeichen
              <select value={xabcde.haut || ''} onChange={(event) => updateXabcde('haut', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="rosig/warm/trocken">rosig/warm/trocken</option>
                <option value="blass">blass</option>
                <option value="kaltschweißig">kaltschweißig</option>
                <option value="zyanotisch">zyanotisch</option>
              </select>
            </label>
            <label>
              Rekapillarisierungszeit
              <input value={xabcde.rekap || ''} onChange={(event) => updateXabcde('rekap', event.target.value)} />
            </label>
            <label>
              Pulsqualität
              <input value={xabcde.pulsqualitaet || ''} onChange={(event) => updateXabcde('pulsqualitaet', event.target.value)} />
            </label>
          </fieldset>

          <fieldset>
            <legend>D · Neurologie</legend>
            <label>
              AVPU
              <select value={xabcde.avpu || ''} onChange={(event) => updateXabcde('avpu', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="Alert">Alert</option>
                <option value="Voice">Voice</option>
                <option value="Pain">Pain</option>
                <option value="Unresponsive">Unresponsive</option>
              </select>
            </label>
            <label>
              Pupillen
              <input value={xabcde.pupillen || ''} onChange={(event) => updateXabcde('pupillen', event.target.value)} />
            </label>
          </fieldset>

          <fieldset>
            <legend>E · Exposure</legend>
            <label>
              Bodycheck
              <select value={xabcde.bodycheck || ''} onChange={(event) => updateXabcde('bodycheck', event.target.value)}>
                <option value="">Keine Angabe</option>
                <option value="unauffällig">unauffällig</option>
                <option value="auffällig">auffällig</option>
                <option value="nicht vollständig möglich">nicht vollständig möglich</option>
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

  return session ? <Dashboard session={session} onLogout={handleLogout} /> : <Login onLogin={handleLogin} />;
}

createRoot(document.getElementById('root')).render(<App />);
