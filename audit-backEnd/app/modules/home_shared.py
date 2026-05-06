from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import HTTPException, UploadFile
from pydantic import BaseModel

try:
    from ..config.config import CLOUD_ROOT, RUNTIME_DATA_DIR, UPLOAD_DIR
    from .user_security import get_user_by_account_id
except ImportError:
    from config.config import CLOUD_ROOT, RUNTIME_DATA_DIR, UPLOAD_DIR
    from modules.user_security import get_user_by_account_id


DATA_DIR = RUNTIME_DATA_DIR
DB_PATH = DATA_DIR / "home.db"

DEFAULT_USER_ID = "default-user"
PENDING_STATUS = "未审计"
COMPLETE_STATUS = "完整"
BROKEN_STATUS = "损坏"


class FileItem(BaseModel):
    file_id: str
    file_name: str
    file_size: int
    upload_time: str
    keywords: List[str]
    audit_status: str


class DashboardResponse(BaseModel):
    user_file_count: int
    integrity_ratio: float
    keyword_count: int
    latest_audit_time: str | None
    files: List[FileItem]


class AuditRecord(BaseModel):
    record_id: str
    file_id: str
    file_name: str
    keyword: str
    audit_result: str
    audit_time: str


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    CLOUD_ROOT.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_home_tables() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_files (
                file_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                upload_time TEXT NOT NULL,
                keywords TEXT NOT NULL,
                audit_status TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_records (
                record_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                keyword TEXT NOT NULL,
                audit_result TEXT NOT NULL,
                audit_time TEXT NOT NULL
            )
            """
        )


def parse_keywords(raw_keywords: str) -> List[str]:
    keywords: List[str] = []
    normalized = raw_keywords.replace("，", ",").replace("；", ",").replace(";", ",")

    for item in normalized.split(","):
        keyword = item.strip().lower()
        if keyword and keyword not in keywords:
            keywords.append(keyword)

    return keywords


def row_to_file(row: sqlite3.Row) -> FileItem:
    return FileItem(
        file_id=row["file_id"],
        file_name=row["file_name"],
        file_size=row["file_size"],
        upload_time=row["upload_time"],
        keywords=json.loads(row["keywords"]),
        audit_status=row["audit_status"],
    )


def row_to_record(row: sqlite3.Row) -> AuditRecord:
    return AuditRecord(
        record_id=row["record_id"],
        file_id=row["file_id"],
        file_name=row["file_name"],
        keyword=row["keyword"],
        audit_result=row["audit_result"],
        audit_time=row["audit_time"],
    )


def list_files(user_id: str = DEFAULT_USER_ID) -> List[FileItem]:
    init_home_tables()

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

    return [row_to_file(row) for row in rows]


def calculate_integrity_ratio(files: List[FileItem]) -> float:
    if not files:
        return 100.0

    complete_or_pending = sum(1 for file in files if file.audit_status != BROKEN_STATUS)
    return round(complete_or_pending / len(files) * 100, 2)


def make_file_id(file_name: str, content: bytes, user_id: str = "") -> str:
    digest = hashlib.sha256()
    digest.update(user_id.encode("utf-8"))
    digest.update(b"::")
    digest.update(file_name.encode("utf-8"))
    digest.update(b"::")
    digest.update(content)
    return digest.hexdigest()


def get_user_cloud_files_dir(user_id: str) -> Path:
    user = get_user_by_account_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    cloud_folder = user["cloud_folder"]
    if not cloud_folder:
        raise HTTPException(status_code=400, detail="用户云端目录未初始化")

    files_dir = CLOUD_ROOT / cloud_folder
    files_dir.mkdir(parents=True, exist_ok=True)
    return files_dir


def cleanup_temp_file(path: Path) -> None:
    if path.exists():
        path.unlink()

    try:
        path.parent.rmdir()
    except OSError:
        pass


def prepare_keyword_forms(files: List[UploadFile], keywords: List[str]) -> List[str]:
    if len(keywords) == len(files):
        return keywords

    if len(keywords) == 1:
        return keywords * len(files)

    raise HTTPException(status_code=400, detail="关键词数量必须为 1 个或与文件数量一致")
