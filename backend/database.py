import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "medledger.db")

SEED_PATIENTS = [
    # (first, last, dob, mrn, diagnosis, medications, allergies, last_visit, phone, insurance, blood_type, emergency_contact, notes)
    ("Sam", "Altman", "1985-04-22", "MRN-001042", "Seasonal Allergies", "Claritin 10mg daily, Flonase nasal spray", "None known", "2026-02-15", "(555) 234-5678", "Blue Cross Blue Shield", "O+", "Greg Altman — (555) 234-9999", "Patient reports symptoms worsen in spring. Recommend follow-up if antihistamines insufficient. Previous trial of Benadryl caused drowsiness."),
    ("Paul", "Graham", "1964-11-13", "MRN-001087", "Mild Eye Strain", "Artificial tears PRN, Blue-light glasses Rx", "None known", "2026-02-20", "(555) 345-6789", "Aetna PPO", "A+", "Jessica Livingston — (555) 456-7890", "Prolonged screen use. Advised 20-20-20 rule. Recheck in 6 months. Considering reading glasses for close work."),
    ("Jessica", "Livingston", "1971-08-09", "MRN-001123", "Common Cold", "Vitamin C 1000mg daily, Zinc lozenges PRN, rest", "Penicillin", "2026-01-28", "(555) 456-7890", "United Healthcare", "B+", "Paul Graham — (555) 345-6789", "Mild upper respiratory symptoms. No antibiotics needed. Rest and fluids. History of recurrent winter colds."),
    ("Garry", "Tan", "1982-06-30", "MRN-001156", "Caffeine Withdrawal Headaches", "Ibuprofen 400mg PRN, gradual caffeine taper plan", "None known", "2026-02-25", "(555) 567-8901", "Cigna", "A-", "Mia Tan — (555) 567-0000", "Consuming ~800mg caffeine/day. Taper by 100mg/week. Headaches should resolve in 2-3 weeks. BP slightly elevated at 135/85."),
    ("Michael", "Seibel", "1982-02-02", "MRN-001198", "Runner's Knee (Patellofemoral Syndrome)", "Ibuprofen 200mg PRN, physical therapy 2x/week, knee brace", "Sulfa drugs", "2026-02-10", "(555) 678-9012", "Kaiser Permanente", "O-", "Y Combinator HR — (555) 678-0000", "Training for half-marathon. Reduce mileage 30%. PT focus on quad strengthening. MRI negative for meniscal tear."),
    ("Dalton", "Caldwell", "1980-01-15", "MRN-001234", "Mild Tension Headache", "Acetaminophen 500mg PRN, stress management techniques", "Aspirin", "2026-02-18", "(555) 789-0123", "Anthem Blue Cross", "AB+", "Sara Caldwell — (555) 789-0000", "Work-related stress. Recommend meditation app. Follow up in 1 month. Sleep quality has improved with magnesium glycinate."),
    ("Jared", "Friedman", "1986-07-20", "MRN-001267", "Seasonal Allergies, Mild Sunburn", "Zyrtec 10mg daily, Aloe vera gel topical, SPF 50 sunscreen", "None known", "2026-02-22", "(555) 890-1234", "Blue Cross Blue Shield", "B-", "Amy Friedman — (555) 890-0000", "Fair complexion, burns easily. Advised SPF 50+ daily, reapply every 2 hours outdoors. Skin exam unremarkable."),
    ("Gustaf", "Alstromer", "1985-03-05", "MRN-001301", "Tennis Elbow (Lateral Epicondylitis)", "Naproxen 250mg BID, elbow strap, ice therapy 3x/day", "NSAIDs", "2026-01-30", "(555) 901-2345", "Humana", "A+", "Emma Alstromer — (555) 901-0000", "Note: NSAID allergy — prescribe Naproxen with caution, monitor for GI symptoms. Consider switching to acetaminophen if issues."),
    ("Kevin", "Hale", "1981-12-18", "MRN-001345", "Mild Sprained Ankle (Grade I)", "RICE protocol, Ibuprofen 400mg TID x5 days, ankle wrap", "Latex", "2026-02-12", "(555) 012-3456", "United Healthcare", "O+", "Kate Hale — (555) 012-0000", "Injury during weekend basketball. No fracture on X-ray. Weight-bearing as tolerated. PT if not improved in 2 weeks."),
    ("Adora", "Cheung", "1987-09-14", "MRN-001389", "Persistent Hiccups (3 days)", "Chlorpromazine 25mg PRN, breathing exercises, peppermint tea", "None known", "2026-02-08", "(555) 123-4567", "Aetna PPO", "AB-", "Henry Cheung — (555) 123-0000", "Hiccups started after a large meal. No underlying pathology on workup. If persists >1 week, refer to GI."),
    ("Brian", "Chesky", "1981-08-29", "MRN-001412", "Mild Lower Back Pain", "Naproxen 500mg BID PRN, lumbar stretches daily, ergonomic chair Rx", "Codeine", "2026-02-24", "(555) 234-0001", "Cigna", "A+", "Joe Gebbia — (555) 234-0002", "Sedentary work posture. X-ray shows no disc herniation. Recommend standing desk intervals. No radiculopathy on exam."),
    ("Patrick", "Collison", "1988-09-09", "MRN-001445", "Insomnia (Mild, Stress-Related)", "Melatonin 3mg nightly, sleep hygiene protocol, magnesium glycinate 400mg", "None known", "2026-02-17", "(555) 345-0001", "Blue Cross Blue Shield", "O+", "John Collison — (555) 345-0002", "Screen time until midnight. Advised blue-light cutoff 2hr before bed. Sleep diary shows 5.5hr average. Target 7hr."),
    ("Drew", "Houston", "1983-03-04", "MRN-001478", "Mild Carpal Tunnel Syndrome", "Wrist splint at night, Ibuprofen 200mg PRN, ergonomic keyboard Rx", "None known", "2026-01-20", "(555) 456-0001", "Aetna PPO", "B+", "Arash Ferdowsi — (555) 456-0002", "Bilateral wrist numbness, worse at night. Nerve conduction normal. Conservative management for 6 weeks before reassessment."),
    ("Tracy", "Young", "1987-04-15", "MRN-001501", "Vitamin D Deficiency", "Vitamin D3 5000 IU daily, calcium 500mg daily, outdoor exercise 30min/day", "Shellfish", "2026-02-05", "(555) 567-0001", "Kaiser Permanente", "A-", "Robert Young — (555) 567-0002", "Level was 18 ng/mL (deficient). Recheck in 8 weeks. Fatigue and mild joint pain likely related. Encourage sun exposure."),
    ("Emmett", "Shear", "1983-06-12", "MRN-001534", "Acid Reflux (GERD)", "Omeprazole 20mg daily before breakfast, dietary modifications", "None known", "2026-02-14", "(555) 678-0001", "United Healthcare", "O-", "Lisa Shear — (555) 678-0002", "Triggered by coffee and spicy food. Elevated head of bed. Avoid eating 3hr before sleep. If no improvement in 4 weeks, consider endoscopy."),
]


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                dob TEXT NOT NULL,
                mrn TEXT NOT NULL UNIQUE,
                diagnosis TEXT NOT NULL,
                medications TEXT NOT NULL,
                allergies TEXT DEFAULT 'None known',
                last_visit TEXT NOT NULL,
                phone TEXT DEFAULT '',
                insurance TEXT DEFAULT '',
                blood_type TEXT DEFAULT '',
                emergency_contact TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                deleted INTEGER DEFAULT 0,
                deleted_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS patient_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                first_name TEXT, last_name TEXT, dob TEXT, mrn TEXT,
                diagnosis TEXT, medications TEXT, allergies TEXT,
                last_visit TEXT, phone TEXT, insurance TEXT,
                change_type TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                changed_field TEXT,
                old_value TEXT,
                new_value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                action_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                hash TEXT NOT NULL,
                signature TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                patient_name TEXT NOT NULL,
                doctor_name TEXT NOT NULL,
                appointment_type TEXT NOT NULL,
                scheduled_for TEXT NOT NULL,
                duration_minutes INTEGER DEFAULT 30,
                status TEXT DEFAULT 'scheduled',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                created_by TEXT DEFAULT 'system'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lab_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                test_name TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                reference_range_low REAL,
                reference_range_high REAL,
                status TEXT DEFAULT 'normal',
                collected_at TEXT NOT NULL,
                resulted_at TEXT NOT NULL,
                ordered_by TEXT DEFAULT 'Dr. Lab'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS patient_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                note_type TEXT DEFAULT 'SOAP',
                content TEXT NOT NULL,
                drafted_by TEXT NOT NULL,
                drafted_at TEXT NOT NULL,
                status TEXT DEFAULT 'draft',
                finalized_by TEXT,
                finalized_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS care_team_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                provider_name TEXT NOT NULL,
                provider_role TEXT NOT NULL,
                action TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                notes TEXT DEFAULT ''
            )
        """)

        cursor = await db.execute("SELECT COUNT(*) FROM patients")
        count = (await cursor.fetchone())[0]
        if count == 0:
            for p in SEED_PATIENTS:
                await db.execute(
                    """INSERT INTO patients
                       (first_name, last_name, dob, mrn, diagnosis, medications, allergies, last_visit, phone, insurance, blood_type, emergency_contact, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    p,
                )

        # Seed appointments if empty
        appt_count = (await (await db.execute("SELECT COUNT(*) FROM appointments")).fetchone())[0]
        if appt_count == 0:
            await _seed_appointments(db)

        # Seed lab results if empty
        lab_count = (await (await db.execute("SELECT COUNT(*) FROM lab_results")).fetchone())[0]
        if lab_count == 0:
            await _seed_lab_results(db)

        await db.commit()


