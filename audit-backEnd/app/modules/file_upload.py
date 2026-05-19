from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel


try:
    from .home_shared import (
        DEFAULT_USER_ID,
        PENDING_STATUS,
        FileItem,
        connect,
        get_user_cloud_files_dir,
        init_audit_table,
        make_file_id,
        now_text,
        parse_keywords,
        prepare_keyword_forms,
    )
    from ..myalgorithm.data_models import PlainFile
    from ..tools.save_to_cloud import load_from_cloud, save_to_cloud
    from ..tools.user_info import load_user_runtime_pp
except ImportError:
    from modules.home_shared import (
        DEFAULT_USER_ID,
        PENDING_STATUS,
        FileItem,
        connect,
        get_user_cloud_files_dir,
        init_audit_table,
        make_file_id,
        now_text,
        parse_keywords,
        prepare_keyword_forms,
    )
    from myalgorithm.data_models import PlainFile
    from tools.save_to_cloud import load_from_cloud, save_to_cloud
    from tools.user_info import load_user_runtime_pp


file_upload_router = APIRouter(prefix="/home", tags=["file-upload"])
DEFAULT_BLOCK_COUNT = 10


class UploadResponse(BaseModel):
    message: str
    files: List[FileItem]


def _algorithm_functions():
    try:
        from ..myalgorithm.auth_gen import auth_gen
        from ..myalgorithm.index_gen import index_gen
        from ..myalgorithm.setup import setup
    except ImportError:
        from myalgorithm.auth_gen import auth_gen
        from myalgorithm.index_gen import index_gen
        from myalgorithm.setup import setup

    return setup, index_gen, auth_gen


def _append_algorithm_functions():
    try:
        from ..myalgorithm.expansion.appendFile import append_files_to_package
    except ImportError:
        from myalgorithm.expansion.appendFile import append_files_to_package

    return append_files_to_package


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


def _ensure_new_file_ids(plain_files: List[PlainFile], existing_file_ids: set[str]) -> None:
    seen: set[str] = set()
    duplicates: List[str] = []

    for plain_file in plain_files:
        if plain_file.file_id in existing_file_ids or plain_file.file_id in seen:
            duplicates.append(plain_file.file_name)
        seen.add(plain_file.file_id)

    if duplicates:
        raise HTTPException(
            status_code=409,
            detail=f"file_already_exists: {', '.join(duplicates)}",
        )


def _save_uploaded_file_records(
    *,
    plain_files: List[PlainFile],
    user_id: str,
    upload_time: str,
    encrypted_paths: Dict[str, Path],
) -> None:
    with connect() as connection:
        for plain_file in plain_files:
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
                    audit_status,
                    last_audit_time
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plain_file.file_id,
                    user_id,
                    plain_file.file_name,
                    str(encrypted_paths[plain_file.file_id]),
                    plain_file.size,
                    upload_time,
                    json.dumps(plain_file.keywords, ensure_ascii=False),
                    PENDING_STATUS,
                    None,
                ),
            )


