from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List

from fastapi import HTTPException, UploadFile
from pydantic import BaseModel

try:
    from ..config.config import AUDIT_DB_PATH, CLOUD_ROOT
    from ..config.database import ensure_column
    from .user_security import get_user_by_account_id
except ImportError:
    from config.config import AUDIT_DB_PATH, CLOUD_ROOT
    from config.database import ensure_column
    from modules.user_security import get_user_by_account_id


DB_PATH = AUDIT_DB_PATH

DEFAULT_USER_ID = "default-user"
PENDING_STATUS = "pending"
COMPLETE_STATUS = "complete"
BROKEN_STATUS = "broken"
FILE_MISSING_STATUS = "missing"

class FileItem(BaseModel):
    file_id: str
    file_name: str
    file_size: int
    upload_time: str
    keywords: List[str]
    audit_status: str
    last_audit_time: str | None = None


class DashboardResponse(BaseModel):
    user_file_count: int
    integrity_ratio: float
    keyword_count: int
    latest_audit_time: str | None
    files: List[FileItem]


class AuditRecordFile(BaseModel):
    file_id: str
    file_name: str
    audit_status: str


class AuditRecord(BaseModel):
    record_id: str
    keyword: str
    challenge_block_count: int
    included_files: List[AuditRecordFile]
    audit_result: str
    audit_time: str


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLOUD_ROOT.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _audit_files_has_composite_primary_key(connection: sqlite3.Connection) -> bool:
    columns = connection.execute("PRAGMA table_info(audit_files)").fetchall()
    primary_keys = {
        column["name"]: column["pk"]
        for column in columns
        if column["pk"]
    }
    return primary_keys == {"user_id": 1, "file_id": 2}


def _migrate_audit_files_primary_key(connection: sqlite3.Connection) -> None:
    if _audit_files_has_composite_primary_key(connection):
        return

    connection.execute("DROP TABLE audit_files")


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        column["name"]
        for column in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def _create_audit_records_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_records (
            record_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            keyword TEXT NOT NULL,
            challenge_block_count INTEGER NOT NULL,
            included_files TEXT NOT NULL,
            audit_result TEXT NOT NULL,
            audit_time TEXT NOT NULL
        )
        """
    )


def _create_audit_files_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_files (
            file_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            upload_time TEXT NOT NULL,
            keywords TEXT NOT NULL,
            audit_status TEXT NOT NULL,
            last_audit_time TEXT,
            PRIMARY KEY (user_id, file_id)
        )
        """
    )


def _migrate_audit_records_table(connection: sqlite3.Connection) -> None:
    """
    Old audit_records rows are not kept. If the table shape is not the current
    one, drop it and rebuild a clean table.
    """

    required_columns = {
        "record_id",
        "user_id",
        "keyword",
        "challenge_block_count",
        "included_files",
        "audit_result",
        "audit_time",
    }
    if not _table_exists(connection, "audit_records"):
        return

    columns = _table_columns(connection, "audit_records")
    if required_columns.issubset(columns):
        return

    connection.execute("DROP TABLE audit_records")


def init_audit_table() -> None:
    with connect() as connection:
        _create_audit_files_table(connection)
        ensure_column(connection, "audit_files", "last_audit_time", "TEXT")
        _migrate_audit_files_primary_key(connection)
        _create_audit_files_table(connection)
        _migrate_audit_records_table(connection)
        _create_audit_records_table(connection)


def parse_keywords(raw_keywords: str) -> List[str]:
    keywords: List[str] = []
    normalized = raw_keywords.replace("，", ",").replace("；", ";").replace(";", ",")

    for item in normalized.split(","):
        keyword = item.strip().lower()
        if keyword and keyword not in keywords:
            keywords.append(keyword)

    return keywords


def row_to_file(row: sqlite3.Row, audit_status: str | None = None) -> FileItem:
    status = audit_status or row["audit_status"]
    return FileItem(
        file_id=row["file_id"],
        file_name=row["file_name"],
        file_size=row["file_size"],
        upload_time=row["upload_time"],
        keywords=json.loads(row["keywords"]),
        audit_status=status,
        last_audit_time=row["last_audit_time"],
    )


def row_to_record(row: sqlite3.Row) -> AuditRecord:
    included_files = [
        AuditRecordFile(**item)
        for item in json.loads(row["included_files"])
    ]
    return AuditRecord(
        record_id=row["record_id"],
        keyword=row["keyword"],
        challenge_block_count=row["challenge_block_count"],
        included_files=included_files,
        audit_result=row["audit_result"],
        audit_time=row["audit_time"],
    )


def list_files(user_id: str = DEFAULT_USER_ID) -> List[FileItem]:
    init_audit_table()

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM audit_files
            WHERE user_id = ?
            ORDER BY upload_time DESC
            """,
            (user_id,),
        ).fetchall()

    files: List[FileItem] = []
    for row in rows:
        audit_status = None
        if not Path(row["storage_path"]).exists():
            audit_status = FILE_MISSING_STATUS
        files.append(row_to_file(row, audit_status=audit_status))

    return files


def calculate_integrity_ratio(files: List[FileItem]) -> float:
    if not files:
        return 100.0

    incomplete_statuses = {BROKEN_STATUS, FILE_MISSING_STATUS}
    complete_or_pending = sum(1 for file in files if file.audit_status not in incomplete_statuses)
    return round(complete_or_pending / len(files) * 100, 2)


def make_file_id(file_name: str, content: bytes, user_id: str = "") -> str:
    digest = hashlib.sha256()
    digest.update(file_name.encode("utf-8"))
    return digest.hexdigest()


def get_user_cloud_files_dir(user_id: str) -> Path:
    user = get_user_by_account_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    cloud_folder = user["cloud_folder"]
    if not cloud_folder:
        raise HTTPException(status_code=400, detail="cloud_folder_not_initialized")

    files_dir = CLOUD_ROOT / cloud_folder
    files_dir.mkdir(parents=True, exist_ok=True)
    return files_dir


def prepare_keyword_forms(files: List[UploadFile], keywords: List[str]) -> List[str]:
    if len(keywords) == len(files):
        return keywords

    if len(keywords) == 1:
        return keywords * len(files)

    detail = "keyword_count_must_be_one_or_match_file_count"
    raise HTTPException(status_code=400, detail=detail)