async def _seed_appointments(db):
    """Seed realistic upcoming appointments for patients."""
    appointments = [
        (1, "Sam Altman", "Dr. Chen", "Allergy Follow-Up", "2026-03-10T09:00:00", 20, "scheduled", "Review antihistamine efficacy", "2026-02-15T10:00:00"),
        (1, "Sam Altman", "Dr. Chen", "Annual Physical", "2026-04-15T14:00:00", 45, "scheduled", "", "2026-02-15T10:00:00"),
        (2, "Paul Graham", "Dr. Patel", "Eye Exam Follow-Up", "2026-03-20T11:00:00", 30, "scheduled", "Recheck eye strain symptoms", "2026-02-20T09:00:00"),
        (3, "Jessica Livingston", "Dr. Chen", "Follow-Up", "2026-03-08T10:30:00", 15, "scheduled", "Ensure cold resolved", "2026-01-28T11:00:00"),
        (4, "Garry Tan", "Dr. Martinez", "Headache Follow-Up", "2026-03-15T13:00:00", 20, "scheduled", "Evaluate caffeine taper progress", "2026-02-25T08:00:00"),
        (4, "Garry Tan", "Dr. Martinez", "BP Recheck", "2026-03-25T09:30:00", 15, "scheduled", "Follow up on elevated BP", "2026-02-25T08:00:00"),
        (5, "Michael Seibel", "Dr. Ortiz", "PT Progress Check", "2026-03-12T15:00:00", 30, "scheduled", "Evaluate knee recovery", "2026-02-10T14:00:00"),
        (6, "Dalton Caldwell", "Dr. Chen", "Stress Management Follow-Up", "2026-03-18T10:00:00", 20, "scheduled", "", "2026-02-18T09:00:00"),
        (7, "Jared Friedman", "Dr. Patel", "Dermatology Consult", "2026-03-22T11:30:00", 30, "scheduled", "Skin exam and sunburn follow-up", "2026-02-22T10:00:00"),
        (8, "Gustaf Alstromer", "Dr. Ortiz", "Elbow Follow-Up", "2026-03-05T14:00:00", 20, "scheduled", "Monitor NSAID tolerance", "2026-01-30T13:00:00"),
        (9, "Kevin Hale", "Dr. Ortiz", "Ankle Follow-Up", "2026-03-14T09:00:00", 20, "scheduled", "Assess need for PT", "2026-02-12T10:00:00"),
        (10, "Adora Cheung", "Dr. Chen", "GI Referral", "2026-03-10T16:00:00", 30, "scheduled", "If hiccups persist", "2026-02-08T11:00:00"),
        (11, "Brian Chesky", "Dr. Ortiz", "Back Pain Follow-Up", "2026-03-20T10:00:00", 20, "scheduled", "", "2026-02-24T09:00:00"),
        (12, "Patrick Collison", "Dr. Chen", "Sleep Study Review", "2026-03-28T14:00:00", 30, "scheduled", "Review sleep diary results", "2026-02-17T15:00:00"),
        (13, "Drew Houston", "Dr. Ortiz", "Carpal Tunnel Recheck", "2026-03-07T11:00:00", 20, "scheduled", "Reassess after 6 weeks conservative tx", "2026-01-20T10:00:00"),
        (14, "Tracy Young", "Dr. Patel", "Vitamin D Recheck Labs", "2026-03-30T08:30:00", 15, "scheduled", "Recheck Vit D level", "2026-02-05T09:00:00"),
        (15, "Emmett Shear", "Dr. Chen", "GERD Follow-Up", "2026-03-14T13:00:00", 20, "scheduled", "Assess PPI response, consider endoscopy", "2026-02-14T10:00:00"),
    ]
    for a in appointments:
        await db.execute(
            """INSERT INTO appointments (patient_id, patient_name, doctor_name, appointment_type, scheduled_for, duration_minutes, status, notes, created_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'system')""", a
        )


