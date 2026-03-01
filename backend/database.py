import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "medledger.db")

SEED_PATIENTS = [
    ("John", "Smith", "1958-03-14", "MRN-001042", "Type 2 Diabetes Mellitus", "Metformin 500mg BID, Lisinopril 10mg daily", "Penicillin", "2026-02-15", "(555) 234-5678", "Blue Cross Blue Shield"),
    ("Maria", "Garcia", "1975-08-22", "MRN-001087", "Hypertension, Hyperlipidemia", "Amlodipine 5mg daily, Atorvastatin 20mg daily", "Sulfa drugs", "2026-02-20", "(555) 345-6789", "Aetna PPO"),
    ("Robert", "Johnson", "1962-11-30", "MRN-001123", "Chronic Kidney Disease Stage 3", "Losartan 50mg daily, Sodium Bicarbonate 650mg TID", "None known", "2026-01-28", "(555) 456-7890", "Medicare Part B"),
    ("Emily", "Chen", "1990-04-05", "MRN-001156", "Generalized Anxiety Disorder", "Sertraline 100mg daily, Buspirone 10mg BID", "Latex", "2026-02-25", "(555) 567-8901", "United Healthcare"),
    ("James", "Williams", "1945-07-19", "MRN-001198", "Atrial Fibrillation, CHF NYHA Class II", "Apixaban 5mg BID, Metoprolol 25mg BID, Furosemide 20mg daily", "Aspirin", "2026-02-10", "(555) 678-9012", "Medicare Advantage"),
    ("Sarah", "Patel", "1983-12-01", "MRN-001234", "Rheumatoid Arthritis", "Methotrexate 15mg weekly, Folic acid 1mg daily, Prednisone 5mg daily", "NSAIDs", "2026-02-18", "(555) 789-0123", "Cigna"),
    ("Michael", "Brown", "1970-09-15", "MRN-001267", "Major Depressive Disorder, Type 2 Diabetes", "Duloxetine 60mg daily, Metformin 1000mg BID, Glipizide 5mg daily", "Codeine", "2026-02-22", "(555) 890-1234", "Anthem Blue Cross"),
    ("Lisa", "Thompson", "1955-02-28", "MRN-001301", "COPD, Osteoporosis", "Tiotropium 18mcg inhaled daily, Albuterol PRN, Alendronate 70mg weekly", "Erythromycin", "2026-01-30", "(555) 901-2345", "Humana"),
    ("David", "Martinez", "1988-06-10", "MRN-001345", "Crohn's Disease", "Adalimumab 40mg every 2 weeks, Mesalamine 800mg TID", "None known", "2026-02-12", "(555) 012-3456", "Kaiser Permanente"),
    ("Jennifer", "Lee", "1972-10-25", "MRN-001389", "Breast Cancer - Stage IIA (in remission)", "Tamoxifen 20mg daily, Calcium/Vitamin D supplement", "Iodine contrast", "2026-02-08", "(555) 123-4567", "UnitedHealth Group"),
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

        cursor = await db.execute("SELECT COUNT(*) FROM patients")
        count = (await cursor.fetchone())[0]
        if count == 0:
            for p in SEED_PATIENTS:
                await db.execute(
                    """INSERT INTO patients
                       (first_name, last_name, dob, mrn, diagnosis, medications, allergies, last_visit, phone, insurance)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    p,
                )
        await db.commit()


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db
