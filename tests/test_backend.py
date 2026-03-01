"""
MedLedger Backend Tests — audit chain, database, API endpoints, clinical modules.
"""

import asyncio
import json
import os
import sys
import pytest

# Ensure backend is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.database import init_db, DB_PATH, SEED_PATIENTS

PATIENT_COUNT = len(SEED_PATIENTS)


# ──────────────────────────── Fixtures ────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Use a temp database for each test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("backend.database.DB_PATH", db_path)
    monkeypatch.setattr("backend.audit_chain.DB_PATH", db_path)
    try:
        import backend.agent
        monkeypatch.setattr("backend.agent.DB_PATH", db_path)
    except Exception:
        pass
    # Reset chain state
    import backend.audit_chain as ac
    ac._last_hash = "GENESIS"
    ac._keys.clear()
    # Use temp key dir
    key_dir = str(tmp_path / "keys")
    monkeypatch.setattr("backend.audit_chain.KEY_DIR", key_dir)
    return db_path


# ──────────────────────────── Database Tests ────────────────────────────

class TestDatabase:
    def test_init_db_creates_tables(self, fresh_db):
        async def run():
            import aiosqlite
            await init_db()
            async with aiosqlite.connect(fresh_db) as db:
                cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in await cursor.fetchall()]
                assert "patients" in tables
                assert "patient_history" in tables
                assert "audit_log" in tables
                assert "appointments" in tables
                assert "lab_results" in tables
                assert "patient_notes" in tables
                assert "care_team_log" in tables
        asyncio.run(run())

    def test_seed_patients_created(self, fresh_db):
        async def run():
            import aiosqlite
            await init_db()
            async with aiosqlite.connect(fresh_db) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM patients")
                count = (await cursor.fetchone())[0]
                assert count == PATIENT_COUNT
        asyncio.run(run())

    def test_seed_patients_have_correct_data(self, fresh_db):
        async def run():
            import aiosqlite
            await init_db()
            async with aiosqlite.connect(fresh_db) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM patients WHERE mrn = 'MRN-001042'")
                p = await cursor.fetchone()
                assert p is not None
                assert p["first_name"] == "Sam"
                assert p["last_name"] == "Altman"
                assert p["blood_type"] == "O+"
                assert "Claritin" in p["medications"]
        asyncio.run(run())

    def test_seed_idempotent(self, fresh_db):
        """Calling init_db twice shouldn't duplicate patients."""
        async def run():
            import aiosqlite
            await init_db()
            await init_db()
            async with aiosqlite.connect(fresh_db) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM patients")
                count = (await cursor.fetchone())[0]
                assert count == PATIENT_COUNT
        asyncio.run(run())

    def test_seed_appointments(self, fresh_db):
        async def run():
            import aiosqlite
            await init_db()
            async with aiosqlite.connect(fresh_db) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM appointments")
                count = (await cursor.fetchone())[0]
                assert count > 0
        asyncio.run(run())

    def test_seed_lab_results(self, fresh_db):
        async def run():
            import aiosqlite
            await init_db()
            async with aiosqlite.connect(fresh_db) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM lab_results")
                count = (await cursor.fetchone())[0]
                assert count > 0
        asyncio.run(run())


# ──────────────────────────── Audit Chain Tests ────────────────────────────

