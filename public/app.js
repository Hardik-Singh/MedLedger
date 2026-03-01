// ===== MedLedger App =====

const STORAGE_KEY = 'medledger_medications';
const HISTORY_KEY = 'medledger_history';
const TAKEN_KEY = 'medledger_taken';

// ===== Data Layer (localStorage) =====
function getMeds() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch {
    return [];
  }
}

function saveMeds(meds) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(meds));
}

function getHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
  } catch {
    return [];
  }
}

function saveHistory(history) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

function getTakenToday() {
  try {
    const data = JSON.parse(localStorage.getItem(TAKEN_KEY)) || {};
    const today = todayKey();
    return data[today] || [];
  } catch {
    return [];
  }
}

function markTaken(medId) {
  const data = JSON.parse(localStorage.getItem(TAKEN_KEY) || '{}');
  const today = todayKey();
  if (!data[today]) data[today] = [];
  if (!data[today].includes(medId)) {
    data[today].push(medId);
  }
  localStorage.setItem(TAKEN_KEY, JSON.stringify(data));

  // Add to history
  const meds = getMeds();
  const med = meds.find(m => m.id === medId);
  if (med) {
    const history = getHistory();
    history.unshift({
      medId: med.id,
      name: med.name,
      dosage: med.dosage,
      takenAt: new Date().toISOString(),
      status: 'taken'
    });
    // Keep last 200 entries
    if (history.length > 200) history.length = 200;
    saveHistory(history);
  }
}

function unmarkTaken(medId) {
  const data = JSON.parse(localStorage.getItem(TAKEN_KEY) || '{}');
  const today = todayKey();
  if (data[today]) {
    data[today] = data[today].filter(id => id !== medId);
  }
  localStorage.setItem(TAKEN_KEY, JSON.stringify(data));
}

function isTakenToday(medId) {
  return getTakenToday().includes(medId);
}

function todayKey() {
  return new Date().toISOString().split('T')[0];
}

// ===== Frequency helpers =====
const FREQ_LABELS = {
  daily: 'Daily',
  twice: 'Twice daily',
  three: '3x daily',
  weekly: 'Weekly',
  asneeded: 'As needed'
};

function formatTime(t) {
  if (!t) return '';
  const [h, m] = t.split(':');
  const hour = parseInt(h, 10);
  const ampm = hour >= 12 ? 'PM' : 'AM';
  const display = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
  return `${display}:${m} ${ampm}`;
}

// ===== Streak Calculation =====
function calculateStreak() {
  const data = JSON.parse(localStorage.getItem(TAKEN_KEY) || '{}');
  const meds = getMeds();
  if (meds.length === 0) return 0;

  let streak = 0;
  const today = new Date();

  for (let i = 0; i < 365; i++) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().split('T')[0];
    const takenIds = data[key] || [];

    // Check if all scheduled meds were taken
    const scheduledMeds = meds.filter(m => m.frequency !== 'asneeded');
    if (scheduledMeds.length === 0) break;

    const allTaken = scheduledMeds.every(m => takenIds.includes(m.id));
    if (allTaken && takenIds.length > 0) {
      streak++;
    } else if (i > 0) {
      break;
    }
  }
  return streak;
}

// ===== Rendering =====
function renderToday() {
  const meds = getMeds();
  const list = document.getElementById('todayList');
  const emptyEl = document.getElementById('todayEmpty');

  // Filter to scheduled meds (not "as needed")
  const scheduled = meds.filter(m => m.frequency !== 'asneeded');
  const asNeeded = meds.filter(m => m.frequency === 'asneeded');

  if (meds.length === 0) {
    emptyEl.style.display = '';
    list.innerHTML = '';
    list.appendChild(emptyEl);
    return;
  }

  emptyEl.style.display = 'none';
  list.innerHTML = '';

  // Streak banner
  const streak = calculateStreak();
  if (streak > 0) {
    const banner = document.createElement('div');
    banner.className = 'streak-banner';
    banner.innerHTML = `
      <div>
        <div class="streak-number">${streak}</div>
        <div class="streak-label">day${streak !== 1 ? 's' : ''}</div>
      </div>
      <div class="streak-text">Current streak! Keep it up!</div>
    `;
    list.appendChild(banner);
  }

  // Sort by time
  const sorted = [...scheduled].sort((a, b) => (a.time || '').localeCompare(b.time || ''));

  sorted.forEach(med => {
    list.appendChild(createTodayCard(med));
  });

  if (asNeeded.length > 0) {
    const label = document.createElement('div');
    label.className = 'date-header';
    label.style.marginTop = '16px';
    label.textContent = 'As Needed';
    list.appendChild(label);
    asNeeded.forEach(med => {
      list.appendChild(createTodayCard(med));
    });
  }
}

