from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from ..config.database import get_user_db_connection
    from .home_shared import connect, init_audit_table
except ImportError:
    from config.database import get_user_db_connection
    from modules.home_shared import connect, init_audit_table


admin_router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserItem(BaseModel):
    account_id: str
    username: str


class AdminFileItem(BaseModel):
    file_id: str
    audit_status: str
    last_audit_time: str | None = None


class AdminAuditRecordItem(BaseModel):
    record_id: str
    audit_result: str
    audit_time: str


class AdminLoginRequest(BaseModel):
    username: str
    password: str


def init_admin_table() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                username TEXT NOT NULL PRIMARY KEY,
                password TEXT NOT NULL,
                identity TEXT NOT NULL DEFAULT 'admin',
                CHECK (identity = 'admin')
            )
            """
        )
        row = connection.execute("SELECT 1 FROM admins LIMIT 1").fetchone()
        if not row:
            connection.execute(
                """
                INSERT INTO admins (username, password, identity)
                VALUES (?, ?, ?)
                """,
                ("admin", "admin", "admin"),
            )


def _ensure_user_exists(user_id: str) -> None:
    with get_user_db_connection() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM users
            WHERE account_id = ?
            """,
            (user_id,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")


@admin_router.post("/login", response_model=str)
def login_admin(request: AdminLoginRequest) -> str:
    init_admin_table()
    username = request.username.strip()

    with connect() as connection:
        row = connection.execute(
            """
            SELECT identity
            FROM admins
            WHERE username = ? AND password = ?
            """,
            (username, request.password),
        ).fetchone()

    if not row or row["identity"] != "admin":
        raise HTTPException(status_code=401, detail="管理员用户名或密码错误")

    return "admin"


@admin_router.get("/users", response_model=List[AdminUserItem])
def list_admin_users() -> List[AdminUserItem]:
    with get_user_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT account_id, username
            FROM users
            ORDER BY created_at DESC, account_id DESC
            """
        ).fetchall()

    return [
        AdminUserItem(account_id=row["account_id"], username=row["username"])
        for row in rows
    ]


@admin_router.get("/users/{user_id}/files", response_model=List[AdminFileItem])
def list_admin_user_files(user_id: str) -> List[AdminFileItem]:
    _ensure_user_exists(user_id)
    init_audit_table()

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT file_id, audit_status, last_audit_time
            FROM audit_files
            WHERE user_id = ?
            ORDER BY COALESCE(last_audit_time, upload_time) DESC, file_id DESC
            """,
            (user_id,),
        ).fetchall()

    return [
        AdminFileItem(
            file_id=row["file_id"],
            audit_status=row["audit_status"],
            last_audit_time=row["last_audit_time"],
        )
        for row in rows
    ]


@admin_router.get("/users/{user_id}/audit-records", response_model=List[AdminAuditRecordItem])
def list_admin_user_audit_records(user_id: str) -> List[AdminAuditRecordItem]:
    _ensure_user_exists(user_id)
    init_audit_table()

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT record_id, audit_result, audit_time
            FROM audit_records
            WHERE user_id = ?
            ORDER BY audit_time DESC, record_id DESC
            """,
            (user_id,),
        ).fetchall()

    return [
        AdminAuditRecordItem(
            record_id=row["record_id"],
            audit_result=row["audit_result"],
            audit_time=row["audit_time"],
        )
        for row in rows
    ]
