from __future__ import annotations

import mimetypes
import json
from pathlib import Path
from typing import Dict, List
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

try:
    from ..config.database import get_user_db_connection
    from .home_shared import (
        DEFAULT_USER_ID,
        DashboardResponse,
        FileItem,
        PENDING_STATUS,
        calculate_integrity_ratio,
        connect,
        get_user_cloud_files_dir,
        init_audit_table,
        list_files,
        now_text,
        parse_keywords,
    )
    from ..myalgorithm.data_models import PlainFile
    from ..tools.save_to_cloud import (
        load_encrypted_file,
        load_from_cloud,
        save_encrypted_file,
        save_authenticator_set,
        save_secure_index,
    )
    from ..tools.user_info import load_user_runtime_pp
    from .user_security import get_user_by_account_id, make_password_hash, verify_password
except ImportError:
    from config.database import get_user_db_connection
    from modules.home_shared import (
        DEFAULT_USER_ID,
        DashboardResponse,
        FileItem,
        PENDING_STATUS,
        calculate_integrity_ratio,
        connect,
        get_user_cloud_files_dir,
        init_audit_table,
        list_files,
        now_text,
        parse_keywords,
    )
    from myalgorithm.data_models import PlainFile
    from tools.save_to_cloud import (
        load_encrypted_file,
        load_from_cloud,
        save_encrypted_file,
        save_authenticator_set,
        save_secure_index,
    )
    from tools.user_info import load_user_runtime_pp
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


def _delete_algorithm_functions():
    try:
        from ..myalgorithm.expansion.deleteFile import (
            delete_encrypted_file_from_cloud,
            delete_file_database_record,
            delete_file_from_package,
        )
    except ImportError:
        from myalgorithm.expansion.deleteFile import (
            delete_encrypted_file_from_cloud,
            delete_file_database_record,
            delete_file_from_package,
        )

    return delete_file_from_package, delete_encrypted_file_from_cloud, delete_file_database_record


def _update_algorithm_functions():
    try:
        from ..myalgorithm.expansion.updateFile import update_file_in_package
    except ImportError:
        from myalgorithm.expansion.updateFile import update_file_in_package

    return update_file_in_package


def _existing_file_keywords(user_id: str) -> Dict[str, List[str]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT file_id, keywords
            FROM audit_files
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchall()

    return {
        row["file_id"]: json.loads(row["keywords"])
        for row in rows
    }


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


def _load_plain_file(user_id: str, file_id: str) -> tuple[str, bytes]:
    init_audit_table()

    with connect() as connection:
        row = connection.execute(
            """
            SELECT file_name, storage_path, file_size
            FROM audit_files
            WHERE user_id = ? AND file_id = ?
            """,
            (user_id, file_id),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="file_not_found")

    storage_path = Path(row["storage_path"])
    if not storage_path.exists():
        raise HTTPException(status_code=404, detail="file_missing")

    pp = load_user_runtime_pp(user_id)
    if pp is None:
        raise HTTPException(status_code=404, detail="user_crypto_keys_not_found")

    try:
        encrypted_file = load_encrypted_file(storage_path)
        plain_blocks = [
            pp["Dec"](pp["k0"], block.ciphertext)
            for block in encrypted_file.blocks
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"file_decrypt_failed: {exc}") from exc

    content = b"".join(plain_blocks)[: int(row["file_size"])]
    return row["file_name"], content


@home_router.get("/files/{file_id}/plain")
def get_plain_file(
    file_id: str,
    user_id: str = DEFAULT_USER_ID,
    disposition: str = "inline",
) -> Response:
    file_name, content = _load_plain_file(user_id, file_id)
    media_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    content_disposition = "attachment" if disposition == "attachment" else "inline"
    quoted_name = quote(file_name, safe="")

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f"{content_disposition}; filename=\"download\"; filename*=UTF-8''{quoted_name}"
            )
        },
    )


