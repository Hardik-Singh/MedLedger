import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';

const WS_URL  = process.env.REACT_APP_WS_URL     || 'ws://localhost:8000/ws';
const API_URL = process.env.REACT_APP_API_URL     || 'http://localhost:8000';
const PORTAL  = process.env.REACT_APP_PORTAL_URL  || 'http://localhost:8001';

const DOT = {
  SEARCH:'#3b82f6', VIEW:'#94a3b8', UPDATE:'#f59e0b', DELETE:'#ef4444',
  HISTORY:'#a78bfa', AUDIT:'#06b6d4', TASK_COMPLETE:'#22c55e',
  LAB_REVIEW:'#818cf8', APPOINTMENTS:'#38bdf8', SCHEDULE:'#34d399',
  RISK_REVIEW:'#fb923c', CARE_TEAM:'#c084fc',
};

/* ── seed runs shown before any real runs happen ── */
const SEED_RUNS = [
  {
    id: 'seed-1', agent: 'ARIA', task: 'Look up Sam Altman medications',
    status: 'complete', summary: { total_actions: 3, patients_touched: 1, elapsed_seconds: 8.2 },
    actions: [
      { id:'s1a', action_type:'SEARCH', agent_id:'ARIA', timestamp:'2026-02-28T09:14:22Z', verified:true,
        payload:{query:'Sam Altman'}, hash:'a3f2c1de9b7842fd01e6c8a94b3d5f107e8a2c6d4b9f1e3a5c7d2b8f4a6e0c19', prev_hash:'GENESIS', signature:'MEUCIQDk7v2Hx9L...(P256)...base64==' },
      { id:'s1b', action_type:'VIEW', agent_id:'ARIA', timestamp:'2026-02-28T09:14:25Z', verified:true,
        payload:{patient_id:1}, hash:'7b1cde45f8a23b6d9c4e0f1a2b3d5e7f8a9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e', prev_hash:'a3f2c1de9b7842fd01e6c8a94b3d5f107e8a2c6d4b9f1e3a5c7d2b8f4a6e0c19', signature:'MEUCIHm8Rp4Q...(P256)...base64==' },
      { id:'s1c', action_type:'HISTORY', agent_id:'ARIA', timestamp:'2026-02-28T09:14:30Z', verified:true,
        payload:{patient_id:1}, hash:'e9d4f8a2b3c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1', prev_hash:'7b1cde45f8a23b6d9c4e0f1a2b3d5e7f8a9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e', signature:'MEYCIQC3nL2x...(P256)...base64==' },
    ],
  },
  {
    id: 'seed-2', agent: 'DELTA', task: 'Update allergy medication for Sam Altman',
    status: 'complete', summary: { total_actions: 4, patients_touched: 1, elapsed_seconds: 11.5 },
    actions: [
      { id:'s2a', action_type:'SEARCH', agent_id:'DELTA', timestamp:'2026-02-28T10:02:11Z', verified:true,
        payload:{query:'Sam Altman'}, hash:'1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b', prev_hash:'e9d4f8a2b3c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1', signature:'MEQCIFkR7z...(P256)...base64==' },
      { id:'s2b', action_type:'VIEW', agent_id:'DELTA', timestamp:'2026-02-28T10:02:14Z', verified:true,
        payload:{patient_id:1}, hash:'2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c', prev_hash:'1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b', signature:'MEUCIQDpW...(P256)...base64==' },
      { id:'s2c', action_type:'UPDATE', agent_id:'DELTA', timestamp:'2026-02-28T10:02:19Z', verified:true,
        payload:{patient_id:1, patient_name:'Sam Altman', field:'medications', old_value:'Claritin 10mg', new_value:'Zyrtec 10mg', warnings:null},
        hash:'3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d', prev_hash:'2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c', signature:'MEYCIQD8a...(P256)...base64==' },
      { id:'s2d', action_type:'HISTORY', agent_id:'DELTA', timestamp:'2026-02-28T10:02:23Z', verified:true,
        payload:{patient_id:1}, hash:'4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e', prev_hash:'3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d', signature:'MEUCIHnQ...(P256)...base64==' },
    ],
  },
];

