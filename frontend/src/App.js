import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';

const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const PORTAL_URL = process.env.REACT_APP_PORTAL_URL || 'http://localhost:8001';

const ACTION_COLORS = {
  SEARCH: { bg: '#1e3a5f', border: '#3b82f6', text: '#60a5fa', label: 'SEARCH' },
  VIEW: { bg: '#1f2937', border: '#6b7280', text: '#9ca3af', label: 'VIEW' },
  UPDATE: { bg: '#422006', border: '#f59e0b', text: '#fbbf24', label: 'UPDATE' },
  DELETE: { bg: '#450a0a', border: '#ef4444', text: '#f87171', label: 'DELETE' },
  HISTORY: { bg: '#1e1b4b', border: '#8b5cf6', text: '#a78bfa', label: 'HISTORY' },
  TASK_COMPLETE: { bg: '#052e16', border: '#22c55e', text: '#4ade80', label: 'COMPLETE' },
};

const RISK_LEVELS = {
  SEARCH: { level: 'LOW', color: '#22c55e' },
  VIEW: { level: 'LOW', color: '#22c55e' },
  HISTORY: { level: 'LOW', color: '#22c55e' },
  UPDATE: { level: 'MEDIUM', color: '#f59e0b' },
  DELETE: { level: 'HIGH', color: '#ef4444' },
  TASK_COMPLETE: { level: 'INFO', color: '#6366f1' },
};

const TASK_TEMPLATES = [
  { label: 'Patient Lookup', icon: '\u{1F50D}', task: "Search for Sam Altman and view his full patient record" },
  { label: 'Medication Update', icon: '\u{1F48A}', task: "Find Sam Altman's record, update his medication from Vitamin C 1000mg daily to Emergen-C 1000mg daily" },
  { label: 'Full Audit Demo', icon: '\u{1F4CB}', task: "Find Sam Altman, view his record, update his medication from Vitamin C 1000mg daily to Emergen-C 1000mg daily, then search for all patients with seasonal allergies" },
  { label: 'Multi-Patient Search', icon: '\u{1F465}', task: "Search for patients with allergies, then search for patients with headaches, and view the details of Garry Tan" },
];

function truncHash(h, len = 12) {
  if (!h) return '\u2014';
  return h.length > len ? h.slice(0, len) + '\u2026' : h;
}

function getRiskScore(actions) {
  const weights = { SEARCH: 1, VIEW: 1, HISTORY: 1, UPDATE: 5, DELETE: 10, TASK_COMPLETE: 0 };
  const total = actions.reduce((sum, a) => sum + (weights[a.action_type] || 0), 0);
  const max = actions.length * 10;
  if (max === 0) return 0;
  return Math.round((total / max) * 100);
}

function clinicalSummary(action) {
  const p = action.payload || {};
  switch (action.action_type) {
    case 'SEARCH': return `Searched the patient registry for "${p.query}"`;
    case 'VIEW': return `Viewed full patient record (Patient #${p.patient_id})`;
    case 'UPDATE': return `Updated ${p.patient_name}'s ${p.field}: changed from "${p.old_value}" to "${p.new_value}"`;
    case 'DELETE': return `Deleted patient record for ${p.patient_name} (${p.mrn})`;
    case 'HISTORY': return `Retrieved version history for Patient #${p.patient_id}`;
    case 'TASK_COMPLETE': return `Agent completed task successfully`;
    default: return `${action.action_type} action performed`;
  }
}

function auditSummary(action) {
  const p = action.payload || {};
  if (action.action_type === 'SEARCH') return `Query: "${p.query}"`;
  if (action.action_type === 'VIEW') return `Patient #${p.patient_id}`;
  if (action.action_type === 'UPDATE') return `${p.patient_name}: ${p.field} "${p.old_value}" \u2192 "${p.new_value}"`;
  if (action.action_type === 'DELETE') return `${p.patient_name} (${p.mrn})`;
  if (action.action_type === 'HISTORY') return `Patient #${p.patient_id}`;
  if (action.action_type === 'TASK_COMPLETE') return `Task finished`;
  return JSON.stringify(p).slice(0, 60);
}

// ─── Chain Explorer Modal ───

