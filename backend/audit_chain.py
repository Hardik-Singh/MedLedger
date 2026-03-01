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
PRIVATE_KEY_PATH = os.path.join(KEY_DIR, "agent_private.pem")
PUBLIC_KEY_PATH = os.path.join(KEY_DIR, "agent_public.pem")

_private_key = None
_public_key = None
_last_hash = "GENESIS"


def _init_keys():
    global _private_key, _public_key
    os.makedirs(KEY_DIR, exist_ok=True)

    if os.path.exists(PRIVATE_KEY_PATH):
        with open(PRIVATE_KEY_PATH, "rb") as f:
            _private_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())
        _public_key = _private_key.public_key()
    else:
        _private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        _public_key = _private_key.public_key()
        with open(PRIVATE_KEY_PATH, "wb") as f:
            f.write(
                _private_key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
        with open(PUBLIC_KEY_PATH, "wb") as f:
            f.write(
                _public_key.public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )


def _canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _compute_hash(record: dict) -> str:
    canonical = _canonical_json(record)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sign_hash(hash_hex: str) -> str:
    hash_bytes = bytes.fromhex(hash_hex)
    signature = _private_key.sign(hash_bytes, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    return signature.hex()


def _verify_signature(hash_hex: str, signature_hex: str) -> bool:
    try:
        hash_bytes = bytes.fromhex(hash_hex)
        signature_bytes = bytes.fromhex(signature_hex)
        _public_key.verify(signature_bytes, hash_bytes, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
        return True
    except Exception:
        return False


async def init_chain():
    global _last_hash
    _init_keys()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT hash FROM audit_log ORDER BY rowid DESC LIMIT 1")
        row = await cursor.fetchone()
        if row:
            _last_hash = row["hash"]
        else:
            _last_hash = "GENESIS"


async def sign_action(action_type: str, payload: dict, agent_id: str = "medledger-agent-1") -> dict:
    global _last_hash

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
    signature = _sign_hash(action_hash)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO audit_log (id, timestamp, action_type, payload, prev_hash, agent_id, hash, signature)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
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
    _init_keys()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM audit_log ORDER BY rowid ASC")
        rows = await cursor.fetchall()

    if not rows:
        return {"intact": True, "total_actions": 0, "last_verified": None, "broken_at": None, "error": None}

    expected_prev = "GENESIS"
    for idx, row in enumerate(rows):
        if row["prev_hash"] != expected_prev:
            return {
                "intact": False,
                "total_actions": len(rows),
                "last_verified": rows[idx - 1]["timestamp"] if idx > 0 else None,
                "broken_at": idx,
                "error": f"Chain broken at action {idx}: expected prev_hash {expected_prev[:16]}... got {row['prev_hash'][:16]}...",
            }

        record = {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "action_type": row["action_type"],
            "payload": json.loads(row["payload"]),
            "prev_hash": row["prev_hash"],
            "agent_id": row["agent_id"],
        }
        computed_hash = _compute_hash(record)
        if computed_hash != row["hash"]:
            return {
                "intact": False,
                "total_actions": len(rows),
                "last_verified": rows[idx - 1]["timestamp"] if idx > 0 else None,
                "broken_at": idx,
                "error": f"Hash mismatch at action {idx}: record may have been tampered with",
            }

        if not _verify_signature(row["hash"], row["signature"]):
            return {
                "intact": False,
                "total_actions": len(rows),
                "last_verified": rows[idx - 1]["timestamp"] if idx > 0 else None,
                "broken_at": idx,
                "error": f"Signature verification failed at action {idx}: key mismatch or tampering detected",
            }

        expected_prev = row["hash"]

    return {
        "intact": True,
        "total_actions": len(rows),
        "last_verified": rows[-1]["timestamp"],
        "broken_at": None,
        "error": None,
    }


_tamper_backup = {}  # stores original payload for restore


async def tamper_record() -> str:
    """Intentionally corrupt the last audit record for demo. Returns tampered record id."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM audit_log ORDER BY rowid DESC LIMIT 1")
        row = await cursor.fetchone()
        if not row:
            return None

        record_id = row["id"]
        _tamper_backup[record_id] = row["payload"]

        # Corrupt the payload — change it so hash won't match
        tampered = json.loads(row["payload"])
        tampered["TAMPERED"] = True
        tampered["original_overwritten"] = "This record was modified outside the audit system"
        await db.execute("UPDATE audit_log SET payload = ? WHERE id = ?", (json.dumps(tampered), record_id))
        await db.commit()

    return record_id


async def restore_record() -> bool:
    """Restore the tampered record from backup."""
    if not _tamper_backup:
        return False

    async with aiosqlite.connect(DB_PATH) as db:
        for record_id, original_payload in _tamper_backup.items():
            await db.execute("UPDATE audit_log SET payload = ? WHERE id = ?", (original_payload, record_id))
        await db.commit()

    _tamper_backup.clear()
    return True


async def get_full_log() -> list:
    _init_keys()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM audit_log ORDER BY rowid ASC")
        rows = await cursor.fetchall()

    results = []
    expected_prev = "GENESIS"
    for row in rows:
        verified = _verify_signature(row["hash"], row["signature"]) and row["prev_hash"] == expected_prev
        record = {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "action_type": row["action_type"],
            "payload": json.loads(row["payload"]),
            "prev_hash": row["prev_hash"],
            "agent_id": row["agent_id"],
            "hash": row["hash"],
            "signature": row["signature"],
            "verified": verified,
        }
        results.append(record)
        expected_prev = row["hash"]
    return results