@file_upload_router.post("/files/upload", response_model=UploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    keywords: List[str] = Form(...),
    user_id: str = Form(DEFAULT_USER_ID),
    s: int = Form(DEFAULT_BLOCK_COUNT),
) -> UploadResponse:
    init_audit_table()
    cloud_files_dir = get_user_cloud_files_dir(user_id)

    if not files:
        raise HTTPException(status_code=400, detail="at_least_one_file_required")
    if s <= 0:
        raise HTTPException(status_code=400, detail="s_must_be_greater_than_0")

    keyword_forms = prepare_keyword_forms(files, keywords)
    pp = load_user_runtime_pp(user_id)
    if pp is None:
        raise HTTPException(status_code=404, detail="user_crypto_keys_not_found")

    upload_time = now_text()
    plain_files: List[PlainFile] = []
    uploaded_files: List[FileItem] = []

    for upload_file, raw_keywords in zip(files, keyword_forms):
        file_name = Path(upload_file.filename or "upload.bin").name
        parsed_keywords = parse_keywords(raw_keywords)
        if not parsed_keywords:
            raise HTTPException(status_code=400, detail=f"{file_name} missing_keywords")

        content = await upload_file.read()
        file_id = make_file_id(file_name, content, user_id)

        plain_files.append(
            PlainFile(
                file_id=file_id,
                file_name=file_name,
                file_path="",
                blocks=[content],
                keywords=parsed_keywords,
                size=len(content),
            )
        )
        uploaded_files.append(
            FileItem(
                file_id=file_id,
                file_name=file_name,
                file_size=len(content),
                upload_time=upload_time,
                keywords=parsed_keywords,
                audit_status=PENDING_STATUS,
                last_audit_time=None,
            )
        )

    try:
        setup, index_gen, auth_gen = _algorithm_functions()
        setup_result = setup(
            files=plain_files,
            k0=pp["k0"],
            Enc=pp["Enc"],
            s=s,
        )
        secure_index = index_gen(setup_result)
        auth_set = auth_gen(setup_result)
        save_result = save_to_cloud(
            setup_result=setup_result,
            secure_index=secure_index,
            auth_set=auth_set,
            user_id=user_id,
            cloud_dir=cloud_files_dir,
            group=pp["group"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"algorithm_upload_failed: {exc}") from exc

    _save_uploaded_file_records(
        plain_files=plain_files,
        user_id=user_id,
        upload_time=upload_time,
        encrypted_paths=save_result.encrypted_files,
    )

    return UploadResponse(message="upload_success", files=uploaded_files)


@file_upload_router.post("/files/append", response_model=UploadResponse)
async def append_files(
    files: List[UploadFile] = File(...),
    keywords: List[str] = Form(...),
    user_id: str = Form(DEFAULT_USER_ID),
) -> UploadResponse:
    init_audit_table()
    cloud_files_dir = get_user_cloud_files_dir(user_id)

    if not files:
        raise HTTPException(status_code=400, detail="at_least_one_file_required")

    keyword_forms = prepare_keyword_forms(files, keywords)
    pp = load_user_runtime_pp(user_id)
    if pp is None:
        raise HTTPException(status_code=404, detail="user_crypto_keys_not_found")

    existing_keywords = _existing_file_keywords(user_id)
    if not existing_keywords:
        raise HTTPException(status_code=400, detail="no_existing_files_to_append")

    upload_time = now_text()
    plain_files: List[PlainFile] = []
    uploaded_files: List[FileItem] = []

    for upload_file, raw_keywords in zip(files, keyword_forms):
        file_name = Path(upload_file.filename or "upload.bin").name
        parsed_keywords = parse_keywords(raw_keywords)
        if not parsed_keywords:
            raise HTTPException(status_code=400, detail=f"{file_name} missing_keywords")

        content = await upload_file.read()
        file_id = make_file_id(file_name, content, user_id)

        plain_files.append(
            PlainFile(
                file_id=file_id,
                file_name=file_name,
                file_path="",
                blocks=[content],
                keywords=parsed_keywords,
                size=len(content),
            )
        )
        uploaded_files.append(
            FileItem(
                file_id=file_id,
                file_name=file_name,
                file_size=len(content),
                upload_time=upload_time,
                keywords=parsed_keywords,
                audit_status=PENDING_STATUS,
                last_audit_time=None,
            )
        )

    _ensure_new_file_ids(plain_files, set(existing_keywords))

    try:
        append_files_to_package = _append_algorithm_functions()
        cloud_package = load_from_cloud(
            user_id=user_id,
            cloud_dir=cloud_files_dir,
            group=pp["group"],
        )
        append_results = append_files_to_package(
            setup_result=cloud_package.setup_result,
            secure_index=cloud_package.secure_index,
            auth_set=cloud_package.auth_set,
            file_keywords=existing_keywords,
            plain_files=plain_files,
            k0=pp["k0"],
            Enc=pp["Enc"],
        )
        setup_result = append_results[-1].setup_result
        save_result = save_to_cloud(
            setup_result=setup_result,
            secure_index=append_results[-1].secure_index,
            auth_set=append_results[-1].auth_set,
            user_id=user_id,
            cloud_dir=cloud_files_dir,
            group=pp["group"],
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"cloud_file_missing: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"append_file_failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"append_file_failed: {exc}") from exc

    _save_uploaded_file_records(
        plain_files=plain_files,
        user_id=user_id,
        upload_time=upload_time,
        encrypted_paths=save_result.encrypted_files,
    )

    return UploadResponse(message="append_success", files=uploaded_files)
