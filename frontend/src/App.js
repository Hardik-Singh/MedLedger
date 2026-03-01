import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';

const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const QUICK_ACTIONS = [
  { label: 'Look up patient', task: "Look up Sam Altman's patient record and check his current medications", agent: 'ARIA' },
  { label: 'Update meds', task: "Sam Altman is switching from Claritin to Zyrtec for allergies — update his record", agent: 'DELTA' },
  { label: 'Check allergies', task: "Which patients have seasonal allergies? Pull up their records", agent: 'ARIA' },
  { label: 'Audit trail', task: "Check Paul Graham, update his eye drops to Refresh Optive, then view his history", agent: 'ARIA' },
];

const ACTION_DOT = {
  SEARCH: '#3b82f6', VIEW: '#94a3b8', UPDATE: '#f59e0b', DELETE: '#ef4444',
  HISTORY: '#a78bfa', AUDIT: '#06b6d4', TASK_COMPLETE: '#22c55e',
  LAB_REVIEW: '#818cf8', APPOINTMENTS: '#38bdf8', SCHEDULE: '#34d399',
  RISK_REVIEW: '#fb923c', CARE_TEAM: '#c084fc',
};

function describeAction(a) {
  const p = a.payload || {};
  switch (a.action_type) {
    case 'SEARCH': return `Searched for "${p.query}"`;
    case 'VIEW': return `Viewed patient #${p.patient_id}`;
    case 'UPDATE': return `Updated ${p.patient_name || 'patient'}: ${p.field} "${p.old_value}" → "${p.new_value}"`;
    case 'DELETE': return `Deleted ${p.patient_name} (${p.mrn})`;
    case 'HISTORY': return `Checked history for patient #${p.patient_id}`;
    case 'AUDIT': return `Audit: ${p.check || 'integrity'} — ${p.intact !== undefined ? (p.intact ? 'passed' : 'FAILED') : `${p.issues_found || 0} issues`}`;
    case 'LAB_REVIEW': return `Reviewed labs for patient #${p.patient_id}`;
    case 'APPOINTMENTS': return `Checked appointments for patient #${p.patient_id}`;
    case 'SCHEDULE': return `Scheduled ${p.type || 'appointment'} for ${p.patient_name || 'patient'}`;
    case 'RISK_REVIEW': return `Reviewed high-risk patients`;
    case 'CARE_TEAM': return `Checked care team for patient #${p.patient_id}`;
    case 'TASK_COMPLETE': return 'Task complete';
    default: return a.action_type;
  }
}

// ── Action Detail Modal ──
function ActionDetail({ action, onClose }) {
  if (!action) return null;
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <div className="modal-top">
          <h3>Action Detail</h3>
          <button className="close-btn" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <div className="detail-row"><span className="detail-label">Type</span><span className="detail-val">{action.action_type}</span></div>
          <div className="detail-row"><span className="detail-label">Agent</span><span className="detail-val">{action.agent_id}</span></div>
          <div className="detail-row"><span className="detail-label">Time</span><span className="detail-val">{new Date(action.timestamp).toLocaleString()}</span></div>
          <div className="detail-row">
            <span className="detail-label">Verified</span>
            <span className={`detail-val ${action.verified ? 'text-green' : 'text-red'}`}>{action.verified ? 'Yes' : 'No'}</span>
          </div>
          <div className="detail-block"><span className="detail-label">Payload</span><pre className="detail-json">{JSON.stringify(action.payload, null, 2)}</pre></div>
          <div className="detail-block"><span className="detail-label">SHA-256 Hash</span><pre className="detail-hash">{action.hash}</pre></div>
          <div className="detail-block"><span className="detail-label">Previous Hash</span><pre className="detail-hash">{action.prev_hash}</pre></div>
          <div className="detail-block"><span className="detail-label">ECDSA P-256 Signature</span><pre className="detail-hash sig">{action.signature}</pre></div>
        </div>
      </div>
    </div>
  );
}

