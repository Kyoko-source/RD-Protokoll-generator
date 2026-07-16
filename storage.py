import base64
import hashlib
import json
import os
import sqlite3

from cryptography.fernet import Fernet, InvalidToken


DB_PATH = os.getenv("NANA_DB_PATH", "nana.db")
ENCRYPTED_PREFIX = "nana-fernet:v1:"


def _connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'employee',
                qualification TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                password_hash TEXT NOT NULL DEFAULT '',
                temp_password_hash TEXT NOT NULL DEFAULT '',
                must_change_password INTEGER NOT NULL DEFAULT 1,
                created_at TEXT,
                password_changed_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS case_drafts (
                employee_id TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL,
                draft_json TEXT NOT NULL,
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS finished_cases (
                id TEXT PRIMARY KEY,
                employee_id TEXT NOT NULL,
                employee_name TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                patient_json TEXT NOT NULL,
                protocol_text TEXT NOT NULL,
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                employee_id TEXT NOT NULL DEFAULT '',
                employee_name TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL DEFAULT '',
                entity_id TEXT NOT NULL DEFAULT '',
                details_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS login_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                employee_id TEXT NOT NULL DEFAULT '',
                employee_name TEXT NOT NULL DEFAULT '',
                device_id TEXT NOT NULL DEFAULT '',
                device_name TEXT NOT NULL DEFAULT '',
                user_agent TEXT NOT NULL DEFAULT '',
                ip_address TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'login'
            )
            """
        )
        existing_case_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(finished_cases)").fetchall()
        }
        existing_employee_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(employees)").fetchall()
        }
        if "qualification" not in existing_employee_columns:
            connection.execute("ALTER TABLE employees ADD COLUMN qualification TEXT NOT NULL DEFAULT ''")
        if "status" not in existing_case_columns:
            connection.execute("ALTER TABLE finished_cases ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        if "anonymized_at" not in existing_case_columns:
            connection.execute("ALTER TABLE finished_cases ADD COLUMN anonymized_at TEXT NOT NULL DEFAULT ''")
        if "deleted_at" not in existing_case_columns:
            connection.execute("ALTER TABLE finished_cases ADD COLUMN deleted_at TEXT NOT NULL DEFAULT ''")
        if "retention_until" not in existing_case_columns:
            connection.execute("ALTER TABLE finished_cases ADD COLUMN retention_until TEXT NOT NULL DEFAULT ''")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            )
            """
        )
        connection.commit()


