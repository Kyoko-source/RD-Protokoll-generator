import base64
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager

from cryptography.fernet import Fernet, InvalidToken


DB_PATH = os.getenv("NANA_DB_PATH", "nana.db")
ENCRYPTED_PREFIX = "nana-fernet:v1:"
SCHEMA_VERSION = 2


@contextmanager
def _connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def init_database():
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
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
        if "ruleset_version" not in existing_case_columns:
            connection.execute("ALTER TABLE finished_cases ADD COLUMN ruleset_version TEXT NOT NULL DEFAULT ''")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token TEXT PRIMARY KEY,
                employee_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                csrf_token TEXT NOT NULL DEFAULT ''
            )
            """
        )
        existing_session_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(auth_sessions)").fetchall()
        }
        if "csrf_token" not in existing_session_columns:
            connection.execute("ALTER TABLE auth_sessions ADD COLUMN csrf_token TEXT NOT NULL DEFAULT ''")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS password_change_tokens (
                token TEXT PRIMARY KEY,
                employee_id TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_failures (
                failure_key TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0,
                first_failed_at TEXT NOT NULL DEFAULT '',
                last_failed_at TEXT NOT NULL DEFAULT '',
                locked_until TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, applied_at)
            VALUES (?, datetime('now'))
            """,
            (SCHEMA_VERSION,),
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


def get_employee(employee_id, active_only=False):
    init_database()
    query = "SELECT * FROM employees WHERE id = ?"
    params = [employee_id]
    if active_only:
        query += " AND active = 1"
    with _connect() as connection:
        row = connection.execute(query, params).fetchone()
    return _employee_from_row(row) if row else None


def create_employee_record(employee):
    init_database()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO employees (
                id, name, role, qualification, active, password_hash, temp_password_hash,
                must_change_password, created_at, password_changed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def update_employee_record(employee_id, changes):
    init_database()
    allowed = {
        "name",
        "role",
        "qualification",
        "active",
        "password_hash",
        "temp_password_hash",
        "must_change_password",
        "created_at",
        "password_changed_at",
    }
    updates = {key: value for key, value in changes.items() if key in allowed}
    if not updates:
        return get_employee(employee_id)
    columns = []
    values = []
    for key, value in updates.items():
        columns.append(f"{key} = ?")
        if key in {"active", "must_change_password"}:
            values.append(1 if value else 0)
        else:
            values.append(value)
    values.append(employee_id)
    with _connect() as connection:
        connection.execute(
            f"UPDATE employees SET {', '.join(columns)} WHERE id = ?",
            values,
        )
        connection.commit()
    return get_employee(employee_id)


def delete_employee_record(employee_id):
    init_database()
    with _connect() as connection:
        connection.execute("DELETE FROM case_drafts WHERE employee_id = ?", (employee_id,))
        deleted = connection.execute("DELETE FROM employees WHERE id = ?", (employee_id,)).rowcount
        connection.commit()
    return deleted > 0


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
                summary, patient_json, protocol_text, status, retention_until, ruleset_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_record["id"],
                case_record["employee_id"],
                case_record.get("employee_name", ""),
                case_record["completed_at"],
                _encrypt_text(case_record.get("summary", "")),
                _json_dumps_secure(case_record.get("patient", {})),
                _encrypt_text(case_record.get("protocol_text", "")),
                case_record.get("status", "active"),
                case_record.get("retention_until", ""),
                case_record.get("ruleset_version", ""),
            ),
        )
        connection.commit()


