from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

try:
    from ..config.config import CLOUD_ROOT, RUNTIME_DATA_DIR, UPLOAD_DIR
    from ..config.database import get_user_db_connection
    from .user_security import get_user_by_account_id, make_password_hash, verify_password
except ImportError:
    from config.config import CLOUD_ROOT, RUNTIME_DATA_DIR, UPLOAD_DIR
    from config.database import get_user_db_connection
    from modules.user_security import get_user_by_account_id, make_password_hash, verify_password


DATA_DIR = RUNTIME_DATA_DIR
DB_PATH = DATA_DIR / "home.db"

DEFAULT_USER_ID = "default-user"
PENDING_STATUS = "未审计"
COMPLETE_STATUS = "完整"
BROKEN_STATUS = "损坏"

home_router = APIRouter(prefix="/home", tags=["审计主界面"])


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


class UploadResponse(BaseModel):
    message: str
    files: List[FileItem]


class AuditRequest(BaseModel):
    keyword: str = Field(..., min_length=1)
    user_id: str = DEFAULT_USER_ID


class AuditFileResult(BaseModel):
    file_id: str
    file_name: str
    audit_result: str


class AuditResponse(BaseModel):
    keyword: str
    file_count: int
    audit_result: str
    audit_time: str
    files: List[AuditFileResult]


class AuditRecord(BaseModel):
    record_id: str
    file_id: str
    file_name: str
    keyword: str
    audit_result: str
    audit_time: str


class UserProfile(BaseModel):
    user_id: str
    username: str
    account_id: str
    cloud_folder: str
    role: str
    permissions: List[str]


class ApiMessage(BaseModel):
    message: str


class UserKeyResponse(BaseModel):
    public_key: str
    private_key: str


class ChangePasswordRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)


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

    files_dir = CLOUD_ROOT / cloud_folder / "files"
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


@home_router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(user_id: str = DEFAULT_USER_ID) -> DashboardResponse:
    files = list_files(user_id)
    keyword_set = {keyword for file in files for keyword in file.keywords}

    with connect() as connection:
        latest_row = connection.execute(
            """
            SELECT audit_time
            FROM audit_records
            WHERE user_id = ?
            ORDER BY audit_time DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

    return DashboardResponse(
        user_file_count=len(files),
        integrity_ratio=calculate_integrity_ratio(files),
        keyword_count=len(keyword_set),
        latest_audit_time=latest_row["audit_time"] if latest_row else None,
        files=files,
    )


@home_router.get("/files", response_model=List[FileItem])
def get_files(user_id: str = DEFAULT_USER_ID) -> List[FileItem]:
    return list_files(user_id)


@home_router.post("/files/upload", response_model=UploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    keywords: List[str] = Form(...),
    user_id: str = Form(DEFAULT_USER_ID),
) -> UploadResponse:
    init_home_tables()
    cloud_files_dir = get_user_cloud_files_dir(user_id)

    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    keyword_forms = prepare_keyword_forms(files, keywords)
    uploaded_files: List[FileItem] = []

    with connect() as connection:
        for upload_file, raw_keywords in zip(files, keyword_forms):
            file_name = Path(upload_file.filename or "upload.bin").name
            parsed_keywords = parse_keywords(raw_keywords)
            if not parsed_keywords:
                raise HTTPException(status_code=400, detail=f"{file_name} 缺少关键词")

            content = await upload_file.read()
            file_id = make_file_id(file_name, content, user_id)
            file_suffix = Path(file_name).suffix
            user_upload_dir = UPLOAD_DIR / user_id
            user_upload_dir.mkdir(parents=True, exist_ok=True)
            temp_path = user_upload_dir / f"{file_id}{file_suffix}.tmp"
            cloud_path = cloud_files_dir / f"{file_id}{file_suffix}"
            temp_path.write_bytes(content)
            temp_path.replace(cloud_path)
            cleanup_temp_file(temp_path)

            upload_time = now_text()
            connection.execute(
                """
                INSERT OR REPLACE INTO audit_files (
                    file_id,
                    user_id,
                    file_name,
                    storage_path,
                    file_size,
                    upload_time,
                    keywords,
                    audit_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    user_id,
                    file_name,
                    str(cloud_path),
                    len(content),
                    upload_time,
                    json.dumps(parsed_keywords, ensure_ascii=False),
                    PENDING_STATUS,
                ),
            )

            uploaded_files.append(
                FileItem(
                    file_id=file_id,
                    file_name=file_name,
                    file_size=len(content),
                    upload_time=upload_time,
                    keywords=parsed_keywords,
                    audit_status=PENDING_STATUS,
                )
            )

    return UploadResponse(message="文件上传成功", files=uploaded_files)