def _derive_fernet_key(secret):
    digest = hashlib.sha256(str(secret).encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_data_secret():
    env_secret = os.getenv("NANA_DATA_KEY", "").strip()
    if env_secret:
        return env_secret

    stored = get_app_setting("local_data_key")
    if stored:
        return stored

    secret = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    set_app_setting("local_data_key", secret)
    return secret


def _fernet():
    return Fernet(_derive_fernet_key(_get_data_secret()))


def _encrypt_text(value):
    raw = "" if value is None else str(value)
    if raw.startswith(ENCRYPTED_PREFIX):
        return raw
    token = _fernet().encrypt(raw.encode("utf-8")).decode("ascii")
    return f"{ENCRYPTED_PREFIX}{token}"


def _decrypt_text(value):
    raw = "" if value is None else str(value)
    if not raw.startswith(ENCRYPTED_PREFIX):
        return raw
    token = raw.removeprefix(ENCRYPTED_PREFIX)
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def _json_dumps_secure(value):
    return _encrypt_text(json.dumps(value, ensure_ascii=False))


def _json_loads_secure(value, default=None):
    if default is None:
        default = {}
    decrypted = _decrypt_text(value)
    try:
        return json.loads(decrypted)
    except (TypeError, json.JSONDecodeError):
        return default


def encryption_status():
    env_secret = bool(os.getenv("NANA_DATA_KEY", "").strip())
    return {
        "enabled": True,
        "provider": "Fernet AES-128-CBC/HMAC",
        "key_source": "environment" if env_secret else "local_app_settings",
        "production_hint": "NANA_DATA_KEY ausserhalb der Datenbank setzen" if not env_secret else "externer Schluessel aktiv",
    }


def _employee_from_row(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "role": row["role"],
        "qualification": row["qualification"] or "",
        "active": bool(row["active"]),
        "password_hash": row["password_hash"] or "",
        "temp_password_hash": row["temp_password_hash"] or "",
        "must_change_password": bool(row["must_change_password"]),
        "created_at": row["created_at"] or "",
        "password_changed_at": row["password_changed_at"] or "",
    }


def load_employee_store():
    init_database()
    with _connect() as connection:
        rows = connection.execute("SELECT * FROM employees ORDER BY lower(name)").fetchall()
    return {"employees": [_employee_from_row(row) for row in rows]}


def save_employee_store(store):
    init_database()
    employees = store.get("employees", []) if isinstance(store, dict) else []
    with _connect() as connection:
        existing_ids = {row["id"] for row in connection.execute("SELECT id FROM employees").fetchall()}
        next_ids = {employee.get("id") for employee in employees if employee.get("id")}

        for employee_id in existing_ids - next_ids:
            connection.execute("DELETE FROM case_drafts WHERE employee_id = ?", (employee_id,))
            connection.execute("DELETE FROM employees WHERE id = ?", (employee_id,))

        for employee in employees:
            if not employee.get("id") or not employee.get("name"):
                continue
            connection.execute(
                """
                INSERT INTO employees (
                    id, name, role, qualification, active, password_hash, temp_password_hash,
                    must_change_password, created_at, password_changed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    role = excluded.role,
                    qualification = excluded.qualification,
                    active = excluded.active,
                    password_hash = excluded.password_hash,
                    temp_password_hash = excluded.temp_password_hash,
                    must_change_password = excluded.must_change_password,
                    created_at = excluded.created_at,
                    password_changed_at = excluded.password_changed_at
                """,
                (
                    employee["id"],
                    employee["name"],
                    employee.get("role", "employee"),
                    employee.get("qualification", ""),
                    1 if employee.get("active", True) else 0,
                    employee.get("password_hash", ""),
                    employee.get("temp_password_hash", ""),
                    1 if employee.get("must_change_password", True) else 0,
                    employee.get("created_at", ""),
                    employee.get("password_changed_at", ""),
                ),
            )
        connection.commit()


def load_case_draft_store():
    init_database()
    with _connect() as connection:
        rows = connection.execute("SELECT employee_id, draft_json FROM case_drafts").fetchall()

    drafts = {}
    for row in rows:
        try:
            drafts[row["employee_id"]] = _json_loads_secure(row["draft_json"], {})
        except Exception:
            continue
    return {"drafts": drafts}


def save_case_draft_store(store):
    init_database()
    drafts = store.get("drafts", {}) if isinstance(store, dict) else {}
    with _connect() as connection:
        existing_ids = {row["employee_id"] for row in connection.execute("SELECT employee_id FROM case_drafts").fetchall()}
        next_ids = set(drafts)

        for employee_id in existing_ids - next_ids:
            connection.execute("DELETE FROM case_drafts WHERE employee_id = ?", (employee_id,))

        for employee_id, draft in drafts.items():
            if not isinstance(draft, dict):
                continue
            connection.execute(
                """
                INSERT INTO case_drafts (employee_id, updated_at, draft_json)
                VALUES (?, ?, ?)
                ON CONFLICT(employee_id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    draft_json = excluded.draft_json
                """,
                (
                    employee_id,
                    draft.get("updated_at", ""),
                    _json_dumps_secure(draft),
                ),
            )
        connection.commit()


def save_finished_case(case_record):
    init_database()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO finished_cases (
                id, employee_id, employee_name, completed_at,
                summary, patient_json, protocol_text, status, retention_until
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_record["id"],
                case_record["employee_id"],
                case_record.get("employee_name", ""),
                case_record["completed_at"],
                case_record.get("summary", ""),
                _json_dumps_secure(case_record.get("patient", {})),
                _encrypt_text(case_record.get("protocol_text", "")),
                case_record.get("status", "active"),
                case_record.get("retention_until", ""),
            ),
        )
        connection.commit()