function ChainExplorer({ action, actions, onClose }) {
  if (!action) return null;
  const idx = actions.findIndex(a => a.id === action.id);
  const prev = idx > 0 ? actions[idx - 1] : null;
  const next = idx < actions.length - 1 ? actions[idx + 1] : null;
  const risk = RISK_LEVELS[action.action_type] || RISK_LEVELS.VIEW;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Chain Explorer &mdash; Action #{idx + 1}</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>

        <div className="explorer-badge-row">
          <span className="action-badge" style={{
            background: ACTION_COLORS[action.action_type]?.bg,
            color: ACTION_COLORS[action.action_type]?.text,
            border: `1px solid ${ACTION_COLORS[action.action_type]?.border}`
          }}>{action.action_type}</span>
          <span className="risk-badge" style={{ color: risk.color, borderColor: risk.color }}>
            {risk.level} RISK
          </span>
          <span className={`action-verified ${action.verified ? 'verified-ok' : 'verified-fail'}`}>
            {action.verified ? '\u2713 Verified' : '\u2717 Failed'}
          </span>
        </div>

        <div className="explorer-section">
          <label>Timestamp</label>
          <p>{new Date(action.timestamp).toLocaleString()}</p>
        </div>
        <div className="explorer-section">
          <label>Agent</label>
          <p className="mono">{action.agent_id}</p>
        </div>
        <div className="explorer-section">
          <label>Payload</label>
          <pre className="explorer-json">{JSON.stringify(action.payload, null, 2)}</pre>
        </div>
        <div className="explorer-section">
          <label>SHA-256 Hash</label>
          <pre className="explorer-hash">{action.hash}</pre>
        </div>
        <div className="explorer-section">
          <label>Previous Hash</label>
          <pre className="explorer-hash">{action.prev_hash}</pre>
        </div>
        <div className="explorer-section">
          <label>ECDSA Signature</label>
          <pre className="explorer-hash" style={{ fontSize: '10px' }}>{action.signature}</pre>
        </div>

        <div className="explorer-chain-nav">
          {prev && (
            <div className="chain-link chain-link-prev">
              <span className="chain-arrow">\u2190</span>
              <span>Prev: {truncHash(prev.hash, 16)}</span>
              <span className="chain-link-type">{prev.action_type}</span>
            </div>
          )}
          <div className="chain-link chain-link-current">
            <span>Current: {truncHash(action.hash, 16)}</span>
          </div>
          {next && (
            <div className="chain-link chain-link-next">
              <span>Next: {truncHash(next.hash, 16)}</span>
              <span className="chain-link-type">{next.action_type}</span>
              <span className="chain-arrow">\u2192</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Action Card (Auditor View) ───

function AuditorCard({ action, index, onClick }) {
  const colors = ACTION_COLORS[action.action_type] || ACTION_COLORS.VIEW;
  const risk = RISK_LEVELS[action.action_type] || RISK_LEVELS.VIEW;
  const ts = new Date(action.timestamp).toLocaleTimeString();

  return (
    <div className="action-card" style={{ borderLeftColor: colors.border }} onClick={() => onClick(action)}>
      <div className="action-header">
        <span className="action-badge" style={{ background: colors.bg, color: colors.text, border: `1px solid ${colors.border}` }}>
          {colors.label}
        </span>
        <span className="risk-dot" style={{ background: risk.color }} title={`${risk.level} risk`}></span>
        <span className="action-index">#{index + 1}</span>
        <span className="action-time">{ts}</span>
        <span className={`action-verified ${action.verified ? 'verified-ok' : 'verified-fail'}`}>
          {action.verified ? '\u2713' : '\u2717'}
        </span>
      </div>
      <div className="action-summary">{auditSummary(action)}</div>
      <div className="action-hashes">
        <div className="hash-row"><span className="hash-label">hash</span><span className="hash-value">{truncHash(action.hash)}</span></div>
        <div className="hash-row"><span className="hash-label">prev</span><span className="hash-value">{truncHash(action.prev_hash)}</span></div>
        <div className="hash-row"><span className="hash-label">sig</span><span className="hash-value">{truncHash(action.signature, 16)}</span></div>
        <div className="hash-row"><span className="hash-label">agent</span><span className="hash-value">{action.agent_id}</span></div>
      </div>
    </div>
  );
}

// ─── Action Card (Clinical View) ───

function ClinicalCard({ action, index }) {
  const colors = ACTION_COLORS[action.action_type] || ACTION_COLORS.VIEW;
  const risk = RISK_LEVELS[action.action_type] || RISK_LEVELS.VIEW;
  const ts = new Date(action.timestamp).toLocaleTimeString();

  return (
    <div className="clinical-card">
      <div className="clinical-timeline-dot" style={{ background: colors.border }}></div>
      <div className="clinical-content">
        <div className="clinical-header">
          <span className="clinical-time">{ts}</span>
          <span className="risk-badge-sm" style={{ color: risk.color, borderColor: risk.color }}>{risk.level}</span>
        </div>
        <p className="clinical-text">{clinicalSummary(action)}</p>
        <span className="clinical-agent">by {action.agent_id}</span>
      </div>
    </div>
  );
}

// ─── Task Summary Card ───

function TaskSummary({ summary, agentName }) {
  if (!summary) return null;
  return (
    <div className="task-summary-card">
      <div className="summary-header">
        <span className="summary-icon">\u2713</span>
        <h4>Task Complete &mdash; {agentName}</h4>
      </div>
      <div className="summary-stats">
        <div className="summary-stat"><span className="summary-val">{summary.total_actions}</span><span className="summary-lbl">Actions</span></div>
        <div className="summary-stat"><span className="summary-val">{summary.patients_touched}</span><span className="summary-lbl">Patients</span></div>
        <div className="summary-stat"><span className="summary-val">{summary.elapsed_seconds}s</span><span className="summary-lbl">Duration</span></div>
      </div>
    </div>
  );
}

// ─── Chain Status Panel ───

function ChainStatus({ chain, actions, onVerify, onTamper, onRestore, tampered }) {
  const riskScore = getRiskScore(actions);
  const riskColor = riskScore < 30 ? '#22c55e' : riskScore < 60 ? '#f59e0b' : '#ef4444';

  return (
    <div className="chain-panel">
      <h3 className="panel-title">Chain Integrity</h3>
      <div className={`chain-status-badge ${chain.intact ? 'chain-ok' : 'chain-broken'}`}>
        {chain.intact ? 'CHAIN INTACT \u2713' : 'CHAIN BROKEN \u2717'}
      </div>
      <div className="chain-stats">
        <div className="stat-item"><span className="stat-value">{chain.total_actions || actions.length}</span><span className="stat-label">Total</span></div>
        <div className="stat-item"><span className="stat-value">{actions.filter(a => a.verified).length}</span><span className="stat-label">Verified</span></div>
        <div className="stat-item"><span className="stat-value">{actions.filter(a => !a.verified).length}</span><span className="stat-label">Failed</span></div>
      </div>

      <div className="risk-meter">
        <label className="risk-meter-label">Session Risk Score</label>
        <div className="risk-bar-bg">
          <div className="risk-bar-fill" style={{ width: `${Math.min(riskScore, 100)}%`, background: riskColor }}></div>
        </div>
        <span className="risk-score" style={{ color: riskColor }}>{riskScore}%</span>
      </div>

      {chain.error && <div className="chain-error">{chain.error}</div>}

      <div className="chain-actions">
        <button className="btn-chain" onClick={onVerify}>Verify Chain</button>
        {!tampered ? (
          <button className="btn-tamper" onClick={onTamper} disabled={actions.length === 0}>Tamper Demo</button>
        ) : (
          <button className="btn-restore" onClick={onRestore}>Restore Chain</button>
        )}
      </div>

      <div className="chain-info">
        <div className="info-row"><span>Algorithm</span><span>ECDSA P-256</span></div>
        <div className="info-row"><span>Hash</span><span>SHA-256</span></div>
        <div className="info-row"><span>Chain</span><span>Hash-linked</span></div>
        <div className="info-row"><span>Genesis</span><span className="mono">GENESIS</span></div>
      </div>
    </div>
  );
}

// ─── Patient List Panel ───

function PatientList({ patients }) {
  return (
    <div className="patient-panel">
      <h3 className="panel-title">Patient Registry <span className="patient-count">{patients.filter(p => !p.deleted).length} active</span></h3>
      <div className="patient-list">
        {patients.map(p => (
          <div key={p.id} className={`patient-row ${p.deleted ? 'patient-deleted' : ''}`}>
            <div className="patient-name">
              {p.deleted && <span className="deleted-tag">[DELETED]</span>}
              {p.first_name} {p.last_name}
            </div>
            <div className="patient-meta">
              <span className="patient-mrn">{p.mrn}</span>
              <span className="patient-dx">{p.diagnosis}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── API Key Config ───

function ApiKeyBar({ keyStatus, onSetKey }) {
  const [key, setKey] = useState('');
  const [show, setShow] = useState(false);

  if (keyStatus.has_key && !show) {
    return (
      <div className="apikey-bar apikey-connected">
        <span className="apikey-dot dot-connected"></span>
        <span>API Key: {keyStatus.key_preview || 'Connected'}</span>
        <button className="apikey-change-btn" onClick={() => setShow(true)}>Change</button>
      </div>
    );
  }

  return (
    <div className="apikey-bar">
      <span className="apikey-dot dot-disconnected"></span>
      <input
        className="apikey-input"
        type="password"
        placeholder="sk-ant-..."
        value={key}
        onChange={e => setKey(e.target.value)}
      />
      <button className="apikey-set-btn" onClick={() => { onSetKey(key); setKey(''); setShow(false); }} disabled={!key}>
        Set Key
      </button>
      {show && <button className="apikey-cancel-btn" onClick={() => setShow(false)}>Cancel</button>}
    </div>
  );
}

// ─── Main App ───

function App() {
  const [actions, setActions] = useState([]);
  const [patients, setPatients] = useState([]);
  const [chain, setChain] = useState({ intact: true, total_actions: 0 });
  const [connected, setConnected] = useState(false);
  const [task, setTask] = useState('');
  const [agentName, setAgentName] = useState('MedLedger Agent');
  const [running, setRunning] = useState(false);
  const [view, setView] = useState('auditor'); // 'auditor' or 'clinical'
  const [selectedAction, setSelectedAction] = useState(null);
  const [tampered, setTampered] = useState(false);
  const [taskSummary, setTaskSummary] = useState(null);
  const [keyStatus, setKeyStatus] = useState({ has_key: false });
  const feedRef = useRef(null);
  const wsRef = useRef(null);

  const fetchData = useCallback(async () => {
    try {
      const [logRes, patientsRes, verifyRes, keyRes] = await Promise.all([
        fetch(`${API_URL}/audit/log`),
        fetch(`${API_URL}/patients/current`),
        fetch(`${API_URL}/audit/verify`),
        fetch(`${API_URL}/api/key-status`),
      ]);
      if (logRes.ok) setActions(await logRes.json());
      if (patientsRes.ok) setPatients(await patientsRes.json());
      if (verifyRes.ok) setChain(await verifyRes.json());
      if (keyRes.ok) setKeyStatus(await keyRes.json());
    } catch (e) { /* API not ready */ }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => { setConnected(false); setTimeout(connect, 2000); };
      ws.onerror = () => ws.close();
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'action') {
          const { type, ...action } = data;
          setActions(prev => [...prev, action]);
          if (['UPDATE', 'DELETE'].includes(action.action_type)) {
            fetch(`${API_URL}/patients/current`).then(r => r.json()).then(setPatients).catch(() => {});
          }
          fetch(`${API_URL}/audit/verify`).then(r => r.json()).then(setChain).catch(() => {});
        }
        if (data.type === 'task_complete') {
          setRunning(false);
          if (data.summary) setTaskSummary({ summary: data.summary, agentName: data.agent_name });
        }
        if (data.type === 'agent_start') {
          setTaskSummary(null);
        }
        if (data.type === 'error') {
          setRunning(false);
        }
        if (data.type === 'tamper') {
          setTampered(true);
          fetch(`${API_URL}/audit/log`).then(r => r.json()).then(setActions).catch(() => {});
          fetch(`${API_URL}/audit/verify`).then(r => r.json()).then(setChain).catch(() => {});
        }
        if (data.type === 'restored') {
          setTampered(false);
          fetch(`${API_URL}/audit/log`).then(r => r.json()).then(setActions).catch(() => {});
          fetch(`${API_URL}/audit/verify`).then(r => r.json()).then(setChain).catch(() => {});
        }
      };
    }
    connect();
    return () => wsRef.current?.close();
  }, []);

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [actions]);

  const runAgent = async () => {
    if (!task.trim()) return;
    setRunning(true);
    setTaskSummary(null);
    try {
      await fetch(`${API_URL}/agent/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: task.trim(), agent_name: agentName }),
      });
    } catch (e) { setRunning(false); }
  };

  const verifyChain = async () => {
    const res = await fetch(`${API_URL}/audit/verify`);
    if (res.ok) setChain(await res.json());
    const logRes = await fetch(`${API_URL}/audit/log`);
    if (logRes.ok) setActions(await logRes.json());
  };

  const doTamper = async () => {
    await fetch(`${API_URL}/audit/tamper`, { method: 'POST' });
  };

  const doRestore = async () => {
    await fetch(`${API_URL}/audit/restore`, { method: 'POST' });
  };

  const exportLog = async () => {
    const res = await fetch(`${API_URL}/audit/export`);
    if (res.ok) {
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `medledger-audit-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  const setApiKey = async (key) => {
    const res = await fetch(`${API_URL}/api/set-key`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key }),
    });
    if (res.ok) {
      const keyRes = await fetch(`${API_URL}/api/key-status`);
      if (keyRes.ok) setKeyStatus(await keyRes.json());
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1 className="app-title">MedLedger</h1>
          <span className="app-subtitle">Cryptographic Audit Trail for AI Agents</span>
        </div>
        <div className="header-right">
          <button className="export-btn" onClick={exportLog} title="Export audit log">Export</button>
          <span className={`connection-dot ${connected ? 'dot-connected' : 'dot-disconnected'}`}></span>
          <span className="connection-text">{connected ? 'Live' : 'Connecting...'}</span>
        </div>
      </header>

      <ApiKeyBar keyStatus={keyStatus} onSetKey={setApiKey} />

      <div className="agent-bar">
        <div className="agent-name-wrap">
          <input
            className="agent-name-input"
            type="text"
            placeholder="Agent name..."
            value={agentName}
            onChange={(e) => setAgentName(e.target.value)}
            disabled={running}
          />
        </div>
        <input
          className="agent-input"
          type="text"
          placeholder="Enter agent task..."
          value={task}
          onChange={(e) => setTask(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && runAgent()}
          disabled={running}
        />
        <button className="agent-run-btn" onClick={runAgent} disabled={running || !task.trim()}>
          {running ? 'Running...' : 'Run Agent'}
        </button>
      </div>

      <div className="template-bar">
        {TASK_TEMPLATES.map((t, i) => (
          <button key={i} className="template-btn" onClick={() => setTask(t.task)} disabled={running}>
            <span className="template-icon">{t.icon}</span> {t.label}
          </button>
        ))}
      </div>

      <div className="main-grid">
        <div className="portal-panel">
          <h3 className="panel-title">
            <span>MedLedger Portal <span className="portal-badge">Agent-Native EHR</span></span>
            <a href={PORTAL_URL} target="_blank" rel="noopener noreferrer" className="portal-link">Open</a>
          </h3>
          <iframe src={PORTAL_URL} title="MedLedger Portal" className="portal-iframe" />
        </div>

        <div className="feed-panel">
          <div className="feed-header">
            <h3 className="panel-title">
              {view === 'auditor' ? 'Audit Feed' : 'Clinical Timeline'}
              <span className="action-count">{actions.length} actions</span>
            </h3>
            <div className="view-toggle">
              <button className={`toggle-btn ${view === 'auditor' ? 'toggle-active' : ''}`} onClick={() => setView('auditor')}>
                Auditor
              </button>
              <button className={`toggle-btn ${view === 'clinical' ? 'toggle-active' : ''}`} onClick={() => setView('clinical')}>
                Clinical
              </button>
            </div>
          </div>

          {taskSummary && <TaskSummary summary={taskSummary.summary} agentName={taskSummary.agentName} />}

          <div className="action-feed" ref={feedRef}>
            {actions.length === 0 ? (
              <div className="empty-feed">
                <div className="empty-icon">{'\u2693'}</div>
                <p>No actions recorded yet.</p>
                <p className="empty-hint">Set your API key above, pick a task template, and hit Run Agent.</p>
              </div>
            ) : view === 'auditor' ? (
              actions.map((action, i) => <AuditorCard key={action.id || i} action={action} index={i} onClick={setSelectedAction} />)
            ) : (
              <div className="clinical-timeline">
                {actions.map((action, i) => <ClinicalCard key={action.id || i} action={action} index={i} />)}
              </div>
            )}
          </div>
        </div>

        <div className="right-col">
          <ChainStatus
            chain={chain}
            actions={actions}
            onVerify={verifyChain}
            onTamper={doTamper}
            onRestore={doRestore}
            tampered={tampered}
          />
          <PatientList patients={patients} />
        </div>
      </div>

      {selectedAction && (
        <ChainExplorer action={selectedAction} actions={actions} onClose={() => setSelectedAction(null)} />
      )}
    </div>
  );
}

export default App;