function createTodayCard(med) {
  const taken = isTakenToday(med.id);
  const card = document.createElement('div');
  card.className = `med-card${taken ? ' taken' : ''}`;

  card.innerHTML = `
    <div class="check-circle${taken ? ' checked' : ''}" data-id="${med.id}">
      ${taken ? '&#10003;' : ''}
    </div>
    <div class="med-info">
      <div class="med-name">${escapeHtml(med.name)}</div>
      <div class="med-dosage">${escapeHtml(med.dosage)}${med.notes ? ' &middot; ' + escapeHtml(med.notes) : ''}</div>
    </div>
    <div>
      <div class="med-time">${formatTime(med.time)}</div>
      <div class="med-freq">${FREQ_LABELS[med.frequency] || med.frequency}</div>
    </div>
  `;

  const checkEl = card.querySelector('.check-circle');
  checkEl.addEventListener('click', (e) => {
    e.stopPropagation();
    if (taken) {
      unmarkTaken(med.id);
    } else {
      markTaken(med.id);
    }
    renderToday();
    renderHistory();
  });

  card.addEventListener('click', () => showDetail(med));
  return card;
}

function renderMedsList() {
  const meds = getMeds();
  const list = document.getElementById('medsList');
  const emptyEl = document.getElementById('medsEmpty');

  if (meds.length === 0) {
    emptyEl.style.display = '';
    list.innerHTML = '';
    list.appendChild(emptyEl);
    return;
  }

  emptyEl.style.display = 'none';
  list.innerHTML = '';

  meds.forEach(med => {
    const card = document.createElement('div');
    card.className = 'med-card';
    card.innerHTML = `
      <div class="med-info">
        <div class="med-name">${escapeHtml(med.name)}</div>
        <div class="med-dosage">${escapeHtml(med.dosage)} &middot; ${FREQ_LABELS[med.frequency] || med.frequency}</div>
      </div>
      <div>
        <div class="med-time">${formatTime(med.time)}</div>
      </div>
    `;
    card.addEventListener('click', () => showDetail(med));
    list.appendChild(card);
  });
}

function renderHistory() {
  const history = getHistory();
  const list = document.getElementById('historyList');
  const emptyEl = document.getElementById('historyEmpty');

  if (history.length === 0) {
    emptyEl.style.display = '';
    list.innerHTML = '';
    list.appendChild(emptyEl);
    return;
  }

  emptyEl.style.display = 'none';
  list.innerHTML = '';

  // Group by date
  const groups = {};
  history.forEach(entry => {
    const date = new Date(entry.takenAt).toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'short',
      day: 'numeric'
    });
    if (!groups[date]) groups[date] = [];
    groups[date].push(entry);
  });

  Object.entries(groups).forEach(([date, entries]) => {
    const label = document.createElement('div');
    label.className = 'history-date';
    label.textContent = date;
    list.appendChild(label);

    entries.forEach(entry => {
      const item = document.createElement('div');
      item.className = 'history-item';
      const time = new Date(entry.takenAt).toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit'
      });
      item.innerHTML = `
        <div class="history-info">
          <div class="history-name">${escapeHtml(entry.name)}</div>
          <div class="history-detail">${escapeHtml(entry.dosage)} &middot; ${time}</div>
        </div>
        <span class="history-badge badge-taken">Taken</span>
      `;
      list.appendChild(item);
    });
  });
}