/* ── helpers ── */

function desc(a) {
  const p = a.payload || {};
  switch (a.action_type) {
    case 'SEARCH':       return `Searched for "${p.query}"`;
    case 'VIEW':         return `Viewed patient #${p.patient_id}`;
    case 'UPDATE':       return `Updated ${p.patient_name||'patient'}: ${p.field} "${p.old_value}" \u2192 "${p.new_value}"`;
    case 'DELETE':       return `Deleted ${p.patient_name} (${p.mrn})`;
    case 'HISTORY':      return `Checked history for patient #${p.patient_id}`;
    case 'AUDIT':        return `Audit: ${p.check||'integrity'} \u2014 ${p.intact!==undefined?(p.intact?'passed':'FAILED'):`${p.issues_found||0} issues`}`;
    case 'LAB_REVIEW':   return `Reviewed labs for patient #${p.patient_id}`;
    case 'APPOINTMENTS': return `Checked appointments for patient #${p.patient_id}`;
    case 'SCHEDULE':     return `Scheduled ${p.type||'appt'} for ${p.patient_name||'patient'}`;
    case 'RISK_REVIEW':  return `Reviewed high-risk patients`;
    case 'CARE_TEAM':    return `Checked care team for patient #${p.patient_id}`;
    case 'TASK_COMPLETE':return 'Task complete';
    default:             return a.action_type;
  }
}

function humanStep(a, i) {
  const p = a.payload || {};
  switch (a.action_type) {
    case 'SEARCH':       return `Searched patient database for "${p.query}"`;
    case 'VIEW':         return `Opened patient record #${p.patient_id}`;
    case 'UPDATE':       return `Changed ${p.field} from "${p.old_value}" to "${p.new_value}" for ${p.patient_name||'patient'}`;
    case 'DELETE':       return `Removed patient ${p.patient_name} from the system`;
    case 'HISTORY':      return `Retrieved full medical history for patient #${p.patient_id}`;
    case 'AUDIT':        return `Ran integrity check: ${p.check||'verification'}`;
    case 'LAB_REVIEW':   return `Pulled lab results for patient #${p.patient_id}`;
    case 'APPOINTMENTS': return `Looked up appointments for patient #${p.patient_id}`;
    case 'SCHEDULE':     return `Booked ${p.type||'appointment'} for ${p.patient_name||'patient'}`;
    case 'RISK_REVIEW':  return `Assessed high-risk patient list`;
    case 'CARE_TEAM':    return `Reviewed care team assignments for patient #${p.patient_id}`;
    case 'TASK_COMPLETE':return `Finished \u2014 task completed successfully`;
    default:             return a.action_type;
  }
}

function groupIntoRuns(actions) {
  if (!actions.length) return [];
  const runs = []; let cur = null; let rid = Date.now();
  for (const a of actions) {
    if (!cur) cur = { id: rid++, agent: a.agent_id||'AGENT', task:'', actions:[], status:'complete', summary:null };
    cur.actions.push(a);
    if (a.action_type === 'TASK_COMPLETE') {
      cur.summary = a.payload;
      const s = cur.actions.find(x=>x.action_type==='SEARCH');
      cur.task = s ? s.payload?.query : `${cur.actions.length} actions`;
      runs.push(cur); cur = null;
    }
  }
  if (cur?.actions.length) {
    const s = cur.actions.find(x=>x.action_type==='SEARCH');
    cur.task = s ? s.payload?.query : `${cur.actions.length} actions`;
    runs.push(cur);
  }
  return runs.reverse();
}

/* ── Block Detail Modal ── */

