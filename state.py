import sqlite3
from datetime import date, datetime
from config import DB_PATH


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS known_accounts (
                id TEXT PRIMARY KEY,
                first_seen DATE NOT NULL,
                notion_page_id TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS run_log (
                run_date DATE PRIMARY KEY,
                watchlist_size INTEGER,
                new_accounts_found INTEGER
            )
        """)


def init_votes_table():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                notion_id TEXT NOT NULL,
                voter_name TEXT NOT NULL,
                vote TEXT NOT NULL CHECK(vote IN ('up', 'down')),
                voted_at TEXT NOT NULL,
                PRIMARY KEY (notion_id, voter_name)
            )
        """)


def upsert_vote(notion_id: str, voter_name: str, vote: str):
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO votes (notion_id, voter_name, vote, voted_at) VALUES (?, ?, ?, ?)",
            (notion_id, voter_name, vote, datetime.utcnow().isoformat()),
        )


def get_votes_for_project(notion_id: str) -> dict:
    """Returns {voter_name: vote} for a single project."""
    with _conn() as con:
        rows = con.execute(
            "SELECT voter_name, vote FROM votes WHERE notion_id = ?", (notion_id,)
        ).fetchall()
    return {r[0]: r[1] for r in rows}


def get_all_votes() -> dict:
    """Returns {notion_id: {voter_name: vote}} for all projects."""
    with _conn() as con:
        rows = con.execute("SELECT notion_id, voter_name, vote FROM votes").fetchall()
    result: dict = {}
    for notion_id, voter_name, vote in rows:
        result.setdefault(notion_id, {})[voter_name] = vote
    return result


def get_known_ids() -> set[str]:
    with _conn() as con:
        rows = con.execute("SELECT id FROM known_accounts").fetchall()
    return {r[0] for r in rows}


def add_account(account_id: str, notion_page_id: str = None):
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO known_accounts (id, first_seen, notion_page_id) VALUES (?, ?, ?)",
            (account_id, date.today().isoformat(), notion_page_id),
        )


def update_notion_page_id(account_id: str, notion_page_id: str):
    with _conn() as con:
        con.execute(
            "UPDATE known_accounts SET notion_page_id = ? WHERE id = ?",
            (notion_page_id, account_id),
        )


def log_run(watchlist_size: int, new_accounts_found: int):
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO run_log (run_date, watchlist_size, new_accounts_found) VALUES (?, ?, ?)",
            (date.today().isoformat(), watchlist_size, new_accounts_found),
        )
