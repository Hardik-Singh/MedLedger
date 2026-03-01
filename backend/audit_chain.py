"""
MedLedger Audit Chain — ECDSA P-256 signing + SHA-256 hash-chaining.
Supports multiple agent identities (ARIA, DELTA, custom) with a shared chain.
"""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.backends import default_backend

import aiosqlite
from backend.database import DB_PATH

KEY_DIR = os.path.join(os.path.dirname(__file__), "keys")

# ──────────────────────────── Key Management ────────────────────────────

_keys = {}  # agent_id -> (private_key, public_key)
_last_hash = "GENESIS"


def _load_or_create_keypair(agent_id: str):
    """Load or generate an ECDSA P-256 keypair for an agent."""
    if agent_id in _keys:
        return _keys[agent_id]

    os.makedirs(KEY_DIR, exist_ok=True)
    safe_name = agent_id.replace(" ", "-").lower()
    priv_path = os.path.join(KEY_DIR, f"{safe_name}_private.pem")
    pub_path = os.path.join(KEY_DIR, f"{safe_name}_public.pem")

    if os.path.exists(priv_path):
        with open(priv_path, "rb") as f:
            priv = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())
        pub = priv.public_key()
    else:
        priv = ec.generate_private_key(ec.SECP256R1(), default_backend())
        pub = priv.public_key()
        with open(priv_path, "wb") as f:
            f.write(priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        with open(pub_path, "wb") as f:
            f.write(pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))

    _keys[agent_id] = (priv, pub)
    return priv, pub


def _canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _compute_hash(record: dict) -> str:
    return hashlib.sha256(_canonical_json(record).encode("utf-8")).hexdigest()


def _sign_hash(private_key, hash_hex: str) -> str:
    hash_bytes = bytes.fromhex(hash_hex)
    sig = private_key.sign(hash_bytes, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    return sig.hex()


def _verify_signature(public_key, hash_hex: str, signature_hex: str) -> bool:
    try:
        public_key.verify(bytes.fromhex(signature_hex), bytes.fromhex(hash_hex), ec.ECDSA(utils.Prehashed(hashes.SHA256())))
        return True
    except Exception:
        return False


# ──────────────────────────── Chain Operations ────────────────────────────

async def init_chain():
    global _last_hash
    # Pre-load default keypair
    _load_or_create_keypair("medledger-agent")
    _load_or_create_keypair("aria")
    _load_or_create_keypair("delta")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT hash FROM audit_log ORDER BY rowid DESC LIMIT 1")
        row = await cursor.fetchone()
        _last_hash = row["hash"] if row else "GENESIS"


async def sign_action(action_type: str, payload: dict, agent_id: str = "medledger-agent") -> dict:
    global _last_hash

    priv, _ = _load_or_create_keypair(agent_id)

    action_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    record = {
        "id": action_id,
        "timestamp": timestamp,
        "action_type": action_type,
        "payload": payload,
        "prev_hash": _last_hash,
        "agent_id": agent_id,
    }

    action_hash = _compute_hash(record)
    signature = _sign_hash(priv, action_hash)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO audit_log (id, timestamp, action_type, payload, prev_hash, agent_id, hash, signature) VALUES (?,?,?,?,?,?,?,?)",
            (action_id, timestamp, action_type, json.dumps(payload), _last_hash, agent_id, action_hash, signature),
        )
        await db.commit()

    _last_hash = action_hash

    return {
        "id": action_id,
        "timestamp": timestamp,
        "action_type": action_type,
        "payload": payload,
        "prev_hash": record["prev_hash"],
        "agent_id": agent_id,
        "hash": action_hash,
        "signature": signature,
        "verified": True,
    }


async def verify_chain() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM audit_log ORDER BY rowid ASC")
        rows = await cursor.fetchall()

    if not rows:
        return {"intact": True, "total_actions": 0, "last_verified": None, "broken_at": None, "error": None}

    expected_prev = "GENESIS"
    for idx, row in enumerate(rows):
        # Check chain link
        if row["prev_hash"] != expected_prev:
            return {
                "intact": False, "total_actions": len(rows),
                "last_verified": rows[idx - 1]["timestamp"] if idx > 0 else None,
                "broken_at": idx,
                "error": f"Chain broken at action {idx}: expected prev_hash {expected_prev[:16]}... got {row['prev_hash'][:16]}...",
            }
        # Check hash integrity
        record = {
            "id": row["id"], "timestamp": row["timestamp"], "action_type": row["action_type"],
            "payload": json.loads(row["payload"]), "prev_hash": row["prev_hash"], "agent_id": row["agent_id"],
        }
        computed = _compute_hash(record)
        if computed != row["hash"]:
            return {
                "intact": False, "total_actions": len(rows),
                "last_verified": rows[idx - 1]["timestamp"] if idx > 0 else None,
                "broken_at": idx,
                "error": f"Hash mismatch at action {idx}: record tampered",
            }
        # Check signature
        _, pub = _load_or_create_keypair(row["agent_id"])
        if not _verify_signature(pub, row["hash"], row["signature"]):
            return {
                "intact": False, "total_actions": len(rows),
                "last_verified": rows[idx - 1]["timestamp"] if idx > 0 else None,
                "broken_at": idx,
                "error": f"Signature failed at action {idx}: key mismatch or tampering",
            }
        expected_prev = row["hash"]

    return {
        "intact": True, "total_actions": len(rows),
        "last_verified": rows[-1]["timestamp"], "broken_at": None, "error": None,
    }


async def get_full_log() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM audit_log ORDER BY rowid ASC")
        rows = await cursor.fetchall()

    results = []
    expected_prev = "GENESIS"
    for row in rows:
        _, pub = _load_or_create_keypair(row["agent_id"])
        verified = _verify_signature(pub, row["hash"], row["signature"]) and row["prev_hash"] == expected_prev
        results.append({
            "id": row["id"], "timestamp": row["timestamp"], "action_type": row["action_type"],
            "payload": json.loads(row["payload"]), "prev_hash": row["prev_hash"],
            "agent_id": row["agent_id"], "hash": row["hash"], "signature": row["signature"],
            "verified": verified,
        })
        expected_prev = row["hash"]
    return results


# ──────────────────────────── Tamper Simulation ────────────────────────────

_tamper_backup = {}


async def tamper_record() -> str:
    """Corrupt the last audit record for demo."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM audit_log ORDER BY rowid DESC LIMIT 1")
        row = await cursor.fetchone()
        if not row:
            return None
        _tamper_backup[row["id"]] = row["payload"]
        tampered = json.loads(row["payload"])
        tampered["TAMPERED"] = True
        tampered["injected"] = "This record was modified outside the audit system"
        await db.execute("UPDATE audit_log SET payload = ? WHERE id = ?", (json.dumps(tampered), row["id"]))
        await db.commit()
    return row["id"]


async def restore_record() -> bool:
    """Restore tampered record."""
    if not _tamper_backup:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        for rid, payload in _tamper_backup.items():
            await db.execute("UPDATE audit_log SET payload = ? WHERE id = ?", (payload, rid))
        await db.commit()
    _tamper_backup.clear()
    return True
