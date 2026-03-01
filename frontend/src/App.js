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
  AUDIT: { bg: '#164e63', border: '#06b6d4', text: '#22d3ee', label: 'AUDIT' },
  LAB_REVIEW: { bg: '#1e1b4b', border: '#818cf8', text: '#a5b4fc', label: 'LABS' },
  APPOINTMENTS: { bg: '#1e3a5f', border: '#38bdf8', text: '#7dd3fc', label: 'APPTS' },
  SCHEDULE: { bg: '#064e3b', border: '#34d399', text: '#6ee7b7', label: 'SCHED' },
  RISK_REVIEW: { bg: '#431407', border: '#fb923c', text: '#fdba74', label: 'RISK' },
  CARE_TEAM: { bg: '#1e1b4b', border: '#c084fc', text: '#d8b4fe', label: 'TEAM' },
  TASK_COMPLETE: { bg: '#052e16', border: '#22c55e', text: '#4ade80', label: 'DONE' },
};

const RISK = {
  SEARCH: { level: 'LOW', color: '#22c55e' },
  VIEW: { level: 'LOW', color: '#22c55e' },
  HISTORY: { level: 'LOW', color: '#22c55e' },
  AUDIT: { level: 'LOW', color: '#06b6d4' },
  LAB_REVIEW: { level: 'LOW', color: '#818cf8' },
  APPOINTMENTS: { level: 'LOW', color: '#38bdf8' },
  SCHEDULE: { level: 'MED', color: '#34d399' },
  RISK_REVIEW: { level: 'LOW', color: '#fb923c' },
  CARE_TEAM: { level: 'LOW', color: '#c084fc' },
  UPDATE: { level: 'MED', color: '#f59e0b' },
  DELETE: { level: 'HIGH', color: '#ef4444' },
  TASK_COMPLETE: { level: 'INFO', color: '#6366f1' },
};

const AGENT_COLORS = { aria: '#3b82f6', delta: '#f59e0b', auditor: '#06b6d4' };

const TEMPLATES = [
  { label: 'Lookup', task: "Look up Sam Altman's patient record and check his current medications" },
  { label: 'Update Meds', task: "Sam Altman is switching from Claritin to Zyrtec for allergies — update his record" },
  { label: 'Allergy Check', task: "Which patients have seasonal allergies? Pull up their records" },
  { label: 'Audit Trail', task: "Check Paul Graham, update his eye drops to Refresh Optive, then view his history" },
];

const MULTI_TEMPLATES = [
  {
    label: 'ARIA + DELTA',
    agents: [
      { name: "ARIA", task: "Search for Sam Altman and view his full record. Report what you find." },
      { name: "DELTA", task: "Update Sam Altman's medication from Claritin 10mg daily to Zyrtec 10mg daily. Keep Flonase nasal spray." },
    ],
  },
  {
    label: 'Triage + Update',
    agents: [
      { name: "ARIA", task: "Find all patients with headaches or allergies and view their records" },
      { name: "DELTA", task: "Update Garry Tan's medication — add Excedrin Migraine PRN to his current meds" },
    ],
  },
];

function trunc(h, n = 12) { return !h ? '\u2014' : h.length > n ? h.slice(0, n) + '\u2026' : h; }

function clinicalText(a) {
  const p = a.payload || {};
  if (a.action_type === 'SEARCH') return `Searched for "${p.query}"`;
  if (a.action_type === 'VIEW') return `Viewed patient #${p.patient_id}`;
  if (a.action_type === 'UPDATE') return `Updated ${p.patient_name}'s ${p.field}: "${p.old_value}" \u2192 "${p.new_value}"`;
  if (a.action_type === 'DELETE') return `Deleted ${p.patient_name} (${p.mrn})`;
  if (a.action_type === 'HISTORY') return `Checked history for patient #${p.patient_id}`;
  if (a.action_type === 'AUDIT') return `Audit check: ${p.check || 'integrity'}`;
  if (a.action_type === 'LAB_REVIEW') return `Reviewed labs for patient #${p.patient_id}`;
  if (a.action_type === 'APPOINTMENTS') return `Checked appointments for patient #${p.patient_id}`;
  if (a.action_type === 'SCHEDULE') return `Scheduled ${p.type || 'appointment'} for ${p.patient_name || `patient #${p.patient_id}`}`;
  if (a.action_type === 'RISK_REVIEW') return `Reviewed high-risk patients`;
  if (a.action_type === 'CARE_TEAM') return `Checked care team for patient #${p.patient_id}`;
  if (a.action_type === 'TASK_COMPLETE') return `Task complete`;
  return a.action_type;
}