@home_router.delete("/files/{file_id}", response_model=ApiMessage)
def delete_file(
    file_id: str,
    user_id: str = DEFAULT_USER_ID,
) -> ApiMessage:
    init_audit_table()

    with connect() as connection:
        row = connection.execute(
            """
            SELECT file_id
            FROM audit_files
            WHERE user_id = ? AND file_id = ?
            """,
            (user_id, file_id),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="file_not_found")

    pp = load_user_runtime_pp(user_id)
    if pp is None:
        raise HTTPException(status_code=404, detail="user_crypto_keys_not_found")

    cloud_dir = get_user_cloud_files_dir(user_id)
    file_keywords = _existing_file_keywords(user_id)

    try:
        (
            delete_file_from_package,
            delete_encrypted_file_from_cloud,
            delete_file_database_record,
        ) = _delete_algorithm_functions()
        cloud_package = load_from_cloud(user_id, cloud_dir, group=pp["group"])
        delete_result = delete_file_from_package(
            setup_result=cloud_package.setup_result,
            secure_index=cloud_package.secure_index,
            auth_set=cloud_package.auth_set,
            file_keywords=file_keywords,
            file_id=file_id,
        )
        save_authenticator_set(
            delete_result.auth_set,
            user_id=user_id,
            cloud_dir=cloud_dir,
            group=pp["group"],
        )
        save_secure_index(
            delete_result.secure_index,
            delete_result.setup_result,
            user_id=user_id,
            cloud_dir=cloud_dir,
            group=pp["group"],
        )
        delete_encrypted_file_from_cloud(cloud_dir=cloud_dir, file_id=file_id)
        with connect() as connection:
            delete_file_database_record(
                connection=connection,
                user_id=user_id,
                file_id=file_id,
            )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"cloud_file_missing: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"delete_file_failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"delete_file_failed: {exc}") from exc

    return ApiMessage(message="delete_success")


@home_router.post("/files/{file_id}/update", response_model=FileItem)
async def update_file(
    file_id: str,
    file: UploadFile = File(...),
    keywords: str = Form(...),
    user_id: str = Form(DEFAULT_USER_ID),
) -> FileItem:
    init_audit_table()

    parsed_keywords = parse_keywords(keywords)
    if not parsed_keywords:
        raise HTTPException(status_code=400, detail="missing_keywords")

    file_name = Path(file.filename or "upload.bin").name
    content = await file.read()
    upload_time = now_text()

    with connect() as connection:
        row = connection.execute(
            """
            SELECT file_id
            FROM audit_files
            WHERE user_id = ? AND file_id = ?
            """,
            (user_id, file_id),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="file_not_found")

    pp = load_user_runtime_pp(user_id)
    if pp is None:
        raise HTTPException(status_code=404, detail="user_crypto_keys_not_found")

    plain_file = PlainFile(
        file_id=file_id,
        file_name=file_name,
        file_path="",
        blocks=[content],
        keywords=parsed_keywords,
        size=len(content),
    )
    cloud_dir = get_user_cloud_files_dir(user_id)
    file_keywords = _existing_file_keywords(user_id)

    try:
        update_file_in_package = _update_algorithm_functions()
        cloud_package = load_from_cloud(user_id, cloud_dir, group=pp["group"])
        update_result = update_file_in_package(
            setup_result=cloud_package.setup_result,
            secure_index=cloud_package.secure_index,
            auth_set=cloud_package.auth_set,
            file_keywords=file_keywords,
            plain_file=plain_file,
            k0=pp["k0"],
            Enc=pp["Enc"],
        )
        encrypted_path = save_encrypted_file(
            update_result.encrypted_file,
            cloud_dir,
        )
        save_authenticator_set(
            update_result.auth_set,
            user_id=user_id,
            cloud_dir=cloud_dir,
            group=pp["group"],
        )
        save_secure_index(
            update_result.secure_index,
            update_result.setup_result,
            user_id=user_id,
            cloud_dir=cloud_dir,
            group=pp["group"],
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"cloud_file_missing: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"update_file_failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"update_file_failed: {exc}") from exc

    with connect() as connection:
        connection.execute(
            """
            UPDATE audit_files
            SET file_name = ?,
                storage_path = ?,
                file_size = ?,
                upload_time = ?,
                keywords = ?,
                audit_status = ?,
                last_audit_time = ?
            WHERE user_id = ? AND file_id = ?
            """,
            (
                plain_file.file_name,
                str(encrypted_path),
                plain_file.size,
                upload_time,
                json.dumps(plain_file.keywords, ensure_ascii=False),
                PENDING_STATUS,
                None,
                user_id,
                file_id,
            ),
        )

    return FileItem(
        file_id=file_id,
        file_name=plain_file.file_name,
        file_size=plain_file.size,
        upload_time=upload_time,
        keywords=plain_file.keywords,
        audit_status=PENDING_STATUS,
        last_audit_time=None,
    )


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