class TestAuditChain:
    def test_sign_action_creates_record(self, fresh_db):
        async def run():
            from backend.audit_chain import init_chain, sign_action
            await init_db()
            await init_chain()
            result = await sign_action("SEARCH", {"query": "test"}, agent_id="medledger-agent")
            assert result["action_type"] == "SEARCH"
            assert result["verified"] is True
            assert result["hash"]
            assert result["signature"]
            assert result["prev_hash"] == "GENESIS"
        asyncio.run(run())

    def test_chain_links_hashes(self, fresh_db):
        async def run():
            from backend.audit_chain import init_chain, sign_action
            await init_db()
            await init_chain()
            a1 = await sign_action("SEARCH", {"query": "first"})
            a2 = await sign_action("VIEW", {"patient_id": 1})
            assert a2["prev_hash"] == a1["hash"]
            a3 = await sign_action("UPDATE", {"field": "meds"})
            assert a3["prev_hash"] == a2["hash"]
        asyncio.run(run())

    def test_verify_chain_intact(self, fresh_db):
        async def run():
            from backend.audit_chain import init_chain, sign_action, verify_chain
            await init_db()
            await init_chain()
            await sign_action("SEARCH", {"query": "a"})
            await sign_action("VIEW", {"patient_id": 1})
            await sign_action("UPDATE", {"field": "meds", "old_value": "x", "new_value": "y"})
            result = await verify_chain()
            assert result["intact"] is True
            assert result["total_actions"] == 3
        asyncio.run(run())

    def test_verify_empty_chain(self, fresh_db):
        async def run():
            from backend.audit_chain import init_chain, verify_chain
            await init_db()
            await init_chain()
            result = await verify_chain()
            assert result["intact"] is True
            assert result["total_actions"] == 0
        asyncio.run(run())

    def test_tamper_breaks_chain(self, fresh_db):
        async def run():
            from backend.audit_chain import init_chain, sign_action, verify_chain, tamper_record
            await init_db()
            await init_chain()
            await sign_action("SEARCH", {"query": "a"})
            await sign_action("VIEW", {"patient_id": 1})
            tampered_id = await tamper_record()
            assert tampered_id is not None
            result = await verify_chain()
            assert result["intact"] is False
            assert "tampered" in result["error"].lower() or "mismatch" in result["error"].lower()
        asyncio.run(run())

    def test_restore_fixes_chain(self, fresh_db):
        async def run():
            from backend.audit_chain import init_chain, sign_action, verify_chain, tamper_record, restore_record
            await init_db()
            await init_chain()
            await sign_action("SEARCH", {"query": "a"})
            await sign_action("VIEW", {"patient_id": 1})
            await tamper_record()
            result = await verify_chain()
            assert result["intact"] is False
            restored = await restore_record()
            assert restored is True
            result = await verify_chain()
            assert result["intact"] is True
        asyncio.run(run())

    def test_multi_agent_keys(self, fresh_db):
        """Different agents get different keypairs."""
        async def run():
            from backend.audit_chain import init_chain, sign_action, verify_chain
            await init_db()
            await init_chain()
            a1 = await sign_action("SEARCH", {"query": "a"}, agent_id="aria")
            a2 = await sign_action("UPDATE", {"field": "meds"}, agent_id="delta")
            assert a1["agent_id"] == "aria"
            assert a2["agent_id"] == "delta"
            assert a2["prev_hash"] == a1["hash"]  # Same chain
            result = await verify_chain()
            assert result["intact"] is True
        asyncio.run(run())

    def test_get_full_log(self, fresh_db):
        async def run():
            from backend.audit_chain import init_chain, sign_action, get_full_log
            await init_db()
            await init_chain()
            await sign_action("SEARCH", {"query": "a"}, agent_id="aria")
            await sign_action("VIEW", {"patient_id": 1}, agent_id="delta")
            log = await get_full_log()
            assert len(log) == 2
            assert log[0]["agent_id"] == "aria"
            assert log[1]["agent_id"] == "delta"
            assert all(entry["verified"] for entry in log)
        asyncio.run(run())

    def test_hash_deterministic(self, fresh_db):
        """Same input produces same hash."""
        from backend.audit_chain import _compute_hash
        record = {"id": "abc", "timestamp": "2026-01-01", "action_type": "SEARCH", "payload": {"q": "test"}, "prev_hash": "GENESIS", "agent_id": "test"}
        h1 = _compute_hash(record)
        h2 = _compute_hash(record)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_different_payloads_different_hashes(self, fresh_db):
        from backend.audit_chain import _compute_hash
        r1 = {"id": "a", "timestamp": "t", "action_type": "X", "payload": {"q": "a"}, "prev_hash": "G", "agent_id": "x"}
        r2 = {"id": "a", "timestamp": "t", "action_type": "X", "payload": {"q": "b"}, "prev_hash": "G", "agent_id": "x"}
        assert _compute_hash(r1) != _compute_hash(r2)


# ──────────────────────────── API Tests (FastAPI TestClient) ────────────────────────────