function auditText(a) {
  const p = a.payload || {};
  if (a.action_type === 'SEARCH') return `Query: "${p.query}"`;
  if (a.action_type === 'VIEW') return `Patient #${p.patient_id}`;
  if (a.action_type === 'UPDATE') return `${p.patient_name}: ${p.field} "${trunc(p.old_value, 20)}" \u2192 "${trunc(p.new_value, 20)}"`;
  if (a.action_type === 'DELETE') return `${p.patient_name} (${p.mrn})`;
  if (a.action_type === 'HISTORY') return `Patient #${p.patient_id}`;
  if (a.action_type === 'AUDIT') return `${p.check || 'audit'}: ${p.intact !== undefined ? (p.intact ? 'PASSED' : 'FAILED') : `${p.issues_found || 0} issues`}`;
  if (a.action_type === 'LAB_REVIEW') return `Labs: Patient #${p.patient_id}`;
  if (a.action_type === 'APPOINTMENTS') return `Appointments: Patient #${p.patient_id}`;
  if (a.action_type === 'SCHEDULE') return `Scheduled: ${p.type || 'appt'} for ${p.patient_name || '#' + p.patient_id}`;
  if (a.action_type === 'RISK_REVIEW') return `Risk review: ${p.query || 'high_risk'}`;
  if (a.action_type === 'CARE_TEAM') return `Care team: Patient #${p.patient_id}`;
  return 'Done';
}

// ─── Chain Explorer Modal ───
function ChainExplorer({ action, actions, onClose }) {
  if (!action) return null;
  const idx = actions.findIndex(a => a.id === action.id);
  const prev = idx > 0 ? actions[idx - 1] : null;
  const next = idx < actions.length - 1 ? actions[idx + 1] : null;
  const risk = RISK[action.action_type] || RISK.VIEW;
  const ac = ACTION_COLORS[action.action_type] || ACTION_COLORS.VIEW;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Chain Explorer \u2014 Block #{idx + 1}</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="explorer-badge-row">
          <span className="action-badge" style={{ background: ac.bg, color: ac.text, border: `1px solid ${ac.border}` }}>{action.action_type}</span>
          <span className="risk-badge" style={{ color: risk.color, borderColor: risk.color }}>{risk.level} RISK</span>
          <span className={action.verified ? 'verified-ok' : 'verified-fail'}>{action.verified ? '\u2713 Verified' : '\u2717 Failed'}</span>
          <span className="explorer-agent" style={{ color: AGENT_COLORS[action.agent_id] || '#94a3b8' }}>{action.agent_id}</span>
        </div>
        <div className="explorer-section"><label>Timestamp</label><p>{new Date(action.timestamp).toLocaleString()}</p></div>
        <div className="explorer-section"><label>Payload</label><pre className="explorer-json">{JSON.stringify(action.payload, null, 2)}</pre></div>
        <div className="explorer-section"><label>SHA-256 Hash</label><pre className="explorer-hash">{action.hash}</pre></div>
        <div className="explorer-section"><label>Previous Hash</label><pre className="explorer-hash">{action.prev_hash}</pre></div>
        <div className="explorer-section"><label>ECDSA P-256 Signature</label><pre className="explorer-hash" style={{ fontSize: '10px' }}>{action.signature}</pre></div>
        <div className="explorer-chain-nav">
          {prev && <div className="chain-link"><span>\u2190 Prev: {trunc(prev.hash, 16)}</span><span className="chain-link-type">{prev.action_type}</span></div>}
          <div className="chain-link chain-link-current"><span>Current: {trunc(action.hash, 16)}</span></div>
          {next && <div className="chain-link"><span>Next: {trunc(next.hash, 16)}</span><span className="chain-link-type">{next.action_type}</span><span>\u2192</span></div>}
        </div>
      </div>
    </div>
  );
}