// ===== Detail Modal =====
function showDetail(med) {
  const modal = document.getElementById('detailModal');
  document.getElementById('detailTitle').textContent = med.name;

  const taken = isTakenToday(med.id);
  const body = document.getElementById('detailBody');
  body.innerHTML = `
    <div class="detail-row">
      <span class="detail-label">Dosage</span>
      <span class="detail-value">${escapeHtml(med.dosage)}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Frequency</span>
      <span class="detail-value">${FREQ_LABELS[med.frequency] || med.frequency}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Time</span>
      <span class="detail-value">${formatTime(med.time) || 'Not set'}</span>
    </div>
    ${med.notes ? `<div class="detail-row">
      <span class="detail-label">Notes</span>
      <span class="detail-value">${escapeHtml(med.notes)}</span>
    </div>` : ''}
    <div class="detail-row">
      <span class="detail-label">Today</span>
      <span class="detail-value">${taken ? 'Taken' : 'Not taken yet'}</span>
    </div>
    <div class="detail-actions">
      <button class="btn-danger" id="deleteMedBtn">Delete</button>
      <button class="btn-success" id="toggleTakenBtn">${taken ? 'Mark Not Taken' : 'Mark as Taken'}</button>
    </div>
  `;

  document.getElementById('deleteMedBtn').addEventListener('click', () => {
    if (confirm(`Delete ${med.name}?`)) {
      let meds = getMeds();
      meds = meds.filter(m => m.id !== med.id);
      saveMeds(meds);
      modal.classList.remove('open');
      renderAll();
    }
  });

  document.getElementById('toggleTakenBtn').addEventListener('click', () => {
    if (taken) {
      unmarkTaken(med.id);
    } else {
      markTaken(med.id);
    }
    modal.classList.remove('open');
    renderAll();
  });

  modal.classList.add('open');
}

// ===== Add Medication =====
document.getElementById('addForm').addEventListener('submit', (e) => {
  e.preventDefault();

  const name = document.getElementById('medName').value.trim();
  const dosage = document.getElementById('medDosage').value.trim();
  const frequency = document.getElementById('medFrequency').value;
  const time = document.getElementById('medTime').value;
  const notes = document.getElementById('medNotes').value.trim();

  if (!name || !dosage) return;

  const meds = getMeds();
  meds.push({
    id: Date.now().toString(),
    name,
    dosage,
    frequency,
    time,
    notes,
    createdAt: new Date().toISOString()
  });
  saveMeds(meds);

  // Reset form
  document.getElementById('addForm').reset();
  document.getElementById('medTime').value = '08:00';
  document.getElementById('addModal').classList.remove('open');

  renderAll();
});

// ===== Tab Switching =====
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
  });
});

// ===== Modal Controls =====
document.getElementById('addBtn').addEventListener('click', () => {
  document.getElementById('addModal').classList.add('open');
  setTimeout(() => document.getElementById('medName').focus(), 300);
});

document.getElementById('closeModal').addEventListener('click', () => {
  document.getElementById('addModal').classList.remove('open');
});

document.getElementById('closeDetail').addEventListener('click', () => {
  document.getElementById('detailModal').classList.remove('open');
});

// Close modals on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      overlay.classList.remove('open');
    }
  });
});

// ===== Utility =====
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function renderAll() {
  renderToday();
  renderMedsList();
  renderHistory();
}

// ===== Set Today's Date =====
function setTodayDate() {
  const el = document.getElementById('todayDate');
  el.textContent = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric'
  });
}

// ===== PWA Install Prompt =====
let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  document.getElementById('installBtn').style.display = '';
});

document.getElementById('installBtn').addEventListener('click', async () => {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    document.getElementById('installBtn').style.display = 'none';
  }
});

// ===== Init =====
setTodayDate();
renderAll();

// Register service worker
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}
