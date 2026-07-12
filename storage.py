import json
import os
import sqlite3


DB_PATH = os.getenv("NANA_DB_PATH", "nana.db")


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
        connection.commit()


def _employee_from_row(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "role": row["role"],
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
                    id, name, role, active, password_hash, temp_password_hash,
                    must_change_password, created_at, password_changed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    role = excluded.role,
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
            drafts[row["employee_id"]] = json.loads(row["draft_json"])
        except json.JSONDecodeError:
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
                    json.dumps(draft, ensure_ascii=False),
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
                summary, patient_json, protocol_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_record["id"],
                case_record["employee_id"],
                case_record.get("employee_name", ""),
                case_record["completed_at"],
                case_record.get("summary", ""),
                json.dumps(case_record.get("patient", {}), ensure_ascii=False),
                case_record.get("protocol_text", ""),
            ),
        )
        connection.commit()


def list_finished_cases(employee_id=None, search=""):
    init_database()
    query = """
        SELECT id, employee_id, employee_name, completed_at, summary, protocol_text
        FROM finished_cases
    """
    params = []
    clauses = []

    if employee_id:
        clauses.append("employee_id = ?")
        params.append(employee_id)

    if search:
        clauses.append("(summary LIKE ? OR protocol_text LIKE ? OR employee_name LIKE ?)")
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY completed_at DESC LIMIT 100"

    with _connect() as connection:
        rows = connection.execute(query, params).fetchall()

    return [
        {
            "id": row["id"],
            "employee_id": row["employee_id"],
            "employee_name": row["employee_name"],
            "completed_at": row["completed_at"],
            "summary": row["summary"],
            "protocol_text": row["protocol_text"],
        }
        for row in rows
    ]


def get_finished_case(case_id):
    init_database()
    with _connect() as connection:
        row = connection.execute("SELECT * FROM finished_cases WHERE id = ?", (case_id,)).fetchone()

    if not row:
        return None

    try:
        patient = json.loads(row["patient_json"])
    except json.JSONDecodeError:
        patient = {}

    return {
        "id": row["id"],
        "employee_id": row["employee_id"],
        "employee_name": row["employee_name"],
        "completed_at": row["completed_at"],
        "summary": row["summary"],
        "patient": patient,
        "protocol_text": row["protocol_text"],
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