def list_finished_cases(employee_id=None, search="", include_deleted=False, limit=100):
    init_database()
    safe_limit = max(1, min(int(limit or 100), 1000))
    query = """
        SELECT id, employee_id, employee_name, completed_at, summary, protocol_text,
               status, anonymized_at, deleted_at, retention_until
        FROM finished_cases
    """
    params = []
    clauses = []

    if not include_deleted:
        clauses.append("status != 'deleted'")

    if employee_id:
        clauses.append("employee_id = ?")
        params.append(employee_id)

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY completed_at DESC LIMIT ?"
    params.append(safe_limit)

    with _connect() as connection:
        rows = connection.execute(query, params).fetchall()

    results = [
        {
            "id": row["id"],
            "employee_id": row["employee_id"],
            "employee_name": row["employee_name"],
            "completed_at": row["completed_at"],
            "summary": row["summary"],
            "protocol_text": _decrypt_text(row["protocol_text"]),
            "status": row["status"],
            "anonymized_at": row["anonymized_at"],
            "deleted_at": row["deleted_at"],
            "retention_until": row["retention_until"],
        }
        for row in rows
    ]
    if search:
        needle = search.lower()
        results = [
            item for item in results
            if needle in item["summary"].lower()
            or needle in item["protocol_text"].lower()
            or needle in item["employee_name"].lower()
        ]
    return results


def get_finished_case(case_id):
    init_database()
    with _connect() as connection:
        row = connection.execute("SELECT * FROM finished_cases WHERE id = ?", (case_id,)).fetchone()

    if not row:
        return None

    try:
        patient = _json_loads_secure(row["patient_json"], {})
    except Exception:
        patient = {}

    return {
        "id": row["id"],
        "employee_id": row["employee_id"],
        "employee_name": row["employee_name"],
        "completed_at": row["completed_at"],
        "summary": row["summary"],
        "patient": patient,
        "protocol_text": _decrypt_text(row["protocol_text"]),
        "status": row["status"],
        "anonymized_at": row["anonymized_at"],
        "deleted_at": row["deleted_at"],
        "retention_until": row["retention_until"],
    }


def anonymize_finished_case(case_id, timestamp):
    init_database()
    anonymized_patient = {
        "vitalwerte": {},
        "xabcde": {},
        "samplers": {},
        "opqrst": {},
        "einweisung": {},
        "amls": {},
        "massnahmen": {},
        "transport": {},
        "einsatz": {},
    }
    with _connect() as connection:
        connection.execute(
            """
            UPDATE finished_cases
            SET status = 'anonymized',
                summary = 'Anonymisierter Einsatz',
                patient_json = ?,
                protocol_text = 'Dieser Einsatz wurde datenschutzbedingt anonymisiert.',
                employee_name = '',
                anonymized_at = ?
            WHERE id = ? AND status != 'deleted'
            """,
            (_json_dumps_secure(anonymized_patient), timestamp, case_id),
        )
        connection.commit()


def delete_finished_case(case_id, timestamp):
    init_database()
    with _connect() as connection:
        connection.execute(
            """
            UPDATE finished_cases
            SET status = 'deleted',
                summary = 'Geloeschter Einsatz',
                patient_json = '{}',
                protocol_text = '',
                employee_name = '',
                deleted_at = ?
            WHERE id = ?
            """,
            (timestamp, case_id),
        )
        connection.commit()