class TestMainAPI:
    def test_audit_log_endpoint(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/audit/log")
            assert r.status_code == 200
            assert isinstance(r.json(), list)

    def test_audit_verify_endpoint(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/audit/verify")
            assert r.status_code == 200
            data = r.json()
            assert "intact" in data

    def test_patients_current(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/patients/current")
            assert r.status_code == 200
            patients = r.json()
            assert len(patients) == PATIENT_COUNT
            names = [p["last_name"] for p in patients]
            assert "Altman" in names

    def test_patient_history_empty(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/patients/1/history")
            assert r.status_code == 200
            assert r.json() == []

    def test_alerts_empty(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        from backend.main import app
        from backend.main import alerts
        alerts.clear()

        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/alerts")
            assert r.status_code == 200
            assert r.json() == []

    def test_stats_endpoint(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        from backend.main import app, alerts
        alerts.clear()
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/stats")
            assert r.status_code == 200
            data = r.json()
            assert data["active_patients"] == PATIENT_COUNT
            assert data["deleted_patients"] == 0

    def test_api_key_status(self, fresh_db, monkeypatch):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/api/key-status")
            assert r.status_code == 200
            assert r.json()["has_key"] is False

    def test_tamper_and_restore(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain, sign_action
            await init_chain()
            await sign_action("SEARCH", {"query": "test"})
        asyncio.run(run())

        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.post("/audit/tamper")
            assert r.status_code == 200
            assert r.json()["status"] == "tampered"
            r = client.get("/audit/verify")
            assert r.json()["intact"] is False
            r = client.post("/audit/restore")
            assert r.status_code == 200
            r = client.get("/audit/verify")
            assert r.json()["intact"] is True

    def test_export_json(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain, sign_action
            await init_chain()
            await sign_action("SEARCH", {"query": "test"})
        asyncio.run(run())

        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/audit/export")
            assert r.status_code == 200
            data = r.json()
            assert "exported_at" in data
            assert "audit_log" in data
            assert "verification" in data

    def test_export_csv(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain, sign_action
            await init_chain()
            await sign_action("SEARCH", {"query": "test"})
        asyncio.run(run())

        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/audit/export/csv")
            assert r.status_code == 200
            assert "text/csv" in r.headers["content-type"]
            assert "block,timestamp" in r.text

    def test_appointments_endpoint(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/appointments/upcoming")
            assert r.status_code == 200
            appts = r.json()
            assert isinstance(appts, list)
            assert len(appts) > 0

    def test_patient_labs_endpoint(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/patients/1/labs")
            assert r.status_code == 200
            labs = r.json()
            assert isinstance(labs, list)
            assert len(labs) > 0

    def test_patient_risk_endpoint(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/patients/1/risk")
            assert r.status_code == 200
            data = r.json()
            assert "risk_level" in data
            assert "score" in data

    def test_all_patient_risks_endpoint(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/patients/risks")
            assert r.status_code == 200
            risks = r.json()
            assert isinstance(risks, list)
            assert len(risks) == PATIENT_COUNT

    def test_handoff_report_endpoint(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/reports/handoff")
            assert r.status_code == 200
            data = r.json()
            assert "generated_at" in data
            assert "patients_accessed" in data

    def test_handoff_html_endpoint(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/reports/handoff/html")
            assert r.status_code == 200
            assert "MedLedger" in r.text

    def test_rounds_summary_endpoint(self, fresh_db):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/patients/1/rounds-summary")
            assert r.status_code == 200
            assert "Sam" in r.text
            assert "Altman" in r.text

    def test_memory_status_endpoint(self, fresh_db, monkeypatch):
        async def run():
            await init_db()
            from backend.audit_chain import init_chain
            await init_chain()
        asyncio.run(run())

        monkeypatch.delenv("SUPERMEMORY_API_KEY", raising=False)
        from backend.main import app
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/api/memory-status")
            assert r.status_code == 200
            data = r.json()
            assert "status" in data


# ──────────────────────────── Portal Tests ────────────────────────────

class TestPortal:
    def test_login_page(self, fresh_db):
        async def run():
            await init_db()
        asyncio.run(run())

        from backend.portal import app as portal_app
        from fastapi.testclient import TestClient
        with TestClient(portal_app, raise_server_exceptions=False) as client:
            r = client.get("/login", follow_redirects=False)
            assert r.status_code == 200
            assert "MedLedger Portal" in r.text

    def test_login_success(self, fresh_db):
        async def run():
            await init_db()
        asyncio.run(run())

        from backend.portal import app as portal_app
        from fastapi.testclient import TestClient
        with TestClient(portal_app, raise_server_exceptions=False) as client:
            r = client.post("/login", data={"username": "demo", "password": "demo123"}, follow_redirects=False)
            assert r.status_code == 302
            assert "/patients" in r.headers["location"]

    def test_login_failure(self, fresh_db):
        async def run():
            await init_db()
        asyncio.run(run())

        from backend.portal import app as portal_app
        from fastapi.testclient import TestClient
        with TestClient(portal_app, raise_server_exceptions=False) as client:
            r = client.post("/login", data={"username": "bad", "password": "bad"}, follow_redirects=False)
            assert r.status_code == 302
            assert "error" in r.headers["location"]

    def test_patient_list_requires_auth(self, fresh_db):
        async def run():
            await init_db()
        asyncio.run(run())

        from backend.portal import app as portal_app
        from fastapi.testclient import TestClient
        with TestClient(portal_app, raise_server_exceptions=False) as client:
            r = client.get("/patients", follow_redirects=False)
            assert r.status_code == 302
            assert "/login" in r.headers["location"]

    def test_patient_api(self, fresh_db):
        async def run():
            await init_db()
        asyncio.run(run())

        from backend.portal import app as portal_app
        from fastapi.testclient import TestClient
        with TestClient(portal_app, raise_server_exceptions=False) as client:
            r = client.get("/api/patients")
            assert r.status_code == 200
            patients = r.json()
            assert len(patients) == PATIENT_COUNT


# ──────────────────────────── Alerts Engine Tests ────────────────────────────

class TestAlerts:
    def test_delete_triggers_critical_alert(self, fresh_db):
        from backend.main import _check_alerts, alerts
        alerts.clear()
        action = {"action_type": "DELETE", "payload": {"patient_name": "Sam Altman"}, "id": "test-1"}
        _check_alerts(action)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "CRITICAL"
        assert "Sam Altman" in alerts[0]["message"]

    def test_med_update_triggers_high_alert(self, fresh_db):
        from backend.main import _check_alerts, alerts
        alerts.clear()
        action = {"action_type": "UPDATE", "payload": {"field": "medications", "patient_name": "Paul Graham", "old_value": "Aspirin", "new_value": "Ibuprofen"}, "id": "test-2"}
        _check_alerts(action)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "HIGH"

    def test_verification_failure_alert(self, fresh_db):
        from backend.main import _check_alerts, alerts
        alerts.clear()
        action = {"action_type": "VIEW", "payload": {}, "id": "test-3", "verified": False}
        _check_alerts(action)
        assert any(a["severity"] == "CRITICAL" and "verification" in a["message"].lower() for a in alerts)


# ──────────────────────────── Models Tests ────────────────────────────

class TestModels:
    def test_agent_task_model(self):
        from backend.models import AgentTask
        t = AgentTask(task="search for Sam Altman")
        assert t.task == "search for Sam Altman"
        assert t.agent_name == "MedLedger Agent"
        assert t.api_key is None

    def test_multi_agent_task_model(self):
        from backend.models import MultiAgentTask
        t = MultiAgentTask(agents=[{"name": "ARIA", "task": "search"}, {"name": "DELTA", "task": "update"}])
        assert len(t.agents) == 2
        assert t.agents[0]["name"] == "ARIA"

    def test_patient_model(self):
        from backend.models import Patient
        p = Patient(id=1, first_name="Sam", last_name="Altman", dob="1985-04-22", mrn="MRN-001042",
                    diagnosis="Allergies", medications="Claritin", allergies="None", last_visit="2026-01-01",
                    phone="555", insurance="BC")
        assert p.deleted is False

    def test_chain_verification_model(self):
        from backend.models import ChainVerification
        cv = ChainVerification(intact=True, total_actions=5)
        assert cv.intact is True
        assert cv.broken_at is None


# ──────────────────────────── Interaction Checker Tests ────────────────────────────

class TestInteractions:
    def test_critical_interaction_warfarin_aspirin(self):
        from backend.interactions import check_interactions
        results = check_interactions("Warfarin 5mg daily", "Aspirin 81mg")
        assert len(results) > 0
        assert results[0]["severity"] == "CRITICAL"

    def test_no_interaction_safe_combo(self):
        from backend.interactions import check_interactions
        results = check_interactions("Claritin 10mg daily", "Vitamin C 1000mg")
        assert len(results) == 0

    def test_allergy_conflict_penicillin(self):
        from backend.interactions import check_allergy
        result = check_allergy("Penicillin", "Amoxicillin 500mg")
        assert result is not None
        assert result["conflict"] is True

    def test_no_allergy_conflict(self):
        from backend.interactions import check_allergy
        result = check_allergy("None known", "Ibuprofen 400mg")
        assert result is None

    def test_current_allergy_conflicts(self):
        from backend.interactions import check_current_allergy_conflicts
        conflicts = check_current_allergy_conflicts("Penicillin", "Amoxicillin 500mg, Ibuprofen 200mg")
        assert len(conflicts) == 1
        assert conflicts[0]["allergen"] == "penicillin"

    def test_nsaid_class_interaction(self):
        from backend.interactions import check_interactions
        results = check_interactions("Ibuprofen 400mg", "Naproxen 250mg")
        assert len(results) > 0
        assert results[0]["severity"] == "HIGH"


# ──────────────────────────── Dosage Checker Tests ────────────────────────────

class TestDosageChecker:
    def test_safe_dosage(self):
        from backend.dosage_checker import check_dosage
        result = check_dosage("ibuprofen", 400)
        assert result["safe"] is True

    def test_over_max_dosage(self):
        from backend.dosage_checker import check_dosage
        result = check_dosage("ibuprofen", 5000)
        assert result["safe"] is False
        assert result["severity"] == "CRITICAL"

    def test_elderly_max_dosage(self):
        from backend.dosage_checker import check_dosage
        result = check_dosage("ibuprofen", 2000, patient_age=70)
        assert result["safe"] is False

    def test_extract_from_string(self):
        from backend.dosage_checker import check_medication_string
        results = check_medication_string("Ibuprofen 5000mg, Acetaminophen 500mg")
        assert len(results) > 0
        over_max = [r for r in results if not r.get("safe", True)]
        assert len(over_max) > 0

    def test_unknown_drug(self):
        from backend.dosage_checker import check_dosage
        result = check_dosage("unknowndrug", 100)
        assert result["checked"] is False


# ──────────────────────────── Risk Engine Tests ────────────────────────────

class TestRiskEngine:
    def test_low_risk_patient(self):
        from backend.risk_engine import calculate_patient_risk
        patient = {"dob": "1990-01-01", "diagnosis": "Common Cold", "medications": "Vitamin C", "allergies": "None known"}
        result = calculate_patient_risk(patient)
        assert result["risk_level"] == "LOW"
        assert result["score"] < 3

    def test_high_risk_patient(self):
        from backend.risk_engine import calculate_patient_risk
        patient = {"dob": "1940-01-01", "diagnosis": "Diabetes, Hypertension, Heart Failure",
                   "medications": "Metformin, Lisinopril, Carvedilol, Furosemide, Aspirin, Atorvastatin",
                   "allergies": "Penicillin"}
        result = calculate_patient_risk(patient)
        assert result["risk_level"] in ("HIGH", "CRITICAL")
        assert result["score"] >= 5

    def test_oncology_patient_critical(self):
        from backend.risk_engine import calculate_patient_risk
        patient = {"dob": "1950-01-01", "diagnosis": "Cancer, COPD, Atrial Fibrillation",
                   "medications": "Drug1, Drug2, Drug3, Drug4, Drug5, Drug6",
                   "allergies": "Sulfa drugs"}
        result = calculate_patient_risk(patient)
        assert result["risk_level"] == "CRITICAL"

    def test_all_patient_risks(self, fresh_db):
        async def run():
            await init_db()
            from backend.risk_engine import get_all_patient_risks
            risks = await get_all_patient_risks()
            assert len(risks) == PATIENT_COUNT
            assert all("risk_level" in r for r in risks)
            assert risks[0]["score"] >= risks[-1]["score"]  # sorted desc
        asyncio.run(run())

    def test_risk_factors_list(self):
        from backend.risk_engine import calculate_patient_risk
        patient = {"dob": "1940-01-01", "diagnosis": "Diabetes", "medications": "Med1, Med2, Med3, Med4",
                   "allergies": "Penicillin"}
        result = calculate_patient_risk(patient)
        assert len(result["factors"]) > 0
        assert "Diabetic" in result["factors"]


# ──────────────────────────── Memory Module Tests ────────────────────────────

class TestMemory:
    def test_memory_status_no_key(self, monkeypatch):
        monkeypatch.delenv("SUPERMEMORY_API_KEY", raising=False)
        from backend.memory import memory_status, reset_client
        reset_client()
        status = memory_status()
        assert status["status"] == "inactive"
        assert status["has_key"] is False

    def test_store_interaction_no_client(self):
        async def run():
            from backend.memory import store_interaction
            result = await store_interaction("test-agent", "SEARCH", {"query": "test"})
            assert result is None
        asyncio.run(run())
