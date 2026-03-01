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

function truncHash(h, len = 12) {
  if (!h) return '—';
  return h.length > len ? h.slice(0, len) + '...' : h;
}

function ActionCard({ action, index }) {
  const colors = ACTION_COLORS[action.action_type] || ACTION_COLORS.VIEW;
  const ts = new Date(action.timestamp).toLocaleTimeString();

  let summary = '';
  const p = action.payload || {};
  if (action.action_type === 'SEARCH') summary = `Query: "${p.query}"`;
  else if (action.action_type === 'VIEW') summary = `Patient #${p.patient_id}`;
  else if (action.action_type === 'UPDATE') summary = `${p.patient_name}: ${p.field} "${p.old_value}" → "${p.new_value}"`;
  else if (action.action_type === 'DELETE') summary = `${p.patient_name} (${p.mrn})`;
  else if (action.action_type === 'HISTORY') summary = `Patient #${p.patient_id}`;
  else if (action.action_type === 'TASK_COMPLETE') summary = `Task finished`;

  return (
    <div className="action-card" style={{ borderLeftColor: colors.border }}>
      <div className="action-header">
        <span className="action-badge" style={{ background: colors.bg, color: colors.text, border: `1px solid ${colors.border}` }}>
          {colors.label}
        </span>
        <span className="action-index">#{index + 1}</span>
        <span className="action-time">{ts}</span>
        <span className={`action-verified ${action.verified ? 'verified-ok' : 'verified-fail'}`}>
          {action.verified ? '\u2713' : '\u2717'}
        </span>
      </div>
      <div className="action-summary">{summary}</div>
      <div className="action-hashes">
        <div className="hash-row">
          <span className="hash-label">hash</span>
          <span className="hash-value">{truncHash(action.hash)}</span>
        </div>
        <div className="hash-row">
          <span className="hash-label">prev</span>
          <span className="hash-value">{truncHash(action.prev_hash)}</span>
        </div>
        <div className="hash-row">
          <span className="hash-label">sig</span>
          <span className="hash-value">{truncHash(action.signature, 16)}</span>
        </div>
      </div>
    </div>
  );
}

function ChainStatus({ chain, actions }) {
  return (
    <div className="chain-panel">
      <h3 className="panel-title">Chain Integrity</h3>
      <div className={`chain-status-badge ${chain.intact ? 'chain-ok' : 'chain-broken'}`}>
        {chain.intact ? 'CHAIN INTACT \u2713' : 'CHAIN BROKEN \u2717'}
      </div>
      <div className="chain-stats">
        <div className="stat-item">
          <span className="stat-value">{chain.total_actions || actions.length}</span>
          <span className="stat-label">Total Actions</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{actions.filter(a => a.verified).length}</span>
          <span className="stat-label">Verified</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{actions.filter(a => !a.verified).length}</span>
          <span className="stat-label">Failed</span>
        </div>
      </div>
      {chain.last_verified && (
        <div className="chain-last-verified">
          Last verified: {new Date(chain.last_verified).toLocaleTimeString()}
        </div>
      )}
      {chain.error && (
        <div className="chain-error">{chain.error}</div>
      )}
      <div className="chain-info">
        <div className="info-row"><span>Algorithm</span><span>ECDSA P-256</span></div>
        <div className="info-row"><span>Hash</span><span>SHA-256</span></div>
        <div className="info-row"><span>Chain Type</span><span>Hash-linked</span></div>
        <div className="info-row"><span>Genesis</span><span className="mono">GENESIS</span></div>
      </div>
    </div>
  );
}

function PatientList({ patients }) {
  return (
    <div className="patient-panel">
      <h3 className="panel-title">Patient Registry</h3>
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

function App() {
  const [actions, setActions] = useState([]);
  const [patients, setPatients] = useState([]);
  const [chain, setChain] = useState({ intact: true, total_actions: 0 });
  const [connected, setConnected] = useState(false);
  const [task, setTask] = useState('');
  const [running, setRunning] = useState(false);
  const feedRef = useRef(null);
  const wsRef = useRef(null);

  const fetchData = useCallback(async () => {
    try {
      const [logRes, patientsRes, verifyRes] = await Promise.all([
        fetch(`${API_URL}/audit/log`),
        fetch(`${API_URL}/patients/current`),
        fetch(`${API_URL}/audit/verify`),
      ]);
      if (logRes.ok) setActions(await logRes.json());
      if (patientsRes.ok) setPatients(await patientsRes.json());
      if (verifyRes.ok) setChain(await verifyRes.json());
    } catch (e) {
      console.log('API not available yet');
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        setTimeout(connect, 2000);
      };
      ws.onerror = () => ws.close();

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'action') {
          const { type, ...action } = data;
          setActions(prev => [...prev, action]);
          // Refresh patients after mutations
          if (['UPDATE', 'DELETE'].includes(action.action_type)) {
            fetch(`${API_URL}/patients/current`).then(r => r.json()).then(setPatients).catch(() => {});
          }
          // Refresh chain verification
          fetch(`${API_URL}/audit/verify`).then(r => r.json()).then(setChain).catch(() => {});
        }
        if (data.type === 'task_complete') {
          setRunning(false);
        }
        if (data.type === 'error') {
          setRunning(false);
        }
      };
    }
    connect();
    return () => wsRef.current?.close();
  }, []);

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [actions]);

  const runAgent = async () => {
    if (!task.trim()) return;
    setRunning(true);
    try {
      await fetch(`${API_URL}/agent/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: task.trim() }),
      });
    } catch (e) {
      setRunning(false);
    }
  };

  const demoTask = 'Find patient John Smith, update his medication from Metformin to Ozempic, then search for any patients with diabetes';

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1 className="app-title">MedLedger</h1>
          <span className="app-subtitle">Cryptographic Audit Trail</span>
        </div>
        <div className="header-right">
          <span className={`connection-dot ${connected ? 'dot-connected' : 'dot-disconnected'}`}></span>
          <span className="connection-text">{connected ? 'Live' : 'Connecting...'}</span>
        </div>
      </header>

      <div className="agent-bar">
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
        <button className="agent-demo-btn" onClick={() => setTask(demoTask)} disabled={running}>
          Load Demo
        </button>
      </div>

      <div className="main-grid">
        <div className="portal-panel">
          <h3 className="panel-title">
            Patient Portal
            <a href={PORTAL_URL} target="_blank" rel="noopener noreferrer" className="portal-link">Open Portal</a>
          </h3>
          <iframe
            src={PORTAL_URL}
            title="MedLedger Portal"
            className="portal-iframe"
          />
        </div>

        <div className="feed-panel">
          <h3 className="panel-title">Audit Feed <span className="action-count">{actions.length} actions</span></h3>
          <div className="action-feed" ref={feedRef}>
            {actions.length === 0 ? (
              <div className="empty-feed">
                <div className="empty-icon">&#9741;</div>
                <p>No actions recorded yet.</p>
                <p className="empty-hint">Run the agent to see cryptographically signed actions appear here in real-time.</p>
              </div>
            ) : (
              actions.map((action, i) => <ActionCard key={action.id || i} action={action} index={i} />)
            )}
          </div>
        </div>

        <div className="right-col">
          <ChainStatus chain={chain} actions={actions} />
          <PatientList patients={patients} />
        </div>
      </div>
    </div>
  );
}

export default App;
