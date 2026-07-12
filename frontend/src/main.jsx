import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  Building2,
  Cable,
  FileText,
  HeartPulse,
  Lock,
  LogOut,
  ShieldCheck,
  Stethoscope,
  Wrench
} from 'lucide-react';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

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

  if (view === 'protocol') {
    return <ProtocolView session={session} employee={employee} onBack={() => setView('home')} onLogout={logout} />;
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
              onClick={() => tile.id === 'protocol' && setView('protocol')}
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
              <article className="case-row" key={item.id}>
                <div>
                  <strong>{item.summary}</strong>
                  <span>{item.completed_at}</span>
                </div>
                <span className={`status-pill status-${item.status}`}>{item.status}</span>
              </article>
            ))
          )}
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
  einsatz: {}
};

function ProtocolView({ session, employee, onBack, onLogout }) {
  const [patient, setPatient] = useState(emptyPatient);
  const [protocolSection, setProtocolSection] = useState('vitalwerte');
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');
  const vitalwerte = patient.vitalwerte || {};
  const xabcde = patient.xabcde || {};
  const samplers = patient.samplers || {};

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
        <button type="button" onClick={saveDraft}>Entwurf speichern</button>
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
    </main>
  );
}

function App() {
  const [session, setSession] = useState(() => {
    const raw = localStorage.getItem('nana_session');
    return raw ? JSON.parse(raw) : null;
  });

  function handleLogin(result) {
    const nextSession = { token: result.token, employee: result.employee };
    localStorage.setItem('nana_session', JSON.stringify(nextSession));
    setSession(nextSession);
  }

  function handleLogout() {
    localStorage.removeItem('nana_session');
    setSession(null);
  }

  return session ? <Dashboard session={session} onLogout={handleLogout} /> : <Login onLogin={handleLogin} />;
}

createRoot(document.getElementById('root')).render(<App />);