// ── Settings Panel ──
function SettingsPanel({ keyStatus, onSetKey, onSetMemoryKey, chain, onVerify, onTamper, onRestore, tampered, onExport, onClose }) {
  const [key, setKey] = useState('');
  const [memKey, setMemKey] = useState('');
  const memStatus = keyStatus.memory || {};
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <div className="modal-top">
          <h3>Settings</h3>
          <button className="close-btn" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <div className="setting-group">
            <label className="setting-label">Anthropic API Key</label>
            {keyStatus.has_key && (
              <div className="key-status"><span className="dot dot-green"></span><span className="key-preview">{keyStatus.key_preview || 'Connected'}</span></div>
            )}
            <div className="key-input-row">
              <input type="password" placeholder="sk-ant-..." value={key} onChange={e => setKey(e.target.value)} className="input" />
              <button className="btn btn-primary btn-sm" onClick={() => { onSetKey(key); setKey(''); }} disabled={!key}>{keyStatus.has_key ? 'Update' : 'Set'}</button>
            </div>
          </div>

          <div className="setting-group">
            <label className="setting-label">Supermemory Key <span className="optional">(optional)</span></label>
            {memStatus.has_key && (
              <div className="key-status"><span className="dot dot-green"></span><span className="key-preview">{memStatus.key_preview || 'Active'}</span></div>
            )}
            <div className="key-input-row">
              <input type="password" placeholder="sm_..." value={memKey} onChange={e => setMemKey(e.target.value)} className="input" />
              <button className="btn btn-primary btn-sm" onClick={() => { onSetMemoryKey(memKey); setMemKey(''); }} disabled={!memKey}>{memStatus.has_key ? 'Update' : 'Set'}</button>
            </div>
          </div>

          <div className="setting-group">
            <label className="setting-label">Chain Integrity</label>
            <div className="chain-row">
              <span className={chain.intact ? 'text-green' : 'text-red'}>{chain.intact ? 'Intact' : 'Broken'}</span>
              <button className="btn btn-sm" onClick={onVerify}>Verify</button>
              {!tampered
                ? <button className="btn btn-sm btn-danger" onClick={onTamper}>Tamper (demo)</button>
                : <button className="btn btn-sm btn-success" onClick={onRestore}>Restore</button>
              }
            </div>
          </div>

          <div className="setting-group">
            <label className="setting-label">Export Audit Log</label>
            <div className="chain-row">
              <button className="btn btn-sm" onClick={() => onExport('json')}>JSON</button>
              <button className="btn btn-sm" onClick={() => onExport('csv')}>CSV</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Setup Form ──
function SetupForm({ onSetKey, onSetMemoryKey }) {
  const [key, setKey] = useState('');
  const [memKey, setMemKey] = useState('');
  const [showMem, setShowMem] = useState(false);
  const handleSubmit = () => {
    if (key) onSetKey(key);
    if (memKey) onSetMemoryKey(memKey);
  };
  return (
    <div className="setup-form">
      <div className="setup-group">
        <label className="setup-label">Anthropic API Key</label>
        <input className="input input-lg" type="password" placeholder="sk-ant-api03-..." value={key} onChange={e => setKey(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSubmit()} />
      </div>
      {!showMem ? (
        <button className="link-btn" onClick={() => setShowMem(true)}>+ Add Supermemory key (optional)</button>
      ) : (
        <div className="setup-group">
          <label className="setup-label">Supermemory Key <span className="optional">(adds persistent memory)</span></label>
          <input className="input input-lg" type="password" placeholder="sm_..." value={memKey} onChange={e => setMemKey(e.target.value)} />
        </div>
      )}
      <button className="btn btn-primary btn-lg" onClick={handleSubmit} disabled={!key}>Get Started</button>
    </div>
  );
}

// ── Main App ──
function App() {
  const [actions, setActions] = useState([]);
  const [connected, setConnected] = useState(false);
  const [task, setTask] = useState('');
  const [agentName, setAgentName] = useState('ARIA');
  const [running, setRunning] = useState(false);
  const [keyStatus, setKeyStatus] = useState({ has_key: false });
  const [chain, setChain] = useState({ intact: true });
  const [tampered, setTampered] = useState(false);
  const [taskSummary, setTaskSummary] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [selectedAction, setSelectedAction] = useState(null);
  const feedRef = useRef(null);

  const fetchData = useCallback(async () => {
    try {
      const [lr, kr, vr] = await Promise.all([
        fetch(`${API_URL}/audit/log`), fetch(`${API_URL}/api/key-status`), fetch(`${API_URL}/audit/verify`),
      ]);
      if (lr.ok) setActions(await lr.json());
      if (kr.ok) setKeyStatus(await kr.json());
      if (vr.ok) setChain(await vr.json());
    } catch (e) { /* API not ready */ }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    let ws;
    function connect() {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => setConnected(true);
      ws.onclose = () => { setConnected(false); setTimeout(connect, 2000); };
      ws.onerror = () => ws.close();
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'action') {
          const { type, ...action } = data;
          setActions(prev => [...prev, action]);
          fetch(`${API_URL}/audit/verify`).then(r => r.json()).then(setChain).catch(() => {});
        }
        if (data.type === 'task_complete') { setRunning(false); if (data.summary) setTaskSummary(data.summary); }
        if (data.type === 'multi_agent_complete') setRunning(false);
        if (data.type === 'agent_start') setTaskSummary(null);
        if (data.type === 'error') setRunning(false);
        if (data.type === 'tamper') { setTampered(true); refresh(); }
        if (data.type === 'restored') { setTampered(false); refresh(); }
      };
    }
    function refresh() {
      fetch(`${API_URL}/audit/log`).then(r => r.json()).then(setActions).catch(() => {});
      fetch(`${API_URL}/audit/verify`).then(r => r.json()).then(setChain).catch(() => {});
    }
    connect();
    return () => ws?.close();
  }, []);

  useEffect(() => { if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight; }, [actions]);

  const runAgent = async (overrideTask, overrideAgent) => {
    const t = overrideTask || task.trim();
    const a = overrideAgent || agentName;
    if (!t) return;
    setRunning(true); setTaskSummary(null); setTask('');
    try {
      await fetch(`${API_URL}/agent/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ task: t, agent_name: a }) });
    } catch (e) { setRunning(false); }
  };

  const runAudit = async () => {
    setRunning(true); setTaskSummary(null);
    try { await fetch(`${API_URL}/agent/audit`, { method: 'POST' }); } catch (e) { setRunning(false); }
  };

  const setApiKey = async (key) => {
    await fetch(`${API_URL}/api/set-key`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key }) });
    const r = await fetch(`${API_URL}/api/key-status`);
    if (r.ok) setKeyStatus(await r.json());
  };

  const setMemoryKey = async (key) => {
    await fetch(`${API_URL}/api/set-memory-key`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key }) });
    const r = await fetch(`${API_URL}/api/key-status`);
    if (r.ok) setKeyStatus(await r.json());
  };

  const verifyChain = async () => { const r = await fetch(`${API_URL}/audit/verify`); if (r.ok) setChain(await r.json()); };
  const doTamper = () => fetch(`${API_URL}/audit/tamper`, { method: 'POST' });
  const doRestore = () => fetch(`${API_URL}/audit/restore`, { method: 'POST' });

  const exportLog = async (format = 'json') => {
    const url = format === 'csv' ? `${API_URL}/audit/export/csv` : `${API_URL}/audit/export`;
    const res = await fetch(url);
    if (!res.ok) return;
    const blob = format === 'csv' ? await res.blob() : new Blob([JSON.stringify(await res.json(), null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `medledger-audit-${new Date().toISOString().slice(0, 10)}.${format}`;
    a.click(); URL.revokeObjectURL(a.href);
  };

  // ── Setup Screen ──
  if (!keyStatus.has_key) {
    return (
      <div className="app setup-screen">
        <div className="setup-card">
          <h1 className="setup-title">MedLedger</h1>
          <p className="setup-subtitle">AI-powered medical record agent with cryptographic audit trails</p>
          <SetupForm onSetKey={setApiKey} onSetMemoryKey={setMemoryKey} />
        </div>
      </div>
    );
  }

  // ── Main Screen ──
  return (
    <div className="app">
      <header className="header">
        <h1 className="logo">MedLedger</h1>
        <div className="header-right">
          <span className={`dot ${connected ? 'dot-green' : 'dot-red'}`}></span>
          <span className="conn-label">{connected ? 'Live' : 'Connecting...'}</span>
          <button className="settings-btn" onClick={() => setShowSettings(true)}>Settings</button>
        </div>
      </header>

      <main className="main">
        <div className="task-section">
          <div className="task-input-row">
            <input
              className="task-input"
              type="text"
              placeholder="Tell the agent what to do... e.g. &quot;Look up Sam Altman's medications&quot;"
              value={task}
              onChange={e => setTask(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && runAgent()}
              disabled={running}
            />
            <select className="agent-picker" value={agentName} onChange={e => setAgentName(e.target.value)} disabled={running}>
              <option value="ARIA">ARIA (read)</option>
              <option value="DELTA">DELTA (write)</option>
              <option value="AUDITOR">AUDITOR</option>
            </select>
            <button className="run-btn" onClick={() => runAgent()} disabled={running || !task.trim()}>
              {running ? 'Running...' : 'Run'}
            </button>
          </div>

          <div className="quick-actions">
            {QUICK_ACTIONS.map((qa, i) => (
              <button key={i} className="quick-btn" onClick={() => runAgent(qa.task, qa.agent)} disabled={running}>{qa.label}</button>
            ))}
            <button className="quick-btn quick-audit" onClick={runAudit} disabled={running}>Run audit</button>
          </div>

          {running && <div className="running-bar"></div>}
        </div>

        <div className="feed-section">
          <h2 className="feed-title">Activity {actions.length > 0 && <span className="feed-count">{actions.length}</span>}</h2>

          {taskSummary && (
            <div className="summary-banner">
              Task complete — {taskSummary.total_actions} actions, {taskSummary.patients_touched} patients, {taskSummary.elapsed_seconds}s
            </div>
          )}

          <div className="feed-list" ref={feedRef}>
            {actions.length === 0 ? (
              <div className="empty-state">
                <p className="empty-main">No activity yet</p>
                <p className="empty-hint">Type a task above or click a quick action to get started</p>
              </div>
            ) : (
              actions.map((a, i) => (
                <div key={a.id || i} className="feed-item" onClick={() => setSelectedAction(a)}>
                  <span className="feed-dot" style={{ background: ACTION_DOT[a.action_type] || '#64748b' }}></span>
                  <span className="feed-text">{describeAction(a)}</span>
                  <span className="feed-meta">
                    <span className="feed-agent">{a.agent_id}</span>
                    <span className="feed-time">{new Date(a.timestamp).toLocaleTimeString()}</span>
                    <span className={a.verified ? 'text-green' : 'text-red'}>{a.verified ? '\u2713' : '\u2717'}</span>
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </main>

      {showSettings && (
        <SettingsPanel
          keyStatus={keyStatus} onSetKey={setApiKey} onSetMemoryKey={setMemoryKey}
          chain={chain} onVerify={verifyChain} onTamper={doTamper} onRestore={doRestore}
          tampered={tampered} onExport={exportLog} onClose={() => setShowSettings(false)}
        />
      )}

      {selectedAction && <ActionDetail action={selectedAction} onClose={() => setSelectedAction(null)} />}
    </div>
  );
}

export default App;