def list_expired_finished_cases(today):
    init_database()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, employee_id, employee_name, completed_at, summary,
                   status, anonymized_at, deleted_at, retention_until
            FROM finished_cases
            WHERE status != 'deleted'
              AND retention_until != ''
              AND retention_until <= ?
            ORDER BY retention_until ASC, completed_at ASC
            """,
            (today,),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "employee_id": row["employee_id"],
            "employee_name": row["employee_name"],
            "completed_at": row["completed_at"],
            "summary": row["summary"],
            "status": row["status"],
            "anonymized_at": row["anonymized_at"],
            "deleted_at": row["deleted_at"],
            "retention_until": row["retention_until"],
        }
        for row in rows
    ]


def delete_expired_finished_cases(today, timestamp):
    expired = list_expired_finished_cases(today)
    for item in expired:
        delete_finished_case(item["id"], timestamp)
    return expired


def encrypt_existing_patient_data():
    init_database()
    changed = 0
    with _connect() as connection:
        draft_rows = connection.execute("SELECT employee_id, draft_json FROM case_drafts").fetchall()
        for row in draft_rows:
            if not str(row["draft_json"]).startswith(ENCRYPTED_PREFIX):
                connection.execute(
                    "UPDATE case_drafts SET draft_json = ? WHERE employee_id = ?",
                    (_encrypt_text(row["draft_json"]), row["employee_id"]),
                )
                changed += 1

        case_rows = connection.execute("SELECT id, patient_json, protocol_text FROM finished_cases").fetchall()
        for row in case_rows:
            updates = {}
            if not str(row["patient_json"]).startswith(ENCRYPTED_PREFIX):
                updates["patient_json"] = _encrypt_text(row["patient_json"])
            if not str(row["protocol_text"]).startswith(ENCRYPTED_PREFIX):
                updates["protocol_text"] = _encrypt_text(row["protocol_text"])
            if updates:
                connection.execute(
                    """
                    UPDATE finished_cases
                    SET patient_json = ?, protocol_text = ?
                    WHERE id = ?
                    """,
                    (
                        updates.get("patient_json", row["patient_json"]),
                        updates.get("protocol_text", row["protocol_text"]),
                        row["id"],
                    ),
                )
                changed += 1
        connection.commit()
    return changed


def get_app_setting(key, default=None):
    init_database()
    with _connect() as connection:
        row = connection.execute("SELECT value_json FROM app_settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value_json"])
    except json.JSONDecodeError:
        return default


def set_app_setting(key, value):
    init_database()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO app_settings (key, value_json)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json
            """,
            (key, json.dumps(value, ensure_ascii=False)),
        )
        connection.commit()


def write_audit_event(event):
    init_database()
    details = event.get("details", {})
    if not isinstance(details, dict):
        details = {"value": str(details)}

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO audit_log (
                timestamp, employee_id, employee_name, action,
                entity_type, entity_id, details_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["timestamp"],
                event.get("employee_id", ""),
                event.get("employee_name", ""),
                event["action"],
                event.get("entity_type", ""),
                event.get("entity_id", ""),
                json.dumps(details, ensure_ascii=False),
            ),
        )
        connection.commit()


def list_audit_events(limit=100):
    init_database()
    safe_limit = max(1, min(int(limit or 100), 500))
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT timestamp, employee_id, employee_name, action,
                   entity_type, entity_id, details_json
            FROM audit_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    events = []
    for row in rows:
        try:
            details = json.loads(row["details_json"])
        except json.JSONDecodeError:
            details = {}
        events.append({
            "timestamp": row["timestamp"],
            "employee_id": row["employee_id"],
            "employee_name": row["employee_name"],
            "action": row["action"],
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "details": details,
        })
    return events


def write_login_event(event):
    init_database()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO login_events (
                timestamp, employee_id, employee_name, device_id,
                device_name, user_agent, ip_address, source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.get("timestamp", ""),
                event.get("employee_id", ""),
                event.get("employee_name", ""),
                event.get("device_id", ""),
                event.get("device_name", ""),
                event.get("user_agent", ""),
                event.get("ip_address", ""),
                event.get("source", "login"),
            ),
        )
        connection.commit()


def list_login_events(limit=100):
    init_database()
    safe_limit = max(1, min(int(limit or 100), 500))
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT timestamp, employee_id, employee_name, device_id,
                   device_name, user_agent, ip_address, source
            FROM login_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    return [
        {
            "timestamp": row["timestamp"],
            "employee_id": row["employee_id"],
            "employee_name": row["employee_name"],
            "device_id": row["device_id"],
            "device_name": row["device_name"],
            "user_agent": row["user_agent"],
            "ip_address": row["ip_address"],
            "source": row["source"],
        }
        for row in rows
    ]


def migrate_json_files(employee_file="employees.json", draft_file="case_drafts.json"):
    init_database()

    with _connect() as connection:
        employee_count = connection.execute("SELECT COUNT(*) AS count FROM employees").fetchone()["count"]
        draft_count = connection.execute("SELECT COUNT(*) AS count FROM case_drafts").fetchone()["count"]

    if employee_count == 0 and os.path.exists(employee_file):
        try:
            with open(employee_file, "r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
            if isinstance(data, dict) and isinstance(data.get("employees"), list):
                save_employee_store(data)
        except Exception:
            pass

    if draft_count == 0 and os.path.exists(draft_file):
        try:
            with open(draft_file, "r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
            if isinstance(data, dict) and isinstance(data.get("drafts"), dict):
                save_case_draft_store(data)
        except Exception:
            pass