function BlockDetail({ action, onClose }) {
  if (!action) return null;
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal-card" onClick={e=>e.stopPropagation()}>
        <div className="modal-top"><h3>Cryptographic Proof</h3><button className="x-btn" onClick={onClose}>&times;</button></div>
        <div className="modal-body">
          <div className="dr"><span className="dl">Type</span><span className="dv">{action.action_type}</span></div>
          <div className="dr"><span className="dl">Agent</span><span className="dv">{action.agent_id}</span></div>
          <div className="dr"><span className="dl">Time</span><span className="dv">{new Date(action.timestamp).toLocaleString()}</span></div>
          <div className="dr"><span className="dl">Verified</span><span className={`dv ${action.verified?'text-green':'text-red'}`}>{action.verified?'\u2713 Cryptographically Signed':'\u2717 Signature Invalid'}</span></div>
          <div className="dr"><span className="dl">Description</span><span className="dv dv-wrap">{desc(action)}</span></div>
          <div className="db"><span className="dl">Payload</span><pre className="d-json">{JSON.stringify(action.payload,null,2)}</pre></div>
          <div className="db"><span className="dl">SHA-256 Hash</span><pre className="d-hash">{action.hash}</pre></div>
          <div className="db"><span className="dl">Previous Hash (Chain Link)</span><pre className="d-hash">{action.prev_hash}</pre></div>
          <div className="db"><span className="dl">ECDSA P-256 Signature</span><pre className="d-hash d-sig">{action.signature}</pre></div>
        </div>
      </div>
    </div>
  );
}

/* ── Settings Modal ── */