def list_finished_cases(employee_id=None, search="", include_deleted=False, limit=100):
    init_database()
    safe_limit = max(1, min(int(limit or 100), 1000))
    query = """
        SELECT id, employee_id, employee_name, completed_at, summary, protocol_text,
               status, anonymized_at, deleted_at, retention_until, ruleset_version
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
            "summary": _decrypt_text(row["summary"]),
            "protocol_text": _decrypt_text(row["protocol_text"]),
            "status": row["status"],
            "anonymized_at": row["anonymized_at"],
            "deleted_at": row["deleted_at"],
            "retention_until": row["retention_until"],
            "ruleset_version": row["ruleset_version"],
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
        "summary": _decrypt_text(row["summary"]),
        "patient": patient,
        "protocol_text": _decrypt_text(row["protocol_text"]),
        "status": row["status"],
        "anonymized_at": row["anonymized_at"],
        "deleted_at": row["deleted_at"],
        "retention_until": row["retention_until"],
        "ruleset_version": row["ruleset_version"],
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
                summary = ?,
                patient_json = ?,
                protocol_text = ?,
                employee_name = '',
                anonymized_at = ?
            WHERE id = ? AND status != 'deleted'
            """,
            (
                _encrypt_text("Anonymisierter Einsatz"),
                _json_dumps_secure(anonymized_patient),
                _encrypt_text("Dieser Einsatz wurde datenschutzbedingt anonymisiert."),
                timestamp,
                case_id,
            ),
        )
        connection.commit()