// ─── Auditor Card ───
function AuditorCard({ action, index, onClick }) {
  const c = ACTION_COLORS[action.action_type] || ACTION_COLORS.VIEW;
  const agentColor = AGENT_COLORS[action.agent_id] || '#64748b';
  return (
    <div className="action-card" style={{ borderLeftColor: agentColor }} onClick={() => onClick(action)}>
      <div className="action-header">
        <span className="action-badge" style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}>{c.label}</span>
        <span className="action-agent-tag" style={{ color: agentColor }}>{action.agent_id}</span>
        <span className="action-index">#{index + 1}</span>
        <span className="action-time">{new Date(action.timestamp).toLocaleTimeString()}</span>
        <span className={action.verified ? 'verified-ok' : 'verified-fail'}>{action.verified ? '\u2713' : '\u2717'}</span>
      </div>
      <div className="action-summary">{auditText(action)}</div>
      <div className="action-hashes">
        <div className="hash-row"><span className="hash-label">hash</span><span className="hash-value">{trunc(action.hash)}</span></div>
        <div className="hash-row"><span className="hash-label">prev</span><span className="hash-value">{trunc(action.prev_hash)}</span></div>
        <div className="hash-row"><span className="hash-label">sig</span><span className="hash-value">{trunc(action.signature, 16)}</span></div>
      </div>
    </div>
  );
}

// ─── Clinical Card ───
function ClinicalCard({ action }) {
  const c = ACTION_COLORS[action.action_type] || ACTION_COLORS.VIEW;
  return (
    <div className="clinical-card">
      <div className="clinical-timeline-dot" style={{ background: c.border }}></div>
      <div className="clinical-content">
        <div className="clinical-header">
          <span className="clinical-time">{new Date(action.timestamp).toLocaleTimeString()}</span>
          <span className="clinical-agent-tag" style={{ color: AGENT_COLORS[action.agent_id] || '#64748b' }}>{action.agent_id}</span>
        </div>
        <p className="clinical-text">{clinicalText(action)}</p>
      </div>
    </div>
  );
}

// ─── Task Summary ───
function TaskSummary({ summary, agentName }) {
  if (!summary) return null;
  return (
    <div className="task-summary-card">
      <div className="summary-header"><span className="summary-icon">\u2713</span><h4>Complete \u2014 {agentName}</h4></div>
      <div className="summary-stats">
        <div className="summary-stat"><span className="summary-val">{summary.total_actions}</span><span className="summary-lbl">Actions</span></div>
        <div className="summary-stat"><span className="summary-val">{summary.patients_touched}</span><span className="summary-lbl">Patients</span></div>
        <div className="summary-stat"><span className="summary-val">{summary.elapsed_seconds}s</span><span className="summary-lbl">Time</span></div>
      </div>
    </div>
  );
}