function Settings({ keyStatus, onSetKey, onSetMemoryKey, chain, onVerify, onTamper, onRestore, tampered, onExport, onClose }) {
  const [key, setKey] = useState('');
  const [memKey, setMemKey] = useState('');
  const mem = keyStatus.memory||{};
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal-card" onClick={e=>e.stopPropagation()}>
        <div className="modal-top"><h3>Settings</h3><button className="x-btn" onClick={onClose}>&times;</button></div>
        <div className="modal-body">
          <div className="sg">
            <label className="sl">Anthropic API Key</label>
            {keyStatus.has_key && <div className="sk"><span className="dot dot-green"/><span className="sp">{keyStatus.key_preview||'Connected'}</span></div>}
            <div className="sr"><input type="password" placeholder="sk-ant-..." value={key} onChange={e=>setKey(e.target.value)} className="input"/><button className="btn btn-primary btn-sm" onClick={()=>{onSetKey(key);setKey('');}} disabled={!key}>{keyStatus.has_key?'Update':'Set'}</button></div>
          </div>
          <div className="sg">
            <label className="sl">Supermemory Key <span className="optional">(optional)</span></label>
            {mem.has_key && <div className="sk"><span className="dot dot-green"/><span className="sp">{mem.key_preview||'Active'}</span></div>}
            <div className="sr"><input type="password" placeholder="sm_..." value={memKey} onChange={e=>setMemKey(e.target.value)} className="input"/><button className="btn btn-primary btn-sm" onClick={()=>{onSetMemoryKey(memKey);setMemKey('');}} disabled={!memKey}>{mem.has_key?'Update':'Set'}</button></div>
          </div>
          <div className="sg">
            <label className="sl">Chain Integrity</label>
            <div className="sa">
              <span className={chain.intact?'text-green':'text-red'}>{chain.intact?'Intact':'Broken'}</span>
              <button className="btn btn-sm" onClick={onVerify}>Verify</button>
              {!tampered?<button className="btn btn-sm btn-danger" onClick={onTamper}>Tamper (demo)</button>:<button className="btn btn-sm btn-success" onClick={onRestore}>Restore</button>}
            </div>
          </div>
          <div className="sg">
            <label className="sl">Export</label>
            <div className="sa"><button className="btn btn-sm" onClick={()=>onExport('json')}>JSON</button><button className="btn btn-sm" onClick={()=>onExport('csv')}>CSV</button></div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Setup Screen ── */

function Setup({ onSetKey, onSetMemoryKey }) {
  const [key, setKey] = useState('');
  const [memKey, setMemKey] = useState('');
  const [showMem, setShowMem] = useState(false);
  const go = () => { if(key) onSetKey(key); if(memKey) onSetMemoryKey(memKey); };
  return (
    <div className="app setup-screen">
      <div className="setup-card">
        <h1 className="setup-title">MedLedger</h1>
        <p className="setup-sub">AI-powered medical record agent with cryptographic audit trails</p>
        <div className="setup-form">
          <div className="setup-group"><label className="setup-label">Anthropic API Key</label>
            <input className="input input-lg" type="password" placeholder="sk-ant-api03-..." value={key} onChange={e=>setKey(e.target.value)} onKeyDown={e=>e.key==='Enter'&&go()} />
          </div>
          {!showMem
            ? <button className="link-btn" onClick={()=>setShowMem(true)}>+ Add Supermemory key (optional)</button>
            : <div className="setup-group"><label className="setup-label">Supermemory Key <span className="optional">(persistent memory)</span></label>
                <input className="input input-lg" type="password" placeholder="sm_..." value={memKey} onChange={e=>setMemKey(e.target.value)} />
              </div>
          }
          <button className="btn btn-primary btn-lg" onClick={go} disabled={!key}>Get Started</button>
        </div>
      </div>
    </div>
  );
}

/* ════════════════════════  MAIN APP  ════════════════════════ */

function App() {
  const [runs, setRuns]               = useState([]);
  const [openRunId, setOpenRunId]     = useState(null);
  const [viewTab, setViewTab]         = useState('human');   // 'human' | 'crypto'
  const [selectedBlock, setBlock]     = useState(null);
  const [connected, setConnected]     = useState(false);
  const [task, setTask]               = useState('');
  const [agentName, setAgentName]     = useState('ARIA');
  const [running, setRunning]         = useState(false);
  const [keyStatus, setKeyStatus]     = useState({ has_key: false });
  const [chain, setChain]             = useState({ intact: true });
  const [tampered, setTampered]       = useState(false);
  const [showSettings, setSettings]   = useState(false);
  const [portalKey, setPortalKey]     = useState(0);
  const [portalStatus, setPortalStatus] = useState(null);   // null | 'reading' | 'updating' | 'searching'

  const curRunRef = useRef(null);

  /* ── data load ── */
  const fetchData = useCallback(async () => {
    try {
      const [lr,kr,vr] = await Promise.all([
        fetch(`${API_URL}/audit/log`), fetch(`${API_URL}/api/key-status`), fetch(`${API_URL}/audit/verify`),
      ]);
      if (lr.ok) {
        const actions = await lr.json();
        setRuns(actions.length ? groupIntoRuns(actions) : SEED_RUNS);
      } else {
        setRuns(SEED_RUNS);
      }
      if (kr.ok) setKeyStatus(await kr.json());
      if (vr.ok) setChain(await vr.json());
    } catch(e) { setRuns(SEED_RUNS); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  /* ── portal status helper ── */
  function showPortalStatus(actionType) {
    const labels = { SEARCH:'Searching records...', VIEW:'Reading patient data...', UPDATE:'Updating records...', DELETE:'Deleting record...', HISTORY:'Loading history...', LAB_REVIEW:'Pulling lab results...', APPOINTMENTS:'Checking appointments...', SCHEDULE:'Scheduling...', RISK_REVIEW:'Reviewing patients...', CARE_TEAM:'Loading care team...' };
    setPortalStatus(labels[actionType] || 'Processing...');
  }

  /* ── websocket ── */
  useEffect(() => {
    let ws;
    function connect() {
      ws = new WebSocket(WS_URL);
      ws.onopen  = () => setConnected(true);
      ws.onclose = () => { setConnected(false); setTimeout(connect, 2000); };
      ws.onerror = () => ws.close();
      ws.onmessage = (evt) => {
        const d = JSON.parse(evt.data);

        if (d.type === 'agent_start') {
          const run = { id: Date.now(), agent: d.agent_name||'AGENT', task: d.task||'Agent task', actions:[], status:'running', summary:null };
          curRunRef.current = run.id;
          // remove seed runs on first real run, add new run on top
          setRuns(prev => {
            const real = prev.filter(r => !String(r.id).startsWith('seed'));
            return [run, ...real];
          });
          setOpenRunId(run.id);
          setViewTab('human');
        }

        if (d.type === 'action') {
          const { type, ...action } = d;
          setRuns(prev => prev.map(r => r.id === curRunRef.current ? { ...r, actions:[...r.actions, action] } : r));
          showPortalStatus(action.action_type);
          setPortalKey(k => k + 1);
          fetch(`${API_URL}/audit/verify`).then(r=>r.json()).then(setChain).catch(()=>{});
        }

        if (d.type === 'task_complete') {
          setRuns(prev => prev.map(r => r.id === curRunRef.current ? { ...r, status:'complete', summary:d.summary } : r));
          setRunning(false); curRunRef.current = null; setPortalStatus(null);
        }
        if (d.type === 'multi_agent_complete') { setRunning(false); curRunRef.current = null; setPortalStatus(null); }
        if (d.type === 'error') { setRunning(false); curRunRef.current = null; setPortalStatus(null); }
        if (d.type === 'tamper')   { setTampered(true);  reload(); }
        if (d.type === 'restored') { setTampered(false); reload(); }
      };
    }
    function reload() {
      fetch(`${API_URL}/audit/log`).then(r=>r.json()).then(a => setRuns(a.length ? groupIntoRuns(a) : SEED_RUNS)).catch(()=>{});
      fetch(`${API_URL}/audit/verify`).then(r=>r.json()).then(setChain).catch(()=>{});
    }
    connect();
    return () => ws?.close();
  }, []);

  /* ── actions ── */
  const runAgent = async (oTask, oAgent) => {
    const t = oTask||task.trim(), a = oAgent||agentName;
    if (!t) return;
    setRunning(true); setTask('');
    try { await fetch(`${API_URL}/agent/run`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({task:t,agent_name:a}) }); }
    catch(e) { setRunning(false); }
  };
  const runAudit = async () => {
    setRunning(true);
    try { await fetch(`${API_URL}/agent/audit`, {method:'POST'}); } catch(e) { setRunning(false); }
  };
  const setApiKey = async k => {
    await fetch(`${API_URL}/api/set-key`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k})});
    const r=await fetch(`${API_URL}/api/key-status`); if(r.ok) setKeyStatus(await r.json());
  };
  const setMemoryKey = async k => {
    await fetch(`${API_URL}/api/set-memory-key`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k})});
    const r=await fetch(`${API_URL}/api/key-status`); if(r.ok) setKeyStatus(await r.json());
  };
  const verifyChain = async () => { const r=await fetch(`${API_URL}/audit/verify`); if(r.ok) setChain(await r.json()); };
  const doTamper  = () => fetch(`${API_URL}/audit/tamper`,  {method:'POST'});
  const doRestore = () => fetch(`${API_URL}/audit/restore`, {method:'POST'});
  const exportLog = async (fmt='json') => {
    const url = fmt==='csv' ? `${API_URL}/audit/export/csv` : `${API_URL}/audit/export`;
    const res=await fetch(url); if(!res.ok) return;
    const blob = fmt==='csv' ? await res.blob() : new Blob([JSON.stringify(await res.json(),null,2)],{type:'application/json'});
    const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
    a.download=`medledger-audit-${new Date().toISOString().slice(0,10)}.${fmt}`; a.click(); URL.revokeObjectURL(a.href);
  };

  /* ── setup guard ── */
  if (!keyStatus.has_key) return <Setup onSetKey={setApiKey} onSetMemoryKey={setMemoryKey} />;

  const openRun = runs.find(r => r.id === openRunId);
  const visibleActions = openRun ? openRun.actions.filter(a=>a.action_type!=='TASK_COMPLETE') : [];

  /* ═══════ RENDER ═══════ */
  return (
    <div className="app">
      {/* header */}
      <header className="hdr">
        <h1 className="logo">MedLedger</h1>
        <div className="hdr-r">
          <span className={`dot ${connected?'dot-green':'dot-red'}`}/><span className="hdr-conn">{connected?'Live':'...'}</span>
          <button className="hdr-btn" onClick={()=>setSettings(true)}>Settings</button>
        </div>
      </header>

      <div className="layout">
        {/* ─── LEFT SIDEBAR (~1/3) ─── */}
        <aside className="sidebar">
          {/* prompt input */}
          <div className="prompt-section">
            <textarea
              className="prompt-input"
              rows={3}
              placeholder={'What should the agent do?\ne.g. "Look up Sam Altman\'s medications"'}
              value={task}
              onChange={e=>setTask(e.target.value)}
              onKeyDown={e=>{ if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); runAgent(); }}}
              disabled={running}
            />
            <div className="prompt-controls">
              <select className="agent-pick" value={agentName} onChange={e=>setAgentName(e.target.value)} disabled={running}>
                <option value="ARIA">ARIA (read)</option>
                <option value="DELTA">DELTA (write)</option>
              </select>
              <button className="run-btn" onClick={()=>runAgent()} disabled={running||!task.trim()}>
                {running ? 'Running\u2026' : 'Run'}
              </button>
            </div>
            <div className="qk-row">
              <button className="qk" onClick={()=>runAgent("Look up Sam Altman's patient record and check his current medications",'ARIA')} disabled={running}>Lookup patient</button>
              <button className="qk" onClick={()=>runAgent("Sam Altman is switching from Claritin to Zyrtec for allergies — update his record",'DELTA')} disabled={running}>Update meds</button>
              <button className="qk" onClick={()=>runAgent("Check Paul Graham's record, review his labs, check appointments, and view full history",'ARIA')} disabled={running}>Full review</button>
              <button className="qk qk-aud" onClick={runAudit} disabled={running}>Audit</button>
            </div>
            {running && <div className="running-bar"/>}
          </div>

          {/* runs list */}
          <div className="runs-section">
            <h3 className="sec-title">Agent Runs</h3>
            <div className="runs-list">
              {runs.map(run => {
                const count = run.actions.filter(a=>a.action_type!=='TASK_COMPLETE').length;
                const active = openRunId === run.id;
                return (
                  <div key={run.id} className={`run-item ${active?'run-active':''} ${run.status==='running'?'run-live':''}`}
                    onClick={()=>{ setOpenRunId(active ? null : run.id); setViewTab('human'); }}>
                    <div className="ri-top">
                      <span className="ri-agent">{run.agent}</span>
                      <span className={`ri-dot ${run.status==='running'?'dot-amber':'dot-green'}`}/>
                    </div>
                    <div className="ri-task">{run.task}</div>
                    <div className="ri-meta">
                      <span>{count} steps</span>
                      {run.summary?.elapsed_seconds != null && <span>{run.summary.elapsed_seconds}s</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </aside>

        {/* ─── RIGHT MAIN (~2/3) ─── */}
        <main className="main-panel">
          {/* if a run is selected show details, otherwise show portal full */}
          {openRun ? (
            <div className="run-detail">
              {/* tabs */}
              <div className="tabs">
                <button className={`tab ${viewTab==='human'?'tab-on':''}`} onClick={()=>setViewTab('human')}>Human View</button>
                <button className={`tab ${viewTab==='crypto'?'tab-on':''}`} onClick={()=>setViewTab('crypto')}>Crypto View</button>
                <div className="tab-spacer"/>
                <button className="tab-close" onClick={()=>setOpenRunId(null)}>&times; Close</button>
              </div>

              {viewTab === 'human' ? (
                /* ── Human View ── */
                <div className="human-view">
                  <div className="hv-header">
                    <span className="hv-agent">{openRun.agent}</span>
                    <span className="hv-task">{openRun.task}</span>
                    {openRun.status === 'complete' && <span className="hv-done">Completed</span>}
                    {openRun.status === 'running' && <span className="hv-running">Running...</span>}
                  </div>
                  <div className="hv-steps">
                    {visibleActions.map((a, i) => (
                      <div key={a.id||i} className="hv-step">
                        <div className="hv-num">{i+1}</div>
                        <div className="hv-content">
                          <span className="hv-dot" style={{background:DOT[a.action_type]||'#64748b'}}/>
                          <span className="hv-text">{humanStep(a, i)}</span>
                          <span className="hv-time">{new Date(a.timestamp).toLocaleTimeString()}</span>
                        </div>
                      </div>
                    ))}
                    {openRun.status === 'running' && (
                      <div className="hv-step hv-pending">
                        <div className="hv-num">...</div>
                        <div className="hv-content"><span className="hv-text pulse">Agent is working...</span></div>
                      </div>
                    )}
                  </div>
                  {openRun.summary && (
                    <div className="hv-summary">
                      {openRun.summary.total_actions} actions | {openRun.summary.patients_touched} patients | {openRun.summary.elapsed_seconds}s
                    </div>
                  )}
                </div>
              ) : (
                /* ── Crypto View ── */
                <div className="crypto-view">
                  <div className="cv-header">
                    <span>Blockchain Audit Trail</span>
                    <span className={visibleActions.every(a=>a.verified)?'text-green':'text-red'}>
                      {visibleActions.every(a=>a.verified) ? '\u2713 All blocks verified' : '\u2717 Chain integrity broken'}
                    </span>
                  </div>

                  {/* chain diagram */}
                  <div className="chain-scroll">
                    <div className="chain">
                      {visibleActions.map((a,i) => (
                        <React.Fragment key={a.id||i}>
                          {i > 0 && <div className="chain-link"><div className="cl-line"/><div className="cl-arrow"/></div>}
                          <div className={`chain-block ${a.verified?'':'cb-tampered'}`} onClick={()=>setBlock(a)}>
                            <div className="cb-head">
                              <span className="cb-dot" style={{background:DOT[a.action_type]||'#64748b'}}/>
                              <span className="cb-type">{a.action_type}</span>
                            </div>
                            <div className="cb-desc">{desc(a)}</div>
                            <div className="cb-hash">#{(a.hash||'').slice(0,12)}</div>
                            <div className={`cb-sig ${a.verified?'text-green':'text-red'}`}>{a.verified?'\u2713 signed':'\u2717 invalid'}</div>
                          </div>
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                  <div className="cv-hint">Click any block to inspect full cryptographic proof</div>

                  {/* table */}
                  <div className="cv-table-wrap">
                    <table className="cv-table">
                      <thead>
                        <tr><th>#</th><th>Type</th><th>Agent</th><th>Hash</th><th>Prev Hash</th><th>Sig</th><th>Time</th></tr>
                      </thead>
                      <tbody>
                        {visibleActions.map((a,i)=>(
                          <tr key={a.id||i} className="cv-row" onClick={()=>setBlock(a)}>
                            <td>{i+1}</td>
                            <td><span className="cv-type-dot" style={{background:DOT[a.action_type]||'#64748b'}}/>{a.action_type}</td>
                            <td>{a.agent_id}</td>
                            <td className="cv-mono">{(a.hash||'').slice(0,16)}...</td>
                            <td className="cv-mono">{(a.prev_hash||'').slice(0,16)}...</td>
                            <td className={a.verified?'text-green':'text-red'}>{a.verified?'\u2713':'\u2717'}</td>
                            <td className="cv-mono">{new Date(a.timestamp).toLocaleTimeString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* no run selected — show portal full */
            <div className="portal-full">
              <div className="portal-bar">
                <span className="portal-label">Patient Portal</span>
                {portalStatus && <span className="portal-status pulse">{portalStatus}</span>}
              </div>
              <div className="portal-wrap">
                <iframe key={portalKey} src={PORTAL} title="Patient Portal" className="portal-frame"/>
                {portalStatus && <div className="portal-overlay"><div className="portal-toast">{portalStatus}</div></div>}
              </div>
            </div>
          )}
        </main>
      </div>

      {/* modals */}
      {showSettings && <Settings keyStatus={keyStatus} onSetKey={setApiKey} onSetMemoryKey={setMemoryKey} chain={chain} onVerify={verifyChain} onTamper={doTamper} onRestore={doRestore} tampered={tampered} onExport={exportLog} onClose={()=>setSettings(false)}/>}
      {selectedBlock && <BlockDetail action={selectedBlock} onClose={()=>setBlock(null)}/>}
    </div>
  );
}

export default App;
