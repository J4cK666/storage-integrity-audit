import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from .config import CLOUD_ROOT, SQLITE_ROOT, USER_DB_PATH


def ensure_storage_paths() -> None:
    SQLITE_ROOT.mkdir(parents=True, exist_ok=True)
    CLOUD_ROOT.mkdir(parents=True, exist_ok=True)


def get_user_db_connection() -> sqlite3.Connection:
    ensure_storage_paths()
    connection = sqlite3.connect(USER_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def ensure_column(connection: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    if any(column["name"] == column_name for column in columns):
        return

    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def init_user_tables() -> None:
    with get_user_db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                account_id TEXT NOT NULL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK (length(account_id) = 10 AND account_id GLOB '[0-9]*')
            )
            """
        )
        ensure_column(connection, "users", "cloud_folder", "TEXT DEFAULT ''")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_crypto_keys (
                account_id TEXT NOT NULL PRIMARY KEY,
                public_key TEXT NOT NULL,
                private_key TEXT NOT NULL,
                g TEXT NOT NULL,
                u TEXT NOT NULL,
                k0 BLOB NOT NULL,
                k1 BLOB NOT NULL,
                k2 BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_user_crypto_keys_user
                    FOREIGN KEY (account_id) REFERENCES users(account_id)
                    ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_id_counters (
                date_key TEXT PRIMARY KEY,
                last_count INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_users_updated_at
            AFTER UPDATE ON users
            FOR EACH ROW
            BEGIN
                UPDATE users
                SET updated_at = CURRENT_TIMESTAMP
                WHERE account_id = OLD.account_id;
            END
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_user_crypto_keys_updated_at
            AFTER UPDATE ON user_crypto_keys
            FOR EACH ROW
            BEGIN
                UPDATE user_crypto_keys
                SET updated_at = CURRENT_TIMESTAMP
                WHERE account_id = OLD.account_id;
            END
            """
        )


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or USER_DB_PATH)
        self.connection: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        ensure_storage_paths()
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def disconnect(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None

    def execute_query(self, query: str, params: Optional[Iterable] = None):
        if not self.connection:
            self.connect()

        cursor = self.connection.cursor()
        cursor.execute(query, tuple(params or ()))
        self.connection.commit()
        return cursor.fetchall()
