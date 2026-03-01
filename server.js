const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

// In-memory store (resets on restart — frontend uses localStorage for persistence)
let medications = [];

app.get('/api/medications', (req, res) => {
  res.json(medications);
});

app.post('/api/medications', (req, res) => {
  const med = {
    id: Date.now().toString(),
    name: req.body.name,
    dosage: req.body.dosage,
    frequency: req.body.frequency,
    time: req.body.time,
    notes: req.body.notes || '',
    createdAt: new Date().toISOString()
  };
  medications.push(med);
  res.status(201).json(med);
});

app.delete('/api/medications/:id', (req, res) => {
  medications = medications.filter(m => m.id !== req.params.id);
  res.status(204).end();
});

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`MedLedger running at http://localhost:${PORT}`);
});
