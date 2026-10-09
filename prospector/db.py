from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import db_path, require_private_directory


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_migration (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workspace_settings (
 id INTEGER PRIMARY KEY CHECK(id=1), global_monthly_cap_micro INTEGER NOT NULL DEFAULT 30000000,
 timezone TEXT NOT NULL DEFAULT 'America/Fortaleza'
);
INSERT OR IGNORE INTO workspace_settings(id) VALUES(1);
CREATE TABLE IF NOT EXISTS credential_settings (
 id INTEGER PRIMARY KEY CHECK(id=1), status TEXT NOT NULL DEFAULT 'not_configured',
 org TEXT, validated_at TEXT, error TEXT
);
INSERT OR IGNORE INTO credential_settings(id) VALUES(1);
CREATE TABLE IF NOT EXISTS admin (
 id INTEGER PRIMARY KEY CHECK(id=1), password_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS session (
 token_hash TEXT PRIMARY KEY, csrf_token TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempt (
 id INTEGER PRIMARY KEY AUTOINCREMENT, remote_ip TEXT NOT NULL, attempted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS login_attempt_ip_idx ON login_attempt(remote_ip,attempted_at);
CREATE TABLE IF NOT EXISTS campaign (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', service TEXT NOT NULL DEFAULT '',
 niche TEXT NOT NULL, cities_json TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'google_maps',
 sources_json TEXT NOT NULL DEFAULT '["google_maps"]',
 target_leads INTEGER NOT NULL DEFAULT 30 CHECK(target_leads BETWEEN 1 AND 1000),
 run_cap_micro INTEGER NOT NULL DEFAULT 1000000 CHECK(run_cap_micro>0),
 monthly_cap_micro INTEGER NOT NULL DEFAULT 30000000 CHECK(monthly_cap_micro>0),
 timezone TEXT NOT NULL DEFAULT 'America/Fortaleza',
 state TEXT NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','active','paused','archived')),
 version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS execution (
 id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaign(id), campaign_snapshot_json TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('queued','running','succeeded','partial','failed','cancelled')),
 financial_state TEXT NOT NULL DEFAULT 'confirmed' CHECK(financial_state IN ('confirmed','pending','unavailable')),
 new_global INTEGER NOT NULL DEFAULT 0, new_campaign INTEGER NOT NULL DEFAULT 0,
 updated INTEGER NOT NULL DEFAULT 0, duplicate INTEGER NOT NULL DEFAULT 0,
 cost_micro INTEGER NOT NULL DEFAULT 0, error TEXT, created_at TEXT NOT NULL,
 started_at TEXT, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS job_queue (
 execution_id TEXT PRIMARY KEY REFERENCES execution(id), state TEXT NOT NULL DEFAULT 'queued',
 claimed_at TEXT, attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tool_call (
 id TEXT PRIMARY KEY, execution_id TEXT NOT NULL REFERENCES execution(id), endpoint TEXT NOT NULL,
 idempotency_key TEXT NOT NULL UNIQUE, treg_call_id TEXT, city TEXT NOT NULL,
 reserved_micro INTEGER NOT NULL, cost_micro INTEGER, financial_state TEXT NOT NULL DEFAULT 'pending',
 created_at TEXT NOT NULL, settled_at TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS budget_reservation (
 tool_call_id TEXT PRIMARY KEY REFERENCES tool_call(id), campaign_id TEXT NOT NULL REFERENCES campaign(id),
 campaign_period TEXT NOT NULL, global_period TEXT NOT NULL, amount_micro INTEGER NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('held','settled')), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lead (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, niche TEXT, city TEXT, uf TEXT, country TEXT NOT NULL DEFAULT 'BR',
 domain TEXT, website TEXT, phone TEXT, email TEXT, status TEXT NOT NULL DEFAULT 'Novo',
 first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lead_source (
 lead_id TEXT NOT NULL REFERENCES lead(id), source TEXT NOT NULL, external_id TEXT NOT NULL,
 evidence_url TEXT, collected_at TEXT NOT NULL, PRIMARY KEY(source,external_id)
);
CREATE TABLE IF NOT EXISTS lead_site_audit (
 lead_id TEXT PRIMARY KEY REFERENCES lead(id), website TEXT NOT NULL, checked_at TEXT NOT NULL,
 availability TEXT NOT NULL, page_type TEXT NOT NULL, provider TEXT,
 seo_score INTEGER, issues_json TEXT NOT NULL, http_status INTEGER, final_url TEXT
);
CREATE TABLE IF NOT EXISTS lead_campaign (
 lead_id TEXT NOT NULL REFERENCES lead(id), campaign_id TEXT NOT NULL REFERENCES campaign(id),
 first_execution_id TEXT NOT NULL REFERENCES execution(id), first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', PRIMARY KEY(lead_id,campaign_id)
);
CREATE TABLE IF NOT EXISTS schedule_binding (
 campaign_id TEXT PRIMARY KEY REFERENCES campaign(id), frequency TEXT NOT NULL,
 days_json TEXT NOT NULL DEFAULT '[]', times_json TEXT NOT NULL DEFAULT '[]',
 timezone TEXT NOT NULL, once_at TEXT, state TEXT NOT NULL DEFAULT 'paused',
 hermes_job_id TEXT, last_occurrence_key TEXT, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS search_cursor (
 campaign_id TEXT NOT NULL REFERENCES campaign(id), source TEXT NOT NULL,
 city TEXT NOT NULL, uf TEXT NOT NULL, query TEXT NOT NULL,
 last_collected_at TEXT NOT NULL, expires_at TEXT NOT NULL,
 PRIMARY KEY(campaign_id,source,city,uf,query)
);
CREATE TABLE IF NOT EXISTS legacy_record (
 source_path TEXT NOT NULL, row_index INTEGER NOT NULL, lead_id TEXT NOT NULL REFERENCES lead(id),
 raw_json TEXT NOT NULL, cost_micro INTEGER, imported_at TEXT NOT NULL,
 PRIMARY KEY(source_path,row_index)
);
CREATE INDEX IF NOT EXISTS lead_name_idx ON lead(name);
CREATE INDEX IF NOT EXISTS lead_city_idx ON lead(city,uf);
CREATE INDEX IF NOT EXISTS lead_domain_idx ON lead(domain);
CREATE INDEX IF NOT EXISTS lead_phone_idx ON lead(phone);
CREATE INDEX IF NOT EXISTS execution_campaign_idx ON execution(campaign_id,created_at);
CREATE INDEX IF NOT EXISTS call_execution_idx ON tool_call(execution_id);
CREATE INDEX IF NOT EXISTS association_campaign_idx ON lead_campaign(campaign_id,last_seen_at);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: Path | None = None) -> sqlite3.Connection:
    if path is None:
        require_private_directory()
        path = db_path()
    else:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.parent.chmod(0o700)
    # O FastAPI pode abrir/usar/fechar uma dependência síncrona em threads distintas.
    # Cada requisição recebe sua própria conexão; o worker usa outra conexão própria.
    conn = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        version = conn.execute("SELECT COALESCE(MAX(version),0) FROM schema_migration").fetchone()[0]
        versions = {row[0] for row in conn.execute("SELECT version FROM schema_migration")}
    except sqlite3.OperationalError:
        version = 0
        versions = set()
    if version < 5:
        conn.executescript(SCHEMA)
        conn.execute("INSERT OR IGNORE INTO schema_migration(version,applied_at) VALUES(1,?)", (now(),))
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(workspace_settings)")}
        if "treg_org" not in columns:
            conn.execute("ALTER TABLE workspace_settings ADD COLUMN treg_org TEXT")
        conn.execute("INSERT OR IGNORE INTO schema_migration(version,applied_at) VALUES(2,?)", (now(),))
        conn.execute("INSERT OR IGNORE INTO schema_migration(version,applied_at) VALUES(3,?)", (now(),))
        conn.execute("INSERT OR IGNORE INTO schema_migration(version,applied_at) VALUES(4,?)", (now(),))
        conn.execute("INSERT OR IGNORE INTO schema_migration(version,applied_at) VALUES(5,?)", (now(),))
    if 6 not in versions:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(campaign)")}
        if "sources_json" not in columns:
            conn.execute("ALTER TABLE campaign ADD COLUMN sources_json TEXT NOT NULL DEFAULT '[\"google_maps\"]'")
            conn.execute("UPDATE campaign SET sources_json=json_array(source)")
        conn.execute("INSERT OR IGNORE INTO schema_migration(version,applied_at) VALUES(6,?)", (now(),))
    if 7 not in versions:
        conn.execute("""CREATE TABLE IF NOT EXISTS lead_site_audit (
            lead_id TEXT PRIMARY KEY REFERENCES lead(id), website TEXT NOT NULL, checked_at TEXT NOT NULL,
            availability TEXT NOT NULL, page_type TEXT NOT NULL, provider TEXT,
            seo_score INTEGER, issues_json TEXT NOT NULL, http_status INTEGER, final_url TEXT)""")
        conn.execute("INSERT OR IGNORE INTO schema_migration(version,applied_at) VALUES(7,?)", (now(),))
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()