async def _seed_lab_results(db):
    """Seed realistic lab results for patients."""
    labs = [
        # Sam Altman - allergies patient, mostly normal
        (1, "Complete Blood Count", 14.2, "g/dL", 12.0, 17.5, "normal", "2026-02-10", "2026-02-11", "Dr. Chen"),
        (1, "IgE Total", 245, "IU/mL", 0, 100, "high", "2026-02-10", "2026-02-11", "Dr. Chen"),
        (1, "Eosinophils", 8.2, "%", 1.0, 4.0, "high", "2026-02-10", "2026-02-11", "Dr. Chen"),
        # Paul Graham - eye strain
        (2, "Glucose (Fasting)", 92, "mg/dL", 70, 100, "normal", "2026-02-15", "2026-02-16", "Dr. Patel"),
        (2, "Vitamin A", 62, "mcg/dL", 30, 65, "normal", "2026-02-15", "2026-02-16", "Dr. Patel"),
        # Garry Tan - caffeine withdrawal, elevated BP
        (4, "Blood Pressure Systolic", 138, "mmHg", 90, 120, "high", "2026-02-20", "2026-02-20", "Dr. Martinez"),
        (4, "Blood Pressure Diastolic", 88, "mmHg", 60, 80, "high", "2026-02-20", "2026-02-20", "Dr. Martinez"),
        (4, "Cortisol (AM)", 28, "mcg/dL", 6, 23, "high", "2026-02-20", "2026-02-21", "Dr. Martinez"),
        # Michael Seibel - runner's knee
        (5, "CRP (C-Reactive Protein)", 3.8, "mg/L", 0, 3.0, "high", "2026-02-05", "2026-02-06", "Dr. Ortiz"),
        (5, "ESR", 18, "mm/hr", 0, 20, "normal", "2026-02-05", "2026-02-06", "Dr. Ortiz"),
        # Gustaf Alstromer - tennis elbow, NSAID allergy concern
        (8, "Creatinine", 0.9, "mg/dL", 0.7, 1.3, "normal", "2026-01-25", "2026-01-26", "Dr. Ortiz"),
        (8, "GFR", 95, "mL/min", 90, 120, "normal", "2026-01-25", "2026-01-26", "Dr. Ortiz"),
        # Tracy Young - Vitamin D deficiency
        (14, "Vitamin D (25-OH)", 18, "ng/mL", 30, 100, "low", "2026-01-30", "2026-01-31", "Dr. Patel"),
        (14, "Calcium", 8.8, "mg/dL", 8.5, 10.5, "normal", "2026-01-30", "2026-01-31", "Dr. Patel"),
        (14, "PTH", 72, "pg/mL", 15, 65, "high", "2026-01-30", "2026-01-31", "Dr. Patel"),
        # Emmett Shear - GERD
        (15, "H. pylori Antibody", 0.3, "index", 0, 0.9, "normal", "2026-02-10", "2026-02-11", "Dr. Chen"),
        # General metabolic panels for others
        (3, "WBC", 11.2, "K/uL", 4.5, 11.0, "high", "2026-01-25", "2026-01-26", "Dr. Chen"),
        (6, "Magnesium", 2.1, "mg/dL", 1.7, 2.2, "normal", "2026-02-15", "2026-02-16", "Dr. Chen"),
        (7, "Vitamin D (25-OH)", 35, "ng/mL", 30, 100, "normal", "2026-02-18", "2026-02-19", "Dr. Patel"),
        (9, "Glucose (Fasting)", 88, "mg/dL", 70, 100, "normal", "2026-02-08", "2026-02-09", "Dr. Ortiz"),
        (10, "CBC - Hemoglobin", 13.8, "g/dL", 12.0, 16.0, "normal", "2026-02-05", "2026-02-06", "Dr. Chen"),
        (11, "Lumbar X-Ray Score", 0, "findings", 0, 0, "normal", "2026-02-20", "2026-02-20", "Dr. Ortiz"),
        (12, "Cortisol (PM)", 8.5, "mcg/dL", 2, 11, "normal", "2026-02-12", "2026-02-13", "Dr. Chen"),
        (13, "Nerve Conduction", 48, "m/s", 50, 70, "low", "2026-01-15", "2026-01-16", "Dr. Ortiz"),
    ]
    for lab in labs:
        await db.execute(
            """INSERT INTO lab_results (patient_id, test_name, value, unit, reference_range_low, reference_range_high, status, collected_at, resulted_at, ordered_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", lab
        )


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db