def delete_finished_case(case_id, timestamp):
    init_database()
    with _connect() as connection:
        connection.execute(
            """
            UPDATE finished_cases
            SET status = 'deleted',
                summary = ?,
                patient_json = ?,
                protocol_text = ?,
                employee_name = '',
                deleted_at = ?
            WHERE id = ?
            """,
            (_encrypt_text("Geloeschter Einsatz"), _json_dumps_secure({}), _encrypt_text(""), timestamp, case_id),
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
            "summary": _decrypt_text(row["summary"]),
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

        case_rows = connection.execute("SELECT id, summary, patient_json, protocol_text FROM finished_cases").fetchall()
        for row in case_rows:
            updates = {}
            if not str(row["summary"]).startswith(ENCRYPTED_PREFIX):
                updates["summary"] = _encrypt_text(row["summary"])
            if not str(row["patient_json"]).startswith(ENCRYPTED_PREFIX):
                updates["patient_json"] = _encrypt_text(row["patient_json"])
            if not str(row["protocol_text"]).startswith(ENCRYPTED_PREFIX):
                updates["protocol_text"] = _encrypt_text(row["protocol_text"])
            if updates:
                connection.execute(
                    """
                    UPDATE finished_cases
                    SET summary = ?, patient_json = ?, protocol_text = ?
                    WHERE id = ?
                    """,
                    (
                        updates.get("summary", row["summary"]),
                        updates.get("patient_json", row["patient_json"]),
                        updates.get("protocol_text", row["protocol_text"]),
                        row["id"],
                    ),
                )
                changed += 1

        audit_rows = connection.execute(
            """
            SELECT id, timestamp, employee_id, employee_name, action,
                   entity_type, entity_id, details_json
            FROM audit_log
            """
        ).fetchall()
        for row in audit_rows:
            updates = {}
            for column in ("timestamp", "employee_id", "employee_name", "action", "entity_type", "entity_id", "details_json"):
                if not str(row[column]).startswith(ENCRYPTED_PREFIX):
                    updates[column] = _encrypt_text(row[column])
            if updates:
                connection.execute(
                    """
                    UPDATE audit_log
                    SET timestamp = ?,
                        employee_id = ?,
                        employee_name = ?,
                        action = ?,
                        entity_type = ?,
                        entity_id = ?,
                        details_json = ?
                    WHERE id = ?
                    """,
                    (
                        updates.get("timestamp", row["timestamp"]),
                        updates.get("employee_id", row["employee_id"]),
                        updates.get("employee_name", row["employee_name"]),
                        updates.get("action", row["action"]),
                        updates.get("entity_type", row["entity_type"]),
                        updates.get("entity_id", row["entity_id"]),
                        updates.get("details_json", row["details_json"]),
                        row["id"],
                    ),
                )
                changed += 1

        login_rows = connection.execute(
            """
            SELECT id, timestamp, employee_id, employee_name, device_id,
                   device_name, user_agent, ip_address, source
            FROM login_events
            """
        ).fetchall()
        for row in login_rows:
            updates = {}
            for column in ("timestamp", "employee_id", "employee_name", "device_id", "device_name", "user_agent", "ip_address", "source"):
                if not str(row[column]).startswith(ENCRYPTED_PREFIX):
                    updates[column] = _encrypt_text(row[column])
            if updates:
                connection.execute(
                    """
                    UPDATE login_events
                    SET timestamp = ?,
                        employee_id = ?,
                        employee_name = ?,
                        device_id = ?,
                        device_name = ?,
                        user_agent = ?,
                        ip_address = ?,
                        source = ?
                    WHERE id = ?
                    """,
                    (
                        updates.get("timestamp", row["timestamp"]),
                        updates.get("employee_id", row["employee_id"]),
                        updates.get("employee_name", row["employee_name"]),
                        updates.get("device_id", row["device_id"]),
                        updates.get("device_name", row["device_name"]),
                        updates.get("user_agent", row["user_agent"]),
                        updates.get("ip_address", row["ip_address"]),
                        updates.get("source", row["source"]),
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


def database_health_status():
    init_database()
    with _connect() as connection:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        migration = connection.execute(
            "SELECT MAX(version) AS version FROM schema_migrations"
        ).fetchone()
        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
    expected_tables = {
        "employees",
        "case_drafts",
        "finished_cases",
        "audit_log",
        "login_events",
        "app_settings",
        "schema_migrations",
        "auth_sessions",
        "password_change_tokens",
        "auth_failures",
    }
    missing_tables = sorted(expected_tables - tables)
    return {
        "ok": quick_check == "ok" and not missing_tables,
        "quick_check": quick_check,
        "schema_version": migration["version"] if migration else None,
        "missing_tables": missing_tables,
    }


def _stored_datetime(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value or "")


def save_auth_session(token, employee_id, expires_at, csrf_token=""):
    init_database()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO auth_sessions (token, employee_id, expires_at, csrf_token)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET
                employee_id = excluded.employee_id,
                expires_at = excluded.expires_at,
                csrf_token = COALESCE(NULLIF(excluded.csrf_token, ''), auth_sessions.csrf_token)
            """,
            (token, employee_id, _stored_datetime(expires_at), csrf_token),
        )
        connection.commit()


def get_auth_session(token):
    init_database()
    with _connect() as connection:
        row = connection.execute(
            "SELECT token, employee_id, expires_at, csrf_token FROM auth_sessions WHERE token = ?",
            (token,),
        ).fetchone()
    if not row:
        return None
    return {
        "token": row["token"],
        "employee_id": row["employee_id"],
        "expires_at": row["expires_at"],
        "csrf_token": row["csrf_token"],
    }


def delete_auth_session(token):
    init_database()
    with _connect() as connection:
        connection.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        connection.commit()


def save_password_change_token(token, employee_id, expires_at):
    init_database()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO password_change_tokens (token, employee_id, expires_at)
            VALUES (?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET
                employee_id = excluded.employee_id,
                expires_at = excluded.expires_at
            """,
            (token, employee_id, _stored_datetime(expires_at)),
        )
        connection.commit()


def get_password_change_token(token):
    init_database()
    with _connect() as connection:
        row = connection.execute(
            "SELECT token, employee_id, expires_at FROM password_change_tokens WHERE token = ?",
            (token,),
        ).fetchone()
    if not row:
        return None
    return {"token": row["token"], "employee_id": row["employee_id"], "expires_at": row["expires_at"]}


def delete_password_change_token(token):
    init_database()
    with _connect() as connection:
        connection.execute("DELETE FROM password_change_tokens WHERE token = ?", (token,))
        connection.commit()


def get_auth_failure(failure_key):
    init_database()
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT failure_key, count, first_failed_at, last_failed_at, locked_until
            FROM auth_failures
            WHERE failure_key = ?
            """,
            (failure_key,),
        ).fetchone()
    if not row:
        return None
    return {
        "failure_key": row["failure_key"],
        "count": row["count"],
        "first_failed_at": row["first_failed_at"],
        "last_failed_at": row["last_failed_at"],
        "locked_until": row["locked_until"],
    }


def save_auth_failure(failure_key, failure):
    init_database()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO auth_failures (
                failure_key, count, first_failed_at, last_failed_at, locked_until
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(failure_key) DO UPDATE SET
                count = excluded.count,
                first_failed_at = excluded.first_failed_at,
                last_failed_at = excluded.last_failed_at,
                locked_until = excluded.locked_until
            """,
            (
                failure_key,
                int(failure.get("count", 0)),
                failure.get("first_failed_at", ""),
                failure.get("last_failed_at", ""),
                _stored_datetime(failure.get("locked_until", "")),
            ),
        )
        connection.commit()


def delete_auth_failure(failure_key):
    init_database()
    with _connect() as connection:
        connection.execute("DELETE FROM auth_failures WHERE failure_key = ?", (failure_key,))
        connection.commit()


def purge_expired_auth_state(now_iso):
    init_database()
    with _connect() as connection:
        session_deleted = connection.execute(
            "DELETE FROM auth_sessions WHERE expires_at < ?",
            (now_iso,),
        ).rowcount
        token_deleted = connection.execute(
            "DELETE FROM password_change_tokens WHERE expires_at < ?",
            (now_iso,),
        ).rowcount
        failure_deleted = connection.execute(
            "DELETE FROM auth_failures WHERE locked_until != '' AND locked_until < ?",
            (now_iso,),
        ).rowcount
        connection.commit()
    return {
        "auth_sessions": max(0, session_deleted),
        "password_change_tokens": max(0, token_deleted),
        "auth_failures": max(0, failure_deleted),
    }


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
                _encrypt_text(event["timestamp"]),
                _encrypt_text(event.get("employee_id", "")),
                _encrypt_text(event.get("employee_name", "")),
                _encrypt_text(event["action"]),
                _encrypt_text(event.get("entity_type", "")),
                _encrypt_text(event.get("entity_id", "")),
                _encrypt_text(json.dumps(details, ensure_ascii=False)),
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
        details_json = _decrypt_text(row["details_json"])
        try:
            details = json.loads(details_json)
        except json.JSONDecodeError:
            details = {}
        events.append({
            "timestamp": _decrypt_text(row["timestamp"]),
            "employee_id": _decrypt_text(row["employee_id"]),
            "employee_name": _decrypt_text(row["employee_name"]),
            "action": _decrypt_text(row["action"]),
            "entity_type": _decrypt_text(row["entity_type"]),
            "entity_id": _decrypt_text(row["entity_id"]),
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
                _encrypt_text(event.get("timestamp", "")),
                _encrypt_text(event.get("employee_id", "")),
                _encrypt_text(event.get("employee_name", "")),
                _encrypt_text(event.get("device_id", "")),
                _encrypt_text(event.get("device_name", "")),
                _encrypt_text(event.get("user_agent", "")),
                _encrypt_text(event.get("ip_address", "")),
                _encrypt_text(event.get("source", "login")),
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
            "timestamp": _decrypt_text(row["timestamp"]),
            "employee_id": _decrypt_text(row["employee_id"]),
            "employee_name": _decrypt_text(row["employee_name"]),
            "device_id": _decrypt_text(row["device_id"]),
            "device_name": _decrypt_text(row["device_name"]),
            "user_agent": _decrypt_text(row["user_agent"]),
            "ip_address": _decrypt_text(row["ip_address"]),
            "source": _decrypt_text(row["source"]),
        }
        for row in rows
    ]


def delete_security_events_before(cutoff_timestamp):
    init_database()
    cutoff = str(cutoff_timestamp or "").strip()
    if not cutoff:
        return {"audit_log": 0, "login_events": 0}
    with _connect() as connection:
        audit_ids = [
            row["id"]
            for row in connection.execute("SELECT id, timestamp FROM audit_log").fetchall()
            if (timestamp := _decrypt_text(row["timestamp"])) and timestamp < cutoff
        ]
        login_ids = [
            row["id"]
            for row in connection.execute("SELECT id, timestamp FROM login_events").fetchall()
            if (timestamp := _decrypt_text(row["timestamp"])) and timestamp < cutoff
        ]

        audit_deleted = 0
        login_deleted = 0
        if audit_ids:
            placeholders = ",".join("?" for _ in audit_ids)
            audit_deleted = connection.execute(
                f"DELETE FROM audit_log WHERE id IN ({placeholders})",
                audit_ids,
            ).rowcount
        if login_ids:
            placeholders = ",".join("?" for _ in login_ids)
            login_deleted = connection.execute(
                f"DELETE FROM login_events WHERE id IN ({placeholders})",
                login_ids,
            ).rowcount
        connection.commit()
    return {
        "audit_log": max(0, audit_deleted),
        "login_events": max(0, login_deleted),
    }


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