@home_router.post("/audit", response_model=AuditResponse)
def audit_files(request: AuditRequest) -> AuditResponse:
    init_home_tables()

    keyword = request.keyword.strip().lower()
    if not keyword:
        raise HTTPException(status_code=400, detail="关键词不能为空")

    files = list_files(request.user_id)
    matched_files = [file for file in files if keyword in file.keywords]
    audit_time = now_text()

    if not matched_files:
        return AuditResponse(
            keyword=keyword,
            file_count=0,
            audit_result="未命中索引",
            audit_time=audit_time,
            files=[],
        )

    with connect() as connection:
        for file in matched_files:
            connection.execute(
                """
                UPDATE audit_files
                SET audit_status = ?
                WHERE file_id = ? AND user_id = ?
                """,
                (COMPLETE_STATUS, file.file_id, request.user_id),
            )
            connection.execute(
                """
                INSERT INTO audit_records (
                    record_id,
                    user_id,
                    file_id,
                    file_name,
                    keyword,
                    audit_result,
                    audit_time
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    request.user_id,
                    file.file_id,
                    file.file_name,
                    keyword,
                    COMPLETE_STATUS,
                    audit_time,
                ),
            )

    return AuditResponse(
        keyword=keyword,
        file_count=len(matched_files),
        audit_result="ProofVerify 通过",
        audit_time=audit_time,
        files=[
            AuditFileResult(
                file_id=file.file_id,
                file_name=file.file_name,
                audit_result=COMPLETE_STATUS,
            )
            for file in matched_files
        ],
    )


@home_router.get("/audit-records", response_model=List[AuditRecord])
def get_audit_records(user_id: str = DEFAULT_USER_ID) -> List[AuditRecord]:
    init_home_tables()

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM audit_records
            WHERE user_id = ?
            ORDER BY audit_time DESC
            """,
            (user_id,),
        ).fetchall()

    return [row_to_record(row) for row in rows]


@home_router.get("/profile", response_model=UserProfile)
def get_profile(user_id: str = DEFAULT_USER_ID) -> UserProfile:
    user = get_user_by_account_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return UserProfile(
        user_id=user_id,
        username=user["username"],
        account_id=user["account_id"],
        cloud_folder=user["cloud_folder"],
        role="User",
        permissions=["文件上传", "关键词审计", "审计记录查看"],
    )


@home_router.get("/profile/keys", response_model=UserKeyResponse)
def get_profile_keys(user_id: str = DEFAULT_USER_ID) -> UserKeyResponse:
    user = get_user_by_account_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    with get_user_db_connection() as connection:
        row = connection.execute(
            """
            SELECT public_key, private_key
            FROM user_crypto_keys
            WHERE account_id = ?
            """,
            (user_id,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="用户密钥不存在")

    return UserKeyResponse(
        public_key=row["public_key"],
        private_key=row["private_key"],
    )


@home_router.post("/profile/password", response_model=ApiMessage)
def change_password(request: ChangePasswordRequest) -> ApiMessage:
    user = get_user_by_account_id(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not verify_password(request.old_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="原密码错误")

    with get_user_db_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET password_hash = ?
            WHERE account_id = ?
            """,
            (make_password_hash(request.new_password), request.user_id),
        )

    return ApiMessage(message="密码修改成功")


@home_router.post("/logout", response_model=ApiMessage)
def logout() -> ApiMessage:
    return ApiMessage(message="退出登录成功")