// ─── Alerts Dropdown ───
function AlertsBell({ alerts, onAck }) {
  const [open, setOpen] = useState(false);
  const unread = alerts.filter(a => !a.acknowledged).length;
  const sevColor = { CRITICAL: '#ef4444', HIGH: '#f59e0b', MEDIUM: '#3b82f6' };
  return (
    <div className="alerts-wrap">
      <button className={`alerts-bell ${unread > 0 ? 'alerts-has-unread' : ''}`} onClick={() => setOpen(!open)}>
        {'\u{1F514}'}{unread > 0 && <span className="alerts-badge">{unread}</span>}
      </button>
      {open && (
        <div className="alerts-dropdown">
          <div className="alerts-header">Alerts ({alerts.length})</div>
          {alerts.length === 0 ? <div className="alerts-empty">No alerts</div> : (
            <div className="alerts-list">
              {[...alerts].reverse().slice(0, 20).map(a => (
                <div key={a.id} className={`alert-item ${a.acknowledged ? 'alert-acked' : ''}`}>
                  <span className="alert-sev" style={{ background: sevColor[a.severity] || '#6366f1' }}>{a.severity}</span>
                  <span className="alert-msg">{a.message}</span>
                  {!a.acknowledged && <button className="alert-ack-btn" onClick={() => onAck(a.id)}>Ack</button>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Chain Status ───
function ChainStatus({ chain, actions, onVerify, onTamper, onRestore, tampered }) {
  const riskScore = actions.length === 0 ? 0 : Math.round(
    actions.reduce((s, a) => s + ({ SEARCH: 1, VIEW: 1, HISTORY: 1, LAB_REVIEW: 1, APPOINTMENTS: 1, CARE_TEAM: 1, RISK_REVIEW: 1, SCHEDULE: 3, UPDATE: 5, DELETE: 10 }[a.action_type] || 0), 0) / (actions.length * 10) * 100
  );
  const riskColor = riskScore < 30 ? '#22c55e' : riskScore < 60 ? '#f59e0b' : '#ef4444';
  const agents = [...new Set(actions.map(a => a.agent_id))];
  return (
    <div className="chain-panel">
      <h3 className="panel-title">Chain Integrity</h3>
      <div className={`chain-status-badge ${chain.intact ? 'chain-ok' : 'chain-broken'}`}>
        {chain.intact ? 'CHAIN INTACT \u2713' : 'CHAIN BROKEN \u2717'}
      </div>
      <div className="chain-stats">
        <div className="stat-item"><span className="stat-value">{chain.total_actions || actions.length}</span><span className="stat-label">Total</span></div>
        <div className="stat-item"><span className="stat-value">{actions.filter(a => a.verified).length}</span><span className="stat-label">Valid</span></div>
        <div className="stat-item"><span className="stat-value">{actions.filter(a => !a.verified).length}</span><span className="stat-label">Failed</span></div>
      </div>
      <div className="risk-meter">
        <label className="risk-meter-label">Session Risk</label>
        <div className="risk-bar-bg"><div className="risk-bar-fill" style={{ width: `${Math.min(riskScore, 100)}%`, background: riskColor }}></div></div>
        <span className="risk-score" style={{ color: riskColor }}>{riskScore}%</span>
      </div>
      {agents.length > 0 && (
        <div className="chain-agents">
          <label className="risk-meter-label">Signing Agents</label>
          {agents.map(a => (
            <span key={a} className="agent-chip" style={{ borderColor: AGENT_COLORS[a] || '#64748b', color: AGENT_COLORS[a] || '#94a3b8' }}>
              {a} ({actions.filter(x => x.agent_id === a).length})
            </span>
          ))}
        </div>
      )}
      {chain.error && <div className="chain-error">{chain.error}</div>}
      <div className="chain-actions">
        <button className="btn-chain" onClick={onVerify}>Verify</button>
        {!tampered
          ? <button className="btn-tamper" onClick={onTamper} disabled={actions.length === 0}>Tamper</button>
          : <button className="btn-restore" onClick={onRestore}>Restore</button>
        }
      </div>
      <div className="chain-info">
        <div className="info-row"><span>Signing</span><span>ECDSA P-256</span></div>
        <div className="info-row"><span>Hashing</span><span>SHA-256</span></div>
        <div className="info-row"><span>Chain</span><span>Hash-linked</span></div>
        <div className="info-row"><span>Genesis</span><span className="mono">GENESIS</span></div>
        <div className="info-row"><span>Keys</span><span>{agents.length || 1} keypair{agents.length !== 1 ? 's' : ''}</span></div>
      </div>
    </div>
  );
}

// ─── Patient List ───
function PatientList({ patients }) {
  return (
    <div className="patient-panel">
      <h3 className="panel-title">Patients <span className="patient-count">{patients.filter(p => !p.deleted).length} active</span></h3>
      <div className="patient-list">
        {patients.map(p => (
          <div key={p.id} className={`patient-row ${p.deleted ? 'patient-deleted' : ''}`}>
            <div className="patient-name">
              {p.deleted && <span className="deleted-tag">[DEL]</span>}
              {p.first_name} {p.last_name}
              {p.blood_type && <span className="blood-type">{p.blood_type}</span>}
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

// ─── Stats Bar ───
function StatsBar({ actions }) {
  const counts = {};
  actions.forEach(a => { counts[a.action_type] = (counts[a.action_type] || 0) + 1; });
  return (
    <div className="stats-bar">
      <span className="stats-item">Actions: <b>{actions.length}</b></span>
      <span className="stats-item">Searches: <b>{counts.SEARCH || 0}</b></span>
      <span className="stats-item">Views: <b>{counts.VIEW || 0}</b></span>
      <span className="stats-item stats-update">Updates: <b>{counts.UPDATE || 0}</b></span>
      <span className="stats-item stats-delete">Deletes: <b>{counts.DELETE || 0}</b></span>
      <span className="stats-item">Agents: <b>{[...new Set(actions.map(a => a.agent_id))].length}</b></span>
    </div>
  );
}

// ─── API Key Bar ───
function ApiKeyBar({ keyStatus, onSetKey, onSetMemoryKey }) {
  const [key, setKey] = useState('');
  const [memKey, setMemKey] = useState('');
  const [show, setShow] = useState(false);
  const [showMem, setShowMem] = useState(false);
  const memStatus = keyStatus.memory || {};
  return (
    <div className="apikey-bar">
      {keyStatus.has_key && !show ? (
        <>
          <span className="apikey-dot dot-connected"></span>
          <span className="apikey-connected">Anthropic: {keyStatus.key_preview || 'Connected'}</span>
          <button className="apikey-change-btn" onClick={() => setShow(true)}>Change</button>
        </>
      ) : (
        <>
          <span className="apikey-dot dot-disconnected"></span>
          <input className="apikey-input" type="password" placeholder="sk-ant-..." value={key} onChange={e => setKey(e.target.value)} />
          <button className="apikey-set-btn" onClick={() => { onSetKey(key); setKey(''); setShow(false); }} disabled={!key}>Set</button>
          {show && <button className="apikey-cancel-btn" onClick={() => setShow(false)}>Cancel</button>}
        </>
      )}
      <span className="apikey-divider">|</span>
      {memStatus.has_key && !showMem ? (
        <>
          <span className="memory-dot dot-connected"></span>
          <span className="apikey-connected">Memory: {memStatus.key_preview || 'Active'}</span>
          <button className="apikey-change-btn" onClick={() => setShowMem(true)}>Change</button>
        </>
      ) : (
        <>
          <span className="memory-dot dot-disconnected"></span>
          <input className="apikey-input apikey-input-sm" type="password" placeholder="sm_..." value={memKey} onChange={e => setMemKey(e.target.value)} />
          <button className="apikey-set-btn" onClick={() => { onSetMemoryKey(memKey); setMemKey(''); setShowMem(false); }} disabled={!memKey}>Set</button>
          {showMem && <button className="apikey-cancel-btn" onClick={() => setShowMem(false)}>Cancel</button>}
        </>
      )}
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
  const [agentName, setAgentName] = useState('ARIA');
  const [running, setRunning] = useState(false);
  const [view, setView] = useState('auditor');
  const [agentFilter, setAgentFilter] = useState('all');
  const [selectedAction, setSelectedAction] = useState(null);
  const [tampered, setTampered] = useState(false);
  const [taskSummary, setTaskSummary] = useState(null);
  const [keyStatus, setKeyStatus] = useState({ has_key: false });
  const [alertsList, setAlertsList] = useState([]);
  const feedRef = useRef(null);
  const wsRef = useRef(null);

  const fetchData = useCallback(async () => {
    try {
      const [lr, pr, vr, kr, ar] = await Promise.all([
        fetch(`${API_URL}/audit/log`), fetch(`${API_URL}/patients/current`),
        fetch(`${API_URL}/audit/verify`), fetch(`${API_URL}/api/key-status`),
        fetch(`${API_URL}/alerts`),
      ]);
      if (lr.ok) setActions(await lr.json());
      if (pr.ok) setPatients(await pr.json());
      if (vr.ok) setChain(await vr.json());
      if (kr.ok) setKeyStatus(await kr.json());
      if (ar.ok) setAlertsList(await ar.json());
    } catch (e) { /* API not ready */ }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    let ws;
    function connect() {
      ws = new WebSocket(WS_URL);
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
          fetch(`${API_URL}/alerts`).then(r => r.json()).then(setAlertsList).catch(() => {});
        }
        if (data.type === 'task_complete') { setRunning(false); if (data.summary) setTaskSummary({ summary: data.summary, agentName: data.agent_name }); }
        if (data.type === 'multi_agent_complete') { setRunning(false); }
        if (data.type === 'agent_start') { setTaskSummary(null); }
        if (data.type === 'error') { setRunning(false); }
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

  const runAgent = async () => {
    if (!task.trim()) return;
    setRunning(true); setTaskSummary(null);
    try {
      await fetch(`${API_URL}/agent/run`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: task.trim(), agent_name: agentName }),
      });
    } catch (e) { setRunning(false); }
  };

  const runMulti = async (agents) => {
    setRunning(true); setTaskSummary(null);
    try {
      await fetch(`${API_URL}/agent/multi`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agents }),
      });
    } catch (e) { setRunning(false); }
  };

  const verifyChain = async () => {
    const [vr, lr] = await Promise.all([fetch(`${API_URL}/audit/verify`), fetch(`${API_URL}/audit/log`)]);
    if (vr.ok) setChain(await vr.json());
    if (lr.ok) setActions(await lr.json());
  };

  const doTamper = () => fetch(`${API_URL}/audit/tamper`, { method: 'POST' });
  const doRestore = () => fetch(`${API_URL}/audit/restore`, { method: 'POST' });
  const ackAlert = async (id) => {
    await fetch(`${API_URL}/alerts/${id}/ack`, { method: 'POST' });
    const r = await fetch(`${API_URL}/alerts`);
    if (r.ok) setAlertsList(await r.json());
  };

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

  const runAudit = async () => {
    setRunning(true); setTaskSummary(null);
    try {
      await fetch(`${API_URL}/agent/audit`, { method: 'POST' });
    } catch (e) { setRunning(false); }
  };

  const filtered = agentFilter === 'all' ? actions : actions.filter(a => a.agent_id === agentFilter);
  const agents = [...new Set(actions.map(a => a.agent_id))];

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1 className="app-title">MedLedger</h1>
          <span className="app-subtitle">Cryptographic Audit Trail</span>
        </div>
        <div className="header-right">
          <div className="export-group">
            <button className="export-btn" onClick={() => exportLog('json')}>JSON</button>
            <button className="export-btn" onClick={() => exportLog('csv')}>CSV</button>
          </div>
          <AlertsBell alerts={alertsList} onAck={ackAlert} />
          <span className={`connection-dot ${connected ? 'dot-connected' : 'dot-disconnected'}`}></span>
          <span className="connection-text">{connected ? 'Live' : '...'}</span>
        </div>
      </header>

      <ApiKeyBar keyStatus={keyStatus} onSetKey={setApiKey} onSetMemoryKey={setMemoryKey} />

      <div className="agent-bar">
        <select className="agent-select" value={agentName} onChange={e => setAgentName(e.target.value)} disabled={running}>
          <option value="ARIA">ARIA (Read)</option>
          <option value="DELTA">DELTA (Write)</option>
          <option value="AUDITOR">AUDITOR (Verify)</option>
          <option value="MedLedger Agent">Custom</option>
        </select>
        <input className="agent-input" type="text" placeholder="Type any task..." value={task} onChange={e => setTask(e.target.value)} onKeyDown={e => e.key === 'Enter' && runAgent()} disabled={running} />
        <button className="agent-run-btn" onClick={runAgent} disabled={running || !task.trim()}>
          {running ? 'Running...' : 'Run'}
        </button>
      </div>

      <div className="template-bar">
        {TEMPLATES.map((t, i) => (
          <button key={i} className="template-btn" onClick={() => setTask(t.task)} disabled={running}>{t.label}</button>
        ))}
        <span className="template-divider">|</span>
        {MULTI_TEMPLATES.map((t, i) => (
          <button key={`m${i}`} className="template-btn template-multi" onClick={() => runMulti(t.agents)} disabled={running}>
            {t.label}
          </button>
        ))}
        <span className="template-divider">|</span>
        <button className="template-btn template-audit" onClick={runAudit} disabled={running}>Audit</button>
      </div>

      <StatsBar actions={actions} />

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
              <span className="action-count">{filtered.length}</span>
            </h3>
            <div className="feed-controls">
              {agents.length > 1 && (
                <select className="agent-filter" value={agentFilter} onChange={e => setAgentFilter(e.target.value)}>
                  <option value="all">All agents</option>
                  {agents.map(a => <option key={a} value={a}>{a}</option>)}
                </select>
              )}
              <div className="view-toggle">
                <button className={`toggle-btn ${view === 'auditor' ? 'toggle-active' : ''}`} onClick={() => setView('auditor')}>Auditor</button>
                <button className={`toggle-btn ${view === 'clinical' ? 'toggle-active' : ''}`} onClick={() => setView('clinical')}>Clinical</button>
              </div>
            </div>
          </div>

          {taskSummary && <TaskSummary summary={taskSummary.summary} agentName={taskSummary.agentName} />}

          <div className="action-feed" ref={feedRef}>
            {filtered.length === 0 ? (
              <div className="empty-feed">
                <div className="empty-icon">{'\u2693'}</div>
                <p>No actions yet</p>
                <p className="empty-hint">Pick a template or type a task and hit Run</p>
              </div>
            ) : view === 'auditor' ? (
              filtered.map((a, i) => <AuditorCard key={a.id || i} action={a} index={actions.indexOf(a)} onClick={setSelectedAction} />)
            ) : (
              <div className="clinical-timeline">{filtered.map((a, i) => <ClinicalCard key={a.id || i} action={a} />)}</div>
            )}
          </div>
        </div>

        <div className="right-col">
          <ChainStatus chain={chain} actions={actions} onVerify={verifyChain} onTamper={doTamper} onRestore={doRestore} tampered={tampered} />
          <PatientList patients={patients} />
        </div>
      </div>

      {selectedAction && <ChainExplorer action={selectedAction} actions={actions} onClose={() => setSelectedAction(null)} />}
    </div>
  );
}

export default App;
