from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from ..config.database import get_user_db_connection
    from .home_shared import (
        DEFAULT_USER_ID,
        DashboardResponse,
        FileItem,
        calculate_integrity_ratio,
        connect,
        init_audit_table,
        list_files,
    )
    from .user_security import get_user_by_account_id, make_password_hash, verify_password
except ImportError:
    from config.database import get_user_db_connection
    from modules.home_shared import (
        DEFAULT_USER_ID,
        DashboardResponse,
        FileItem,
        calculate_integrity_ratio,
        connect,
        init_audit_table,
        list_files,
    )
    from modules.user_security import get_user_by_account_id, make_password_hash, verify_password


home_router = APIRouter(prefix="/home", tags=["审计主界面"])


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
