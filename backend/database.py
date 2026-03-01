import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "medledger.db")

SEED_PATIENTS = [
    ("Sam", "Altman", "1985-04-22", "MRN-001042", "Seasonal Allergies", "Claritin 10mg daily, Flonase nasal spray", "None known", "2026-02-15", "(555) 234-5678", "Blue Cross Blue Shield"),
    ("Paul", "Graham", "1964-11-13", "MRN-001087", "Mild Eye Strain", "Artificial tears PRN, Blue-light glasses prescription", "None known", "2026-02-20", "(555) 345-6789", "Aetna PPO"),
    ("Jessica", "Livingston", "1971-08-09", "MRN-001123", "Common Cold", "Vitamin C 1000mg daily, Zinc lozenges PRN, rest", "Penicillin", "2026-01-28", "(555) 456-7890", "United Healthcare"),
    ("Garry", "Tan", "1982-06-30", "MRN-001156", "Caffeine Withdrawal Headaches", "Ibuprofen 400mg PRN, gradual caffeine taper plan", "None known", "2026-02-25", "(555) 567-8901", "Cigna"),
    ("Michael", "Seibel", "1982-02-02", "MRN-001198", "Runner's Knee (Patellofemoral Syndrome)", "Ibuprofen 200mg PRN, physical therapy 2x/week, knee brace", "Sulfa drugs", "2026-02-10", "(555) 678-9012", "Kaiser Permanente"),
    ("Dalton", "Caldwell", "1980-01-15", "MRN-001234", "Mild Tension Headache", "Acetaminophen 500mg PRN, stress management techniques", "Aspirin", "2026-02-18", "(555) 789-0123", "Anthem Blue Cross"),
    ("Jared", "Friedman", "1986-07-20", "MRN-001267", "Seasonal Allergies, Mild Sunburn", "Zyrtec 10mg daily, Aloe vera gel topical, SPF 50 sunscreen", "None known", "2026-02-22", "(555) 890-1234", "Blue Cross Blue Shield"),
    ("Gustaf", "Alstromer", "1985-03-05", "MRN-001301", "Tennis Elbow (Lateral Epicondylitis)", "Naproxen 250mg BID, elbow strap, ice therapy 3x/day", "NSAIDs", "2026-01-30", "(555) 901-2345", "Humana"),
    ("Kevin", "Hale", "1981-12-18", "MRN-001345", "Mild Sprained Ankle", "RICE protocol, Ibuprofen 400mg TID, ankle wrap", "Latex", "2026-02-12", "(555) 012-3456", "United Healthcare"),
    ("Adora", "Cheung", "1987-09-14", "MRN-001389", "Hiccups (Persistent, 3 days)", "Chlorpromazine 25mg PRN, breathing exercises, peppermint tea", "None known", "2026-02-08", "(555) 123-4567", "Aetna PPO"),
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
